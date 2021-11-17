from csv import writer
from re import sub

from django.contrib import messages
from django.http.response import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from authentication.admin_authentication import authenticate_researcher_study_access
from database.schedule_models import InterventionDate
from database.study_models import Study
from database.user_models import Participant, ParticipantFieldValue
from libs.internal_types import ResearcherRequest
from libs.push_notification_helpers import repopulate_all_survey_scheduled_events
from libs.s3 import create_client_key_pair, s3_upload
from libs.streaming_bytes_io import StreamingStringsIO


@require_POST
@authenticate_researcher_study_access
def reset_participant_password(request: ResearcherRequest):
    """ Takes a patient ID and resets its password. Returns the new random password."""
    # FIXME: validate researcher on study
    patient_id = request.POST.get('patient_id', None)
    study_id = request.POST.get('study_id', None)
    
    try:
        participant = Participant.objects.get(patient_id=patient_id)
    except Participant.DoesNotExist:
        # Fixme: bleach this
        messages.error(request, f'The participant "{patient_id}" does not exist')
        return redirect(f'/view_study/{study_id}/')
    
    if participant.study.id != int(study_id):
        messages.error(
            request,
            f'Participant {patient_id} is not in study {Study.objects.get(id=study_id).name}'
        )
        # FIXME: this  was a referrer redirect
        return redirect(f'/view_study/{study_id}/')
    
    new_password = participant.reset_password()
    messages.success(request, f'Patient {patient_id}\'s password has been reset to {new_password}.')
    # FIXME: this  was a referrer redirect
    return redirect(f'/view_study/{study_id}/')


@require_POST
@authenticate_researcher_study_access
def reset_device(request: ResearcherRequest):
    """ Resets a participant's device. The participant will not be able to connect until they
    register a new device. """
    
    patient_id = request.POST.get('patient_id', None)
    study_id = request.POST.get('study_id', None)
    
    try:
        participant = Participant.objects.get(patient_id=patient_id)
    except Participant.DoesNotExist:
        messages.error(request, f'The participant {patient_id} does not exist')
        return redirect(f'/view_study/{study_id}/')
    
    if participant.study.id != int(study_id):
        messages.error(
            request,
            f'Participant {patient_id} is not in study {Study.objects.get(id=study_id).name}'
        )
        # FIXME: this was originally request.referrer
        return redirect(f'/view_study/{study_id}/')
    
    participant.device_id = ""
    participant.save()
    messages.success(request, f'For patient {patient_id}, device was reset; password is untouched.')
    # FIXME: this was originally request.referrer
    return redirect(f'/view_study/{study_id}/')


@require_POST
@authenticate_researcher_study_access
def unregister_participant(request: ResearcherRequest):
    """ Block participant from uploading further data """
    patient_id = request.POST['patient_id']
    study_id = request.POST['study_id']
    
    try:
        participant = Participant.objects.get(patient_id=patient_id)
    except Participant.DoesNotExist:
        messages.error(f'The participant {patient_id} does not exist')
        return redirect(request, f'/view_study/{study_id}/')
    
    if participant.study.id != int(study_id):
        messages.error(f'Participant {patient_id} is not in study {Study.objects.get(id=study_id).name}')
        return redirect(request, request.referrer)
    
    if participant.unregistered:
        messages.error(f'Participant {patient_id} is already unregistered')
        return redirect(request, request.referrer)
    
    participant.unregistered = True
    participant.save()
    messages.error(f'{patient_id} was successfully unregisted from the study. They will not be able to upload further data. ')
    return redirect(request, request.referrer)


@require_POST
@authenticate_researcher_study_access
def create_new_participant(request: ResearcherRequest):
    """ Creates a new user, generates a password and keys, pushes data to s3 and user database, adds
    user to the study they are supposed to be attached to and returns a string containing
    password and patient id. """
    
    study_id = request.POST['study_id']
    patient_id, password = Participant.create_with_password(study_id=study_id)
    participant = Participant.objects.get(patient_id=patient_id)
    study = Study.objects.get(id=study_id)
    add_fields_and_interventions(participant, study)
    
    # Create an empty file on S3 indicating that this user exists
    study_object_id = Study.objects.filter(pk=study_id).values_list('object_id', flat=True).get()
    s3_upload(patient_id, b"", study_object_id)
    create_client_key_pair(patient_id, study_object_id)
    repopulate_all_survey_scheduled_events(study, participant)
    
    response_string = f'Created a new patient\npatient_id: {patient_id}\npassword: {password}'
    messages.success(response_string)
    return redirect(request, f'/view_study/{study_id}')


@require_POST
@authenticate_researcher_study_access
def create_many_patients(request: ResearcherRequest, study_id=None):
    """ Creates a number of new users at once for a study.  Generates a password and keys for
    each one, pushes data to S3 and the user database, adds users to the study they're supposed
    to be attached to, and returns a CSV file for download with a mapping of Patient IDs and
    passwords. """
    number_of_new_patients = int(request.POST.get('number_of_new_patients', 0))
    desired_filename = request.POST.get('desired_filename', '')
    filename_spaces_to_underscores = sub(r'[\ =]', '_', desired_filename)
    filename = sub(r'[^a-zA-Z0-9_\.=]', '', filename_spaces_to_underscores)
    if not filename.endswith('.csv'):
        filename += ".csv"
    return HttpResponse(
        request,
        participant_csv_generator(study_id, number_of_new_patients),
        mimetype="csv",
        headers={'Content-Disposition': 'attachment; filename="%s"' % filename}
    )


def participant_csv_generator(study_id, number_of_new_patients):
    study = Study.objects.get(pk=study_id)
    si = StreamingStringsIO()
    filewriter = writer(si)
    filewriter.writerow(['Patient ID', "Registration password"])
    
    for _ in range(number_of_new_patients):
        patient_id, password = Participant.create_with_password(study_id=study_id)
        participant = Participant.objects.get(patient_id=patient_id)
        add_fields_and_interventions(participant, Study.objects.get(id=study_id))
        # Creates an empty file on s3 indicating that this user exists
        s3_upload(patient_id, b"", study.object_id)
        create_client_key_pair(patient_id, study.object_id)
        repopulate_all_survey_scheduled_events(study, participant)
        
        filewriter.writerow([patient_id, password])
        yield si.getvalue()
        si.empty()


def add_fields_and_interventions(participant: Participant, study: Study):
    """ Creates empty ParticipantFieldValue and InterventionDate objects for newly created
     participants, doesn't affect existing instances. """
    for field in study.fields.all():
        ParticipantFieldValue.objects.get_or_create(participant=participant, field=field)
    for intervention in study.interventions.all():
        InterventionDate.objects.get_or_create(participant=participant, intervention=intervention)
