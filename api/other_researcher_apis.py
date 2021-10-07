import json

from django.views.decorators.http import require_http_methods

from authentication.data_access_authentication import (api_credential_check,
    api_study_credential_check, get_api_researcher, get_api_study)
from database.user_models import StudyRelation


@require_http_methods(['POST', "GET"])
@api_credential_check
def get_studies():
    """
    Retrieve a dict containing the object ID and name of all Study objects that the user can access
    If a GET request, access_key and secret_key must be provided in the URL as GET params. If
    a POST request (strongly preferred!), access_key and secret_key must be in the POST
    request body.
    :return: string: JSON-dumped dict {object_id: name}
    """
    return json.dumps(
        dict(
            StudyRelation.objects.filter(researcher=get_api_researcher())
                .values_list("study__object_id", "study__name")
        )
    )


@require_http_methods(['POST', "GET"])
@api_study_credential_check()
def get_users_in_study():
    return json.dumps(  # json can't operate on query, need as list.
        list(get_api_study().participants.values_list('patient_id', flat=True))
    )

