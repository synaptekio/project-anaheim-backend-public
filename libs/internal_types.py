from database.user_models import Researcher
from django.http.request import HttpRequest

""" This file includes types and typing information that may be missing from your development
environment or your IDE.  """


class BeiweHttpRequest(HttpRequest):
    session_researcher: Researcher
