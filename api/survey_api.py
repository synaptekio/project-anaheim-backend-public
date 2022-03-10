import json

from django.contrib import messages
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST

from authentication.admin_authentication import authenticate_researcher_study_access
from database.schedule_models import AbsoluteSchedule, RelativeSchedule, WeeklySchedule
from database.study_models import Study
from database.survey_models import Survey
from libs.internal_types import ResearcherRequest
from libs.json_logic import do_validate_survey
from libs.push_notification_helpers import (repopulate_absolute_survey_schedule_events,
    repopulate_relative_survey_schedule_events, repopulate_weekly_survey_schedule_events)


################################################################################
############################## Creation/Deletion ###############################
################################################################################


@require_http_methods(['GET', 'POST'])
@authenticate_researcher_study_access
def create_survey(request: ResearcherRequest, study_id=None, survey_type: str = 'tracking_survey'):
    new_survey = Survey.create_with_settings(study_id=study_id, survey_type=survey_type)
    return redirect(f'/edit_survey/{new_survey.study.id}/{new_survey.id}')


@require_http_methods(['GET', 'POST'])
@authenticate_researcher_study_access
def delete_survey(request: ResearcherRequest, study_id=None, survey_id=None):
    survey = get_object_or_404(Survey, pk=survey_id)
    # mark as deleted, delete all schedules and schedule events
    survey.deleted = True
    survey.save()
    # clear out any active schedules
    survey.absolute_schedules.all().delete()
    survey.relative_schedules.all().delete()
    survey.weekly_schedules.all().delete()
    return redirect(f'/view_study/{survey.study_id}')

################################################################################
############################# Setters and Editors ##############################
################################################################################


@require_http_methods(['GET', 'POST'])
@authenticate_researcher_study_access
def rename_survey(request: ResearcherRequest, study_id: int = None, survey_id: int = None):
    study = get_object_or_404(Study, id=study_id)
    survey = get_object_or_404(Survey, study=study, id=survey_id)
    survey_name = request.POST.get("survey_name", "")
    survey.update(name=survey_name)  # django escapes content shoved into a string
    return redirect(f'/edit_survey/{study_id}/{survey_id}')


@require_POST
@authenticate_researcher_study_access
def update_survey(request: ResearcherRequest, study_id: int, survey_id: int):
    """
    Updates the survey when the 'Save & Deploy button on the edit_survey page is hit. Expects
    content, weekly_timings, absolute_timings, relative_timings, and settings in the request body
    """
    survey = get_object_or_404(Survey, pk=survey_id)
    
    # BUG: There is an unknown situation where the frontend sends a string requiring an extra
    # deserialization operation, causing 'content' to be a string containing a json string
    # containing a json list, instead of just a string containing a json list.
    json_content = request.POST.get('content')
    content = None
    
    # Image survey does not have any content associated with it.  request.values.get('content')
    # returns a json string containing two double quotes, not the empty string.
    # recursive_survey_content_json_decode function is not able to decode this.
    if json_content != '""':
        content = recursive_survey_content_json_decode(json_content)
        content = make_slider_min_max_values_strings(content)
    if survey.survey_type == Survey.TRACKING_SURVEY:
        errors = do_validate_survey(content)
        if len(errors) > 1:
            return HttpResponse(json.dumps(errors), status_code=400)
    
    # For each of the schedule types, creates Schedule objects and ScheduledEvent objects
    weekly_timings = json.loads(request.POST.get('weekly_timings'))
    w_duplicated = WeeklySchedule.create_weekly_schedules(weekly_timings, survey)
    repopulate_weekly_survey_schedule_events(survey)
    absolute_timings = json.loads(request.POST.get('absolute_timings'))
    a_duplicated = AbsoluteSchedule.create_absolute_schedules(absolute_timings, survey)
    repopulate_absolute_survey_schedule_events(survey)
    relative_timings = json.loads(request.POST.get('relative_timings'))
    r_duplicated = RelativeSchedule.create_relative_schedules(relative_timings, survey)
    repopulate_relative_survey_schedule_events(survey)
    
    # These three all stay JSON when added to survey
    content = json.dumps(content)
    settings = request.POST.get('settings')
    survey.update(content=content, settings=settings)
    
    # if any duplicate schedules were submitted, flash a message
    if w_duplicated or a_duplicated or r_duplicated:
        messages.success(
            request, 'Duplicate schedule was submitted. Only one of the duplicates was created.'
        )
    return HttpResponse(status=201)


def recursive_survey_content_json_decode(json_entity: str):
    """ Decodes through up to 100 attempts a json entity until it has deserialized to a list. """
    count = 100
    decoded_json = None
    while not isinstance(decoded_json, list):
        count -= 1
        if count < 0:
            raise Exception("could not decode json entity to list")
        decoded_json = json.loads(json_entity)
    return decoded_json


def make_slider_min_max_values_strings(json_content):
    """ Turns min/max int values into strings, because the iOS app expects strings. This is for
    backwards compatibility; when all the iOS apps involved in studies can handle ints,
    we can remove this function. """
    for question in json_content:
        if 'max' in question:
            question['max'] = str(question['max'])
        if 'min' in question:
            question['min'] = str(question['min'])
    return json_content
