import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict

from django.db.models import Q
from django.utils import timezone
from firebase_admin.messaging import (AndroidConfig, Message, Notification,
                                      send as send_notification, ThirdPartyAuthError,
                                      UnregisteredError)

from config.constants import API_TIME_FORMAT, PUSH_NOTIFICATION_SEND_QUEUE, ScheduleTypes
from database.schedule_models import ArchivedEvent, ScheduledEvent, ParticipantMessage, \
    ParticipantMessageScheduleType, ParticipantMessageStatus
from database.user_models import Participant
from libs.celery_control import push_send_celery_app, safe_apply_async
from libs.push_notification_config import check_firebase_instance, set_next_weekly
from libs.sentry import make_error_sentry, SentryTypes


class MissingFCMToken(Exception):
    pass


def create_push_notification_tasks():
    # we reuse the high level strategy from data processing celery tasks, see that documentation.
    now = timezone.now()
    
    with make_error_sentry(sentry_type=SentryTypes.data_processing):
        if not check_firebase_instance():
            print("Firebase is not configured, cannot queue notifications.")
            return
        queue_message_tasks(now)
        queue_survey_tasks(now)


def queue_message_tasks(now):
    asap_filter = Q(schedule_type=ParticipantMessageScheduleType.asap)
    absolute_filter = (
        Q(schedule_type=ParticipantMessageScheduleType.absolute)
        & Q(scheduled_send_datetime__lte=now)
    )
    participant_message_ids = ParticipantMessage.objects.filter(
        asap_filter | absolute_filter,
        status=ParticipantMessageStatus.scheduled,
        ).values_list("id", flat=True)
    for participant_message_id in participant_message_ids:
        queue_celery_task(
            celery_send_message_push_notification,
            args=[participant_message_id],
        )


def queue_survey_tasks(now):
    # get: schedule time is in the past for participants that have fcm tokens.
    query = ScheduledEvent.objects.filter(
        # core
        participant__fcm_tokens__isnull=False,
        participant__fcm_tokens__unregistered=None,
        scheduled_time__lte=now,
        scheduled_time__gte=now - timedelta(weeks=1),
        # safety
        participant__deleted=False,
        survey__deleted=False,
    ).values_list(
        "id",
        "participant_id",
    )
    
    participant_to_scheduled_events = defaultdict(list)
    for schedule_id, participant_id in query:
        participant_to_scheduled_events[participant_id].append(schedule_id)
    
    for participant_id, schedule_ids in participant_to_scheduled_events.items():
        print(
            f"Queueing up survey push notification for participant {participant_id} for schedules "
            f"{schedule_ids}")
        queue_celery_task(
            celery_send_survey_push_notification,
            args=[participant_id, schedule_ids],
        )


@push_send_celery_app.task(queue=PUSH_NOTIFICATION_SEND_QUEUE)
def celery_send_message_push_notification(participant_message_id):
    with make_error_sentry(sentry_type=SentryTypes.data_processing):
        participant_message = ParticipantMessage.objects.get(id=participant_message_id)
        data_kwargs = {
            'message': participant_message.message,
            'type': 'message',
        }
        send_push_notification(
            participant_message.participant,
            data_kwargs,
            participant_message.message,
        )


