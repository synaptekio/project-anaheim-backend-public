import json
import plistlib
from collections import defaultdict
from typing import List

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from markupsafe import escape, Markup

from authentication.admin_authentication import (abort, assert_admin, assert_researcher_under_admin,
    authenticate_admin, authenticate_researcher_study_access)
from constants.celery_constants import (ANDROID_FIREBASE_CREDENTIALS, BACKEND_FIREBASE_CREDENTIALS,
    IOS_FIREBASE_CREDENTIALS)
from constants.common_constants import RUNNING_TEST_OR_IN_A_SHELL
from constants.html_constants import CHECKBOX_TOGGLES, TIMER_VALUES
from constants.message_strings import (ALERT_ANDROID_DELETED_TEXT, ALERT_ANDROID_SUCCESS_TEXT,
    ALERT_ANDROID_VALIDATION_FAILED_TEXT, ALERT_DECODE_ERROR_TEXT, ALERT_EMPTY_TEXT,
    ALERT_FIREBASE_DELETED_TEXT, ALERT_IOS_DELETED_TEXT, ALERT_IOS_SUCCESS_TEXT,
    ALERT_IOS_VALIDATION_FAILED_TEXT, ALERT_MISC_ERROR_TEXT, ALERT_SPECIFIC_ERROR_TEXT,
    ALERT_SUCCESS_TEXT)
from constants.researcher_constants import ResearcherRole
from database.data_access_models import FileToProcess
from database.study_models import Study
from database.survey_models import Survey
from database.system_models import FileAsText
from database.user_models import Researcher, StudyRelation
from libs.copy_study import copy_study_from_json, format_study, unpack_json_study
from libs.firebase_config import get_firebase_credential_errors, update_firebase_instance
from libs.http_utils import checkbox_to_boolean, string_to_int
from libs.internal_types import ResearcherRequest
from libs.sentry import make_error_sentry, SentryTypes
from libs.timezone_dropdown import ALL_TIMEZONES_DROPDOWN


####################################################################################################
###################################### Helpers #####################################################
####################################################################################################


def get_administerable_studies_by_name(request: ResearcherRequest) -> List[Study]:
    """ Site admins see all studies, study admins see only studies they are admins on. """
    if request.session_researcher.site_admin:
        return Study.get_all_studies_by_name()
    else:
        return request.session_researcher.get_administered_studies_by_name()


def get_administerable_researchers(request: ResearcherRequest) -> List[Researcher]:
    """ Site admins see all researchers, study admins see researchers on their studies. """
    if request.session_researcher.site_admin:
        return Researcher.filter_alphabetical()
    else:
        return request.session_researcher.get_administered_researchers_by_username()


def unflatten_consent_sections(consent_sections_dict: dict):
    # consent_sections is a flat structure with structure like this:
    # { 'label_ending_in.text': 'text content',  'label_ending_in.more': 'more content' }
    # we need to transform it into a nested structure like this:
    # { 'label': {'text':'text content',  'more':'more content' }
    refactored_consent_sections = defaultdict(dict)
    for key, content in consent_sections_dict.items():
        _, label, content_type = key.split(".")
        refactored_consent_sections[label][content_type] = content
    return dict(refactored_consent_sections)


def validate_android_credentials(credentials: str) -> bool:
    """Ensure basic formatting and field validation for android firebase credential json file uploads
    the credentials argument should contain a decoded string of such a file"""
    try:
        json_obj = json.dumps(credentials)
        # keys are inconsistent in presence, but these should be present in all.  (one is structure,
        # one is a critical data point.)
        if "project_info" not in json_obj or "project_id" not in json_obj:
            return False
    except Exception:
        return False
    return True


def validate_ios_credentials(credentials: str) -> bool:
    """Ensure basic formatting and field validation for ios firebase credential plist file uploads
    the credentials argument should contain a decoded string of such a file"""
    try:
        plist_obj = plistlib.loads(str.encode(credentials))
        # ios has different key values than android, and they are somewhat opaque and inconsistently
        # present when generated. Just test for API_KEY
        if "API_KEY" not in plist_obj:
            return False
    except Exception:
        return False
    return True

####################################################################################################
######################################## Pages #####################################################
####################################################################################################


