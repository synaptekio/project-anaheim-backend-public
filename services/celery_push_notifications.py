import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List

from django.utils import timezone
from firebase_admin.messaging import (AndroidConfig, Message, Notification, QuotaExceededError,
    send as send_notification, SenderIdMismatchError, ThirdPartyAuthError, UnregisteredError)

from config.constants import API_TIME_FORMAT, PUSH_NOTIFICATION_SEND_QUEUE, ScheduleTypes
from config.settings import BLOCK_QUOTA_EXCEEDED_ERROR, PUSH_NOTIFICATION_ATTEMPT_COUNT
from config.study_constants import OBJECT_ID_ALLOWED_CHARS
from database.schedule_models import ArchivedEvent, ScheduledEvent
from database.user_models import Participant, ParticipantFCMHistory, PushNotificationDisabledEvent
from libs.celery_control import push_send_celery_app, safe_apply_async
from libs.firebase_config import check_firebase_instance
from libs.push_notification_helpers import set_next_weekly
from libs.sentry import make_error_sentry, SentryTypes


def create_push_notification_tasks():
    # we reuse the high level strategy from data processing celery tasks, see that documentation.
    now = timezone.now()
    with make_error_sentry(sentry_type=SentryTypes.data_processing):
        if not check_firebase_instance():
            print("Firebase is not configured, cannot queue notifications.")
            return
        queue_survey_tasks(now)


def queue_survey_tasks(now):
    # get: schedule time is in the past for participants that have fcm tokens.
    query = ScheduledEvent.objects.filter(
        # core
        participant__fcm_tokens__isnull=False,
        participant__fcm_tokens__unregistered=None,  # TODO: should this be here?
        scheduled_time__lte=now,
        scheduled_time__gte=now - timedelta(weeks=7),  # If it's older than 1 week, don't send it
        # safety
        participant__deleted=False,
        survey__deleted=False,
    ).values_list(
        "participant_id",
        "id",
    )

    participants_and_scheduled_events = defaultdict(list)
    for participant_id, schedule_id in query:
        participants_and_scheduled_events[participant_id].append(schedule_id)

    for participant_id, schedule_ids in participants_and_scheduled_events.items():
        print(
            f"Queuing up survey push notification for participant {participant_id} for schedules "
            f"{schedule_ids}"
        )
        queue_celery_task(participant_id, schedule_ids)


def queue_celery_task(participant_id: int, schedule_pks: List[int]):
    safe_apply_async(
        celery_send_push_notification,
        args=[participant_id, schedule_pks],
        max_retries=0,
        expires=(datetime.utcnow() + timedelta(minutes=5)).replace(second=30, microsecond=0),
        task_track_started=True,
        task_publish_retry=False,
        retry=False,
    )


@push_send_celery_app.task(queue=PUSH_NOTIFICATION_SEND_QUEUE)
def celery_send_push_notification(participant_id: int, schedule_pks: List[int]):
    ''' Celery task that sends push notifications. Note that this list of pks may contain duplicates.'''
    with make_error_sentry(sentry_type=SentryTypes.data_processing):
        if not check_firebase_instance():
            print("Firebase credentials are not configured.")
            return

        # use the earliest timed schedule as our reference for the sent_time parameter.  (why?)
        participant = Participant.objects.get(pk=participant_id)
        patient_id = participant.patient_id  # patient_id helps with debugging
        fcm_token = participant.get_fcm_token().token
        schedules = participant.scheduled_events.filter(id__in=schedule_pks).prefetch_related('survey')
        reference_schedule = schedules.order_by("scheduled_time").first()
        survey_obj_ids = list(schedules.values_list('survey__object_id', flat=True).distinct())

        print(f"Sending push notification to {patient_id} for {survey_obj_ids}...")
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
            print(e)
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
        participant: Participant,
        reference_schedule: ScheduledEvent,
        survey_obj_ids: List[str],
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
            android=AndroidConfig(data=data_kwargs, priority='high'), token=fcm_token,
        )
    else:
        display_message = \
            "You have a survey to take." if len(survey_obj_ids) == 1 else "You have surveys to take."
        message = Message(
            data=data_kwargs,
            token=fcm_token,
            notification=Notification(title="Beiwe", body=display_message),
        )
    send_notification(message)


def success_send_handler(participant: Participant, fcm_token: str, schedules: List[ScheduledEvent]):
    # If the query was successful archive the schedules.  Clear the fcm unregistered flag
    # if it was set (this shouldn't happen. ever. but in case we hook in a ui element we need it.)
    print(f"Push notification send succeeded for {participant.patient_id}.")

    # this condition shouldn't occur.  Leave in, this case would be super stupid to diagnose.
    fcm_hist = ParticipantFCMHistory.objects.get(token=fcm_token)
    if fcm_hist.unregistered is not None:
        fcm_hist.unregistered = None
        fcm_hist.save()

    participant.push_notification_unreachable_count = 0
    participant.save()

    create_archived_events(schedules, success=True, status=ArchivedEvent.SUCCESS)
    enqueue_weekly_surveys(participant, schedules)


def failed_send_handler(
        participant: Participant, fcm_token: str, error_message: str, schedules: List[ScheduledEvent]
):
    """ Contains body of code for unregistering a participants push notification behavior.
        Participants get reenabled when they next touch the app checkin endpoint. """

    if participant.push_notification_unreachable_count >= PUSH_NOTIFICATION_ATTEMPT_COUNT:
        now = timezone.now()
        fcm_hist = ParticipantFCMHistory.objects.get(token=fcm_token)
        fcm_hist.unregistered = now
        fcm_hist.save()

        PushNotificationDisabledEvent(
            participant=participant, timestamp=now, count=participant.push_notification_unreachable_count
        ).save()

        # disable the credential
        participant.push_notification_unreachable_count = 0
        participant.save()

        print(f"Participant {participant.patient_id} has had push notifications "
              f"disabled after {PUSH_NOTIFICATION_ATTEMPT_COUNT} failed attempts to send.")

    else:
        now = None
        participant.push_notification_unreachable_count += 1
        participant.save()
        print(f"Participant {participant.patient_id} has had push notifications failures "
              f"incremented to {participant.push_notification_unreachable_count}.")

    create_archived_events(schedules, success=False, created_on=now, status=error_message)
    enqueue_weekly_surveys(participant, schedules)


def create_archived_events(
        schedules: List[ScheduledEvent], success: bool, status: str, created_on: datetime = None,
    ):
    """ Populates event history, successes will delete source ScheduledEvents. """
    for schedule in schedules:
        schedule.archive(self_delete=success, status=status, created_on=created_on)


def enqueue_weekly_surveys(participant: Participant, schedules: List[ScheduledEvent]):
    # set_next_weekly is idempotent until the next weekly event passes.
    # its perfectly safe (commit time) to have many of the same weekly survey be scheduled at once.
    for schedule in schedules:
        if schedule.get_schedule_type() == ScheduleTypes.weekly:
            set_next_weekly(participant, schedule.survey)


celery_send_push_notification.max_retries = 0  # requires the celerytask function object.
