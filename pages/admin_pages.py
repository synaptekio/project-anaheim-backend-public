from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST
from markupsafe import Markup

from authentication.admin_authentication import (authenticate_researcher_login,
    authenticate_researcher_study_access, get_researcher_allowed_studies_as_query_set,
    logout_researcher, SESSION_NAME)
from constants.message_strings import NEW_API_KEY_MESSAGE, RESET_DOWNLOAD_API_CREDENTIALS_MESSAGE
from database.security_models import ApiKey
from database.study_models import Study
from database.user_models import Researcher
from forms.django_forms import DisableApiKeyForm, NewApiKeyForm
from libs.firebase_config import check_firebase_instance
from libs.internal_types import ResearcherRequest
from libs.security import check_password_requirements
from serializers.tableau_serializers import ApiKeySerializer


####################################################################################################
############################################# Basics ###############################################
####################################################################################################


def logout_admin(request: ResearcherRequest):
    """ clear session information for a researcher """
    logout_researcher(request)
    return redirect("/")

####################################################################################################
###################################### Endpoints ###################################################
####################################################################################################


@require_GET
@authenticate_researcher_login
def choose_study(request: ResearcherRequest):
    allowed_studies = get_researcher_allowed_studies_as_query_set(request)
    # If the admin is authorized to view exactly 1 study, redirect to that study,
    # Otherwise, show the "Choose Study" page
    if allowed_studies.count() == 1:
        return redirect('/view_study/{:d}'.format(allowed_studies.values_list('pk', flat=True).get()))

    return render(
        request,
        'choose_study.html',
        context=dict(
            studies=[obj.as_unpacked_native_python() for obj in allowed_studies],
            is_admin=request.session_researcher.is_an_admin(),
        )
    )


@require_GET
@authenticate_researcher_study_access
def view_study(request: ResearcherRequest, study_id=None):
    study = Study.objects.get(pk=study_id)

    return render(
        request,
        template_name='view_study.html',
        context=dict(
            study=study,
            audio_survey_ids=study.get_survey_ids_and_object_ids('audio_survey'),
            image_survey_ids=study.get_survey_ids_and_object_ids('image_survey'),
            tracking_survey_ids=study.get_survey_ids_and_object_ids('tracking_survey'),
            # these need to be lists because they will be converted to json.
            study_fields=list(study.fields.all().values_list('field_name', flat=True)),
            interventions=list(study.interventions.all().values_list("name", flat=True)),
            page_location='study_landing',
            study_id=study_id,
            is_site_admin=request.session_researcher.site_admin,
            push_notifications_enabled=check_firebase_instance(require_android=True) or
                                       check_firebase_instance(require_ios=True),
        )
    )


@authenticate_researcher_login
def manage_credentials(request: ResearcherRequest):
    serializer = ApiKeySerializer(
        ApiKey.objects.filter(researcher=request.session_researcher), many=True)
    return render(
        request,
        'manage_credentials.html',
        context=dict(is_admin=request.session_researcher.is_an_admin(),
                     api_keys=sorted(serializer.data, reverse=True, key=lambda x: x['created_on']))
    )


@require_POST
@authenticate_researcher_login
def reset_admin_password(request: ResearcherRequest):
    username = request.session[SESSION_NAME]
    current_password = request.POST['current_password']
    new_password = request.POST['new_password']
    confirm_new_password = request.POST['confirm_new_password']

    if not Researcher.check_password(username, current_password):
        messages.warning(request, "The Current Password you have entered is invalid")
        return redirect('admin_pages.manage_credentials')
    if not check_password_requirements(new_password, flash_message=True):
        return redirect("admin_pages.manage_credentials")
    if new_password != confirm_new_password:
        messages.warning(request, "New Password does not match Confirm New Password")
        return redirect('admin_pages.manage_credentials')

    # todo: sanitize password?
    Researcher.objects.get(username=username).set_password(new_password)
    messages.warning(request, "Your password has been reset!")
    return redirect('admin_pages.manage_credentials')


@require_POST
@authenticate_researcher_login
def reset_download_api_credentials(request: ResearcherRequest):
    researcher = Researcher.objects.get(username=request.session[SESSION_NAME])
    access_key, secret_key = researcher.reset_access_credentials()
    messages.warning(request, Markup(RESET_DOWNLOAD_API_CREDENTIALS_MESSAGE % (access_key, secret_key)), 'warning')
    return redirect("admin_pages.manage_credentials")


# @admin_pages.route('/new_api_key', methods=['POST'])
@require_POST
@authenticate_researcher_login
def new_api_key(request: ResearcherRequest):
    form = NewApiKeyForm(request.POST)
    if not form.is_valid():
        return redirect("admin_pages.manage_credentials")
    researcher = Researcher.objects.get(username=request.session[SESSION_NAME])

    api_key = ApiKey.generate(
        researcher=researcher,
        has_tableau_api_permissions=form.cleaned_data['tableau_api_permission'],
        readable_name=form.cleaned_data['readable_name'],
    )
    # noinspection StrFormat
    msg = NEW_API_KEY_MESSAGE % (api_key.access_key_id, api_key.access_key_secret_plaintext)
    # messages.warning(request, Markup(msg))
    return redirect("admin_pages.manage_credentials")


@require_POST
@authenticate_researcher_login
def disable_api_key(request: ResearcherRequest):
    form = DisableApiKeyForm(request.POST)
    if not form.is_valid():
        return redirect("admin_pages.manage_credentials")

    api_key_id = request.POST["api_key_id"]
    api_key_query = ApiKey.objects.filter(access_key_id=api_key_id).filter(researcher=request.session_researcher)
    if not api_key_query.exists():
        messages.warning(request, Markup("No matching API key found to disable"))
        return redirect("admin_pages.manage_credentials")
    api_key = api_key_query[0]
    if not api_key.is_active:
        messages.warning(request, f"That API key has already been disabled: {api_key_id}")
        return redirect("admin_pages.manage_credentials")
    api_key.is_active = False
    api_key.save()
    # messages.warning(request, "The API key %s is now disabled" % str(api_key.access_key_id))
    return redirect("admin_pages.manage_credentials")
