from datetime import date, datetime

from django.db import transaction
from django.db.models import ProtectedError
from flask import abort, Blueprint, flash, redirect, render_template, request, url_for

from api.participant_administration import add_fields_and_interventions
from authentication.admin_authentication import (authenticate_researcher_study_access,
    get_researcher_allowed_studies, researcher_is_an_admin)
from config.constants import API_DATE_FORMAT
from database.schedule_models import Intervention, InterventionDate, ParticipantMessage, \
    ParticipantMessageStatus
from database.study_models import Study, StudyField
from database.user_models import Participant, ParticipantFieldValue
from libs.forms import ParticipantMessageForm
from libs.push_notification_config import (check_firebase_instance,
    repopulate_all_survey_scheduled_events)

study_api = Blueprint('study_api', __name__)


@study_api.context_processor
def inject_html_params():
    # these variables will be accessible to every template rendering attached to the blueprint
    return {
        "allowed_studies": get_researcher_allowed_studies(),
        "is_admin": researcher_is_an_admin(),
    }


@study_api.route('/view_study/<string:study_id>/edit_participant/<string:participant_id>', methods=['GET', 'POST'])
@authenticate_researcher_study_access
def edit_participant(study_id, participant_id):
    try:
        participant = Participant.objects.get(pk=participant_id)
        study = participant.study
    except Participant.DoesNotExist:
        return abort(404)

    # safety check, enforce fields and interventions to be present for both page load and edit.
    add_fields_and_interventions(participant, study)

    if request.method == 'GET':
        return render_edit_participant(participant, study)

    # update intervention dates for participant
    for intervention in study.interventions.all():
        input_date = request.values.get(f"intervention{intervention.id}", None)
        intervention_date = participant.intervention_dates.get(intervention=intervention)
        if input_date:
            intervention_date.date = datetime.strptime(input_date, API_DATE_FORMAT).date()
            intervention_date.save()

    # update custom fields dates for participant
    for field in study.fields.all():
        input_id = f"field{field.id}"
        field_value = participant.field_values.get(field=field)
        field_value.value = request.values.get(input_id, None)
        field_value.save()

    # always call through the repopulate everything call, even though we only need to handle
    # relative surveys, the function handles extra cases.
    repopulate_all_survey_scheduled_events(study, participant)

    flash('Successfully edited participant {}.'.format(participant.patient_id), 'success')
    return redirect('/view_study/{:d}/edit_participant/{:d}'.format(study.id, participant.id))


def render_edit_participant(participant: Participant, study: Study):
    # to reduce database queries we get all the data across 4 queries and then merge it together.
    # dicts of intervention id to intervention date string, and of field names to value
    # (this was quite slow previously)
    intervention_dates_map = {
        intervention_id:  # this is the intervention's id, not the intervention_date's id.
            intervention_date.strftime(API_DATE_FORMAT) if isinstance(intervention_date, date) else ""
        for intervention_id, intervention_date in
        participant.intervention_dates.values_list("intervention_id", "date")
    }
    participant_fields_map = {
        name: value for name, value in participant.field_values.values_list("field__field_name", "value")
    }

    # list of tuples of (intervention id, intervention name, intervention date)
    intervention_data = [
        (intervention.id, intervention.name, intervention_dates_map.get(intervention.id, ""))
        for intervention in study.interventions.order_by("name")
    ]
    # list of tuples of field name, value.
    field_data = [
        (field_id, field_name, participant_fields_map.get(field_name, ""))
        for field_id, field_name in study.fields.order_by("field_name").values_list('id', "field_name")
    ]

    participant_messages = (
        participant
            .participant_messages
            .prefetch_related("participant__study")
            .order_by("-created_on")
    )

    return render_template(
        'edit_participant.html',
        participant=participant,
        participant_messages=participant_messages,
        study=study,
        intervention_data=intervention_data,
        field_values=field_data,
        push_notifications_enabled_for_ios=check_firebase_instance(require_ios=True),
        push_notifications_enabled_for_android=check_firebase_instance(require_android=True)
    )


@study_api.route("/studies/<string:study_object_id>/participants/<string:participant_patient_id>/messages/schedule", methods=["GET", "POST"])
@authenticate_researcher_study_access
def schedule_message(study_object_id, participant_patient_id):
    participant = Participant.get_or_404(
        patient_id=participant_patient_id,
        study__object_id=study_object_id,
    )
    form = ParticipantMessageForm(request.values or None, participant=participant)
    if request.method == "GET":
        return render_schedule_message(form, participant)
    if not form.is_valid():
        return render_schedule_message(form, participant)
    form.save()
    flash(
        f"Your message to participant \"{participant.patient_id}\" was successfully scheduled.",
        "success",
    )
    return redirect(
        url_for(
            "study_api.edit_participant",
            participant_id=participant.id,
            study_id=participant.study_id,
        )
    )


def render_schedule_message(form, participant):
    return render_template(
        "participant_message.html",
        form=form,
        participant=participant,
    )


