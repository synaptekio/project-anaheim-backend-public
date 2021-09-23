from types import FunctionType
from django.http.response import HttpResponse
from constants.session_constants import EXPIRY_NAME, SESSION_UUID
from django.http.request import HttpRequest
from django.shortcuts import redirect

from database.study_models import Study
from database.user_models import Researcher


EXCLUDED_PATHS = ["/", "/validate_login"]


def logout_researcher(request: HttpRequest):
    """ clear session information for a researcher """
    if SESSION_UUID in request.session:
        del request.session[SESSION_UUID]
    if EXPIRY_NAME in request.session:
        del request.session[EXPIRY_NAME]


class AdminAuthenticationMiddleware:
    def __init__(self, get_response: FunctionType):
        # (runs at django start))
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        self.request = request  # cache for researcher_is_an_admin etc.

        # this is part of the cached context processor stuff
        if not hasattr(request, "_cached_contexts"):
            request._cached_contexts = {}

        # the login page and validate password endpoint are special
        if request.path in EXCLUDED_PATHS:
            return self.get_response(request)

        username = request.session.get("researcher_username", None)
        if username is None and request.path not in EXCLUDED_PATHS:
            print("researcher username is not present\n\n\n")
            return redirect("/", status=400)

        try:
            # Cache the Researcher and the session_researcher
            request.session_researcher = Researcher.objects.get(username=username)
        except Researcher.DoesNotExist:
            return redirect("/", status=400)

        request.researcher_is_an_admin = self.researcher_is_an_admin

        return self.get_response(request)


    def researcher_is_an_admin(self):
        return self.request.session_researcher.site_admin \
            or self.request.session_researcher.is_study_admin()


#
# Context Processors
#

class CachedContext:
    def __init__(self, an_function: callable):
        print("instantiating cached context processor '{an_function.__name__}'")
        self.cached_context_procssor_function = an_function

    def __call__(self, request: HttpRequest):
        # django context processors are only allowed to take a request object as their argument
        try:
            return request._cached_contexts[self.cached_context_procssor_function.__name__]
        except KeyError:
            pass

        request._cached_contexts[self.cached_context_procssor_function.__name__] = \
            self.cached_context_procssor_function(request)
        return request._cached_contexts[self.cached_context_procssor_function.__name__]


# @CachedContext
def researcher_contexts(request: HttpRequest):
    # def get_researcher_allowed_studies() -> List[Dict]:
    """
    Return a list of studies which the currently logged-in researcher is authorized to view and edit.
    """
    if request.path in EXCLUDED_PATHS:
        return {}

    # this is definitely not needed everywhere, it was sourced from get_researcher_allowed_studies
    allowed_studies_kwargs = {} if request.session_researcher.site_admin else \
        {"study_relations__researcher": request.session_researcher}

    return {
        "allowed_studies": [
            study_info_dict for study_info_dict in Study.get_all_studies_by_name()
            .filter(**allowed_studies_kwargs).values("name", "object_id", "id", "is_test")
        ],
        "site_admin": request.session_researcher.site_admin,
        "session_researcher": request.session_researcher,
    }
