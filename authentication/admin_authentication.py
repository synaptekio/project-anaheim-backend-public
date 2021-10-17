import functools
from datetime import datetime, timedelta
from typing import Dict, List

from django.contrib import messages
from django.http.request import HttpRequest
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.timezone import is_naive

from config.constants import ALL_RESEARCHER_TYPES, ResearcherRole
from constants.session_constants import EXPIRY_NAME, SESSION_NAME, SESSION_UUID
from database.study_models import Study
from database.user_models import Researcher, StudyRelation
from libs.internal_types import ResearcherRequest
from libs.security import generate_easy_alphanumeric_string
from middleware.abort_middleware import abort


DEBUG_ADMIN_NAUTHENTICATION = False


def log(*args, **kwargs):
    if DEBUG_ADMIN_NAUTHENTICATION:
        print(*args, **kwargs)


# Top level authentication wrappers
def authenticate_researcher_login(some_function):
    """ Decorator for functions (pages) that require a login, redirect to login page on failure. """
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        request: ResearcherRequest = args[0]
        assert isinstance(request, HttpRequest), \
            f"first parameter of {some_function.__name__} must be an HttpRequest, was {type(request)}."

        if check_is_logged_in(request):
            populate_session_researcher(request)
            return some_function(*args, **kwargs)
        else:
            return redirect("/")

    return authenticate_and_call


################################################################################
############################ Website Functions #################################
################################################################################


def logout_researcher(request: HttpRequest):
    """ clear session information for a researcher """
    if SESSION_UUID in request.session:
        del request.session[SESSION_UUID]
    if EXPIRY_NAME in request.session:
        del request.session[EXPIRY_NAME]


def log_in_researcher(request: ResearcherRequest, username: str):
    """ populate session for a researcher """
    request.session[SESSION_UUID] = generate_easy_alphanumeric_string()
    request.session[EXPIRY_NAME] = datetime.now() + timedelta(hours=6)
    request.session[SESSION_NAME] = username


def check_is_logged_in(request: ResearcherRequest):
    """ automatically logs out the researcher if their session is timed out. """
    if EXPIRY_NAME in request.session:
        if assert_session_unexpired(request):
            return SESSION_UUID in request.session
        else:
            log("session had expired")
    else:
        log("expiry (cookie value) was missing")
    logout_researcher(request)
    return False


def assert_session_unexpired(request: ResearcherRequest):
    # probably a development environment issue, sometimes the datetime is naive.
    expiry_datetime = request.session[EXPIRY_NAME]
    if is_naive(expiry_datetime):
        return expiry_datetime > datetime.now()
    else:
        return expiry_datetime > timezone.now()


def populate_session_researcher(request: ResearcherRequest):
    # this function defines the ResearcherRequest, which is purely for IDE assistence
    username = request.session.get("researcher_username", None)
    if username is None:
        log("researcher username was not present in session")
        return abort(400)
    try:
        # Cache the Researcher into request.session_researcher.
        request.session_researcher = Researcher.objects.get(username=username)
    except Researcher.DoesNotExist:
        log("could not identify researcher in session")
        return abort(400)


def assert_admin(request: ResearcherRequest, study_id: int):
    """ This function will throw a 403 forbidden error and stop execution.  Note that the abort
        directly raises the 403 error, if we don't hit that return True. """
    session_researcher = request.session_researcher
    if not session_researcher.site_admin and not session_researcher.check_study_admin(study_id):
        messages.warning("This user does not have admin privilages on this study.")
        log("no admin privilages")
        return abort(403)
    # allow usage in if statements
    return True


def assert_researcher_under_admin(request: ResearcherRequest, researcher: Researcher, study=None):
    """ Asserts that the researcher provided is allowed to be edited by the session user.
        If study is provided then the admin test is strictly for that study, otherwise it checks
        for admin status anywhere. """
    session_researcher = request.session_researcher
    if session_researcher.site_admin:
        return

    if researcher.site_admin:
        messages.warning("This user is a site administrator, action rejected.")
        log("target researcher is a site admin")
        return abort(403)

    kwargs = dict(relationship=ResearcherRole.study_admin)
    if study is not None:
        kwargs['study'] = study

    if researcher.study_relations.filter(**kwargs).exists():
        messages.warning("This user is a study administrator, action rejected.")
        log("target researcher is a study administrator")
        return abort(403)

    session_studies = set(session_researcher.get_admin_study_relations().values_list("study_id", flat=True))
    researcher_studies = set(researcher.get_researcher_study_relations().values_list("study_id", flat=True))

    if not session_studies.intersection(researcher_studies):
        messages.warning("You are not an administrator for that researcher, action rejected.")
        log("session researcher is not an administrator of target researcher")
        return abort(403)


################################################################################
########################## Study Editing Privileges ############################
################################################################################

class ArgumentMissingException(Exception): pass


