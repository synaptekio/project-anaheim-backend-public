from sys import argv

from django.contrib import messages
from django.test import TestCase
from django.urls import reverse
from tests.helpers import ReferenceObjectMixin

from database.study_models import Study
from database.survey_models import Survey
from database.user_models import Participant, Researcher


# this makes print statements during debugging easier to read by bracketting the statement of which
# test is running with some separater.
VERBOSE_2_OR_3 = ("-v2" in argv or "-v3" in argv) and "-v1" not in argv


if VERBOSE_2_OR_3:

    def monkeypatch_messages(function: callable):
        """ This function wraps the messages library and directs it to the terminal for easy
        behavior identification. """

        def intercepted(request, message, extra_tags='', fail_silently=False):
            print(f"from messages.{function.__name__}(): '{message}'")
            return function(request, message, extra_tags=extra_tags, fail_silently=fail_silently)

        return intercepted

    messages.debug = monkeypatch_messages(messages.debug)
    messages.info = monkeypatch_messages(messages.info)
    messages.success = monkeypatch_messages(messages.success)
    messages.warning = monkeypatch_messages(messages.warning)
    messages.error = monkeypatch_messages(messages.error)


class CommonTestCase(TestCase, ReferenceObjectMixin):

    def setUp(self) -> None:
        if VERBOSE_2_OR_3:
            print("\n==")
        return super().setUp()

    def tearDown(self) -> None:
        if VERBOSE_2_OR_3:
            print("==")
        return super().tearDown()

    def assert_not_present(self, test_str, corpus):
        # does a test for "in" and also handles the type coersion for bytes and strings, which is
        # common due to response.content being a bytes object.
        return self._assert_present(False, test_str, corpus)

    def assert_present(self, test_str, corpus):
        return self._assert_present(True, test_str, corpus)

    def _assert_present(self, the_test: bool, test_str, corpus):
        # True does a test for "in", False does a test for "not in", and we handle the type coersion
        # for bytes and strings, which is common due to response.content being a bytes object.
        t_test = type(test_str)
        t_corpus = type(corpus)
        the_test_function = self.assertIn if the_test else self.assertNotIn
        if t_test == t_corpus:
            return the_test_function(test_str, corpus)
        elif t_test == str and t_corpus == bytes:
            return the_test_function(test_str.encode(), corpus)
        elif t_test == bytes and t_corpus == str:
            return the_test_function(test_str.decode(), corpus)
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


class PopulatedSessionTestCase(CommonTestCase):
    def setUp(self) -> None:
        self.session_researcher  # setup the default user, we always need it.
        self.do_default_login()
        return super().setUp()


class TestDefaults(CommonTestCase):

    def test_defaults(self):
        researcher = self.session_researcher
        participant = self.default_participant
        study = self.session_study
        survey = self.session_survey
        assert Researcher.objects.filter(pk=researcher.pk).exists()
        assert Participant.objects.filter(pk=participant.pk).exists()
        assert Study.objects.filter(pk=study.pk).exists()
        assert Survey.objects.filter(pk=survey.pk).exists()


class ApiRedirectMixin:
    # some api calls only come from pages, which means they need to return 302 in all cases
    def do_post(self, **post_params):
        # instantiate the default researcher, pass through params, refresh default researcher.
        self.session_researcher
        response = self.client.post(reverse(self.ENDPOINT_NAME), data=post_params)
        self.session_researcher.refresh_from_db()
        # this is an api call, it should return a 302, not an error or page.
        self.assertEqual(response.status_code, 302)
        return response

    @property
    def manage_credentials_content(self) -> bytes:
        # we need a page, manage credentials works
        return self.client.get(reverse("admin_pages.manage_credentials")).content


class ApiSessionMixin:
    # some api calls return real 400 codes
    def do_post(self, **post_params):
        # instantiate the default researcher, pass through params, refresh default researcher.
        self.session_researcher
        response = self.client.post(reverse(self.ENDPOINT_NAME), data=post_params)
        self.session_researcher.refresh_from_db()
        return response

    def do_basic_test(self, researcher: Researcher, status_code: int):
        resp = self.do_post(researcher_id=researcher.id, study_id=self.session_study.id)
        self.assertEqual(resp.status_code, status_code)
        return resp


class GeneralPageMixin:
    def do_get(self, *get_params, **kwargs):
        # instantiate the default researcher, pass through params, refresh default researcher.
        self.session_researcher
        response = self.client.get(reverse(self.ENDPOINT_NAME, args=get_params, kwargs=kwargs))
        self.session_researcher.refresh_from_db()
        return response
    
    def do_basic_test(self, status_code: int, *params, **kwargs):
        if not isinstance(status_code, int):
            raise TypeError(f"received a {type(status_code)} for 'status_code', did you get the order wrong?")
        resp = self.do_get(*params)
        self.assertEqual(resp.status_code, status_code)
        return resp


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
