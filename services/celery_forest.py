import json
import os
import traceback
from datetime import datetime, timedelta
from multiprocessing.pool import ThreadPool

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from pkg_resources import get_distribution

from constants.celery_constants import FOREST_QUEUE
from constants.data_access_api_constants import CHUNK_FIELDS
from constants.forest_constants import ForestTaskStatus, ForestTree
from database.data_access_models import ChunkRegistry
from database.tableau_api_models import ForestTask
from libs.celery_control import forest_celery_app, safe_apply_async
from libs.s3 import s3_retrieve
from libs.sentry import make_error_sentry, SentryTypes
from libs.streaming_zip import determine_file_name

from forest.jasmine.traj2stats import gps_stats_main
from forest.willow.log_stats import log_stats_main


DEBUG_CELERY_FOREST = False

def log(*args, **kwargs):
    if DEBUG_CELERY_FOREST:
        print("celery_forest debug: ", end="")
        print(*args, **kwargs)


TREE_TO_FOREST_FUNCTION = {
    ForestTree.jasmine: gps_stats_main,
    ForestTree.willow: log_stats_main,
}


FOREST_ERROR_LOCATION_KEY = "forest_error_location"


def create_forest_celery_tasks():
    pending_tasks = ForestTask.objects.filter(status=ForestTaskStatus.queued)
    with make_error_sentry(sentry_type=SentryTypes.data_processing):
        for task in pending_tasks:
            print(f"Queueing up celery task for {task.participant} on tree {task.forest_tree} from {task.data_date_start} to {task.data_date_end}")
            enqueue_forest_task(args=[task.id])


#run via celery as long as tasks exist
@forest_celery_app.task(queue=FOREST_QUEUE)
def celery_run_forest(forest_task_id):
    with transaction.atomic():
        task = ForestTask.objects.filter(id=forest_task_id).first()
        
        participant = task.participant
        forest_tree = task.forest_tree
        
        # Check if there already is a running task for this participant and tree, handling
        # concurrency and requeuing of the ask if necessary
        tasks = (
            ForestTask
                .objects
                .select_for_update()
                .filter(participant=participant, forest_tree=forest_tree)
        )
        if tasks.filter(status=ForestTaskStatus.running).exists():
            enqueue_forest_task(args=[task.id])
            return
        
        # Get the chronologically earliest task that's queued
        task: ForestTask = (
            tasks
                .filter(status=ForestTaskStatus.queued)
                .order_by("-data_date_start")
                .first()
        )
        if task is None:
            return
        
        # Set metadata on the task
        task.status = ForestTaskStatus.running
        task.forest_version = get_distribution("forest").version
        task.process_start_time = timezone.now()
        task.save(update_fields=["status", "forest_version", "process_start_time"])
    
    try:
        # Save file size data
        # The largest UTC offsets are -12 and +14
        min_datetime = datetime.combine(task.data_date_start, datetime.min.time()) - timedelta(hours=12)
        max_datetime = datetime.combine(task.data_date_end, datetime.max.time()) + timedelta(hours=14)
        log("min_datetime: ", min_datetime.isoformat())
        log("max_datetime: ", max_datetime.isoformat())
        chunks = (
            ChunkRegistry
                .objects
                .filter(participant=participant)
                .filter(time_bin__gte=min_datetime)
                .filter(time_bin__lte=max_datetime)
        )
        file_size = chunks.aggregate(Sum('file_size')).get('file_size__sum')
        if file_size is None:
            raise Exception('No chunked data found for participant for the dates specified.')
        task.total_file_size = file_size
        task.save(update_fields=["total_file_size"])
        
        # Download data
        create_local_data_files(task, chunks)
        task.process_download_end_time = timezone.now()
        task.save(update_fields=["process_download_end_time"])
        log("task.process_download_end_time:", task.process_download_end_time.isoformat())
        
        # Run Forest
        params_dict = task.params_dict()
        log("params_dict:", params_dict)
        task.params_dict_cache = json.dumps(params_dict, cls=DjangoJSONEncoder)
        task.save(update_fields=["params_dict_cache"])
        
        log("running:", task.forest_tree)
        TREE_TO_FOREST_FUNCTION[task.forest_tree](**params_dict)
        
        # Save data
        task.forest_output_exists = task.construct_summary_statistics()
        task.save(update_fields=["forest_output_exists"])
        save_cached_files(task)
    
    except Exception:
        task.status = ForestTaskStatus.error
        task.stacktrace = traceback.format_exc()
        tags = {k: str(v) for k, v in task.as_dict().items()}
        tags[FOREST_ERROR_LOCATION_KEY] = "forest task general error"
        with make_error_sentry(SentryTypes.data_processing, tags=tags):
            raise
    
    else:
        task.status = ForestTaskStatus.success
    
    finally:
        log("deleting files 1")
        try:
            task.clean_up_files()
        except Exception:
            if task.stacktrace is None:
                task.stacktrace = traceback.format_exc()
            else:
                task.stacktrace = task.stacktrace + "\n\n" + traceback.format_exc()
            
            tags = {k: str(v) for k, v in task.as_dict().items()}
            tags[FOREST_ERROR_LOCATION_KEY] = "forest task cleanup error"
            with make_error_sentry(SentryTypes.data_processing, tags=tags):
                raise
    
    log("task.status:", task.status)
    if task.stacktrace:
        log("stacktrace:", task.stacktrace)
    
    task.save(update_fields=["status", "stacktrace"])
    
    log("deleting files 2")
    task.clean_up_files()
    task.process_end_time = timezone.now()
    task.save(update_fields=["process_end_time"])


def create_local_data_files(task, chunks):
    # downloading data is highly threadable and can be the majority of the run time. 4 works for
    # most files, a very high small file count can make use of 10+ before we are cpu limited.
    with ThreadPool(4) as pool:
        for _ in pool.imap_unordered(
            func=batch_create_file,
            iterable=[(task, chunk) for chunk in chunks
            .values("study__object_id", *CHUNK_FIELDS)],
        ):
            pass

def batch_create_file(singular_task_chunk):
    task: ForestTask  # chunk is a values dict
    task, chunk = singular_task_chunk
    contents = s3_retrieve(chunk["chunk_path"], chunk["study__object_id"], raw_path=True)
    file_name = os.path.join(
        task.data_input_path,
        determine_file_name(chunk),
    )
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, "xb") as f:
        f.write(contents)


def enqueue_forest_task(**kwargs):
    updated_kwargs = {
        "expires": (datetime.utcnow() + timedelta(minutes=5)).replace(second=30, microsecond=0),
        "max_retries": 0,
        "retry": False,
        "task_publish_retry": False,
        "task_track_started": True,
        **kwargs,
    }
    safe_apply_async(celery_run_forest, **updated_kwargs)


def save_cached_files(task: ForestTask):
    if os.path.exists(task.all_bv_set_path):
        with open(task.all_bv_set_path, "rb") as f:
            task.save_all_bv_set_bytes(f.read())
    
    if os.path.exists(task.all_memory_dict_path):
        with open(task.all_memory_dict_path, "rb") as f:
            task.save_all_memory_dict_bytes(f.read())
