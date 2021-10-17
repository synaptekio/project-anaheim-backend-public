from types import FunctionType

from django.http.request import HttpRequest
from django.http.response import HttpResponse


class AbortError(Exception): pass


def abort(http_error_code: int, error_message: str = ""):
    abort_error = AbortError()
    abort_error.error_code = http_error_code
    abort_error.error_message = error_message
    raise abort_error


class AbortMiddleware:
    """ A midleware that mimics the excellent Flask abort behavior.  Just call
    abort(http_error_code), and, by raising a special error, it stops and sends that response. """

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
