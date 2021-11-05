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

    def assertPresentIn(self, test_str, corpus):
        # does a test for "in" and also handles the type coersion for bytes and strings, which is
        # common due to response.content being a bytes object.
        t_test = type(test_str)
        t_corpus = type(corpus)
        if t_test == t_corpus:
            return self.assertIn(test_str, corpus)
        elif t_test == str and t_corpus == bytes:
            return self.assertIn(test_str.encode(), corpus)
        elif t_test == bytes and t_corpus == str:
            return self.assertIn(test_str.decode(), corpus)
        else:
            raise TypeError(f"type mismatch, test_str ({t_test}) is not a ({t_corpus})")

    # common client operations
    def do_default_login(self):
        # logs in the default researcher user, assumes it has been instantiated.
        return self.do_login(self.DEFAULT_RESEARCHER_NAME, self.DEFAULT_RESEARCHER_PASSWORD)

    def do_login(self, username, password):
        return self.client.post(
            reverse("login_pages.validate_login"),
            data={"username": username, "password": password}
        )


class DefaultLoggedInCommonTestCase(CommonTestCase):
    def setUp(self) -> None:
        self.default_researcher  # setup the default user, we always need it.
        self.do_default_login()
        return super().setUp()


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


class GeneralApiMixin:
    def do_post(self, **post_params):
        # instantiate the default researcher, pass through params, refresh default researcher.
        self.default_researcher
        response = self.client.post(reverse(self.ENDPOINT_NAME), data=post_params)
        self.default_researcher.refresh_from_db()
        # this is an api call, it should return a 302, not an error or page.
        self.assertEqual(response.status_code, 302)
        return response

    @property
    def manage_credentials_content(self) -> bytes:
        # we need a page, manage credentials works
        return self.client.get(reverse("admin_pages.manage_credentials")).content


class GeneralPageMixin(CommonTestCase):
    def do_get(self, *get_params):
        # instantiate the default researcher, pass through params, refresh default researcher.
        self.default_researcher
        response = self.client.get(reverse(self.ENDPOINT_NAME, args=get_params))
        self.default_researcher.refresh_from_db()
        return response


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
