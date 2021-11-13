import json

from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import HttpResponse, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from authentication.admin_authentication import authenticate_researcher_study_access
from database.schedule_models import Intervention, InterventionDate
from database.study_models import Study, StudyField
from database.user_models import Participant, ParticipantFieldValue
from libs.internal_types import ResearcherRequest


@require_GET
@authenticate_researcher_study_access
def study_participants_api(request: ResearcherRequest, study_id: int):
    study: Study = Study.objects.get(pk=study_id)
    # `draw` is passed by DataTables. It's automatically incremented, starting with 1 on the page
    # load, and then 2 with the next call to this API endpoint, and so on.
    draw = int(request.GET.get('draw'))
    start = int(request.GET.get('start'))
    length = int(request.GET.get('length'))
    sort_by_column_index = int(request.GET.get('order[0][column]'))
    sort_in_descending_order = request.GET.get('order[0][dir]') == 'desc'
    contains_string = request.GET.get('search[value]')
    total_participants_count = Participant.objects.filter(study_id=study_id).count()
    filtered_participants_count = (study.filtered_participants(contains_string).count())
    data = study.get_values_for_participants_table(start, length, sort_by_column_index,
                                                   sort_in_descending_order, contains_string)
    table_data = {
        "draw": draw,
        "recordsTotal": total_participants_count,
        "recordsFiltered": filtered_participants_count,
        "data": data
    }
    return HttpResponse(json.dumps(table_data), status_code=200)


@require_http_methods(['GET', 'POST'])
@authenticate_researcher_study_access
def interventions_page(request: ResearcherRequest, study_id=None):
    study: Study = Study.objects.get(pk=study_id)
    # FIXME: get rid of dual endpoint pattern, it is a bad idea.
    if request.method == 'GET':
        return render(
            request,
            'study_interventions.html',
            context=dict(
                study=study,
                interventions=study.interventions.all(),
            ),
        )
    
    # slow but safe
    new_intervention = request.POST.get('new_intervention', None)
    if new_intervention:
        intervention, _ = Intervention.objects.get_or_create(study=study, name=new_intervention)
        for participant in study.participants.all():
            InterventionDate.objects.get_or_create(participant=participant, intervention=intervention)
    
    return redirect(f'/interventions/{study.id}')


@require_POST
@authenticate_researcher_study_access
def delete_intervention(request: ResearcherRequest, study_id=None):
    """Deletes the specified Intervention. Expects intervention in the request body."""
    study = Study.objects.get(pk=study_id)
    intervention_id = request.POST.get('intervention')
    if intervention_id:
        try:
            intervention = Intervention.objects.get(id=intervention_id)
        except Intervention.DoesNotExist:
            intervention = None
        try:
            if intervention:
                intervention.delete()
        except ProtectedError:
            messages.warning("This Intervention can not be removed because it is already in use")
    
    return redirect(f'/interventions/{study.id}')


@require_POST
@authenticate_researcher_study_access
def edit_intervention(request: ResearcherRequest, study_id=None):
    """
    Edits the name of the intervention. Expects intervention_id and edit_intervention in the
    request body
    """
    study = Study.objects.get(pk=study_id)
    intervention_id = request.POST.get('intervention_id', None)
    new_name = request.POST.get('edit_intervention', None)
    if intervention_id:
        try:
            intervention = Intervention.objects.get(id=intervention_id)
        except Intervention.DoesNotExist:
            intervention = None
        if intervention and new_name:
            intervention.name = new_name
            intervention.save()
    
    return redirect(f'/interventions/{study.id}')

@require_http_methods(['GET', 'POST'])
@authenticate_researcher_study_access
def study_fields(request: ResearcherRequest, study_id=None):
    study = Study.objects.get(pk=study_id)
    
    # FIXME: get rid of dual endpoint pattern, it is a bad idea.
    if request.method == 'GET':
        return render(
            request,
            'study_custom_fields.html',
            context=dict(
                study=study,
                fields=study.fields.all(),
            ),
        )
    
    new_field = request.POST.get('new_field', None)
    if new_field:
        study_field, _ = StudyField.objects.get_or_create(study=study, field_name=new_field)
        for participant in study.participants.all():
            ParticipantFieldValue.objects.create(participant=participant, field=study_field)
    
    return redirect(f'/study_fields/{study.id}')


@require_POST
@authenticate_researcher_study_access
def delete_field(request: ResearcherRequest, study_id=None):
    """Deletes the specified Custom Field. Expects field in the request body."""
    study = Study.objects.get(pk=study_id)
    field = request.POST.get('field', None)
    if field:
        try:
            study_field = StudyField.objects.get(study=study, id=field)
        except StudyField.DoesNotExist:
            study_field = None
        
        try:
            if study_field:
                study_field.delete()
        except ProtectedError:
            messages.warning("This field can not be removed because it is already in use")
    
    return redirect(f'/study_fields/{study.id}')


@require_POST
@authenticate_researcher_study_access
def edit_custom_field(request: ResearcherRequest, study_id=None):
    """Edits the name of a Custom field. Expects field_id anf edit_custom_field in request body"""
    field_id = request.POST.get("field_id")
    new_field_name = request.POST.get("edit_custom_field")
    if field_id:
        try:
            field = StudyField.objects.get(id=field_id)
        except StudyField.DoesNotExist:
            field = None
        if field and new_field_name:
            field.field_name = new_field_name
            field.save()
    
    # this apparent insanity is a hopefully unnecessary confirmation of the study id
    return redirect(f'/study_fields/{Study.objects.get(pk=study_id).id}')
