from unittest.case import skip

import urls

from database.study_models import Study
from database.survey_models import Survey
from database.user_models import Participant, Researcher
from tests.common import CommonTestCase, SmartRequestsTestCase


class TestDefaults(CommonTestCase):
    
    def test_defaults(self):
        researcher = self.session_researcher
        participant = self.default_participant
        study = self.session_study
        survey = self.default_survey
        assert Researcher.objects.filter(pk=researcher.pk).exists()
        assert Participant.objects.filter(pk=participant.pk).exists()
        assert Study.objects.filter(pk=study.pk).exists()
        assert Survey.objects.filter(pk=survey.pk).exists()


class TestUrls(CommonTestCase):
    
    @skip("too meta")
    def test(self):
        # this is a consistency test - all endpoint names really should reflect reality with a name
        # composed of "module_name.function_name"
        for url in urls.urlpatterns:
            if url.default_args == {'default_args': {'document_root': 'frontend/static/'}}:
                continue
            declared_module_name, declared_function_name = url.name.split(".")
            actual_callback_name = url.callback.__name__
            callback_module_name = url.callback.__module__.split(".")[-1]
            self.assertEqual(actual_callback_name, declared_function_name)
            self.assertEqual(declared_module_name, callback_module_name)


class TestAllEndpoints(CommonTestCase):
    
    EXCEPTIONS_ENDPOINTS = [
        # special case, these are manually tested
        "login_pages.validate_login",
        "login_pages.login_page",
        "admin_pages.logout_admin",
    ]
    
    EXCEPTIONS_TESTS = []
    
    @skip("too meta")
    def test(self):
        SEPARATOR = '\n\t'  # no special chars in the {} section of an f-string? okaysurewhatever.
        
        # a counter that can indicate "was not present".
        names_of_paths_counter = {path.name: 0 for path in urls.urlpatterns}
        
        # keep these imports local, don't pollute the global namespace, that may confuse the testrunner
        from tests import (test_endpoints, test_meta, test_models, test_security_models,
            test_tableau_api)
        # get all the tests and check that there is a test for every endpoint
        all_the_tests = []
        all_the_tests.extend(vars(test_endpoints).values())
        all_the_tests.extend(vars(test_models).values())
        all_the_tests.extend(vars(test_meta).values())
        all_the_tests.extend(vars(test_security_models).values())
        all_the_tests.extend(vars(test_tableau_api).values())
        
        # map of test class enpoinds to test classes
        test_classes_by_endpoint_name = {
            obj.ENDPOINT_NAME: obj
            for obj in all_the_tests
            if hasattr(obj, "ENDPOINT_NAME")
            and obj.ENDPOINT_NAME is not None
            and obj.ENDPOINT_NAME != SmartRequestsTestCase.IGNORE_THIS_ENDPOINT
        }

        for obj_endpoint_name in test_classes_by_endpoint_name.keys():
            if obj_endpoint_name in names_of_paths_counter:
                names_of_paths_counter[obj_endpoint_name] += 1
            else:
                names_of_paths_counter[obj_endpoint_name] = None
        
        has_no_tests = [
            endpoint_name for endpoint_name, count in names_of_paths_counter.items()
            if count == 0 and endpoint_name not in self.EXCEPTIONS_ENDPOINTS
        ]
        has_no_endpoint = [
            test_classes_by_endpoint_name[endpoint_name].__name__
            for endpoint_name, count in names_of_paths_counter.items()
            if count is None and endpoint_name not in self.EXCEPTIONS_TESTS
        ]
        
        msg = ""
        if has_no_endpoint:
            msg = msg + f"\nThese tests have no matching endpoint:\n\t{SEPARATOR.join(has_no_endpoint)}"
        if has_no_tests:
            msg = msg + f"\nThese endpoints have no tests:\n\t{SEPARATOR.join(has_no_tests)}"
        self.assertTrue(not has_no_tests and not has_no_endpoint, msg)
