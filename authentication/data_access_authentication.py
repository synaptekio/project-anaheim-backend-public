import functools
from typing import Tuple

from django.http.request import HttpRequest

from config.study_constants import BASE64_GENERIC_ALLOWED_CHARACTERS, OBJECT_ID_ALLOWED_CHARS
from database.study_models import Study
from database.user_models import Researcher, StudyRelation
from libs.internal_types import ApiResearcherRequest, ApiStudyResearcherRequest, ResearcherRequest
from middleware.abort_middleware import abort


class BadObjectIdType(Exception): pass
class IncorrectAPIAuthUsage(Exception): pass


DEBUG_API_AUTHENTICATION = False


def log(*args, **kwargs):
    if DEBUG_API_AUTHENTICATION:
        print(*args, **kwargs)


def is_object_id(object_id: str) -> bool:
    """ Object IDs, we have random strings in newer objects, so we only care about length. """
    # due to change in django we have to check database queries for byte strings as they get coerced
    # to strings prepended with b'
    if not isinstance(object_id, str) or object_id.startswith("b'"):
        raise BadObjectIdType(str(object_id))

    # need to be composed of alphanumerics
    for c in object_id:
        if c not in OBJECT_ID_ALLOWED_CHARS:
            return False

    return len(object_id) == 24


################################# Primary Access Validation ########################################


def api_credential_check(some_function: callable):
    """ Checks API credentials and attaches the researcher to the request object. """
    @functools.wraps(some_function)
    def wrapper(*args, **kwargs):
        request: ApiResearcherRequest = args[0]
        assert isinstance(request, HttpRequest), \
            f"first parameter of {some_function.__name__} type HttpRequest, was {type(request)}."
        # populate the ApiResearcherRequest
        request.api_researcher = api_get_and_validate_researcher(request)  # validate and cache
        return some_function(*args, **kwargs)
    return wrapper


def api_study_credential_check(block_test_studies: bool=False) -> callable:
    """ Decorate api-credentialed functions to test whether user exists, has provided correct
     credentials, and then attach the study and researcher to the request. """
    def the_decorator(some_function: callable):
        @functools.wraps(some_function)
        def the_inner_wrapper(*args, **kwargs):
            request: ApiStudyResearcherRequest = args[0]
            assert isinstance(request, HttpRequest), \
                f"first parameter of {some_function.__name__} type HttpRequest, was {type(request)}."

            # populate the ApiStudyResearcherRequest
            request.api_study, request.api_researcher = \
                api_check_researcher_study_access(request, block_test_studies)

            return some_function(*args, **kwargs)
        return the_inner_wrapper
    return the_decorator


def api_get_and_validate_researcher(request: HttpRequest) -> Researcher:
    access_key, secret_key = api_get_and_validate_credentials(request)
    try:
        researcher = Researcher.objects.get(access_key_id=access_key)
    except Researcher.DoesNotExist:
        log("no such researcher")
        return abort(403)  # access key DNE

    if not researcher.validate_access_credentials(secret_key):
        log("key did not match researcher")
        return abort(403)  # incorrect secret key

    return researcher


################################# Interact with the request ########################################
"""
In general use the decorators. These functions are the underlying components of those decorators,
they are complex and easy to misuse.
"""


def api_check_researcher_study_access(request: ResearcherRequest, block_test_studies: bool) -> Tuple[Study, Researcher]:
    """ Checks whether the researcher is allowed to do api access on this study.
    Parameter allows control of whether to allow the api call to hit a test study. """
    study = api_get_study_confirm_exists(request)
    researcher = api_get_validate_researcher_on_study(request, study)

    user_exceptions = researcher.site_admin or researcher.is_batch_user
    do_block = block_test_studies and not study.is_test

    if not user_exceptions and do_block:
        # You're only allowed to download chunked data from test studies, otherwise doesn't exist.
        log("study not accessible to researcher")
        return abort(404)

    return study, researcher


def api_get_and_validate_credentials(request: HttpRequest) -> Tuple[str, str]:
    """ Sanitize access and secret keys from request """
    access_key = request.values.get("access_key", None)
    secret_key = request.values.get("secret_key", None)

    # reject empty strings and value-not-present cases
    if not access_key or not secret_key:
        log("missing cred")
        return abort(400)

    # access keys use generic base64
    for c in access_key:
        if c not in BASE64_GENERIC_ALLOWED_CHARACTERS:
            log("bad cred access key")
            return abort(400)
    for c in secret_key:
        if c not in BASE64_GENERIC_ALLOWED_CHARACTERS:
            log("bad cred secret key")
            return abort(400)

    return access_key, secret_key


def api_get_validate_researcher_on_study(request: ResearcherRequest, study: Study) -> Researcher:
    """
    Finds researcher based on the secret key provided.
    Returns 403 if researcher doesn't exist, is not credentialed on the study, or if
    the secret key does not match.
    """
    researcher = api_get_and_validate_researcher(request)
    # if the researcher has no relation to the study, and isn't a batch user or site admin, 403.
    # case: batch users and site admins have access to everything.
    # case: researcher is not credentialed for this study.
    if (
        not StudyRelation.objects.filter(study_id=study.pk, researcher=researcher).exists()
        and not researcher.site_admin
        and not researcher.is_batch_user
    ):
        log(f"study found: {StudyRelation.objects.filter(study_id=study.pk, researcher=researcher).exists()}")
        log(f"researcher.site_admin: {researcher.site_admin}")
        log(f"researcher.is_batch_user: {researcher.is_batch_user}")
        log("no study access")
        return abort(403)

    return researcher


def api_get_study_confirm_exists(request: ResearcherRequest) -> Study:
    """
    Checks for a valid study object id or primary key.
    Study object id malformed (not 24 characters) causes 400 error.
    Study does not exist in our database causes 404 error.
    """
    study_object_id = request.values.get('study_id', None)
    study_pk = request.values.get('study_pk', None)

    if study_object_id is not None:

        # If the ID is incorrectly sized, we return a 400
        if not is_object_id(study_object_id):
            log("bad study obj id: ", study_object_id)
            return abort(400)

        # If no Study with the given ID exists, we return a 404
        try:
            return Study.objects.get(object_id=study_object_id)
        except Study.DoesNotExist:
            log(f"study '{study_object_id}' does not exist (obj id)")
            return abort(404)

    elif study_pk is not None:
        # study pk must coerce to an int
        try:
            int(study_pk)
        except ValueError:
            log("bad study pk")
            return abort(400)

        # If no Study with the given ID exists, we return a 404
        try:
            return Study.objects.get(pk=study_pk)
        except Study.DoesNotExist:
            log("study '%s' does not exist (study pk)" % study_object_id)
            return abort(404)

    else:
        log("no study provided at all")
        return abort(400)
