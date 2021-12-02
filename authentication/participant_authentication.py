import functools

from django.http.request import HttpRequest
from django.utils.datastructures import MultiValueDict

from database.user_models import Participant
from libs.internal_types import ParticipantRequest
from middleware.abort_middleware import abort


DEBUG_PARTICIPANT_AUTHENTICATION = True


def log(*args, **kwargs):
    if DEBUG_PARTICIPANT_AUTHENTICATION:
        print(*args, **kwargs)


def validate_post(request: HttpRequest, require_password: bool, validate_device_id: bool) -> bool:
    """Check if user exists, check if the provided passwords match, and if the device id matches."""
    # even if the password won't be checked we want the key to be present.
    rp = request.POST
    if "patient_id" not in rp or "password" not in rp or "device_id" not in rp:
        log("missing parameters entirely.")
        log("patient_id:", "patient_id" in rp)
        log("password:", "password" in rp)
        log("device_id:", "device_id" in rp)
        return False
    
    # FIXME: Device Testing. need to check the app expectations on response codes
    #  this used to throw a 400 if the there was no patient_id field in the post request,
    #  and 404 when there was no such user, when it was get_session_participant.
    # This isn't True? the old code included the test for presence of keys, and returned False,
    #  triggering the os-specific failure codes.
    try:
        session_participant: Participant = Participant.objects.get(patient_id=request.POST['patient_id'])
    except Participant.DoesNotExist:
        log("invalid patient_id")
        return False
    
    if require_password:
        if not session_participant.validate_password(request.POST['password']):
            log("incorrect password")
            return False
    
    if validate_device_id:
        if not session_participant.device_id == request.POST['device_id']:
            log("incorrect device_id")
            return False
    
    # attach session participant to request object, defining the ParticipantRequest class.
    request.session_participant = session_participant
    return True

####################################################################################################


def minimal_validation(some_function) -> callable:
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        request: ParticipantRequest = args[0]
        assert isinstance(request, HttpRequest), \
            f"first parameter of {some_function.__name__} must be an HttpRequest, was {type(request)}."
        correct_for_basic_auth(request)
        
        if validate_post(request, require_password=False, validate_device_id=False):
            return some_function(*args, **kwargs)
        
        # ios requires different http codes
        is_ios = kwargs.get("OS_API", None) == Participant.IOS_API
        return abort(401 if is_ios else 403)
    return authenticate_and_call


def authenticate_participant(some_function) -> callable:
    """Decorator for functions (pages) that require a user to provide identification. Returns 403
    (forbidden) or 401 (depending on beiwei-api-version) if the identifying info (usernames,
    passwords device IDs are invalid.

    In any funcion wrapped with this decorator provide a parameter named "patient_id" (with the
    user's id), a parameter named "password" with an SHA256 hashed instance of the user's
    password, a parameter named "device_id" with a unique identifier derived from that device. """
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        request: ParticipantRequest = args[0]
        assert isinstance(request, HttpRequest), \
            f"first parameter of {some_function.__name__} must be an HttpRequest, was {type(request)}."
        correct_for_basic_auth(request)
        
        if validate_post(request, require_password=True, validate_device_id=True):
            return some_function(*args, **kwargs)
        is_ios = kwargs.get("OS_API", None) == Participant.IOS_API
        return abort(401 if is_ios else 403)
    return authenticate_and_call


def authenticate_participant_registration(some_function) -> callable:
    """ Decorator for functions (pages) that require a user to provide identification. Returns
    403 (forbidden) or 401 (depending on beiwe-api-version) if the identifying info (username,
    password, device ID) are invalid.

    In any function wrapped with this decorator provide a parameter named "patient_id" (with the
    user's id) and a parameter named "password" with an SHA256 hashed instance of the user's
    password. """
    @functools.wraps(some_function)
    def authenticate_and_call(*args, **kwargs):
        request: ParticipantRequest = args[0]
        assert isinstance(request, HttpRequest), \
            f"first parameter of {some_function.__name__} must be an HttpRequest, was {type(request)}."
        correct_for_basic_auth(request)
        
        if validate_post(request, require_password=True, validate_device_id=False):
            return some_function(*args, **kwargs)
        
        is_ios = kwargs.get("OS_API", None) == Participant.IOS_API
        return abort(401 if is_ios else 403)
    return authenticate_and_call


# TODO: basic auth is not a good thing, it is only used because it was easy and we enforce
#  https on all connections.  Fundamentally we need a rewrite of the participant auth structure to
#  disconnect it from the user password.  This is a major undertaking.
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
    
    # from pprint import pprint
    # pprint(vars(request))
    # print()
    # pprint(request.headers)
    
    if "Authorization" in request.headers:
        raise Exception("NOT IMPLEMENTED 1")
    elif "authorization" in request.headers:
        raise Exception("NOT IMPLEMENTED 2")
    else:
        return
    
    auth = request.authorization
    # FIXME: Device Testing. this is broken - django port
    if not auth:
        return
    
    username_parts = auth.username.split('@')
    if len(username_parts) == 2:
        replace_dict = MultiValueDict(request.POST.to_dict())
        if "patient_id" not in replace_dict:
            replace_dict['patient_id'] = username_parts[0]
        if "device_id" not in replace_dict:
            replace_dict['device_id'] = username_parts[1]
        if "password" not in replace_dict:
            replace_dict['password'] = auth.password
        request.POST = replace_dict