@require_GET
@authenticate_admin
def manage_researchers(request: ResearcherRequest):
    # get the study names that each user has access to, but only those that the current admin  also
    # has access to.
    
    if request.session_researcher.site_admin:
        session_ids = Study.objects.exclude(deleted=True).values_list("id", flat=True)
    else:
        session_ids = request.session_researcher.\
            study_relations.filter(study__deleted=False).values_list("study__id", flat=True)
    
    researcher_list = []
    for researcher in get_administerable_researchers(request):
        allowed_studies = Study.get_all_studies_by_name().filter(
            study_relations__researcher=researcher, study_relations__study__in=session_ids,
        ).values_list('name', flat=True)
        researcher_list.append((researcher.as_unpacked_native_python(), list(allowed_studies)))
    
    return render(request, 'manage_researchers.html', context=dict(admins=researcher_list))


@require_http_methods(['GET', 'POST'])
@authenticate_admin
def edit_researcher_page(request: ResearcherRequest, researcher_pk):
    # Wow this got complex...
    session_researcher = request.session_researcher
    edit_researcher = Researcher.objects.get(pk=researcher_pk)
    
    # site admins can edit study admins, but not other site admins.
    # (users do not edit their own passwords on this page.)
    editable_password = (
            not edit_researcher.username == session_researcher.username
            and not edit_researcher.site_admin
    )
    
    # if the session researcher is not a site admin then we need to restrict password editing
    # to only researchers that are not study_admins anywhere.
    if not session_researcher.site_admin:
        editable_password = editable_password and not edit_researcher.is_study_admin()
    
    # edit_study_info is a list of tuples of (study relationship, whether that study is editable by
    # the current session admin, and the study itself.)
    visible_studies = session_researcher.get_visible_studies_by_name()
    if edit_researcher.site_admin:
        # if the session admin is a site admin then we can skip the complex logic
        edit_study_info = [("Site Admin", True, study) for study in visible_studies]
    else:
        # When the session admin is just a study admin then we need to determine if the study that
        # the session admin can see is also one they are an admin on so we can display buttons.
        administerable_studies = set(get_administerable_studies_by_name(request).values_list("pk", flat=True))
        
        # We need the overlap of the edit_researcher studies with the studies visible to the session
        # admin, and we need those relationships for display purposes on the page.
        edit_study_relationship_map = {
            study_id: relationship.replace("_", " ").title()
            for study_id, relationship in edit_researcher.study_relations
                .filter(study__in=visible_studies)
                .values_list("study_id", "relationship")
        }
        
        # get the relevant studies, populate with relationship, editability, and the study.
        edit_study_info = []
        for study in visible_studies.filter(pk__in=edit_study_relationship_map.keys()):
            edit_study_info.append((
                edit_study_relationship_map[study.id],
                study.id in administerable_studies,
                study,
            ))
    
    return render(
        request,
        'edit_researcher.html',
        dict(
            edit_researcher=edit_researcher,
            edit_study_info=edit_study_info,
            all_studies=get_administerable_studies_by_name(request),
            editable_password=editable_password,
            redirect_url=f'/edit_researcher/{researcher_pk}',
            is_self=edit_researcher.id == session_researcher.id,
        )
    )

@require_POST
@authenticate_admin
def elevate_researcher(request: ResearcherRequest):
    researcher_pk = request.POST.get("researcher_id", None)
    # some extra validation on the researcher id
    try:
        int(researcher_pk)
    except ValueError:
        return abort(400)
    
    study_pk = request.POST.get("study_id", None)
    assert_admin(request, study_pk)
    edit_researcher = get_object_or_404(Researcher, pk=researcher_pk)
    study = get_object_or_404(Study, pk=study_pk)
    assert_researcher_under_admin(request, edit_researcher, study)
    if edit_researcher.site_admin:
        return abort(403)
    StudyRelation.objects.filter(researcher=edit_researcher, study=study) \
        .update(relationship=ResearcherRole.study_admin)
    
    return redirect(
        request.POST.get("redirect_url", None) or f'/edit_researcher/{researcher_pk}'
    )


@require_POST
@authenticate_admin
def demote_study_admin(request: ResearcherRequest):
    # FIXME: this endpoint does not test for site admin cases correctly, the test passes but is
    # wrong. Behavior is fine because it has no relevant side effects except for the know bug where
    # site admins need to be manually added to a study before being able to download data.
    researcher_pk = request.POST.get("researcher_id")
    study_pk = request.POST.get("study_id")
    assert_admin(request, study_pk)
    # assert_researcher_under_admin() would fail here...
    StudyRelation.objects.filter(
        researcher=Researcher.objects.get(pk=researcher_pk),
        study=Study.objects.get(pk=study_pk),
    ).update(relationship=ResearcherRole.researcher)
    return redirect(
        request.POST.get("redirect_url", None) or f'/edit_researcher/{researcher_pk}'
    )


