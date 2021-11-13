from sys import argv

from django.contrib import messages
from django.http.response import HttpResponse, HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from django.urls.base import resolve

from constants.testing_constants import ALL_ROLE_PERMUTATIONS, REAL_ROLES
from database.user_models import Researcher
from tests.helpers import ReferenceObjectMixin


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


class CommonTestCase(TestCase, ReferenceObjectMixin):
    """ This class contains the various test-oriented features, for example the assert_present
    method that handles a common case of some otherwise distracting type coersion. """
    
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


class BasicSessionTestCase(CommonTestCase):
    """ This class has the basics needed to do login operations, but runs no extra setup before each
    test.  This class is probably only useful to test the login pages. """
    
    def do_default_login(self):
        # logs in the default researcher user, assumes it has been instantiated.
        return self.do_login(self.DEFAULT_RESEARCHER_NAME, self.DEFAULT_RESEARCHER_PASSWORD)
    
    def do_login(self, username, password):
        return self.client.post(
            reverse("login_pages.validate_login"),
            data={"username": username, "password": password}
        )


class PopulatedSessionTestCase(BasicSessionTestCase):
    """ This class sets up a logged-in researcher user (using the variable name "session_researcher"
    to mimic the convenience variable in the real code).  This is the base test class that all
    researcher endpoints should use. """
    
    def setUp(self) -> None:
        """ Log in the session researcher. """
        self.session_researcher
        self.do_default_login()
        return super().setUp()
    
    def assign_role(self, researcher: Researcher, role: str):
        """ Helper function to assign a user role to a Researcher.  Clears all existing roles on
        that user. """
        if role in REAL_ROLES:
            researcher.study_relations.all().delete()
            self.generate_study_relation(researcher, self.session_study, role)
            researcher.update(site_admin=False)
        elif role is None:
            researcher.study_relations.all().delete()
            researcher.update(site_admin=False)
        elif role == "site_admin":
            researcher.study_relations.all().delete()
            researcher.update(site_admin=True)
    
    def iterate_researcher_permutations(self):
        """ Iterates over all possible combinations of user types for the session researcher and a
        target researcher. """
        session_researcher = self.session_researcher
        r2 = self.generate_researcher()
        for session_researcher_role, target_researcher_role in ALL_ROLE_PERMUTATIONS:
            self.assign_role(session_researcher, session_researcher_role)
            self.assign_role(r2, target_researcher_role)
            yield session_researcher, r2


class SmartRequestsTestCase(PopulatedSessionTestCase):
    ENDPOINT_NAME = None
    REDIRECT_ENDPOINT_NAME = None
    
    def smart_post(self, *reverse_args, reverse_kwargs=None, **post_params) -> HttpResponse:
        if reverse_kwargs is None:
            reverse_kwargs = {}
        return self.client.post(
            reverse(self.ENDPOINT_NAME, args=reverse_args, kwargs=reverse_kwargs), data=post_params
        )
    
    def smart_get(self, *reverse_params, **reverse_kwargs) -> HttpResponse:
        return self.client.get(
            reverse(self.ENDPOINT_NAME, args=reverse_params, kwargs=reverse_kwargs)
        )
    
    def smart_get_redirect(self, *reverse_params, **reverse_kwargs) -> HttpResponse:
        return self.client.get(
            reverse(self.REDIRECT_ENDPOINT_NAME, args=reverse_params, kwargs=reverse_kwargs)
        )


class RedirectSessionApiTest(SmartRequestsTestCase):
    """ Some api calls return only redirects, and the fact of an error is reported only via the
    django.contrib.messages library.  This class implements some specific helper functions to handle
    very common cases.
    When using this class make sure to set ENDPOINT_NAME and REDIRECT_ENDPOINT_NAME. The first is
    used to populate the http post operation, the second is part of validation inside do_post. """
    ENDPOINT_NAME = None
    REDIRECT_ENDPOINT_NAME = None
    
    def smart_post(self, *reverse_args, reverse_kwargs={}, **post_params) -> HttpResponseRedirect:
        # As smart post, but assert that the request was redirected, and that it points to the
        # appropriate endpoint.
        response = super().smart_post(*reverse_args, reverse_params=reverse_kwargs, **post_params)
        self.assertEqual(response.status_code, 302)
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(resolve(response.url).url_name, self.REDIRECT_ENDPOINT_NAME)
        return response
    
    def get_redirect_content(self, *args, **kwargs) -> bytes:
        # Tests for this class usually need a page to test for content messages.  This method loads
        # the REDIRECT_ENDPOINT_NAME page, ensures it has the required 200 code, and returns the
        # html content for further checking by the test itself.
        resp = self.smart_get_redirect(*args, **kwargs)
        self.assertEqual(resp.status_code, 200)
        return resp.content


class SessionApiTest(SmartRequestsTestCase):
    """ This class is for non-redirect api endpoints.  It includes helper functions for issuing a
    post request to the endpoint declared for ENDPOINT_NAME and testing its return code. """
    ENDPOINT_NAME = None
    
    def do_test_status_code(
        self, status_code: int, *reverse_args, reverse_kwargs=None, **post_params
    ) -> HttpResponse:
        """ This helper function takes a status code in addition to post paramers, and tests for
        it.  Use for writing concise tests. """
        if not isinstance(status_code, int):
            raise TypeError(f"received {type(status_code)} '{status_code}' for status_code?")
        resp = self.smart_post(*reverse_args, reverse_kwargs=reverse_kwargs, **post_params)
        self.assertEqual(resp.status_code, status_code)
        return resp


class GeneralPageTest(SmartRequestsTestCase):
    """ This class implements a do_get and a do_test_status_code function for implementing concise
    tests on normal, non-api web pages. """    
    ENDPOINT_NAME = None
    
    def do_test_status_code(self, status_code: int, *params, **kwargs) -> HttpResponse:
        if not isinstance(status_code, int):
            raise TypeError(f"received {type(status_code)} '{status_code}' for status_code?")
        resp = self.smart_get(*params, **kwargs)
        self.assertEqual(resp.status_code, status_code)
        return resp
