from datetime import date
from types import FunctionType

from django.http.request import HttpRequest
from django.http.response import HttpResponse

from database.study_models import Study
from libs.internal_types import BeiweHttpRequest


class AbortError(Exception): pass


def abort(http_error_code: int, error_message: str = ""):
    abort_error = AbortError()
    abort_error.error_code = http_error_code
    abort_error.error_message = error_message
    raise abort_error


class EasyAbortMiddleware:
    """ A midleware that mimics the excellent Flask abort behavior.  Just call abort(http_error_code),
    and, by raising a special error, it stops and sends that response. """

    def __init__(self, get_response: FunctionType):
        # (runs at django start))
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        try:
            return self.get_response(request)
        except AbortError as abort_error:
            return HttpResponse(
                request,
                content=abort_error.error_message,
                status=abort_error.error_code,
            )

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
def researcher_contexts(request: BeiweHttpRequest):
    """
    Return a list of studies which the currently logged-in researcher is authorized to view and edit.
    """
    current_year = date.today().year

    if hasattr(request, "session_researcher"):
        # this is definitely not needed everywhere, it was sourced from get_researcher_allowed_studies
        allowed_studies_kwargs = {} if request.session_researcher.site_admin else \
            {"study_relations__researcher": request.session_researcher}

        return {
            "allowed_studies": [
                study_info_dict for study_info_dict in Study.get_all_studies_by_name()
                .filter(**allowed_studies_kwargs).values("name", "object_id", "id", "is_test")
            ],
            "is_admin": request.session_researcher.is_an_admin(),
            "site_admin": request.session_researcher.site_admin,
            "session_researcher": request.session_researcher,
            "current_year": current_year,
        }
    else:
        return {"current_year": current_year}
