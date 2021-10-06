from json import dumps, loads

from django.contrib import messages
from django.http.response import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST

from authentication.admin_authentication import authenticate_admin
from database.study_models import Study
from libs.copy_study import (ABSOLUTE_SCHEDULE_KEY, add_new_surveys, allowed_file_extension,
    DEVICE_SETTINGS_KEY, purge_unnecessary_fields, RELATIVE_SCHEDULE_KEY, SURVEYS_KEY,
    update_device_settings, WEEKLY_SCHEDULE_KEY)
from libs.internal_types import BeiweHttpRequest
from middleware.admin_authentication_middleware import abort


"""
JSON structure for exporting and importing study surveys and settings:
    {
     'device_settings': {},
     'surveys': [{}, {}, ...]
    }
    Also, purge all id keys
"""

@require_GET
@authenticate_admin
def export_study_settings_file(request: BeiweHttpRequest, study_id):
    """ Endpoint that returns a json representation of a study. """
    study = Study.objects.get(pk=study_id)

    # get only the necessary information for the survey and settings representation.
    surveys = []
    for survey in study.surveys.filter(deleted=False):
        # content, cleanup, then schedules.
        survey_content = survey.as_unpacked_native_python()
        purge_unnecessary_fields(survey_content)

        survey_content[WEEKLY_SCHEDULE_KEY] = survey.weekly_timings()
        survey_content[ABSOLUTE_SCHEDULE_KEY] = survey.absolute_timings()
        survey_content[RELATIVE_SCHEDULE_KEY] = survey.relative_timings()
        surveys.append(survey_content)

    device_settings = study.device_settings.as_unpacked_native_python()
    purge_unnecessary_fields(device_settings)

    output = {
        SURVEYS_KEY: surveys,
        DEVICE_SETTINGS_KEY: device_settings,
    }

    filename = study.name.replace(' ', '_') + "_surveys_and_settings.json"
    return HttpResponse(
        request,
        dumps(output),
        mimetype="application/json",
        headers={'Content-Disposition': 'attachment;filename=' + filename}
    )


@require_POST
@authenticate_admin
def import_study_settings_file(request: BeiweHttpRequest, study_id):
    """ Endpoint that takes the output of export_study_settings_file and creates a new study. """
    study = Study.objects.get(pk=study_id)
    file = request.files.get('upload', None)
    if not file:
        abort(400)

    if not allowed_file_extension(file.filename):
        messages.warning(request, "You can only upload .json files!")
        return redirect(request.referrer)

    study_data = loads(file.read())
    device_settings = study_data.pop(DEVICE_SETTINGS_KEY, None)
    surveys = study_data.pop(SURVEYS_KEY, None)

    # these functions return a message to construct for the user
    msg = update_device_settings(request, device_settings, study, file.filename)
    msg += " \n" + add_new_surveys(request, surveys, study, file.filename)
    messages.success(request, msg)
    return redirect(f'/edit_study/{study_id}')