@require_http_methods(['GET', 'POST'])
@authenticate_admin
def create_new_researcher(request: ResearcherRequest):
    # FIXME: get rid of dual endpoint pattern, it is a bad idea.
    if request.method == 'GET':
        return render(request, 'create_new_researcher.html')
    
    # Drop any whitespace or special characters from the username (restrictive, alphanumerics-only)
    username = ''.join(c for c in request.POST.get('admin_id', '') if c.isalnum())
    password = request.POST.get('password', '')
    
    if Researcher.objects.filter(username=username).exists():
        messages.error(request, f"There is already a researcher with username {username}")
        return redirect('/create_new_researcher')
    else:
        researcher = Researcher.create_with_password(username, password)
        return redirect(f'/edit_researcher/{researcher.pk}')


"""########################### Study Pages ##################################"""

@require_GET
@authenticate_admin
def manage_studies(request: ResearcherRequest):
    studies = [
        study.as_unpacked_native_python() for study in get_administerable_studies_by_name(request)
    ]
    return render(
        request,
        'manage_studies.html',
        context=dict(
            studies=studies,
            unprocessed_files_count=FileToProcess.objects.count(),
        )
    )


@require_GET
@authenticate_admin
def edit_study(request, study_id=None):
    # get the data points for display for all researchers in this study
    query = Researcher.filter_alphabetical(study_relations__study_id=study_id).values_list(
        "id", "username", "study_relations__relationship", "site_admin"
    )
    
    # transform raw query data as needed
    listed_researchers = []
    for pk, username, relationship, site_admin in query:
        listed_researchers.append((
            pk,
            username,
            "Site Admin" if site_admin else relationship.replace("_", " ").title(),
            site_admin
        ))
    
    return render(
        request,
        'edit_study.html',
        context=dict(
            study=Study.objects.get(pk=study_id),
            administerable_researchers=get_administerable_researchers(request),
            listed_researchers=listed_researchers,
            redirect_url=f'/edit_study/{study_id}',
            timezones=ALL_TIMEZONES_DROPDOWN,
            page_location="edit_study"
        )
    )


@require_http_methods(['GET', 'POST'])
@authenticate_admin
def create_study(request: ResearcherRequest):
    # Only a SITE admin can create new studies.
    if not request.session_researcher.site_admin:
        return abort(403)
    
    # FIXME: get rid of dual endpoint pattern, it is a bad idea.
    if request.method == 'GET':
        studies = [study.as_unpacked_native_python() for study in Study.get_all_studies_by_name()]
        return render(request, 'create_study.html', context=dict(studies=studies))
    
    name = request.POST.get('name', '')
    encryption_key = request.POST.get('encryption_key', '')
    is_test = request.POST.get('is_test', "").lower() == 'true'  # 'true' -> True, 'false' -> False
    duplicate_existing_study = request.POST.get('copy_existing_study', None) == 'true'
    forest_enabled = request.POST.get('forest_enabled', "").lower() == 'true'
    
    if len(name) > 5000:
        if not RUNNING_TEST_OR_IN_A_SHELL:
            with make_error_sentry(SentryTypes.elastic_beanstalk):
                raise Exception("Someone tried to create a study with a suspiciously long name.")
        return abort(400)
    
    if escape(name) != name:
        if not RUNNING_TEST_OR_IN_A_SHELL:
            with make_error_sentry(SentryTypes.elastic_beanstalk):
                raise Exception("Someone tried to create a study with unsafe characters in its name.")
        return abort(400)
    
    try:
        new_study = Study.create_with_object_id(
            name=name, encryption_key=encryption_key, is_test=is_test, forest_enabled=forest_enabled
        )
        if duplicate_existing_study:
            do_duplicate_step(request, new_study)
        messages.success(request, f'Successfully created study {name}.')
        return redirect(f'/device_settings/{new_study.pk}')
    
    except ValidationError as ve:
        # display message describing failure based on the validation error (hacky, but works.)
        for field, message in ve.message_dict.items():
            messages.error(request, f'{field}: {message[0]}')
        return redirect('/create_study')


