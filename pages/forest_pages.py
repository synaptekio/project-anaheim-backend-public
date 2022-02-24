import csv
import datetime
from collections import defaultdict

from django.contrib import messages
from django.http.response import FileResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from authentication.admin_authentication import (authenticate_admin,
    authenticate_researcher_study_access, forest_enabled)
from constants.data_access_api_constants import CHUNK_FIELDS
from constants.forest_constants import ForestTaskStatus, ForestTree
from database.data_access_models import ChunkRegistry
from database.study_models import Study
from database.tableau_api_models import ForestTask
from database.user_models import Participant
from forms.django_forms import CreateTasksForm
from libs.http_utils import easy_url
from libs.internal_types import ParticipantQuerySet, ResearcherRequest
from libs.streaming_zip import zip_generator
from libs.utils.date_utils import daterange
from middleware.abort_middleware import abort
from serializers.forest_serializers import ForestTaskCsvSerializer, ForestTaskSerializer


@require_GET
@authenticate_researcher_study_access
@forest_enabled
def analysis_progress(request: ResearcherRequest, study_id=None):
    study: Study = Study.objects.get(pk=study_id)
    participants: ParticipantQuerySet = Participant.objects.filter(study=study_id)
    
    # generate chart of study analysis progress logs
    trackers = ForestTask.objects.filter(participant__in=participants).order_by("created_on")
    
    start_date = (study.get_earliest_data_time_bin() or study.created_on).date()
    end_date = (study.get_latest_data_time_bin() or timezone.now()).date()
    
    # this code simultaneously builds up the chart of most recent forest results for date ranges
    # by participant and tree, and tracks the metadata
    params = dict()
    results = defaultdict(lambda: "--")
    tracker: ForestTask
    for tracker in trackers:
        for date in daterange(tracker.data_date_start, tracker.data_date_end, inclusive=True):
            results[(tracker.participant_id, tracker.forest_tree, date)] = tracker.status
            if tracker.status == tracker.status.success:
                params[(tracker.participant_id, tracker.forest_tree, date)] = tracker.forest_param_id
            else:
                params[(tracker.participant_id, tracker.forest_tree, date)] = None
    
    # generate the date range for charting
    dates = list(daterange(start_date, end_date, inclusive=True))
    
    chart = []
    for participant in participants:
        for tree in ForestTree.values():
            row = [participant.patient_id, tree] + \
                [results[(participant.id, tree, date)] for date in dates]
            chart.append(row)
    
    # ensure that within each tree, only a single set of param values are used (only the most recent runs
    # are considered, and unsuccessful runs are assumed to invalidate old runs, clearing params)
    params_conflict = False
    for tree in set([k[1] for k in params.keys()]):
        if len(set([m for k, m in params.items() if m is not None and k[1] == tree])) > 1:
            params_conflict = True
            break
    
    return render(
        request,
        'forest/analysis_progress.html',
        context=dict(
            study=study,
            chart_columns=["participant", "tree"] + dates,
            status_choices=ForestTaskStatus,
            params_conflict=params_conflict,
            start_date=start_date,
            end_date=end_date,
            chart=chart  # this uses the jinja safe filter and should never involve user input
        )
    )


@require_http_methods(['GET', 'POST'])
@authenticate_admin
@forest_enabled
def create_tasks(request: ResearcherRequest, study_id=None):
    # Only a SITE admin can queue forest tasks
    if not request.session_researcher.site_admin:
        return abort(403)
    try:
        study = Study.objects.get(pk=study_id)
    except Study.DoesNotExist:
        return abort(404)
    
    # FIXME: remove this double endpoint pattern, it is bad.
    if request.method == "GET":
        return render_create_tasks(request, study)
    form = CreateTasksForm(data=request.POST, study=study)
    
    if not form.is_valid():
        error_messages = [
            f'"{field}": {message}'
            for field, messages in form.errors.items()
            for message in messages
        ]
        error_messages_string = "\n".join(error_messages)
        messages.warning(request, f"Errors:\n\n{error_messages_string}")
        return render_create_tasks(request, study)
    
    form.save()
    messages.success(request, "Forest tasks successfully queued!")
    return redirect(easy_url("forest_pages.task_log", study_id=study_id))


