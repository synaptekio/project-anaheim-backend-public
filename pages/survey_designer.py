from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.timezone import localtime

from authentication.admin_authentication import authenticate_researcher_study_access
from config.settings import DOMAIN_NAME
from database.survey_models import Survey
from libs.firebase_config import check_firebase_instance
from libs.internal_types import ResearcherRequest


@authenticate_researcher_study_access
def render_edit_survey(request: ResearcherRequest, study_id: int, survey_id: int):
    survey = get_object_or_404(Survey, pk=survey_id)
    return render(
        request,
        'edit_survey.html',
        dict(
            survey=survey.as_unpacked_native_python(),
            study=survey.study,
            domain_name=DOMAIN_NAME,  # used in a Javascript alert, see survey-editor.js
            interventions_dict={
                intervention.id: intervention.name for intervention in survey.study.interventions.all()
            },
            weekly_timings=survey.weekly_timings(),
            relative_timings=survey.relative_timings(),
            absolute_timings=survey.absolute_timings(),
            push_notifications_enabled=check_firebase_instance(require_android=True) or check_firebase_instance(require_ios=True),
            today=localtime(timezone.now(), survey.study.timezone).strftime('%Y-%m-%d'),
        )
    )
