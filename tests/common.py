from itertools import chain
from sys import argv

from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model
from django.http.response import HttpResponse, HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from django.urls.base import resolve

from constants.testing_constants import ALL_ROLE_PERMUTATIONS, REAL_ROLES, ResearcherRole
from database.study_models import Study
from database.user_models import Researcher, StudyRelation
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
    
    def assert_resolve_equal(self, a, b):
        # when a url comes in from a response object (e.g. response.url) the / characters are
        # encoded in html escape format.  This causes an error in the call to resolve
        a = a.replace(r"%2F", "/")
        b = b.replace(r"%2F", "/")
        resolve_a, resolve_b, = resolve(a), resolve(b)
        msg = f"urls do not point to the same function:\n a - {a}, {resolve_a}\nb - {b}, {resolve_b}"
        return self.assertIs(resolve(a).func, resolve(b).func, msg)
    
    def assert_not_present(self, test_str, corpus):
        """ Tests "in" and also handles the type coersion for bytes and strings, and suppresses 
        excessively long output that can occur when testing for presence of substrings in html."""
        return self._assert_present(False, test_str, corpus)
    
    def assert_present(self, test_str, corpus):
        """ Tests "not in" and also handles the type coersion for bytes and strings, and suppresses 
        excessively long output that can occur when testing for presence of substrings in html."""
        return self._assert_present(True, test_str, corpus)
    
    def _assert_present(self, the_test: bool, test_str, corpus):
        t_test = type(test_str)
        t_corpus = type(corpus)
        test_str = test_str.encode() if t_test == str and t_corpus == bytes else test_str
        test_str = test_str.decode() if t_test == bytes and t_corpus == str else test_str
        the_test_function = self.assertIn if the_test else self.assertNotIn
        msg_param = "was not found" if the_test else "was found"
        
        try:
            return the_test_function(test_str, corpus)
        except AssertionError:
            if len(corpus) > 1000:
                test_str = test_str.decode() if isinstance(test_str, bytes) else test_str
                raise AssertionError(
                    f"'{test_str}' {msg_param} in the provided text. (The provided text was over "
                    "1000 characters, try self.assertIn or self.assertNotIn for full text of failure."
                ) from None
                # from None suppresses the original stack trace.
            else:
                raise
    
    def assert_researcher_relation(self, researcher: Researcher, study: Study, relationship: str):
        try:
            if relationship == ResearcherRole.site_admin:
                researcher.refresh_from_db()
                self.assertTrue(researcher.site_admin)
                # no relationships because it is a site admin
                self.assertEqual(
                    StudyRelation.objects.filter(study=study, researcher=researcher).count(), 0
                )
            elif relationship is None:
                # Relationship should not exist because it was set to None
                self.assertFalse(
                    StudyRelation.objects.filter(study=study, researcher=researcher).exists()
                )
            elif relationship in REAL_ROLES:
                # relatioship is supposed to be the provided relatioship (researcher or study_admin)
                self.assertEqual(
                    StudyRelation.objects.filter(
                        study=study, researcher=researcher, relationship=relationship).count(),
                    1
                )
            else:
                raise Exception("invalid researcher role provided")
        except AssertionError:
            print("researcher:", researcher.username)
            print("study:", study.name)
            print("relationship that it should be:", relationship)
            real_relatiosnship = StudyRelation.objects.filter(study=study, researcher=researcher)
            if not real_relatiosnship:
                print("relationship was 'None'")
            else:
                print(f"relationship was '{real_relatiosnship.get().relationship}'")
            raise
    
    @staticmethod
    def mutate_variable(var, ignore_bools=False):
        if isinstance(var, bool):
            return var if ignore_bools else not var
        elif isinstance(var, (float, int)):
            return var + 1
        elif isinstance(var, str):
            return var + "aaa"
        else:
            raise TypeError(f"Unhandled type: {type(var)}")
    
    @staticmethod
    def un_mutate_variable(var, ignore_bools=False):
        if isinstance(var, bool):
            return not var if ignore_bools else var
        elif isinstance(var, (float, int)):
            return var - 1
        elif isinstance(var, str):
            if not var.endswith("eee"):
                raise Exception(f"string '{var} was not a mutated variable")
            return var[-3:]
        else:
            raise TypeError(f"Unhandled type: {type(var)}")


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
        elif role == ResearcherRole.site_admin:
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
        """ A wrapper to do a post request, using reverse on the ENDPOINT_NAME, and with a
        reasonable pattern for providing parameters to both reverse and post. """
        reverse_kwargs = reverse_kwargs or {}
        # print(f"*reverse_args: {reverse_args}\n**reverse_kwargs: {reverse_kwargs}\n**post_params: {post_params}\n")
        self._detect_obnoxious_type_error("smart_post", reverse_args, reverse_kwargs, post_params)
        return self.client.post(
            reverse(self.ENDPOINT_NAME, args=reverse_args, kwargs=reverse_kwargs), data=post_params
        )
    
    def smart_get(self, *reverse_params, reverse_kwargs=None, **get_kwargs) -> HttpResponse:
        """ A wrapper to do a get request, using reverse on the ENDPOINT_NAME, and with a reasonable
        pattern for providing parameters to both reverse and get. """
        reverse_kwargs = reverse_kwargs or {}
        # print(f"*reverse_params: {reverse_params}\n**get_kwargs: {get_kwargs}\n**reverse_kwargs: {reverse_kwargs}\n")
        self._detect_obnoxious_type_error("smart_get", reverse_params, reverse_kwargs, get_kwargs)
        return self.client.get(
            reverse(self.ENDPOINT_NAME, args=reverse_params, kwargs=reverse_kwargs), **get_kwargs
        )
    
    def smart_get_redirect(self, *reverse_params, get_kwargs=None, **reverse_kwargs) -> HttpResponse:
        """ As smart_get, but uses REDIRECT_ENDPOINT_NAME. """
        get_kwargs = get_kwargs or {}
        # print(f"*reverse_params: {reverse_params}\n**get_kwargs: {get_kwargs}\n**reverse_kwargs: {reverse_kwargs}\n")
        self._detect_obnoxious_type_error("smart_get_redirect", reverse_params, reverse_kwargs, get_kwargs)
        return self.client.get(
            reverse(self.REDIRECT_ENDPOINT_NAME, args=reverse_params, kwargs=reverse_kwargs), **get_kwargs
        )
    
    @staticmethod
    def _detect_obnoxious_type_error(function_name: str, args: tuple, kwargs1: dict, kwargs2: dict):
        for arg in chain(args, kwargs1.values(), kwargs2.values()):
            if isinstance(arg, Model):
                raise TypeError(f"encountered {type(arg)} passed to {function_name}.")


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
        if self.REDIRECT_ENDPOINT_NAME is None:
            raise ImproperlyConfigured("You must provide a value for REDIRECT_ENDPOINT_NAME.")
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
    
    def do_test_status_code(
        self, status_code: int, *reverse_params, reverse_kwargs=None, **get_kwargs
    ) -> HttpResponse:
        if not isinstance(status_code, int):
            raise TypeError(f"received {type(status_code)} '{status_code}' for status_code?")
        if status_code < 200 or status_code > 600:
            raise ImproperlyConfigured(f"'{status_code}' ({type(status_code)}) is definetely not a status code.")
        resp = self.smart_get(*reverse_params, reverse_kwargs=reverse_kwargs, **get_kwargs)
        self.assertEqual(resp.status_code, status_code)
        return resp