def authenticate_researcher_study_access(some_function):
    """ This authentication decorator checks whether the user has permission to to access the
    study/survey they are accessing.
    This decorator requires the specific keywords "survey_id" or "study_id" be provided as
    keywords to the function, and will error if one is not.
    The pattern is for a url with <string:survey/study_id> to pass in this value.
    A site admin is always able to access a study or survey. """
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        # Check for regular login requirement
        request: ResearcherRequest = args[0]
        assert isinstance(request, HttpRequest), \
            f"first parameter of {some_function.__name__} must be an HttpRequest, was {type(request)}."

        if not check_is_logged_in(request):
            log("researcher is not logged in")
            return redirect("/")

        populate_session_researcher(request)

        # first get from kwargs, then from the POST request, either one is fine
        survey_id = kwargs.get('survey_id', request.POST.get('survey_id', None))
        study_id = kwargs.get('study_id', request.POST.get('study_id', None))

        # Check proper usage
        if survey_id is None and study_id is None:
            log("no survey or study provided")
            return abort(400)

        if survey_id is not None and study_id is None:
            log("survey was provided but no study was provided")
            return abort(400)

        # We want the survey_id check to execute first if both args are supplied, surveys are
        # attached to studies but do not supply the study id.
        if survey_id:
            # get studies for a survey, fail with 404 if study does not exist
            studies = Study.objects.filter(surveys=survey_id)
            if not studies.exists():
                return abort(404)

            # Check that researcher is either a researcher on the study or a site admin,
            # and populate study_id variable
            study_id = studies.values_list('pk', flat=True).get()

        # assert that such a study exists
        if not Study.objects.filter(pk=study_id, deleted=False).exists():
            return abort(404)

        # always allow site admins, allow all types of study relations (there is/was only one).
        if not request.session_researcher.site_admin:
            relation = StudyRelation.objects.filter(study_id=study_id, researcher=request.session_researcher)
            if relation.values_list("relationship").get() not in ALL_RESEARCHER_TYPES:
                log("invalid study relationship for researcher")
                return abort(403)

        return some_function(*args, **kwargs)

    return authenticate_and_call


def get_researcher_allowed_studies_as_query_set(request: ResearcherRequest):
    if request.session_researcher.site_admin:
        return Study.get_all_studies_by_name()

    return Study.get_all_studies_by_name().filter(
        id__in=request.session_researcher.study_relations.values_list("study", flat=True)
    )


def get_researcher_allowed_studies(request: ResearcherRequest) -> List[Dict]:
    """
    Return a list of studies which the currently logged-in researcher is authorized to view and edit.
    """
    kwargs = {}
    if not request.session_researcher.site_admin:
        kwargs = dict(study_relations__researcher=request.session_researcher)

    return [
        study_info_dict for study_info_dict in
        Study.get_all_studies_by_name().filter(**kwargs).values("name", "object_id", "id", "is_test")
    ]


################################################################################
############################# Site Administrator ###############################
################################################################################

def authenticate_admin(some_function):
#    """ Authenticate site admin, checks whether a user is a system admin before allowing access
#    to pages marked with this decorator.  If a study_id variable is supplied as a keyword
#    argument, the decorator will automatically grab the ObjectId in place of the string provided
#    in a route.
#
#    NOTE: if you are using this function along with the authenticate_researcher_study_access decorator
#    you must place this decorator below it, otherwise behavior is undefined and probably causes a
#    500 error inside the authenticate_researcher_study_access decorator. """
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        request: ResearcherRequest = args[0]

        # this is debugging code for the django frontend server port
        if not isinstance(request, HttpRequest):
            raise TypeError(f"request was a {type(request)}, expected {HttpRequest}")

        # Check for regular login requirement
        if not check_is_logged_in(request):
            return redirect("/")

        session_researcher = request.session_researcher
        # if researcher is not a site admin assert that they are a study admin somewhere, then test
        # the special case of a the study id, if it is present.
        if not session_researcher.site_admin:
            if not session_researcher.study_relations.filter(relationship=ResearcherRole.study_admin).exists():
                return abort(403)

            # fail if there is a study_id and it either does not exist or the researcher is not an
            # admin on that study.
            if 'study_id' in kwargs:
                if not StudyRelation.objects.filter(
                    researcher=session_researcher,
                    study_id=kwargs['study_id'],
                    relationship=ResearcherRole.study_admin,
                ).exists():
                    return abort(403)

        return some_function(*args, **kwargs)

    return authenticate_and_call


def forest_enabled(func):
    """ Decorator for validating that Forest is enabled for this study. """
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            study = Study.objects.get(id=kwargs.get("study_id", None))
        except Study.DoesNotExist:
            return abort(404)

        if not study.forest_enabled:
            return abort(404)

        return func(*args, **kwargs)

    return wrapped
