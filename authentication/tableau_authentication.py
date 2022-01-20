import functools
import json

from django.http.request import HttpRequest
from django.http.response import HttpResponse

from constants.tableau_api_constants import (APIKEY_NO_ACCESS_MESSAGE,
    CREDENTIALS_NOT_VALID_ERROR_MESSAGE, NO_STUDY_FOUND_MESSAGE, NO_STUDY_PROVIDED_MESSAGE,
    RESEARCHER_NOT_ALLOWED, RESOURCE_NOT_FOUND, STUDY_HAS_FOREST_DISABLED_MESSAGE, X_ACCESS_KEY_ID,
    X_ACCESS_KEY_SECRET)
from database.security_models import ApiKey
from database.study_models import Study
from database.user_models import StudyRelation
from forms.django_forms import AuthenticationForm
from libs.internal_types import TableauRequest


class TableauAuthenticationFailed(Exception): pass
class TableauPermissionDenied(Exception): pass


DEBUG_TABLEAU_AUTHENTICATION = False


def log(*args, **kwargs):
    if DEBUG_TABLEAU_AUTHENTICATION:
        print(*args, **kwargs)


def authenticate_tableau(some_function):
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        request: TableauRequest = args[0]
        
        # this is debugging code for the django frontend server port
        if not isinstance(request, HttpRequest):
            raise TypeError(f"request was a {type(request)}, expected {HttpRequest}")
        
        try:
            # ettempt to get the study_object_id from the url parameter
            check_tableau_permissions(request, study_object_id=kwargs.get("study_object_id", None))
        except TableauAuthenticationFailed as error:
            log("returning as 400")
            return HttpResponse(json.dumps({"errors": error.args}), status=400)
        except TableauPermissionDenied:
            # Prefer 404 over 403 to hide information about validity of these resource identifiers
            log("returning as 404")
            return HttpResponse(json.dumps({"errors": RESOURCE_NOT_FOUND}), status=404)
        
        return some_function(*args, **kwargs)
    
    return authenticate_and_call


def check_tableau_permissions(request: HttpRequest, study_object_id=None):
    """ Authenticate API key and check permissions for access to a study/participant data. """
    authorization_form = AuthenticationForm(request.headers)
    
    # sanitize
    if not authorization_form.is_valid():
        log("form not valid")
        raise TableauAuthenticationFailed(authorization_form.errors)
    
    try:
        api_key: ApiKey = ApiKey.objects.get(
            access_key_id=authorization_form.cleaned_data[X_ACCESS_KEY_ID], is_active=True,
        )
    except ApiKey.DoesNotExist:
        log("ApiKey does not exist")
        raise TableauAuthenticationFailed(CREDENTIALS_NOT_VALID_ERROR_MESSAGE)
    
    # test key
    if not api_key.proposed_secret_key_is_valid(
        authorization_form.cleaned_data[X_ACCESS_KEY_SECRET]
    ):
        log("proposed secret key is not valid")
        raise TableauAuthenticationFailed(CREDENTIALS_NOT_VALID_ERROR_MESSAGE)
    
    if not api_key.has_tableau_api_permissions:
        log("api key does not have permission")
        raise TableauPermissionDenied(APIKEY_NO_ACCESS_MESSAGE)
    # existence errors
    if study_object_id is None:
        log("study_object_id was None")
        raise TableauPermissionDenied(NO_STUDY_PROVIDED_MESSAGE)
    
    if not Study.objects.filter(object_id=study_object_id).exists():
        log("no such study object id")
        raise TableauPermissionDenied(NO_STUDY_FOUND_MESSAGE)
    
    if not Study.objects.get(object_id=study_object_id).forest_enabled:
        log("forest not enabled on study")
        raise TableauPermissionDenied(STUDY_HAS_FOREST_DISABLED_MESSAGE)
    
    if not api_key.researcher.site_admin:
        try:
            StudyRelation.objects.filter(study__object_id=study_object_id) \
                .get(researcher=api_key.researcher)
        except StudyRelation.DoesNotExist:
            log("Researcher not associated with study")
            raise TableauPermissionDenied(RESEARCHER_NOT_ALLOWED)
