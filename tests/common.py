from sys import argv

from django.contrib import messages
from django.http.response import HttpResponse, HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from django.urls.base import resolve
from tests.helpers import ReferenceObjectMixin

from constants.researcher_constants import ResearcherRole
from database.user_models import Researcher


# this makes print statements during debugging easier to read by bracketting the statement of which
# test is running with some separater.
VERBOSE_2_OR_3 = ("-v2" in argv or "-v3" in argv) and "-v1" not in argv


# extra printout of calls to the messages library
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


# ALL_ROLE_PERMUTATIONS is generated from this:
# ALL_ROLE_PERMUTATIONS = tuple(
# from constants.researcher_constants import ResearcherRole
# from itertools import permutations
#     two_options for two_options in permutations(
#     ("site_admin", ResearcherRole.study_admin, ResearcherRole.researcher, None), 2)
# )

ALL_ROLE_PERMUTATIONS = (
    ('site_admin', 'study_admin'),
    ('site_admin', 'study_researcher'),
    ('site_admin', None),
    ('study_admin', 'site_admin'),
    ('study_admin', 'study_researcher'),
    ('study_admin', None),
    ('study_researcher', 'site_admin'),
    ('study_researcher', 'study_admin'),
    ('study_researcher', None),
    (None, 'site_admin'),
    (None, 'study_admin'),
    (None, 'study_researcher'),
)

REAL_ROLES = (ResearcherRole.study_admin, ResearcherRole.researcher)
ALL_ROLES = (ResearcherRole.study_admin, ResearcherRole.researcher, "site_admin", None)


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


class BasicDefaultTestCase(CommonTestCase):
    # common client operations
    def do_default_login(self):
        # logs in the default researcher user, assumes it has been instantiated.
        return self.do_login(self.DEFAULT_RESEARCHER_NAME, self.DEFAULT_RESEARCHER_PASSWORD)
    
    def do_login(self, username, password):
        return self.client.post(
            reverse("login_pages.validate_login"),
            data={"username": username, "password": password}
        )


class PopulatedSessionTestCase(BasicDefaultTestCase):
    
    def setUp(self) -> None:
        self.session_researcher  # setup the default user, we always need it.
        self.do_default_login()
        return super().setUp()
    
    def assign_role(self, researcher, role):
        if role in REAL_ROLES:
            researcher.study_relations.delete()
            self.generate_study_relation(researcher, role)
            researcher.update(site_admin=False)
        elif role is None:
            researcher.study_relations.delete()
            researcher.update(site_admin=False)
        elif role == "site_admin":
            researcher.study_relations.delete()
            researcher.update(site_admin=True)
    
    def iterate_researcher_permutations(self):
        session_researcher = self.session_researcher
        r2 = self.generate_researcher()
        for session_researcher_role, target_researcher_role in ALL_ROLE_PERMUTATIONS:
            self.assign_role(session_researcher, session_researcher_role)
            self.assign_role(r2, target_researcher_role)
            yield session_researcher, r2


# These mixin classes implement some common patterns, please educate yourself on what the
# "do_post", "do_get", and "do_test_status_code", functions do, and use them.


class RedirectSessionApiTest(PopulatedSessionTestCase):
    ENDPOINT_NAME = None
    REDIRECT_ENDPOINT_NAME = None
    
    # some api calls only come from pages, which means they need to return 302 in all cases.
    def do_post(self, **post_params) -> HttpResponseRedirect:
        # instantiate the default researcher, pass through params, reverse the enpoint and pass in
        # post params, then refresh default researcher just in case it has mutated during the call.
        self.session_researcher
        response = self.client.post(reverse(self.ENDPOINT_NAME), data=post_params)
        self.session_researcher.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(resolve(response.url).url_name, self.REDIRECT_ENDPOINT_NAME)
        return response
    
    def get_redirect_content(self, *args, **kwargs) -> bytes:
        # these tests usually need a page to test for content messages.  We use the Edit Credentials
        # page (admin_pages.manage_credentials) because this page should be accessible by all user
        # types, takes no arguments, and a bunch of these commands work on this page anyway.
        resp = self.client.get(reverse(self.REDIRECT_ENDPOINT_NAME), *args, **kwargs)
        self.assertEqual(resp.status_code, 200)  # if it is not a 200 something has gone wrong.
        return resp.content


class SessionApiTest(PopulatedSessionTestCase):
    ENDPOINT_NAME = None
    
    # some api calls return real 400 codes
    def do_post(self, **post_params) -> HttpResponse:
        # instantiate the default researcher, pass through params, refresh default researcher.
        self.session_researcher
        response = self.client.post(reverse(self.ENDPOINT_NAME), data=post_params)
        self.session_researcher.refresh_from_db()
        return response
    
    def do_test_status_code(self, status_code: int, researcher: Researcher) -> HttpResponse:
        if not isinstance(status_code, int):
            raise TypeError(f"received {type(status_code)} '{status_code}' for status_code?")
        resp = self.do_post(researcher_id=researcher.id, study_id=self.session_study.id)
        self.assertEqual(resp.status_code, status_code)
        return resp


class GeneralPageTest(PopulatedSessionTestCase):
    ENDPOINT_NAME = None
    
    def do_get(self, *get_params, **kwargs) -> HttpResponse:
        # instantiate the default researcher, pass through params, refresh default researcher.
        self.session_researcher
        response = self.client.get(reverse(self.ENDPOINT_NAME, args=get_params, kwargs=kwargs))
        self.session_researcher.refresh_from_db()  # just in case
        return response
    
    def do_test_status_code(self, status_code: int, *params, **kwargs) -> HttpResponse:
        if not isinstance(status_code, int):
            raise TypeError(f"received {type(status_code)} '{status_code}' for status_code?")
        resp = self.do_get(*params, **kwargs)
        self.assertEqual(resp.status_code, status_code)
        return resp