def do_duplicate_step(request: ResearcherRequest, new_study: Study):
    """ Everything you need to copy a study. """
    # surveys are always provided, there is a checkbox about whether to import them
    copy_device_settings = request.POST.get('device_settings', None) == 'true'
    copy_surveys = request.POST.get('surveys', None) == 'true'
    old_study = Study.objects.get(pk=request.POST.get('existing_study_id', None))
    device_settings, surveys, interventions = unpack_json_study(format_study(old_study))
    
    copy_study_from_json(
        new_study,
        device_settings if copy_device_settings else {},
        surveys if copy_surveys else [],
        interventions,
    )
    tracking_surveys_added = new_study.surveys.filter(survey_type=Survey.TRACKING_SURVEY).count()
    audio_surveys_added = new_study.surveys.filter(survey_type=Survey.AUDIO_SURVEY).count()
    # image_surveys_added = new_study.objects.filter(survey_type=Survey.IMAGE_SURVEY).count()
    messages.success(
        request,
        f"Copied {tracking_surveys_added} Surveys and {audio_surveys_added} "
        f"Audio Surveys from {old_study.name} to {new_study.name}.",
    )
    if copy_device_settings:
        messages.success(
            request, f"Overwrote {new_study.name}'s App Settings with custom values."
        )
    else:
        messages.success(request, f"Did not alter {new_study.name}'s App Settings.")


# FIXME: this should take a post parameter, not a url endpoint.
@require_POST
@authenticate_admin
def toggle_study_forest_enabled(request: ResearcherRequest, study_id=None):
    # Only a SITE admin can toggle forest on a study
    if not request.session_researcher.site_admin:
        return abort(403)
    study = Study.objects.get(pk=study_id)
    study.forest_enabled = not study.forest_enabled
    study.save()
    if study.forest_enabled:
        messages.success(request, f"Enabled Forest on '{study.name}'")
    else:
        messages.success(request, f"Disabled Forest on '{study.name}'")
    return redirect(f'/edit_study/{study_id}')


# TODO: move to api
@require_POST
@authenticate_admin
def delete_study(request: ResearcherRequest, study_id=None):
    # Site admins and study admins can delete studies.
    assert_admin(request, study_id)
    
    if request.POST.get('confirmation', 'false') == 'true':
        study = Study.objects.get(pk=study_id)
        study.deleted = True
        study.save()
        messages.success(request, f"Deleted study '{study.name}'")
    
    return redirect("system_admin_pages.manage_studies")


@require_http_methods(['GET', 'POST'])
@authenticate_researcher_study_access
def device_settings(request: ResearcherRequest, study_id=None):
    study = Study.objects.get(pk=study_id)
    researcher = request.session_researcher
    readonly = not researcher.check_study_admin(study_id) and not researcher.site_admin
    
    # FIXME: get rid of dual endpoint pattern, it is a bad idea.
    if request.method == 'GET':
        return render(
            request,
            "device_settings.html",
            context=dict(
                study=study.as_unpacked_native_python(),
                settings=study.device_settings.as_unpacked_native_python(),
                readonly=readonly,
            )
        )
    
    if readonly:
        abort(403)
    
    params = {k: v for k, v in request.POST.items() if not k.startswith("consent_section")}
    consent_sections = {k: v for k, v in request.POST.items() if k.startswith("consent_section")}
    params = checkbox_to_boolean(CHECKBOX_TOGGLES, params)
    params = string_to_int(TIMER_VALUES, params)
    # the ios consent sections are a json field but the frontend returns something weird,
    # see the documentation in unflatten_consent_sections for details
    params["consent_sections"] = json.dumps(unflatten_consent_sections(consent_sections))
    study.device_settings.update(**params)
    return redirect(f'/edit_study/{study.id}')


########################## FIREBASE CREDENTIALS ENDPOINTS ##################################
# note: all of the strings passed in the following function (eg: ALERT_DECODE_ERROR_TEXT) are plain strings
# not intended for use with .format or other potential injection vectors

@authenticate_admin
def manage_firebase_credentials(request: ResearcherRequest):
    return render(
        request,
        'manage_firebase_credentials.html',
        dict(
            firebase_credentials_exists=FileAsText.objects.filter(tag=BACKEND_FIREBASE_CREDENTIALS).exists(),
            android_credentials_exists=FileAsText.objects.filter(tag=ANDROID_FIREBASE_CREDENTIALS).exists(),
            ios_credentials_exists=FileAsText.objects.filter(tag=IOS_FIREBASE_CREDENTIALS).exists(),
        )
    )


