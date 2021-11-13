from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http.request import HttpRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from authentication.admin_authentication import (assert_admin, assert_researcher_under_admin,
    authenticate_admin, authenticate_researcher_login)
from config.settings import DOMAIN_NAME, DOWNLOADABLE_APK_URL
from constants.researcher_constants import ResearcherRole
from database.study_models import Study
from database.user_models import Researcher, StudyRelation
from libs.internal_types import ResearcherRequest
from libs.push_notification_helpers import repopulate_all_survey_scheduled_events
from libs.security import check_password_requirements
from libs.timezone_dropdown import ALL_TIMEZONES
from middleware.abort_middleware import abort


"""######################### Study Administration ###########################"""


@require_POST
@authenticate_admin
def set_study_timezone(request: ResearcherRequest, study_id=None):
    """ Sets the custom timezone on a study. """
    new_timezone = request.POST.get("new_timezone_name")
    if new_timezone not in ALL_TIMEZONES:
        messages.warning(request, ("The timezone chosen does not exist."))
        return redirect(f'/edit_study/{study_id}')
    
    study = Study.objects.get(pk=study_id)
    study.timezone_name = new_timezone
    study.save()
    
    # All scheduled events for this study need to be recalculated
    # this causes chaos, relative and absolute surveys will be regenerated if already sent.
    repopulate_all_survey_scheduled_events(study)
    messages.warning(request, (f"Timezone {study.timezone_name} has been applied."))
    return redirect(f'/edit_study/{study_id}')


@require_POST
@authenticate_admin
def add_researcher_to_study(request: ResearcherRequest, ):
    researcher_id = request.POST['researcher_id']
    study_id = request.POST['study_id']
    assert_admin(request, study_id)
    try:
        StudyRelation.objects.get_or_create(
            study_id=study_id, researcher_id=researcher_id, relationship=ResearcherRole.researcher
        )
    except ValidationError:
        # handle case of the study id + researcher already existing
        pass
    
    # This gets called by both edit_researcher and edit_study, so the POST request
    # must contain which URL it came from.
    # FIXME: don't source the url from the page, give it a required post parameter for the redirect and check against that
    return redirect(request.POST['redirect_url'])


@require_POST
@authenticate_admin
def remove_researcher_from_study(request: ResearcherRequest, ):
    researcher_id = request.POST['researcher_id']
    study_id = request.POST['study_id']
    try:
        researcher = Researcher.objects.get(pk=researcher_id)
    except Researcher.DoesNotExist:
        return abort(404)
    assert_admin(request, study_id)
    assert_researcher_under_admin(request, researcher, study_id)
    StudyRelation.objects.filter(study_id=study_id, researcher_id=researcher_id).delete()
    # FIXME: don't source the url from the page, give it a required post parameter for the redirect and check against that
    return redirect(request.POST['redirect_url'])


@require_POST
@authenticate_admin
def delete_researcher(request: ResearcherRequest, researcher_id):
    # only site admins can delete researchers from the system.
    if not request.session_researcher.site_admin:
        return abort(403)
    
    try:
        researcher = Researcher.objects.get(pk=researcher_id)
    except Researcher.DoesNotExist:
        return abort(404)
    
    StudyRelation.objects.filter(researcher=researcher).delete()
    researcher.delete()
    return redirect('/manage_researchers')


@require_POST
@authenticate_admin
def set_researcher_password(request: ResearcherRequest, ):
    researcher = Researcher.objects.get(pk=request.POST.get('researcher_id', None))
    assert_researcher_under_admin(request, researcher)
    new_password = request.POST.get('password', '')
    success, msg = check_password_requirements(new_password)
    if success:
        researcher.set_password(new_password)
    else:
        messages.warning(request, msg)
    return redirect(f'/edit_researcher/{researcher.pk}')


@require_POST
@authenticate_admin
def rename_study(request: ResearcherRequest, study_id=None):
    study = Study.objects.get(pk=study_id)
    assert_admin(request, study_id)
    new_study_name = request.POST.get('new_study_name', '')
    study.name = new_study_name
    study.save()
    return redirect(f'/edit_study/{study.pk}')


"""##### Methods responsible for distributing APK file of Android app. #####"""


@authenticate_researcher_login
def download_page(request: ResearcherRequest):
    return render(
        request,
        "download_landing_page.html",
        context=dict(domain_name=DOMAIN_NAME)
    )


def download_current(request: ResearcherRequest):
    return redirect(DOWNLOADABLE_APK_URL)


@authenticate_researcher_login
def download_current_debug(request: ResearcherRequest):
    return redirect("https://s3.amazonaws.com/beiwe-app-backups/release/Beiwe-debug.apk")


@authenticate_researcher_login
def download_beta(request: ResearcherRequest):
    return redirect("https://s3.amazonaws.com/beiwe-app-backups/release/Beiwe.apk")


@authenticate_researcher_login
def download_beta_debug(request: ResearcherRequest):
    return redirect("https://s3.amazonaws.com/beiwe-app-backups/debug/Beiwe-debug.apk")


@authenticate_researcher_login
def download_beta_release(request: ResearcherRequest):
    return redirect("https://s3.amazonaws.com/beiwe-app-backups/release/Beiwe-2.2.3-onnelaLabServer-release.apk")


def download_privacy_policy(request: HttpRequest):
    return redirect("https://s3.amazonaws.com/beiwe-app-backups/Beiwe+Data+Privacy+and+Security.pdf")
