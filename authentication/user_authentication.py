import functools
from django.http.request import HttpRequest

from werkzeug.datastructures import MultiDict

from database.user_models import Participant
from libs.internal_types import ParticipantRequest
from middleware.abort_middleware import abort


####################################################################################################


def minimal_validation(some_function) -> callable:
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        request = args[0]
        assert isinstance(request, HttpRequest), \
            f"first parameter of {some_function.__name__} must be an HttpRequest, was {type(request)}."

        # handle ios requests, they require basic auth
        is_ios = kwargs.get("OS_API", None) == Participant.IOS_API
        correct_for_basic_auth(request)
        if validate_post_ignore_password(request, is_ios):
            return some_function(*args, **kwargs)

        # ios requires different http codes
        return abort(401 if is_ios else 403)
    return authenticate_and_call


def validate_post_ignore_password(request: ParticipantRequest, is_ios: bool) -> bool:
    """Check if user exists, that a password was provided but IGNORES its validation, and if the
    device id matches.
    IOS apparently has problems retaining the device id, so we want to bypass it when it is an ios user
    """
    rp = request.POST
    if "patient_id" not in rp or "password" not in rp or "device_id" not in rp:
        return False

    participant_query = Participant.objects.filter(patient_id=request.POST['patient_id'])
    if not participant_query.exists():
        return False

    try:
        request.participant = participant_query.get()
    except Participant.DoesNotExist:
        # FIXME: need to check the app expectations on response codes
        #  this used to throw a 400 if the there was no patient_id field in the post request,
        #  and 404 when there was no such user, when it was get_session_participant.
        return False  # invalid participant id

    return True

####################################################################################################


def authenticate_user(some_function) -> callable:
    """Decorator for functions (pages) that require a user to provide identification. Returns 403
    (forbidden) or 401 (depending on beiwei-api-version) if the identifying info (usernames,
    passwords device IDs are invalid.

   In any funcion wrapped with this decorator provide a parameter named "patient_id" (with the
   user's id), a parameter named "password" with an SHA256 hashed instance of the user's
   password, a parameter named "device_id" with a unique identifier derived from that device. """
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        request = args[0]
        assert isinstance(request, HttpRequest), \
            f"first parameter of {some_function.__name__} must be an HttpRequest, was {type(request)}."

        correct_for_basic_auth()
        if validate_post():
            return some_function(*args, **kwargs)
        return abort(401 if (kwargs.get("OS_API", None) == Participant.IOS_API) else 403)
    return authenticate_and_call


def validate_post(request: ParticipantRequest) -> bool:
    """Check if user exists, check if the provided passwords match, and if the device id matches."""
    rp = request.POST
    if "patient_id" not in rp or "password" not in rp or "device_id" not in rp:
        return False

    participant_query = Participant.objects.filter(patient_id=request.POST['patient_id'])
    if not participant_query.exists():
        return False

    if not request.participant.validate_password(request.POST['password']):
        return False

    if not request.participant.device_id == request.POST['device_id']:
        return False

    request.participant = participant_query.get()
    # FIXME: need to check the app expectations on response codes
    #  this used to throw a 400 if the there was no patient_id field in the post request,
    #  and 404 when there was no such user, when it was get_session_participant.
    return True


def authenticate_user_registration(some_function) -> callable:
    """ Decorator for functions (pages) that require a user to provide identification. Returns
    403 (forbidden) or 401 (depending on beiwe-api-version) if the identifying info (username,
    password, device ID) are invalid.

   In any function wrapped with this decorator provide a parameter named "patient_id" (with the
   user's id) and a parameter named "password" with an SHA256 hashed instance of the user's
   password. """
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        request = args[0]
        assert isinstance(request, HttpRequest), \
            f"first parameter of {some_function.__name__} must be an HttpRequest, was {type(request)}."

        correct_for_basic_auth()
        if validate_registration():
            return some_function(*args, **kwargs)
        return abort(401 if (kwargs.get("OS_API", None) == Participant.IOS_API) else 403)
    return authenticate_and_call


def validate_registration(request: ParticipantRequest) -> bool:
    """Check if user exists, check if the provided passwords match"""
    rv = request.POST
    if "patient_id" not in rv or "password" not in rv or "device_id" not in rv:
        return False

    participant_query = Participant.objects.filter(patient_id=request.POST['patient_id'])
    if not participant_query.exists():
        return False

    request.participant = participant_query.get()
    if not request.participant.validate_password(request.POST['password']):
        return False

    return True


# TODO: basic auth is not a good thing, it is only used because it was easy and we enforce
#  https on all connections.  Review.
def correct_for_basic_auth(request: ParticipantRequest):
    """
    Basic auth is used in IOS.

    If basic authentication exists and is in the correct format, move the patient_id,
    device_id, and password into request.values for processing by the existing user
    authentication functions.

    Flask automatically parses a Basic authentication header into request.authorization

    If this is set, and the username portion is in the form xxxxxx@yyyyyyy, then assume this is
    patient_id@device_id.

    Parse out the patient_id, device_id from username, and then store patient_id, device_id and
    password as if they were passed as parameters (into request.values)

    Note:  Because request.values is immutable in Flask, copy it and replace with a mutable dict
    first.

    Check if user exists, check if the provided passwords match.
    """
    # FIXME: this is broken - django port
    auth = request.authorization
    if not auth:
        return

    username_parts = auth.username.split('@')
    if len(username_parts) == 2:
        replace_dict = MultiDict(request.POST.to_dict())
        if "patient_id" not in replace_dict:
            replace_dict['patient_id'] = username_parts[0]
        if "device_id" not in replace_dict:
            replace_dict['device_id'] = username_parts[1]
        if "password" not in replace_dict:
            replace_dict['password'] = auth.password
        request.POST = replace_dict
