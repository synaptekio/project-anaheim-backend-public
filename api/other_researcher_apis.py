import json

from django.http.response import HttpResponse
from django.views.decorators.http import require_http_methods

from authentication.data_access_authentication import (api_credential_check,
    api_study_credential_check)
from database.user_models import StudyRelation
from libs.internal_types import ApiResearcherRequest, ApiStudyResearcherRequest


@require_http_methods(['POST', "GET"])
@api_credential_check
def get_studies(request: ApiResearcherRequest):
    """
    Retrieve a dict containing the object ID and name of all Study objects that the user can access
    If a GET request, access_key and secret_key must be provided in the URL as GET params. If
    a POST request (strongly preferred!), access_key and secret_key must be in the POST
    request body.
    :return: string: JSON-dumped dict {object_id: name}
    """
    return HttpResponse(
        json.dumps(
            dict(StudyRelation.objects.filter(
                researcher=request.api_researcher).values_list("study__object_id", "study__name")
            )
        )
    )


@require_http_methods(['POST', "GET"])
@api_study_credential_check
def get_users_in_study(request: ApiStudyResearcherRequest):
    return json.dumps(  # json can't operate on queryset, need as list.
        list(request.api_study.participants.values_list('patient_id', flat=True))
    )