@require_POST
@authenticate_admin
def upload_backend_firebase_cert(request: ResearcherRequest):
    uploaded = request.FILES.get('backend_firebase_cert', None)
    
    if uploaded is None:
        messages.error(request, Markup(ALERT_EMPTY_TEXT))
        return redirect('/manage_firebase_credentials')
    
    try:
        cert = uploaded.read().decode()
    except UnicodeDecodeError:  # raised for an unexpected file type
        messages.error(request, Markup(ALERT_DECODE_ERROR_TEXT))
        return redirect('/manage_firebase_credentials')
    
    if not cert:
        messages.error(request, Markup(ALERT_EMPTY_TEXT))
        return redirect('/manage_firebase_credentials')
    
    instantiation_errors = get_firebase_credential_errors(cert)
    if instantiation_errors:
        # noinspection StrFormat
        # This string is sourced purely from the error message of get_firebase_credential_errors,
        # all of which are known-safe text. (no javascript injection)
        error_string = ALERT_SPECIFIC_ERROR_TEXT.format(error_message=instantiation_errors)
        messages.error(request, Markup(error_string))
        return redirect('/manage_firebase_credentials')
    
    # delete and recreate to get metadata timestamps
    FileAsText.objects.filter(tag=BACKEND_FIREBASE_CREDENTIALS).delete()
    FileAsText.objects.create(tag=BACKEND_FIREBASE_CREDENTIALS, text=cert)
    update_firebase_instance()
    messages.info(request, Markup(ALERT_SUCCESS_TEXT))
    return redirect('/manage_firebase_credentials')


@require_POST
@authenticate_admin
def upload_android_firebase_cert(request: ResearcherRequest):
    uploaded = request.FILES.get('android_firebase_cert', None)
    try:
        if uploaded is None:
            raise AssertionError("file name missing from upload")
        cert = uploaded.read().decode()
        if not cert:
            raise AssertionError("unexpected empty string")
        if not validate_android_credentials(cert):
            raise ValidationError('wrong keys for android cert')
        FileAsText.objects.get_or_create(tag=ANDROID_FIREBASE_CREDENTIALS, defaults={"text": cert})
        messages.info(request, Markup(ALERT_ANDROID_SUCCESS_TEXT))
    except AssertionError:
        messages.error(request, Markup(ALERT_EMPTY_TEXT))
    except UnicodeDecodeError:  # raised for an unexpected file type
        messages.error(request, Markup(ALERT_DECODE_ERROR_TEXT))
    except ValidationError:
        messages.error(request, Markup(ALERT_ANDROID_VALIDATION_FAILED_TEXT))
    except AttributeError:  # raised for a missing file
        messages.error(request, Markup(ALERT_EMPTY_TEXT))
    except ValueError:
        messages.error(request, Markup(ALERT_MISC_ERROR_TEXT))
    return redirect('/manage_firebase_credentials')


@require_POST
@authenticate_admin
def upload_ios_firebase_cert(request: ResearcherRequest):
    uploaded = request.FILES.get('ios_firebase_cert', None)
    try:
        if uploaded is None:
            raise AssertionError("file name missing from upload")
        cert = uploaded.read().decode()
        if not cert:
            raise AssertionError("unexpected empty string")
        if not validate_ios_credentials(cert):
            raise ValidationError('wrong keys for ios cert')
        FileAsText.objects.get_or_create(tag=IOS_FIREBASE_CREDENTIALS, defaults={"text": cert})
        messages.info(request, Markup(ALERT_IOS_SUCCESS_TEXT))
    except AssertionError:
        messages.error(request, Markup(ALERT_EMPTY_TEXT))
    except UnicodeDecodeError:  # raised for an unexpected file type
        messages.error(request, Markup(ALERT_DECODE_ERROR_TEXT))
    except AttributeError:  # raised for a missing file
        messages.error(request, Markup(ALERT_EMPTY_TEXT))
    except ValidationError:
        messages.error(request, Markup(ALERT_IOS_VALIDATION_FAILED_TEXT))
    except ValueError:
        messages.error(request, Markup(ALERT_MISC_ERROR_TEXT))
    return redirect('/manage_firebase_credentials')


@require_POST
@authenticate_admin
def delete_backend_firebase_cert(request: ResearcherRequest):
    FileAsText.objects.filter(tag=BACKEND_FIREBASE_CREDENTIALS).delete()
    # deletes the existing firebase app connection to clear credentials from memory
    update_firebase_instance()
    messages.info(request, Markup(ALERT_FIREBASE_DELETED_TEXT))
    return redirect('/manage_firebase_credentials')


@require_POST
@authenticate_admin
def delete_android_firebase_cert(request: ResearcherRequest):
    FileAsText.objects.filter(tag=ANDROID_FIREBASE_CREDENTIALS).delete()
    messages.info(request, Markup(ALERT_ANDROID_DELETED_TEXT))
    return redirect('/manage_firebase_credentials')


@require_POST
@authenticate_admin
def delete_ios_firebase_cert(request: ResearcherRequest):
    FileAsText.objects.filter(tag=IOS_FIREBASE_CREDENTIALS).delete()
    messages.info(request, Markup(ALERT_IOS_DELETED_TEXT))
    return redirect('/manage_firebase_credentials')
