import json
import functools

from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.http.request import HttpRequest
from django.http.response import HttpResponse

from constants.tableau_api_constants import (APIKEY_NO_ACCESS_MESSAGE,
    CREDENTIALS_NOT_VALID_ERROR_MESSAGE, HEADER_IS_REQUIRED, NO_STUDY_FOUND_MESSAGE,
    NO_STUDY_PROVIDED_MESSAGE, RESEARCHER_NOT_ALLOWED, RESOURCE_NOT_FOUND,
    STUDY_HAS_FOREST_DISABLED_MESSAGE, X_ACCESS_KEY_ID, X_ACCESS_KEY_SECRET)
from database.security_models import ApiKey
from database.study_models import Study
from database.user_models import StudyRelation
from libs.internal_types import TableauRequest


class TableauAuthenticationFailed(Exception): pass
class PermissionDenied(Exception): pass


class AuthenticationForm(forms.Form):
    """ Form for fetching request headers """

    def __init__(self, *args, **kwargs):
        """ Define authentication form fields since the keys contain illegal characters for variable
        names. """
        super().__init__(*args, **kwargs)
        self.fields[X_ACCESS_KEY_ID] = forms.CharField(
            error_messages={"required": HEADER_IS_REQUIRED}
        )
        self.fields[X_ACCESS_KEY_SECRET] = forms.CharField(
            error_messages={"required": HEADER_IS_REQUIRED}
        )


def authenticate_tableau(some_function):
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        request: TableauRequest = args[0]

        # this is debugging code for the django frontend server port
        if not isinstance(request, HttpRequest):
            raise TypeError(f"request was a {type(request)}, expected {HttpRequest}")

        try:
            check_tableau_permissions(request)
        except TableauAuthenticationFailed as error:
            return HttpResponse(json.dumps({"errors": error.args}), status_code=400)
        except PermissionDenied:
            # Prefer 404 over 403 to hide information about validity of these resource identifiers
            return HttpResponse(json.dumps({"errors": RESOURCE_NOT_FOUND}), status_code=404)

        return some_function(*args, **kwargs)

    return authenticate_and_call


def check_tableau_permissions(request, study_object_id=None):
    """ Authenticate API key and check permissions for access to a study/participant data. """
    authorization_form = AuthenticationForm(request.headers)

    # sanitize
    if not authorization_form.is_valid():
        raise TableauAuthenticationFailed(authorization_form.errors)

    try:
        api_key: ApiKey = ApiKey.objects.get(
            access_key_id=authorization_form.cleaned_data[X_ACCESS_KEY_ID], is_active=True,
        )
    except ApiKey.DoesNotExist:
        raise TableauAuthenticationFailed(CREDENTIALS_NOT_VALID_ERROR_MESSAGE)

    # test key
    if not api_key.proposed_secret_key_is_valid(form.cleaned_data[X_ACCESS_KEY_SECRET]):
        raise TableauAuthenticationFailed(CREDENTIALS_NOT_VALID_ERROR_MESSAGE)
    if not api_key.has_tableau_api_permissions:
        raise PermissionDenied(APIKEY_NO_ACCESS_MESSAGE)
    # existence errors
    if study_object_id is None:
        raise PermissionDenied(NO_STUDY_PROVIDED_MESSAGE)
    if not Study.objects.filter(object_id=study_object_id).exists():
        raise PermissionDenied(NO_STUDY_FOUND_MESSAGE)
    if not Study.objects.get(object_id=study_object_id).forest_enabled:
        raise PermissionDenied(STUDY_HAS_FOREST_DISABLED_MESSAGE)

    if not api_key.researcher.site_admin:
        try:
            StudyRelation.objects.filter(study__object_id=study_object_id) \
                .get(researcher=api_key.researcher)
        except ObjectDoesNotExist:
            raise PermissionDenied(RESEARCHER_NOT_ALLOWED)
