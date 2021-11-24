from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from authentication.participant_authentication import authenticate_participant
from libs.graph_data import get_survey_results
from libs.internal_types import ParticipantRequest


@require_http_methods(['GET', 'POST'])
@authenticate_participant
def fetch_graph(request: ParticipantRequest):
    """ Fetches the patient's answers to the most recent survey, marked by survey ID. The results
    are dumped into a jinja template and pushed to the device. """
    participant = request.participant
    # See docs in config manipulations for details
    study_object_id = participant.study.object_id
    survey_object_id_set = participant.study.surveys.values_list('object_id', flat=True)
    data = []
    for survey_id in survey_object_id_set:
        data.append(get_survey_results(study_object_id, participant.patient_id, survey_id, 7))
    return render(request, "phone_graphs.html", context=dict(data=data))
