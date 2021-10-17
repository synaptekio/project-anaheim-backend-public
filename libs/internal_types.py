from django.http.request import HttpRequest

from database.study_models import Study
from database.user_models import Researcher


""" This file includes types and typing information that may be missing from your development
environment or your IDE.  """


class BeiweHttpRequest(HttpRequest):
    # these attributes are present on the normal researcher endpoints
    session_researcher: Researcher


class BeiweApiRequest(HttpRequest):
    api_researcher: Researcher
    api_study: Study


class BeiweApiLightRequest(HttpRequest):
    api_researcher: Researcher

