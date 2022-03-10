import functools

from django.http.request import HttpRequest
from django.urls.base import reverse

from constants.participant_constants import ANDROID_API, IOS_API
from libs.internal_types import ParticipantRequest


def easy_url(url: str, *args, **kwargs) -> str:
    """ The django reverse function, but args and kwargs are passed thnough to the args and kwargs
    variables.  (Imported in the jinja templates.) """
    return reverse(url, args=args, kwargs=kwargs)


def checkbox_to_boolean(list_checkbox_params, dict_all_params):
    """ Takes a list of strings that are to be processed as checkboxes on a post parameter,
    (checkboxes supply some arbitrary value in a post if they are checked, and no value at all if
    they are not checked.), and a dict of parameters and their values to update.
    Returns a dictionary with modified/added values containing appropriate booleans. """
    for param in list_checkbox_params:
        if param not in dict_all_params:
            dict_all_params[param] = False
        else:
            dict_all_params[param] = True
    return dict_all_params


def string_to_int(list_int_params, dict_all_params):
    for key in list_int_params:
        dict_all_params[key] = int(dict_all_params[key])
    return dict_all_params


def determine_os_api(some_function):
    """ Add this as a decorator to a url function, under (after) the wsgi route
    decorator.  It detects if the url ends in /ios.
    This decorator provides to the function with the new variable "OS_API", which can
    then be compared against the IOS_API and ANDROID_API variables in constants.

    To handle any issues that arise from an undeclared keyword argument, throw
    'OS_API=""' into your url function declaration. """
    @functools.wraps(some_function)
    def provide_os_determination_and_call(*args, **kwargs):
        request: ParticipantRequest = args[0]
        assert isinstance(request, HttpRequest), \
            f"first parameter of {some_function.__name__} must be an HttpRequest, was {type(request)}."
        
        # naive, could be improved, but sufficient
        url_end = request.path[-4:].lower()
        if "ios" in url_end:
            kwargs["OS_API"] = IOS_API
        else:
            kwargs["OS_API"] = ANDROID_API
        return some_function(*args, **kwargs)
    
    return provide_os_determination_and_call
