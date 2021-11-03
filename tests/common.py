from sys import argv

from django.test import TestCase
from django.urls import reverse
from tests.helpers import ReferenceObjectMixin

from database.study_models import Study
from database.survey_models import Survey
from database.user_models import Participant, Researcher


# this makes print statements during debugging easier to read by bracketting the statement of which
# test is running with some separater.
MAKE_PRINTING_LESS_AWFUL = ("-v2" in argv or "-v3" in argv) and "-v1" not in argv


class CommonTestCase(TestCase, ReferenceObjectMixin):

    def setUp(self) -> None:
        if MAKE_PRINTING_LESS_AWFUL:
            print("\n==")
        return super().setUp()

    def tearDown(self) -> None:
        if MAKE_PRINTING_LESS_AWFUL:
            print("==")
        return super().tearDown()

    def do_default_login(self):
        return self.client.post(
            reverse("login_pages.validate_login"),
            data={"username": self.RESEARCHER_NAME, "password": self.RESEARCHER_PASSWORD}
        )


class TestDefaults(CommonTestCase):

    def test_defaults(self):
        researcher = self.default_researcher
        participant = self.default_participant
        study = self.default_study
        survey = self.default_survey
        assert Researcher.objects.filter(pk=researcher.pk).exists()
        assert Participant.objects.filter(pk=participant.pk).exists()
        assert Study.objects.filter(pk=study.pk).exists()
        assert Survey.objects.filter(pk=survey.pk).exists()


def compare_dictionaries(reference, comparee, ignore=None):
    if not isinstance(reference, dict):
        raise Exception("reference was %s, not dictionary" % type(reference))
    if not isinstance(comparee, dict):
        raise Exception("comparee was %s, not dictionary" % type(comparee))

    if ignore is None:
        ignore = []

    b = set((x, y) for x, y in comparee.items() if x not in ignore)
    a = set((x, y) for x, y in reference.items() if x not in ignore)
    differences_a = a - b
    differences_b = b - a

    if len(differences_a) == 0 and len(differences_b) == 0:
        return True

    try:
        differences_a = sorted(differences_a)
        differences_b = sorted(differences_b)
    except Exception:
        pass

    print("These dictionaries are not identical:")
    if differences_a:
        print("in reference, not in comparee:")
        for x, y in differences_a:
            print("\t", x, y)
    if differences_b:
        print("in comparee, not in reference:")
        for x, y in differences_b:
            print("\t", x, y)

    return False
