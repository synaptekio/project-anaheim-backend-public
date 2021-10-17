from django.http.request import HttpRequest

from database.study_models import Study
from database.user_models import Participant, Researcher


"""
This file includes types and typing information that may be missing from your development
environment or your IDE.
"""


class ResearcherRequest(HttpRequest):
    # these attributes are present on the normal researcher endpoints
    session_researcher: Researcher


class ApiStudyResearcherRequest(HttpRequest):
    api_researcher: Researcher
    api_study: Study


class ApiResearcherRequest(HttpRequest):
    api_researcher: Researcher


class ParticipantRequest(HttpRequest):
    participant: Participant