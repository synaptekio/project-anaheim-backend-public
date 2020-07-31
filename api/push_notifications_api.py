import json
from datetime import datetime

import pytz
from django.utils.timezone import make_aware
from firebase_admin import messaging
from flask import Blueprint, request

from config import constants
from authentication.user_authentication import authenticate_user, get_session_participant
from database.user_models import ParticipantFCMHistory

push_notifications_api = Blueprint('push_notifications_api', __name__)


################################################################################
########################### NOTIFICATION FUNCTIONS #############################
################################################################################


@push_notifications_api.route('/set_fcm_token', methods=['POST'])
@authenticate_user
def set_fcm_token():
    """
    Sets a participants Firebase CLoud Messaging (FCM) instance token, called whenever a new token
    is generated. Expects a patient_id and and fcm_token in the request body.
    """
    participant = get_session_participant()
    token = request.values.get('fcm_token', "")
    now = make_aware(datetime.utcnow(), timezone=pytz.utc)

    # These cases shouldn't happen.  All we want is to force the state that the app is serving us.
    try:
        # try, force to unregistered on success, force every not-unregistered as unregistered.
        p = ParticipantFCMHistory.objects.get(token=token)
        p.unregistered = None
        p.save()  # retain as save, we want last_updated to mutate
        ParticipantFCMHistory.objects.exclude(token=token).filter(unregistered=None).update(
            unregistered=now
        )
    except ParticipantFCMHistory.DoesNotExist:
        # It wasn't found, it is new, unregister the existing and create the new one.
        ParticipantFCMHistory.objects.filter(participant=participant, unregistered=None).update(
            unregistered=now
        )
        ParticipantFCMHistory.objects.create(token=token, participant=participant, unregistered=None)

    return '', 204


@push_notifications_api.route('/test_notification', methods=['POST'])
@authenticate_user
def send_notification():
    """
    Sends a push notification to the participant, used for testing
    Expects a patient_id in the request body.
    """
    message = messaging.Message(
        data={
            'type': 'fake',
            'content': 'hello good sir',
        },
        token=get_session_participant().get_fcm_token().token,
    )
    response = messaging.send(message)
    print('Successfully sent notification message:', response)
    return '', 204


@push_notifications_api.route('/send_survey_notification', methods=['Post'])
@authenticate_user
def send_survey_notification():
    """
    Sends a push notification to the participant with survey data, used for testing
    Expects a patient_id in the request body
    """
    participant = get_session_participant()
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
    return '', 204

