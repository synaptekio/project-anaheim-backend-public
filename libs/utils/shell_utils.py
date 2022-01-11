from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pprint import pprint
from time import sleep

from dateutil.tz import gettz
from django.utils.timezone import localtime

from database.data_access_models import FileToProcess
from database.profiling_models import UploadTracking
from database.study_models import Study
from database.survey_models import Survey
from database.user_models import Participant, Researcher


# Some utility functions for a quality of life.


def as_local(dt: datetime, tz=gettz("America/New_York")):
    return localtime(dt, tz)


def PARTICIPANT(patient_id: str or int):
    if isinstance(patient_id, int):
        return Participant.objects.get(pk=patient_id)
    return Participant.objects.get(patient_id=patient_id)

P = PARTICIPANT  # Pah, who has time for that.


def RESEARCHER(username: str or int):
    if isinstance(username, int):
        return Researcher.objects.get(pk=username)
    return Researcher.objects.get(username=username)

R = RESEARCHER


def SURVEY(object_id: str or int):
    if isinstance(object_id, int):
        return Survey.objects.get(pk=object_id)
    return Survey.objects.get(object_id=object_id)


def STUDY(object_id: str or int):
    if isinstance(object_id, int):
        return Study.objects.get(pk=object_id)
    return Study.objects.get(object_id=object_id)


def count():
    return FileToProcess.objects.count()


def status():
    pprint(
        sorted(Counter(FileToProcess.objects.values_list("participant__patient_id", flat=True))
               .most_common(), key=lambda x: x[1])
    )


def remove_duplicate_ftps():
    # removes any duplicate files to process
    path_counter = defaultdict(list)
    
    for p in Participant.objects.all():
        for path, pk in p.files_to_process.values_list("s3_file_path", "pk").order_by("pk"):
            path_counter[path].append(pk)
    
    pks_to_delete = []
    for path, pks in dict(path_counter).items():
        if len(pks) in (1,0):
            continue
        
        pks.pop(0)
        pks_to_delete.extend(pks)
    
    y_n = input(f"delete {len(pks_to_delete)} duplicate uploads? y/n: ")
    if y_n == "y":
        ret = FileToProcess.objects.filter(pk__in=pks_to_delete).delete()
        pprint(ret)


def watch_processing():
    # cannot be imported on EB servers
    from libs.celery_control import (CeleryNotRunningException, get_processing_active_job_ids,
        get_processing_reserved_job_ids, get_processing_scheduled_job_ids)
    
    periodicity = 5
    orig_start = localtime()
    a_now = orig_start
    s_now = orig_start
    r_now = orig_start
    active = []
    scheduled = []
    registered = []
    prior_users = 0
    
    for i in range(2**64):
        errors = 0
        start = localtime()
        
        count = FileToProcess.objects.count()
        user_count = FileToProcess.objects.values_list("participant__patient_id",
                                                       flat=True).distinct().count()
        
        if prior_users != user_count:
            print(f"{start:} Number of participants with files to process: {user_count}")
        
        print(f"{start}: {count} files to process")
        
        try:
            a_now, active = localtime(), get_processing_active_job_ids()
        except CeleryNotRunningException:
            errors += 1
        try:
            s_now, scheduled = localtime(), get_processing_scheduled_job_ids()
        except CeleryNotRunningException:
            errors += 1
        try:
            r_now, registered = localtime(), get_processing_reserved_job_ids()
        except CeleryNotRunningException:
            errors += 1
        
        if errors:
            print(f"  (Couldn't connect to celery on {errors} attempt(s), data is slightly stale.)")
        
        print(a_now, "active tasks:", active)
        print(s_now, "scheduled tasks:", scheduled)
        print(r_now, "registered tasks:", registered)
        
        prior_users = user_count
        
        # we will set a minimum time between info updates, database call can be slow.
        end = localtime()
        total = abs((start - end).total_seconds())
        wait = periodicity - total if periodicity - total > 0 else 0
        
        print("\n=================================\n")
        sleep(wait)


def watch_uploads():
    while True:
        start = localtime()
        data = list(UploadTracking.objects.filter(
            timestamp__gte=(start - timedelta(minutes=1))).values_list("file_size", flat=True))
        end = localtime()
        total = abs((start - end).total_seconds())
        
        # we will set a minimum time between prints at 2 seconds, database call can be slow.
        wait = 2 - total if 0 < (2 - total) < 2 else 0
        
        print("time delta: %ss, %s files, %.4fMB in the past minute" % (
            total + wait, len(data), (sum(data) / 1024.0 / 1024.0)))
        sleep(wait)


def get_and_summarize(patient_id: str):
    p = Participant.objects.get(patient_id=patient_id)
    byte_sum = sum(UploadTracking.objects.filter(participant=p).values_list("file_size", flat=True))
    print(f"Total Data Uploaded: {byte_sum/1024/1024}MB")
    
    counter = Counter(
        path.split("/")[2] for path in
        FileToProcess.objects.filter(participant=p).values_list("s3_file_path", flat=True)
    )
    return counter.most_common()
