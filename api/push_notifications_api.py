import json
from datetime import datetime

from django.core.exceptions import ValidationError
from django.http.response import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from firebase_admin import messaging

from authentication.participant_authentication import authenticate_participant
from constants.datetime_constants import API_TIME_FORMAT
from database.user_models import ParticipantFCMHistory
from libs.firebase_config import check_firebase_instance
from libs.internal_types import ParticipantRequest


################################################################################
########################### NOTIFICATION FUNCTIONS #############################
################################################################################


# FIXME:this function incorrectly resets the push_notification_unreachable_count on an unsuccessful
#   empty push notification.  There is also a race condition at play, and while the current
#   mechanism works there is inappropriate content within the try statement that obscures the source
#   of the validation error, which actually occurs at the get-or-create line resulting in the bug.
#  Probably use a transaction?
@require_POST
@authenticate_participant
def set_fcm_token(request: ParticipantRequest):
    """ Sets a participants Firebase Cloud Messaging (FCM) instance token, called whenever a new
    token is generated. Expects a patient_id and and fcm_token in the request body. """
    participant = request.session_participant
    token = request.POST.get('fcm_token', "")
    now = timezone.now()
    
    # force to unregistered on success, force every not-unregistered as unregistered.
    
    # need to get_or_create rather than catching DoesNotExist to handle if two set_fcm_token
    # requests are made with the same token one after another and one request.
    try:
        p, _ = ParticipantFCMHistory.objects.get_or_create(token=token, participant=participant)
        p.unregistered = None
        p.save()  # retain as save, we want last_updated to mutate
        ParticipantFCMHistory.objects.exclude(token=token).filter(
            participant=participant, unregistered=None
        ).update(unregistered=now, last_updated=now)
    # ValidationError happens when the app sends a blank token
    except ValidationError:
        ParticipantFCMHistory.objects.filter(
            participant=participant, unregistered=None
        ).update(unregistered=now, last_updated=now)
    
    participant.push_notification_unreachable_count = 0
    participant.save()
    return HttpResponse(status=204)


@require_POST
@authenticate_participant
def developer_send_test_notification(request: ParticipantRequest):
    """ Sends a push notification to the participant, used ONLY for testing.
    Expects a patient_id in the request body. """
    print(check_firebase_instance())
    message = messaging.Message(
        data={
            'type': 'fake',
            'content': 'hello good sir',
        },
        token=request.session_participant.get_fcm_token().token,
    )
    response = messaging.send(message)
    print('Successfully sent notification message:', response)
    return HttpResponse(status=204)


@require_POST
@authenticate_participant
def developer_send_survey_notification(request: ParticipantRequest):
    """ Sends a push notification to the participant with survey data, used ONLY for testing
    Expects a patient_id in the request body """
    participant = request.session_participant
    survey_ids = list(
        participant.study.surveys.filter(deleted=False).exclude(survey_type="image_survey")
            .values_list("object_id", flat=True)[:4]
    )
    message = messaging.Message(
        data={
            'type': 'survey',
            'survey_ids': json.dumps(survey_ids),
            'sent_time': datetime.now().strftime(API_TIME_FORMAT),
        },
        token=participant.get_fcm_token().token,
    )
    response = messaging.send(message)
    print('Successfully sent survey message:', response)
    return HttpResponse(status=204)