@push_send_celery_app.task(queue=PUSH_NOTIFICATION_SEND_QUEUE)
def celery_send_survey_push_notification(participant_id: str, schedule_ids: List[int]):
    """
    Celery task that sends push notifications for surveys.
    
    Note: `schedule_pks` may contain duplicates.
    """
    with make_error_sentry(sentry_type=SentryTypes.data_processing):
        # use the earliest timed schedule as our reference for the sent_time parameter.  (why?)
        participant = Participant.objects.get(id=participant_id)
        schedules = participant.scheduled_events.filter(id__in=schedule_ids).prefetch_related('survey')
        reference_schedule = schedules.order_by("scheduled_time").first()
        survey_object_ids = schedules.values_list('survey__object_id', flat=True).distinct()
        
        data_kwargs = {
            'sent_time': reference_schedule.scheduled_time.strftime(API_TIME_FORMAT),
            'type': 'survey',
            'survey_ids': json.dumps(list(survey_object_ids)),
        }
        display_message = f"You have {'a survey' if len(survey_object_ids) == 1 else 'surveys'} to take."
        
        # Always enqueue the next weekly surveys
        _enqueue_weekly_surveys(participant, schedules)
        
        # Send push notification
        try:
            print(f"Sending push notification to {participant.patient_id} for {survey_object_ids}...")
            send_push_notification(participant, data_kwargs, display_message)
        except Exception as e:
            _create_archived_events(schedules, success=False, created_on=timezone.now(),
                                    status=str(e))
            raise e
        else:
            _create_archived_events(schedules, success=True, status=ArchivedEvent.SUCCESS)


def send_push_notification(participant: Participant, data: Dict, display_message: str):
    """
    Send push notification to participant. No exceptions are raised if it completed successfully.
    """
    if not check_firebase_instance():
        # Running `check_firebase_instance` is needed to load the configured Firebase instance,
        # otherwise you get a `ValueError: The default Firebase app does not exist.`
        print("Firebase is not configured, cannot queue notifications.")
        return
    participant_fcm_history = participant.fcm_tokens.filter(unregistered=None).last()
    if participant_fcm_history is None:
        raise MissingFCMToken(f"FCM token missing for participant id {participant.id}.")
    fcm_token = participant_fcm_history.token
    
    if "nonce" not in data:
        # Include a nonce for notification deduplication
        data["nonce"] = uuid.uuid4().hex
    
    if participant.os_type == Participant.ANDROID_API:
        message = Message(
            android=AndroidConfig(data=data, priority="high"),
            token=fcm_token,
        )
    else:
        message = Message(
            data=data,
            notification=Notification(title="Beiwe", body=display_message),
            token=fcm_token,
        )
    
    try:
        send_notification(message)
    # error types are documented at firebase.google.com/docs/reference/fcm/rest/v1/ErrorCode
    except UnregisteredError:
        # is an internal 404 http response, it means the token used was wrong.
        # mark the fcm history as out of date.
        participant_fcm_history.handle_failure()
    except ThirdPartyAuthError as e:
        # This means the credentials used were wrong for the target app instance.  This can occur
        # both with bad server credentials, and with bad device credentials.
        # We have only seen this error statement, error name is generic so there may be others.
        participant_fcm_history.handle_failure()
        if str(e) != "Auth error from APNS or Web Push Service":
            raise e
    else:
        participant_fcm_history.handle_success()
    

def _create_archived_events(
        schedules: List[ScheduledEvent], success: bool, status: str, created_on: datetime = None,
):
    """ Populates event history, successes will delete source ScheduledEvents. """
    for schedule in schedules:
        schedule.archive(self_delete=success, status=status, created_on=created_on)


def _enqueue_weekly_surveys(participant: Participant, schedules: List[ScheduledEvent]):
    # set_next_weekly is idempotent until the next weekly event passes.
    # its perfectly safe (commit time) to have many of the same weekly survey be scheduled at once.
    for schedule in schedules:
        if schedule.get_schedule_type() == ScheduleTypes.weekly:
            set_next_weekly(participant, schedule.survey)


def queue_celery_task(func, *args, **kwargs):
    default_kwargs = {
        "max_retries": 0,
        "expires": (datetime.utcnow() + timedelta(minutes=5)).replace(second=30, microsecond=0),
        "task_track_started": True,
        "task_publish_retry": False,
        "retry": False,
    }
    combined_kwargs = {**default_kwargs, **kwargs}
    
    return safe_apply_async(func, *args, **combined_kwargs)

celery_send_survey_push_notification.max_retries = 0  # requires the celerytask function object.
celery_send_message_push_notification.max_retries = 0  # requires the celerytask function object.
