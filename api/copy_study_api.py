from io import BytesIO

from django.contrib import messages
from django.http.response import FileResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST

from authentication.admin_authentication import authenticate_admin
from database.study_models import Study
from database.survey_models import Survey
from libs.copy_study import (allowed_file_extension, copy_study_from_json, format_study,
    unpack_json_study)
from libs.internal_types import ResearcherRequest
from middleware.abort_middleware import abort


"""
JSON structure for exporting and importing study surveys and settings:
    {
     'device_settings': {},
     'surveys': [{}, {}, ...],
     'interventions: [{}, {}, ...],
    }
"""

@require_GET
@authenticate_admin
def export_study_settings_file(request: ResearcherRequest, study_id):
    """ Endpoint that returns a json representation of a study. """
    study = Study.objects.get(pk=study_id)
    filename = study.name.replace(' ', '_') + "_surveys_and_settings.json"
    return FileResponse(
        BytesIO(format_study(study).encode()),  # this is particularly stupid.
        content_type="application/json",
        as_attachment=True,
        filename=filename,
    )


@require_POST
@authenticate_admin
def import_study_settings_file(request: ResearcherRequest, study_id):
    """ Endpoint that takes the output of export_study_settings_file and creates a new study. """
    study = Study.objects.get(pk=study_id)
    file = request.files.get('upload', None)
    if not file:
        abort(400)
    
    if not allowed_file_extension(file.filename):
        messages.warning(request, "You can only upload .json files!")
        return redirect(request.referrer)
    
    copy_device_settings = request.form.get('device_settings', None) == 'true'
    copy_surveys = request.form.get('surveys', None) == 'true'
    device_settings, surveys, interventions = unpack_json_study(file.read())
    
    initial_tracking_surveys = study.surveys.filter(survey_type=Survey.TRACKING_SURVEY).count()
    initial_audio_surveys = study.surveys.filter(survey_type=Survey.AUDIO_SURVEY).count()
    # initial_image_surveys = study.objects.filter(survey_type=Survey.IMAGE_SURVEY).count()
    copy_study_from_json(
        study,
        device_settings if copy_device_settings else {},
        surveys if copy_surveys else [],
        interventions,
    )
    end_tracking_surveys = study.surveys.filter(survey_type=Survey.TRACKING_SURVEY).count()
    end_audio_surveys = study.surveys.filter(survey_type=Survey.AUDIO_SURVEY).count()
    # end_image_surveys = study.objects.filter(survey_type=Survey.IMAGE_SURVEY).count()
    messages.success(
        f"Copied {end_tracking_surveys-initial_tracking_surveys} " +
        f"Surveys and {end_audio_surveys-initial_audio_surveys} Audio Surveys",
    )
    if copy_device_settings:
        messages.success(f"Overwrote {study.name}'s App Settings with custom values.")
    else:
        messages.success(f"Did not alter {study.name}'s App Settings.")
    return redirect(f'/edit_study/{study_id}')
