import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict

from django.db.models import Q
from django.utils import timezone
from firebase_admin.messaging import (AndroidConfig, Message, Notification, QuotaExceededError,
    send as send_notification, SenderIdMismatchError, ThirdPartyAuthError, UnregisteredError)

from config.constants import API_TIME_FORMAT, PUSH_NOTIFICATION_SEND_QUEUE, ScheduleTypes
from config.settings import BLOCK_QUOTA_EXCEEDED_ERROR, PUSH_NOTIFICATION_ATTEMPT_COUNT
from config.study_constants import OBJECT_ID_ALLOWED_CHARS
from database.schedule_models import (ArchivedEvent, ScheduledEvent, ParticipantMessage, ParticipantMessageStatus,
                                      ParticipantMessageScheduleType)
from database.user_models import Participant, ParticipantFCMHistory, PushNotificationDisabledEvent
from libs.celery_control import push_send_celery_app, safe_apply_async
from libs.firebase_config import check_firebase_instance
from libs.push_notification_helpers import set_next_weekly
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
    asap_filter = Q(scheduled_type=ParticipantMessageScheduleType.asap)
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
        scheduled_time__lte=now, participant__fcm_tokens__isnull=False,
        # safety
        participant__deleted=False, survey__deleted=False,
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


def create_push_notification_tasks():
    # we reuse the high level strategy from data processing celery tasks, see that documentation.
    expiry = (datetime.utcnow() + timedelta(minutes=5)).replace(second=30, microsecond=0)
    now = timezone.now()
    surveys, schedules, patient_ids = get_surveys_and_schedules(now)
    print("Surveys:", surveys, sep="\n\t")
    print("Schedules:", schedules, sep="\n\t")
    print("Patient_ids:", patient_ids, sep="\n\t")

    with make_error_sentry(sentry_type=SentryTypes.data_processing):
        if not check_firebase_instance():
            print("Firebase is not configured, cannot queue notifications.")
            return

        # surveys and schedules are guaranteed to have the same keys, assembling the data structures
        # is a pain, so it is factored out. sorry, but not sorry. it was a mess.
        for fcm_token in surveys.keys():
            print(f"Queueing up push notification for user {patient_ids[fcm_token]} for {surveys[fcm_token]}")
            safe_apply_async(
                celery_send_push_notification,
                args=[fcm_token, surveys[fcm_token], schedules[fcm_token]],
                max_retries=0,
                expires=expiry,
                task_track_started=True,
                task_publish_retry=False,
                retry=False,
            )


@push_send_celery_app.task(queue=PUSH_NOTIFICATION_SEND_QUEUE)
def celery_send_push_notification(fcm_token: str, survey_obj_ids: List[str], schedule_pks: List[int]):
    ''' Celery task that sends push notifications. Note that this list of pks may contain duplicates.'''
    # Oh.  The reason we need the patient_id is so that we can debug anything ever. lol...
    patient_id = ParticipantFCMHistory.objects.filter(token=fcm_token) \
        .values_list("participant__patient_id", flat=True).get()

    with make_error_sentry(sentry_type=SentryTypes.data_processing):
        # use the earliest timed schedule as our reference for the sent_time parameter.  (why?)
        participant = Participant.objects.get(id=participant_id)
        schedules = participant.scheduled_events.filter(id__in=schedule_ids).prefetch_related('survey')
        reference_schedule = schedules.order_by("scheduled_time").first()
        survey_object_ids = schedules.values_list('survey__object_id', flat=True)

        data_kwargs = {
            'sent_time': reference_schedule.scheduled_time.strftime(API_TIME_FORMAT),
            'type': 'survey',
            'survey_ids': json.dumps(survey_object_ids),
        }
        display_message = f"You have {'a survey' if len(survey_object_ids) == 1 else 'surveys'} to take."

        # Always enqueue the next weekly surveys
        _enqueue_weekly_surveys(participant, schedules)

        # Send push notification
        try:
            send_push_notification(participant, reference_schedule, survey_obj_ids, fcm_token)
        # error types are documented at firebase.google.com/docs/reference/fcm/rest/v1/ErrorCode
        except UnregisteredError:
            print("\nUnregisteredError\n")
            # Is an internal 404 http response, it means the token that was used has been disabled.
            # Mark the fcm history as out of date, return early.
            ParticipantFCMHistory.objects.filter(token=fcm_token).update(unregistered=timezone.now())
            return

        except QuotaExceededError as e:
            # Limits are very high, this should be impossible. Reraise because this requires
            # sysadmin attention and probably new development to allow multiple firebase
            # credentials. Read comments in settings.py if toggling.
            if BLOCK_QUOTA_EXCEEDED_ERROR:
                failed_send_handler(participant, fcm_token, str(e), schedules)
                return
            else:
                raise

        except ThirdPartyAuthError as e:
            print("\nThirdPartyAuthError\n")
            failed_send_handler(participant, fcm_token, str(e), schedules)
            # This means the credentials used were wrong for the target app instance.  This can occur
            # both with bad server credentials, and with bad device credentials.
            # We have only seen this error statement, error name is generic so there may be others.
            if str(e) != "Auth error from APNS or Web Push Service":
                raise
            return

        except SenderIdMismatchError as e:
            # TODO: need text of error message certainty of multiple similar error cases.
            # (but behavior shouldn't be broken anymore, failed_send_handler executes.)
            print("\nSenderIdMismatchError:\n")
            print(e)
            failed_send_handler(participant, fcm_token, str(e), schedules)
            return

        except ValueError as e:
            print("\nValueError\n")
            # This case occurs ever? is tested for in check_firebase_instance... weird race condition?
            # Error should be transient, and like all other cases we enqueue the next weekly surveys regardless.
            if "The default Firebase app does not exist" in str(e):
                enqueue_weekly_surveys(participant, schedules)
                return
            else:
                raise

        except Exception as e:
            failed_send_handler(participant, fcm_token, str(e), schedules)
            return

        success_send_handler(participant, fcm_token, schedules)


def send_push_notification(
        participant: Participant, reference_schedule: ScheduledEvent, survey_obj_ids: List[str],
        fcm_token: str
):
    """ Contains the body of the code to send a notification  """
    # we include a nonce in case of notification deduplication.
    data_kwargs = {
        'nonce': ''.join(random.choice(OBJECT_ID_ALLOWED_CHARS) for _ in range(32)),
        'sent_time': reference_schedule.scheduled_time.strftime(API_TIME_FORMAT),
        'type': 'survey',
        'survey_ids': json.dumps(list(set(survey_obj_ids))),  # Dedupe.
    }

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


celery_send_push_notification.max_retries = 0  # requires the celerytask function object.