@require_GET
@authenticate_researcher_study_access
@forest_enabled
def task_log(request: ResearcherRequest, study_id=None):
    study = Study.objects.get(pk=study_id)
    forest_tasks = ForestTask.objects.filter(participant__study_id=study_id).order_by("-created_on")
    return render(
        request,
        "forest/task_log.html",
        context=dict(
            study=study,
            is_site_admin=request.session_researcher.site_admin,
            status_choices=ForestTaskStatus,
            forest_log=ForestTaskSerializer(forest_tasks, many=True).data,
        )
    )


@require_GET
@authenticate_admin
def download_task_log(request: ResearcherRequest):
    forest_tasks = ForestTask.objects.order_by("created_on")
    return FileResponse(
        stream_forest_task_log_csv(forest_tasks),
        content_type="text/csv",
        filename=f"forest_task_log_{timezone.now().isoformat()}.csv",
        as_attachment=True,
    )


@require_POST
@authenticate_admin
@forest_enabled
def cancel_task(request: ResearcherRequest, study_id, forest_task_external_id):
    if not request.session_researcher.site_admin:
        return abort(403)
        
    number_updated = \
        ForestTask.objects.filter(
            external_id=forest_task_external_id, status=ForestTaskStatus.queued
        ).update(
            status=ForestTaskStatus.cancelled,
            stacktrace=f"Canceled by {request.session_researcher.username} on {datetime.date.today()}",
        )
    
    if number_updated > 0:
        messages.success(request, "Forest task successfully cancelled.")
    else:
        messages.warning(request, "Sorry, we were unable to find or cancel this Forest task.")
    
    return redirect(easy_url("forest_pages.task_log", study_id=study_id))


@require_GET
@authenticate_admin
@forest_enabled
def download_task_data(request: ResearcherRequest, study_id, forest_task_external_id):
    try:
        tracker: ForestTask = ForestTask.objects.get(
            external_id=forest_task_external_id, participant__study_id=study_id
        )
    except ForestTask.DoesNotExist:
        return abort(404)
    
    chunks = ChunkRegistry.objects.filter(participant=tracker.participant).values(*CHUNK_FIELDS)
    f = FileResponse(
        zip_generator(chunks),
        content_type="zip",
        as_attachment=True,
        filename=f"{tracker.get_slug()}.zip",
    )
    f.set_headers(None)
    return f


def stream_forest_task_log_csv(forest_tasks):
    buffer = CSVBuffer()
    writer = csv.DictWriter(buffer, fieldnames=ForestTaskCsvSerializer.Meta.fields)
    writer.writeheader()
    yield buffer.read()
    
    for forest_task in forest_tasks:
        writer.writerow(ForestTaskCsvSerializer(forest_task).data)
        yield buffer.read()


def render_create_tasks(request: ResearcherRequest, study: Study):
    participants = Participant.objects.filter(study=study)
    try:
        start_date = ChunkRegistry.objects.filter(participant__in=participants).earliest("time_bin")
        end_date = ChunkRegistry.objects.filter(participant__in=participants).latest("time_bin")
        start_date = start_date.time_bin.date()
        end_date = end_date.time_bin.date()
    except ChunkRegistry.DoesNotExist:
        start_date = study.created_on.date()
        end_date = timezone.now().date()
    return render(
        request,
        "forest/create_tasks.html",
        context=dict(
            study=study,
            participants=list(
                study.participants.order_by("patient_id").values_list("patient_id", flat=True)
            ),
            trees=ForestTree.choices(),
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
    )


class CSVBuffer:
    line = ""
    
    def read(self):
        return self.line
    
    def write(self, line):
        self.line = line
