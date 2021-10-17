import json
from datetime import datetime

from django.core.exceptions import ValidationError
from django.http.response import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from firebase_admin import messaging

from authentication.user_authentication import authenticate_user
from config import constants
from database.user_models import ParticipantFCMHistory
from libs.firebase_config import check_firebase_instance
from libs.internal_types import ParticipantRequest


################################################################################
########################### NOTIFICATION FUNCTIONS #############################
################################################################################

@require_POST
@authenticate_user
def set_fcm_token(request: ParticipantRequest):
    """ Sets a participants Firebase CLoud Messaging (FCM) instance token, called whenever a new
    token is generated. Expects a patient_id and and fcm_token in the request body. """
    participant = request.participant
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
    return HttpResponse(request, status_code=204)


@require_POST
@authenticate_user
def send_test_notification(request: ParticipantRequest):
    """ Sends a push notification to the participant, used for testing.
    Expects a patient_id in the request body. """
    print(check_firebase_instance())
    message = messaging.Message(
        data={
            'type': 'fake',
            'content': 'hello good sir',
        },
        token=request.participant.get_fcm_token().token,
    )
    response = messaging.send(message)
    print('Successfully sent notification message:', response)
    return HttpResponse(request, status_code=204)


@require_POST
@authenticate_user
def send_survey_notification(request: ParticipantRequest):
    """ Sends a push notification to the participant with survey data, used for testing
    Expects a patient_id in the request body """
    participant = request.participant
    survey_ids = list(
        participant.study.surveys.filter(deleted=False).exclude(survey_type="image_survey")
            .values_list("object_id", flat=True)[:4]
    )
    message = messaging.Message(
        data={
            'type': 'survey',
            'survey_ids': json.dumps(survey_ids),
            'sent_time': datetime.now().strftime(constants.API_TIME_FORMAT),
        },
        token=participant.get_fcm_token().token,
    )
    response = messaging.send(message)
    print('Successfully sent survey message:', response)
    return HttpResponse(request, status_code=204)