@study_api.route("/studies/<string:study_object_id>/messages/<string:participant_message_uuid>/cancel", methods=["POST"])
@authenticate_researcher_study_access
def cancel_message(study_object_id, participant_message_uuid):
    with transaction.atomic():
        # Lock to prevent message from being sent while we're cancelling (or cancelling while it's
        # being sent)
        try:
            participant_message = ParticipantMessage.objects.select_for_update().get(
                uuid=participant_message_uuid,
                participant__study__object_id=study_object_id,
            )
        except ParticipantMessage.DoesNotExist:
            flash("Sorry, could not find the message specified.", "yellow")
        else:
            if participant_message.status == ParticipantMessageStatus.sent:
                flash("Sorry, could not cancel because the message was already sent.", "danger")
            elif participant_message.status == ParticipantMessageStatus.error:
                flash(
                    "Sorry, could not cancel because the message status is \"error\" and it may have "
                    "already been sent.",
                    "danger",
                )
            elif participant_message.status in ParticipantMessageStatus.scheduled:
                if participant_message.status == ParticipantMessageStatus.scheduled:
                    participant_message.status = ParticipantMessageStatus.cancelled
                    participant_message.save(update_fields=["status"])
                flash("The message was successfully cancelled.", "success")
            elif participant_message.status in ParticipantMessageStatus.cancelled:
                flash("The message was successfully cancelled.", "success")
    return redirect(
        url_for(
            "study_api.edit_participant",
            participant_id=participant_message.participant.id,
            study_id=participant_message.participant.study_id,
        )
    )


@study_api.route('/interventions/<string:study_id>', methods=['GET', 'POST'])
@authenticate_researcher_study_access
def interventions_page(study_id=None):
    study = Study.objects.get(pk=study_id)

    if request.method == 'GET':
        return render_template(
            'study_interventions.html',
            study=study,
            interventions=study.interventions.all(),
        )

    # slow but safe
    new_intervention = request.values.get('new_intervention', None)
    if new_intervention:
        intervention, _ = Intervention.objects.get_or_create(study=study, name=new_intervention)
        for participant in study.participants.all():
            InterventionDate.objects.get_or_create(participant=participant, intervention=intervention)

    return redirect('/interventions/{:d}'.format(study.id))


@study_api.route('/delete_intervention/<string:study_id>', methods=['POST'])
@authenticate_researcher_study_access
def delete_intervention(study_id=None):
    """Deletes the specified Intervention. Expects intervention in the request body."""
    study = Study.objects.get(pk=study_id)
    intervention_id = request.values.get('intervention')
    if intervention_id:
        try:
            intervention = Intervention.objects.get(id=intervention_id)
        except Intervention.DoesNotExist:
            intervention = None
        try:
            if intervention:
                intervention.delete()
        except ProtectedError:
            flash("This Intervention can not be removed because it is already in use", 'danger')

    return redirect('/interventions/{:d}'.format(study.id))


@study_api.route('/edit_intervention/<string:study_id>', methods=['POST'])
@authenticate_researcher_study_access
def edit_intervention(study_id=None):
    """
    Edits the name of the intervention. Expects intervention_id and edit_intervention in the
    request body
    """
    study = Study.objects.get(pk=study_id)
    intervention_id = request.values.get('intervention_id', None)
    new_name = request.values.get('edit_intervention', None)
    if intervention_id:
        try:
            intervention = Intervention.objects.get(id=intervention_id)
        except Intervention.DoesNotExist:
            intervention = None
        if intervention and new_name:
            intervention.name = new_name
            intervention.save()

    return redirect('/interventions/{:d}'.format(study.id))


@study_api.route('/study_fields/<string:study_id>', methods=['GET', 'POST'])
@authenticate_researcher_study_access
def study_fields(study_id=None):
    study = Study.objects.get(pk=study_id)

    if request.method == 'GET':
        return render_template(
            'study_custom_fields.html',
            study=study,
            fields=study.fields.all(),
        )

    new_field = request.values.get('new_field', None)
    if new_field:
        study_field, _ = StudyField.objects.get_or_create(study=study, field_name=new_field)
        for participant in study.participants.all():
            ParticipantFieldValue.objects.create(participant=participant, field=study_field)

    return redirect('/study_fields/{:d}'.format(study.id))


@study_api.route('/delete_field/<string:study_id>', methods=['POST'])
@authenticate_researcher_study_access
def delete_field(study_id=None):
    """Deletes the specified Custom Field. Expects field in the request body."""
    study = Study.objects.get(pk=study_id)
    field = request.values.get('field', None)
    if field:
        try:
            study_field = StudyField.objects.get(study=study, id=field)
        except StudyField.DoesNotExist:
            study_field = None

        try:
            if study_field:
                study_field.delete()
        except ProtectedError:
            flash("This field can not be removed because it is already in use", 'danger')

    return redirect('/study_fields/{:d}'.format(study.id))


@study_api.route('/edit_custom_field/<string:study_id>', methods=['POST'])
@authenticate_researcher_study_access
def edit_custom_field(study_id=None):
    """Edits the name of a Custom field. Expects field_id anf edit_custom_field in request body"""
    field_id = request.values.get("field_id")
    new_field_name = request.values.get("edit_custom_field")
    if field_id:
        try:
            field = StudyField.objects.get(id=field_id)
        except StudyField.DoesNotExist:
            field = None
        if field and new_field_name:
            field.field_name = new_field_name
            field.save()

    # this apparent insanity is a hopefully unnecessary confirmation of the study id
    return redirect('/study_fields/{:d}'.format(Study.objects.get(pk=study_id).id))
