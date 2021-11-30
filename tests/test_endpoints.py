import json
from copy import copy
from io import BytesIO
from typing import List
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from django.forms.fields import NullBooleanField
from django.http.response import FileResponse, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone

from api.tableau_api import FINAL_SERIALIZABLE_FIELD_NAMES
from config.jinja2 import easy_url
from constants.celery_constants import (ANDROID_FIREBASE_CREDENTIALS, BACKEND_FIREBASE_CREDENTIALS,
    IOS_FIREBASE_CREDENTIALS)
from constants.data_processing_constants import BEIWE_PROJECT_ROOT
from constants.data_stream_constants import ALL_DATA_STREAMS, SURVEY_TIMINGS
from constants.message_strings import (NEW_PASSWORD_8_LONG, NEW_PASSWORD_MISMATCH,
    NEW_PASSWORD_RULES_FAIL, PASSWORD_RESET_SUCCESS, TABLEAU_API_KEY_IS_DISABLED,
    TABLEAU_NO_MATCHING_API_KEY, WRONG_CURRENT_PASSWORD)
from constants.researcher_constants import ALL_RESEARCHER_TYPES, ResearcherRole
from constants.testing_constants import (ADMIN_ROLES, ALL_TESTING_ROLES, ANDROID_CERT, BACKEND_CERT,
    IOS_CERT, ResearcherRole)
from database.data_access_models import ChunkRegistry, FileToProcess
from database.profiling_models import DecryptionKeyError
from database.schedule_models import Intervention
from database.security_models import ApiKey
from database.study_models import DeviceSettings, Study, StudyField
from database.survey_models import Survey
from database.system_models import FileAsText
from database.user_models import Participant, ParticipantFCMHistory, Researcher
from libs.copy_study import format_study
from libs.encryption import get_RSA_cipher
from libs.security import generate_easy_alphanumeric_string
from tests.common import (BasicSessionTestCase, DataApiTest, ParticipantSessionTest,
    RedirectSessionApiTest, ResearcherSessionTest, SmartRequestsTestCase)
from tests.helpers import compare_dictionaries, DummyThreadPool


class TestLoginPages(BasicSessionTestCase):
    """ Basic authentication test, make sure that the machinery for logging a user
    in and out are functional at setting and clearing a session. """
    
    def test_load_login_page_while_not_logged_in(self):
        # make sure the login page loads without logging you in when it should not
        response = self.client.post(reverse("login_pages.login_page"))
        self.assertEqual(response.status_code, 200)
        # this should uniquely identify the login page
        self.assertIn(b'<form method="POST" action="/validate_login">', response.content)
    
    def test_load_login_page_while_logged_in(self):
        # make sure the login page loads without logging you in when it should not
        self.session_researcher  # create the default researcher
        self.do_default_login()
        response = self.client.post(reverse("login_pages.login_page"))
        self.assertEqual(response.status_code, 302)
        self.assert_resolve_equal(response.url, reverse("admin_pages.choose_study"))
        # this should uniquely identify the login page
        self.assertNotIn(b'<form method="POST" action="/validate_login">', response.content)
    
    def test_logging_in_success(self):
        self.session_researcher  # create the default researcher
        r = self.do_default_login()
        self.assertEqual(r.status_code, 302)
        self.assert_resolve_equal(r.url, reverse("admin_pages.choose_study"))
    
    def test_logging_in_fail(self):
        r = self.do_default_login()
        self.assertEqual(r.status_code, 302)
        self.assert_resolve_equal(r.url, reverse("login_pages.login_page"))
    
    def test_logging_out(self):
        # create the default researcher, login, logout, attempt going to main page,
        self.session_researcher
        self.do_default_login()
        self.client.get(reverse("admin_pages.logout_admin"))
        r = self.client.get(reverse("admin_pages.choose_study"))
        self.assertEqual(r.status_code, 302)
        self.assert_resolve_equal(r.url, reverse("login_pages.login_page"))


class TestChooseStudy(ResearcherSessionTest):
    ENDPOINT_NAME = "admin_pages.choose_study"
    
    def test_2_studies(self):
        study2 = self.generate_study("study2")
        self.set_session_study_relation(ResearcherRole.researcher)
        self.generate_study_relation(self.session_researcher, study2, ResearcherRole.researcher)
        resp = self.smart_get_status_code(200)
        self.assert_present(self.session_study.name, resp.content)
        self.assert_present(study2.name, resp.content)
    
    def test_1_study(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        resp = self.smart_get_status_code(302)
        self.assert_(resp.url, easy_url("admin_pages.view_study", study_id=self.session_study.id))
    
    def test_no_study(self):
        self.set_session_study_relation(None)
        resp = self.smart_get_status_code(200)
        self.assert_not_present(self.session_study.name, resp.content)


class TestViewStudy(ResearcherSessionTest):
    """ view_study is pretty simple, no custom content in the :
    tests push_notifications_enabled, is_site_admin, study.is_test, study.forest_enabled
    populates html elements with custom field values
    populates html elements of survey buttons
    """
    
    ENDPOINT_NAME = "admin_pages.view_study"
    
    def test_view_study_no_relation(self):
        self.smart_get_status_code(403, self.session_study.id)
    
    def test_view_study_researcher(self):
        study = self.session_study
        study.update(is_test=True)
        self.set_session_study_relation(ResearcherRole.researcher)
        response = self.smart_get_status_code(200, study.id)
        
        # template has several customizations, test for some relevant strings
        self.assertIn(b"This is a test study.", response.content)
        self.assertNotIn(b"This is a production study", response.content)
        study.update(is_test=False)
        
        response = self.smart_get_status_code(200, study.id)
        self.assertNotIn(b"This is a test study.", response.content)
        self.assertIn(b"This is a production study", response.content)
    
    def test_view_study_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self.smart_get_status_code(200, self.session_study.id)
    
    @patch('pages.admin_pages.check_firebase_instance')
    def test_view_study_site_admin(self, check_firebase_instance: MagicMock):
        study = self.session_study
        self.set_session_study_relation(ResearcherRole.site_admin)
        
        # test rendering with several specifc values set to observe the rendering changes
        study.update(forest_enabled=False)
        check_firebase_instance.return_value = False
        response = self.smart_get_status_code(200, study.id)
        self.assertNotIn(b"Edit interventions for this study", response.content)
        self.assertNotIn(b"View Forest Task Log", response.content)
        
        check_firebase_instance.return_value = True
        study.update(forest_enabled=True)
        response = self.smart_get_status_code(200, study.id)
        self.assertIn(b"Edit interventions for this study", response.content)
        self.assertIn(b"View Forest Task Log", response.content)
        # assertInHTML is several hundred times slower but has much better output when it fails...
        # self.assertInHTML("Edit interventions for this study", response.content.decode())


class TestManageCredentials(ResearcherSessionTest):
    ENDPOINT_NAME = "admin_pages.manage_credentials"
    
    def test_manage_credentials(self):
        self.session_study
        self.smart_get_status_code(200)
        api_key = ApiKey.generate(
            researcher=self.session_researcher,
            has_tableau_api_permissions=True,
            readable_name="not important",
        )
        response = self.smart_get_status_code(200)
        self.assert_present(api_key.access_key_id, response.content)


class TestResetAdminPassword(RedirectSessionApiTest):
    # test for every case and messages present on the page
    ENDPOINT_NAME = "admin_pages.reset_admin_password"
    REDIRECT_ENDPOINT_NAME = "admin_pages.manage_credentials"
    
    def test_reset_admin_password_success(self):
        self.smart_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD,
            new_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
            confirm_new_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
        )
        # we are ... teleologically correct here mimicking the code...
        researcher = self.session_researcher
        self.assertFalse(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD + "1"))
        # Always stick the check for the string after the check for the db mutation.
        self.assert_present(PASSWORD_RESET_SUCCESS, self.get_redirect_content())
    
    def test_reset_admin_password_wrong(self):
        self.smart_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
            new_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
            confirm_new_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
        )
        researcher = self.session_researcher
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertFalse(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD + "1"))
        self.assert_present(WRONG_CURRENT_PASSWORD, self.get_redirect_content())
    
    def test_reset_admin_password_rules_fail(self):
        non_default = "abcdefghijklmnop"
        self.smart_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD,
            new_password=non_default,
            confirm_new_password=non_default,
        )
        researcher = self.session_researcher
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertFalse(researcher.check_password(researcher.username, non_default))
        self.assert_present(NEW_PASSWORD_RULES_FAIL, self.get_redirect_content())
    
    def test_reset_admin_password_too_short(self):
        non_default = "a1#"
        self.smart_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD,
            new_password=non_default,
            confirm_new_password=non_default,
        )
        researcher = self.session_researcher
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertFalse(researcher.check_password(researcher.username, non_default))
        self.assert_present(NEW_PASSWORD_8_LONG, self.get_redirect_content())
    
    def test_reset_admin_password_mismatch(self):
        # has to pass the length and character checks
        self.smart_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD,
            new_password="aA1#aA1#aA1#",
            confirm_new_password="aA1#aA1#aA1#aA1#",
        )
        researcher = self.session_researcher
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertFalse(researcher.check_password(researcher.username, "aA1#aA1#aA1#"))
        self.assertFalse(researcher.check_password(researcher.username, "aA1#aA1#aA1#aA1#"))
        self.assert_present(NEW_PASSWORD_MISMATCH, self.get_redirect_content())


class TestResetDownloadApiCredentials(RedirectSessionApiTest):
    ENDPOINT_NAME = "admin_pages.reset_download_api_credentials"
    REDIRECT_ENDPOINT_NAME = "admin_pages.manage_credentials"
    
    def test_reset(self):
        self.assertIsNone(self.session_researcher.access_key_id)
        self.smart_post()
        self.session_researcher.refresh_from_db()
        self.assertIsNotNone(self.session_researcher.access_key_id)
        self.assert_present("Your Data-Download API access credentials have been reset",
                             self.get_redirect_content())


class TestNewTableauApiKey(RedirectSessionApiTest):
    ENDPOINT_NAME = "admin_pages.new_tableau_api_key"
    REDIRECT_ENDPOINT_NAME = "admin_pages.manage_credentials"
    
    # FIXME: when NewApiKeyForm does anything develop a test for naming the key, probably more.
    #  (need to review the tableau tests)
    def test_reset(self):
        self.assertIsNone(self.session_researcher.api_keys.first())
        self.smart_post()
        self.assertIsNotNone(self.session_researcher.api_keys.first())
        self.assert_present("New Tableau API credentials have been generated for you",
                             self.get_redirect_content())


# admin_pages.disable_tableau_api_key
class TestDisableTableauApiKey(RedirectSessionApiTest):
    ENDPOINT_NAME = "admin_pages.disable_tableau_api_key"
    REDIRECT_ENDPOINT_NAME = "admin_pages.manage_credentials"
    
    def test_disable_success(self):
        # basic test
        api_key = ApiKey.generate(
            researcher=self.session_researcher,
            has_tableau_api_permissions=True,
            readable_name="something",
        )
        self.smart_post(api_key_id=api_key.access_key_id)
        self.assertFalse(self.session_researcher.api_keys.first().is_active)
        content = self.get_redirect_content()
        self.assert_present(api_key.access_key_id, content)
        self.assert_present("is now disabled", content)
    
    def test_no_match(self):
        # fail with empty and fail with success
        self.smart_post(api_key_id="abc")
        self.assert_present(TABLEAU_NO_MATCHING_API_KEY, self.get_redirect_content())
        api_key = ApiKey.generate(
            researcher=self.session_researcher,
            has_tableau_api_permissions=True,
            readable_name="something",
        )
        self.smart_post(api_key_id="abc")
        api_key.refresh_from_db()
        self.assertTrue(api_key.is_active)
        self.assert_present(TABLEAU_NO_MATCHING_API_KEY, self.get_redirect_content())
    
    def test_already_disabled(self):
        api_key = ApiKey.generate(
            researcher=self.session_researcher,
            has_tableau_api_permissions=True,
            readable_name="something",
        )
        api_key.update(is_active=False)
        self.smart_post(api_key_id=api_key.access_key_id)
        api_key.refresh_from_db()
        self.assertFalse(api_key.is_active)
        self.assert_present(TABLEAU_API_KEY_IS_DISABLED, self.get_redirect_content())


class TestDashboard(ResearcherSessionTest):
    ENDPOINT_NAME = "dashboard_api.dashboard_page"
    
    def test_dashboard(self):
        # default user and default study already instantiated
        self.set_session_study_relation(ResearcherRole.researcher)
        resp = self.smart_get_status_code(200, str(self.session_study.id))
        self.assert_present("Choose a participant or data stream to view", resp.content)


# FIXME: dashboard is going to require a fixture to populate data.
class TestDashboardStream(ResearcherSessionTest):
    ENDPOINT_NAME = "dashboard_api.get_data_for_dashboard_datastream_display"
    
    # this  url doesn't fit any helpers I've built yet
    # dashboard_api.get_data_for_dashboard_datastream_display
    def test_data_streams(self):
        # test is currently limited to rendering the page for each data stream but with no data in it
        self.set_session_study_relation()
        for data_stream in ALL_DATA_STREAMS:
            self.smart_get_status_code(200, self.session_study.id, data_stream)


# FIXME: this page renders with almost no data
class TestPatientDisplay(ResearcherSessionTest):
    ENDPOINT_NAME = "dashboard_api.dashboard_participant_page"
    
    def test_patient_display(self):
        self.set_session_study_relation()
        self.smart_get_status_code(200, self.session_study.id, self.default_participant.patient_id)


# system_admin_pages.manage_researchers
class TestManageResearchers(ResearcherSessionTest):
    ENDPOINT_NAME = "system_admin_pages.manage_researchers"
    
    def test_researcher(self):
        self.smart_get_status_code(403)
    
    def test_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self.smart_get_status_code(200)
    
    def test_site_admin(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        self.smart_get_status_code(200)
    
    def test_render_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self._test_render_with_researchers()
        # make sure that site admins are not present
        r4 = self.generate_researcher(relation_to_session_study=ResearcherRole.site_admin)
        resp = self.smart_get_status_code(200)
        self.assert_not_present(r4.username, resp.content)
        
        # make sure that unaffiliated researchers are not present
        r5 = self.generate_researcher()
        resp = self.smart_get_status_code(200)
        self.assert_not_present(r5.username, resp.content)
    
    def test_render_site_admin(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        self._test_render_with_researchers()
        # make sure that site admins ARE present
        r4 = self.generate_researcher(relation_to_session_study=ResearcherRole.site_admin)
        resp = self.smart_get_status_code(200)
        self.assert_present(r4.username, resp.content)
        
        # make sure that unaffiliated researchers ARE present
        r5 = self.generate_researcher()
        resp = self.smart_get_status_code(200)
        self.assert_present(r5.username, resp.content)
    
    def _test_render_with_researchers(self):
        # render the page with a regular user
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.researcher)
        resp = self.smart_get_status_code(200)
        self.assert_present(r2.username, resp.content)
        
        # render with 2 reseaorchers
        r3 = self.generate_researcher(relation_to_session_study=ResearcherRole.researcher)
        resp = self.smart_get_status_code(200)
        self.assert_present(r2.username, resp.content)
        self.assert_present(r3.username, resp.content)


class TestEditResearcher(ResearcherSessionTest):
    ENDPOINT_NAME = "system_admin_pages.edit_researcher"
    
    # render self
    def test_render_for_self_as_researcher(self):
        # should fail
        self.set_session_study_relation()
        self.smart_get_status_code(403, self.session_researcher.id)
    
    def test_render_for_self_as_study_admin(self):
        # ensure it renders (buttons will be disabled)
        self.set_session_study_relation(ResearcherRole.study_admin)
        self.smart_get_status_code(200, self.session_researcher.id)
    
    def test_render_for_self_as_site_admin(self):
        # ensure it renders (buttons will be disabled)
        self.set_session_study_relation(ResearcherRole.site_admin)
        self.smart_get_status_code(200, self.session_researcher.id)
    
    def test_render_for_researcher_as_researcher(self):
        # should fail
        self.set_session_study_relation()
        # set up, test when not on study
        r2 = self.generate_researcher()
        resp = self.smart_get_status_code(403, r2.id)
        self.assert_not_present(r2.username, resp.content)
        # attach other researcher and try again
        self.generate_study_relation(r2, self.session_study, ResearcherRole.researcher)
        resp = self.smart_get_status_code(403, r2.id)
        self.assert_not_present(r2.username, resp.content)
    
    # study admin, renders
    def test_render_valid_researcher_as_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self._test_render_generic_under_study()
    
    def test_render_researcher_with_no_study_as_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self._test_render_researcher_with_no_study()
    
    # site admin, renders
    def test_render_valid_researcher_as_site_admin(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        self._test_render_generic_under_study()
    
    def test_render_researcher_with_no_study_as_site_admin(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        self._test_render_researcher_with_no_study()
    
    def _test_render_generic_under_study(self):
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.researcher)
        resp = self.smart_get_status_code(200, r2.id)
        self.assert_present(r2.username, resp.content)
    
    def _test_render_researcher_with_no_study(self):
        r2 = self.generate_researcher()
        resp = self.smart_get_status_code(200, r2.id)
        self.assert_present(r2.username, resp.content)


class TestElevateResearcher(ResearcherSessionTest):
    ENDPOINT_NAME = "system_admin_pages.elevate_researcher"
    # (this one is tedious.)
    
    def test_self_as_researcher_on_study(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        self.smart_post_status_code(
            403, researcher_id=self.session_researcher.id, study_id=self.session_study.id
        )
    
    def test_self_as_study_admin_on_study(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self.smart_post_status_code(
            403, researcher_id=self.session_researcher.id, study_id=self.session_study.id
        )
    
    def test_researcher_as_study_admin_on_study(self):
        # this is the only case that succeeds
        self.set_session_study_relation(ResearcherRole.study_admin)
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.researcher)
        self.smart_post_status_code(302, researcher_id=r2.id, study_id=self.session_study.id)
        self.assertEqual(r2.study_relations.get().relationship, ResearcherRole.study_admin)
    
    def test_study_admin_as_study_admin_on_study(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.study_admin)
        self.smart_post_status_code(403, researcher_id=r2.id, study_id=self.session_study.id)
        self.assertEqual(r2.study_relations.get().relationship, ResearcherRole.study_admin)
    
    def test_site_admin_as_study_admin_on_study(self):
        self.session_researcher
        self.set_session_study_relation(ResearcherRole.study_admin)
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.site_admin)
        self.smart_post_status_code(403, researcher_id=r2.id, study_id=self.session_study.id)
        self.assertFalse(r2.study_relations.filter(study=self.session_study).exists())
    
    def test_site_admin_as_site_admin(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.site_admin)
        self.smart_post_status_code(403, researcher_id=r2.id, study_id=self.session_study.id)
        self.assertFalse(r2.study_relations.filter(study=self.session_study).exists())


class TestDemoteStudyAdmin(ResearcherSessionTest):
    # FIXME: this endpoint does not test for site admin cases correctly, the test passes but is
    # wrong. Behavior is fine because it has no relevant side effects except for the know bug where
    # site admins need to be manually added to a study before being able to download data.
    ENDPOINT_NAME = "system_admin_pages.demote_study_admin"
    
    def test_researcher_as_researcher(self):
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.researcher)
        self.smart_post_status_code(403, researcher_id=r2.id, study_id=self.session_study.id)
        self.assertEqual(r2.study_relations.get().relationship, ResearcherRole.researcher)
    
    def test_researcher_as_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.researcher)
        self.smart_post_status_code(302, researcher_id=r2.id, study_id=self.session_study.id)
        self.assertEqual(r2.study_relations.get().relationship, ResearcherRole.researcher)
    
    def test_study_admin_as_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.study_admin)
        self.smart_post_status_code(302, researcher_id=r2.id, study_id=self.session_study.id)
        self.assertEqual(r2.study_relations.get().relationship, ResearcherRole.researcher)
    
    def test_site_admin_as_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.site_admin)
        self.smart_post_status_code(302, researcher_id=r2.id, study_id=self.session_study.id)
        self.assertFalse(r2.study_relations.exists())
        r2.refresh_from_db()
        self.assertTrue(r2.site_admin)
    
    def test_site_admin_as_site_admin(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.site_admin)
        self.smart_post_status_code(302, researcher_id=r2.id, study_id=self.session_study.id)
        self.assertFalse(r2.study_relations.exists())
        r2.refresh_from_db()
        self.assertTrue(r2.site_admin)


class TestCreateNewResearcher(ResearcherSessionTest):
    """ Admins should be able to create and load the page. """
    ENDPOINT_NAME = "system_admin_pages.create_new_researcher"
    
    def test_load_page_at_endpoint(self):
        # This test should be transformed into a separate endpoint
        for user_role in ALL_RESEARCHER_TYPES:
            prior_researcher_count = Researcher.objects.count()
            self.assign_role(self.session_researcher, user_role)
            resp = self.smart_get()
            if user_role in ADMIN_ROLES:
                self.assertEqual(resp.status_code, 200)
            else:
                self.assertEqual(resp.status_code, 403)
            self.assertEqual(prior_researcher_count, Researcher.objects.count())
    
    def test_create_researcher(self):
        for user_role in ALL_RESEARCHER_TYPES:
            prior_researcher_count = Researcher.objects.count()
            self.assign_role(self.session_researcher, user_role)
            username = generate_easy_alphanumeric_string()
            password = generate_easy_alphanumeric_string()
            resp = self.smart_post(admin_id=username, password=password)
            
            if user_role in ADMIN_ROLES:
                self.assertEqual(resp.status_code, 302)
                self.assertEqual(prior_researcher_count + 1, Researcher.objects.count())
                self.assertTrue(Researcher.check_password(username, password))
            else:
                self.assertEqual(resp.status_code, 403)
                self.assertEqual(prior_researcher_count, Researcher.objects.count())


class TestManageStudies(ResearcherSessionTest):
    """ All we do with this page is make sure it loads... there isn't much to hook onto and
    determine a failure or a success... the study names are always present in the json on the
    html... """
    ENDPOINT_NAME = "system_admin_pages.manage_studies"
    
    def test(self):
        for user_role in ALL_TESTING_ROLES:
            self.assign_role(self.session_researcher, user_role)
            resp = self.smart_get()
            if user_role in ADMIN_ROLES:
                self.assertEqual(resp.status_code, 200)
            else:
                self.assertEqual(resp.status_code, 403)


class TestEditStudy(ResearcherSessionTest):
    """ Test basics of permissions, test details of the study are appropriately present on page... """
    ENDPOINT_NAME = "system_admin_pages.edit_study"
    
    def test_only_admins_allowed(self):
        for user_role in ALL_TESTING_ROLES:
            self.assign_role(self.session_researcher, user_role)
            self.smart_get_status_code(
                200 if user_role in ADMIN_ROLES else 403,
                self.session_study.id
            )
    
    def test_content_study_admin(self):
        """ tests that various important pieces of information are present """
        self.set_session_study_relation(ResearcherRole.study_admin)
        self.session_study.update(is_test=True, forest_enabled=False)
        resp = self.smart_get_status_code(200, self.session_study.id)
        self.assert_present("Forest is currently disabled.", resp.content)
        self.assert_present("This is a test study", resp.content)
        self.assert_present(self.session_researcher.username, resp.content)
        
        self.session_study.update(is_test=False, forest_enabled=True)
        r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.researcher)
        
        resp = self.smart_get_status_code(200, self.session_study.id)
        self.assert_present(self.session_researcher.username, resp.content)
        self.assert_present(r2.username, resp.content)
        self.assert_present("Forest is currently enabled.", resp.content)
        self.assert_present("This is a production study", resp.content)


# FIXME: need to implement tests for copy study.
# FIXME: this test is not well factored, it doesn't follow a common pattern.
class TestCreateStudy(ResearcherSessionTest):
    ENDPOINT_NAME = "system_admin_pages.create_study"
    NEW_STUDY_NAME = "something anything"
    
    @property
    def get_the_new_study(self):
        return Study.objects.get(name=self.NEW_STUDY_NAME)
    
    def create_study_params(self, *except_these: List[str]):
        """ keys are: name, encryption_key, is_test, copy_existing_study, forest_enabled """
        params = dict(
            name=self.NEW_STUDY_NAME,
            encryption_key="a" * 32,
            is_test="true",
            copy_existing_study="",
            forest_enabled="false",
        )
        for k in except_these:
            params.pop(k)
        return params
    
    def test_load_page(self):
        # only site admins can load the page
        for user_role in ALL_TESTING_ROLES:
            self.assign_role(self.session_researcher, user_role)
            self.smart_post_status_code(302 if user_role == ResearcherRole.site_admin else 403)
    
    def test_create_study_success(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        resp = self.smart_post_status_code(302, **self.create_study_params())
        self.assertIsInstance(resp, HttpResponseRedirect)
        target_url = easy_url(
            "system_admin_pages.device_settings", study_id=self.get_the_new_study.id
        )
        self.assert_resolve_equal(resp.url, target_url)
        resp = self.client.get(target_url)
        self.assertEqual(resp.status_code, 200)
        self.assert_present(f"Successfully created study {self.get_the_new_study.name}.", resp.content)
    
    def test_create_study_long_name(self):
        # this situation reports to sentry manually, the response is a hard 400, no calls to messages
        self.set_session_study_relation(ResearcherRole.site_admin)
        params = self.create_study_params()
        params["name"] = "a"*10000
        resp = self.smart_post_status_code(400, **params)
        self.assertEqual(resp.content, b"")
    
    def test_create_study_bad_name(self):
        # this situation reports to sentry manually, the response is a hard 400, no calls to messages
        self.set_session_study_relation(ResearcherRole.site_admin)
        params = self.create_study_params()
        params["name"] = "&" * 50
        resp = self.smart_post_status_code(400, **params)
        self.assertEqual(resp.content, b"")


# FIXME: this test has the annoying un-factored url with post params and url params
class TestToggleForest(RedirectSessionApiTest):
    ENDPOINT_NAME = "system_admin_pages.toggle_study_forest_enabled"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.edit_study"
    
    def test_toggle_on(self):
        resp = self._do_test_toggle(True)
        self.assert_present("Enabled Forest on", resp.content)
    
    def test_toggle_off(self):
        resp = self._do_test_toggle(False)
        self.assert_present("Disabled Forest on", resp.content)
    
    def _do_test_toggle(self, enable: bool):
        redirect_endpoint = easy_url(self.REDIRECT_ENDPOINT_NAME, study_id=self.session_study.id)
        self.set_session_study_relation(ResearcherRole.site_admin)
        self.session_study.update(forest_enabled=not enable)  # directly mutate the database.
        # resp = self.smart_post(study_id=self.session_study.id)  # nope this does not follow the normal pattern
        resp = self.smart_post(self.session_study.id)
        self.assert_resolve_equal(resp.url, redirect_endpoint)
        self.session_study.refresh_from_db()
        if enable:
            self.assertTrue(self.session_study.forest_enabled)
        else:
            self.assertFalse(self.session_study.forest_enabled)
        return self.client.get(redirect_endpoint)


# FIXME: this test has the annoying un-factored url with post params and url params
class TestDeleteStudy(RedirectSessionApiTest):
    ENDPOINT_NAME = "system_admin_pages.delete_study"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.manage_studies"
    
    def test_success(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        resp = self.smart_post(self.session_study.id, confirmation="true")
        self.session_study.refresh_from_db()
        self.assertTrue(self.session_study.deleted)
        self.assertEqual(resp.url, easy_url(self.REDIRECT_ENDPOINT_NAME))
        self.assert_present("Deleted study ", self.get_redirect_content())


class TestDeviceSettings(ResearcherSessionTest):
    ENDPOINT_NAME = "system_admin_pages.device_settings"
    
    CONSENT_SECTIONS = {
        'consent_sections.data_gathering.more': 'a',
        'consent_sections.data_gathering.text': 'b',
        'consent_sections.privacy.more': 'c',
        'consent_sections.privacy.text': 'd',
        'consent_sections.study_survey.more': 'e',
        'consent_sections.study_survey.text': 'f',
        'consent_sections.study_tasks.more': 'g',
        'consent_sections.study_tasks.text': 'h',
        'consent_sections.time_commitment.more': 'i',
        'consent_sections.time_commitment.text': 'j',
        'consent_sections.welcome.more': 'k',
        'consent_sections.welcome.text': 'l',
        'consent_sections.withdrawing.more': 'm',
        'consent_sections.withdrawing.text': 'n',
    }
    
    BOOLEAN_FIELD_NAMES = [
        field.name
        for field in DeviceSettings._meta.fields
        if isinstance(field, (models.BooleanField, NullBooleanField))
    ]
    
    def invert_boolean_checkbox_fields(self, some_dict):
        for field in self.BOOLEAN_FIELD_NAMES:
            if field in some_dict and bool(some_dict[field]):
                some_dict.pop(field)
            else:
                some_dict[field] = "true"
    
    def test_get(self):
        for role in ALL_TESTING_ROLES:
            self.assign_role(self.session_researcher, role)
            resp = self.smart_get(self.session_study.id)
            self.assertEqual(resp.status_code, 200 if role is not None else 403)
    
    def test_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self.do_test_update()
    
    def test_site_admin(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        self.do_test_update()
    
    def do_test_update(self):
        """ This test mimics the frontend input (checkboxes are a little strange and require setup).
        The test mutates all fields in the input that is sent to the backend, and confirms that every
        field pushed changed. """
        
        # extract data from database (it is all default values, unpacking jsonstrings)
        # created_on and last_updated are already absent
        post_params = self.session_device_settings.as_unpacked_native_python()
        old_device_settings = copy(post_params)
        post_params.pop("id")
        post_params.pop("consent_sections")  # this is not present in the form
        post_params.update(**self.CONSENT_SECTIONS)
        
        # mutate everything
        post_params = {k: self.mutate_variable(v, ignore_bools=True) for k, v in post_params.items()}
        self.invert_boolean_checkbox_fields(post_params)
        
        # Hit endpoint
        self.smart_post_status_code(302, self.session_study.id, **post_params)
        
        # Test database update, get new data, extract consent sections.
        self.assertEqual(DeviceSettings.objects.count(), 1)
        new_device_settings = DeviceSettings.objects.first().as_unpacked_native_python()
        new_device_settings.pop("id")
        old_consent_sections = old_device_settings.pop("consent_sections")
        new_consent_sections = new_device_settings.pop("consent_sections")
        
        for k, v in new_device_settings.items():
            # boolean values are set to true or false based on presence in the post request,
            # that's how checkboxes work.
            if k in self.BOOLEAN_FIELD_NAMES:
                if k not in post_params:
                    self.assertFalse(v)
                    self.assertTrue(old_device_settings[k])
                else:
                    self.assertTrue(v)
                    self.assertFalse(old_device_settings[k])
                continue
            
            # print(f"key: '{k}', DB: {type(v)}'{v}', post param: {type(post_params[k])} '{post_params[k]}'")
            self.assertEqual(v, post_params[k])
            self.assertNotEqual(v, old_device_settings[k])
        
        # FIXME: why does this fail?
        # Consent sections need to be unpacked, ensure they have the keys
        # self.assertEqual(set(old_consent_sections.keys()), set(new_consent_sections.keys()))
        
        for outer_key, a_dict_of_two_values in new_consent_sections.items():
            # this data structure is of the form:  {'more': 'aaaa', 'text': 'baaa'}
            self.assertEqual(len(a_dict_of_two_values), 2)
            
            # compare the inner values of every key, make sure they differ
            for inner_key, v2 in a_dict_of_two_values.items():
                self.assertNotEqual(old_consent_sections[outer_key][inner_key], v2)


class TestManageFirebaseCredentials(ResearcherSessionTest):
    ENDPOINT_NAME = "system_admin_pages.manage_firebase_credentials"
    
    def test(self):
        # just test that the page loads, I guess
        self.set_session_study_relation(ResearcherRole.site_admin)
        self.smart_get_status_code(200)


# FIXME: implement tests for error cases
class TestUploadBackendFirebaseCert(RedirectSessionApiTest):
    ENDPOINT_NAME = "system_admin_pages.upload_backend_firebase_cert"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.manage_firebase_credentials"
    
    @patch("pages.system_admin_pages.update_firebase_instance")
    @patch("pages.system_admin_pages.get_firebase_credential_errors")
    def test(self, get_firebase_credential_errors: MagicMock, update_firebase_instance: MagicMock):
        # test that the data makes it to the backend, patch out the errors that are sourced from the
        # firbase admin lbrary
        get_firebase_credential_errors.return_value = None
        update_firebase_instance.return_value = True
        # test upload as site admin
        self.set_session_study_relation(ResearcherRole.site_admin)
        file = SimpleUploadedFile("backend_cert.json", BACKEND_CERT.encode(), "text/json")
        self.smart_post(backend_firebase_cert=file)
        resp_content = self.get_redirect_content()
        self.assert_present("New firebase credentials have been received", resp_content)


# FIXME: implement tests for error cases
class TestUploadIosFirebaseCert(RedirectSessionApiTest):
    ENDPOINT_NAME = "system_admin_pages.upload_ios_firebase_cert"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.manage_firebase_credentials"
    
    def test(self):
        # test upload as site admin
        self.set_session_study_relation(ResearcherRole.site_admin)
        file = SimpleUploadedFile("ios_firebase_cert.plist", IOS_CERT.encode(), "text/json")
        self.smart_post(ios_firebase_cert=file)
        resp_content = self.get_redirect_content()
        self.assert_present("New IOS credentials were received", resp_content)


# FIXME: implement tests for error cases
class TestUploadAndroidFirebaseCert(RedirectSessionApiTest):
    ENDPOINT_NAME = "system_admin_pages.upload_android_firebase_cert"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.manage_firebase_credentials"
    
    def test(self):
        # test upload as site admin
        self.set_session_study_relation(ResearcherRole.site_admin)
        file = SimpleUploadedFile("android_firebase_cert.json", ANDROID_CERT.encode(), "text/json")
        self.smart_post(android_firebase_cert=file)
        resp_content = self.get_redirect_content()
        self.assert_present("New android credentials were received", resp_content)


class TestDeleteFirebaseBackendCert(RedirectSessionApiTest):
    ENDPOINT_NAME = "system_admin_pages.delete_backend_firebase_cert"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.manage_firebase_credentials"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        FileAsText.objects.create(tag=BACKEND_FIREBASE_CREDENTIALS, text="any_string")
        self.smart_post()
        self.assertFalse(FileAsText.objects.exists())


class TestDeleteFirebaseIosCert(RedirectSessionApiTest):
    ENDPOINT_NAME = "system_admin_pages.delete_ios_firebase_cert"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.manage_firebase_credentials"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        FileAsText.objects.create(tag=IOS_FIREBASE_CREDENTIALS, text="any_string")
        self.smart_post()
        self.assertFalse(FileAsText.objects.exists())


class TestDeleteFirebaseAndroidCert(RedirectSessionApiTest):
    ENDPOINT_NAME = "system_admin_pages.delete_android_firebase_cert"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.manage_firebase_credentials"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        FileAsText.objects.create(tag=ANDROID_FIREBASE_CREDENTIALS, text="any_string")
        self.smart_post()
        self.assertFalse(FileAsText.objects.exists())


class TestDataAccessWebFormPage(ResearcherSessionTest):
    ENDPOINT_NAME = "data_access_web_form.data_api_web_form_page"
    
    def test(self):
        resp = self.smart_get()
        self.assert_present("Reset Data-Download API Access Credentials", resp.content)
        id_key, secret_key = self.session_researcher.reset_access_credentials()
        resp = self.smart_get()
        self.assert_not_present("Reset Data-Download API Access Credentials", resp.content)


class TestPipelineWebFormPage(ResearcherSessionTest):
    ENDPOINT_NAME = "data_access_web_form.pipeline_download_page"
    
    def test(self):
        resp = self.smart_get()
        self.assert_present("Reset Data-Download API Access Credentials", resp.content)
        id_key, secret_key = self.session_researcher.reset_access_credentials()
        resp = self.smart_get()
        self.assert_not_present("Reset Data-Download API Access Credentials", resp.content)


# FIXME: add error cases to this test
class TestSetStudyTimezone(RedirectSessionApiTest):
    ENDPOINT_NAME = "admin_api.set_study_timezone"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.edit_study"
    
    def test_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self._test_success()
    
    def test_site_admin(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        self._test_success()
    
    def _test_success(self):
        self.smart_post(self.session_study.id, new_timezone_name="Pacific/Noumea")
        self.session_study.refresh_from_db()
        self.assertEqual(self.session_study.timezone_name, "Pacific/Noumea")


class TestAddResearcherToStudy(ResearcherSessionTest):
    ENDPOINT_NAME = "admin_api.add_researcher_to_study"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.edit_study"
    
    def test_site_admin(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        self._test(None, 302, ResearcherRole.researcher)
        self._test(ResearcherRole.study_admin, 302, ResearcherRole.study_admin)
        self._test(ResearcherRole.researcher, 302, ResearcherRole.researcher)
    
    # # FIXME: test fails, need to fix data download bug on site admin users first
    # def test_site_admin_on_site_admin(self):
    #     self.set_session_study_relation(ResearcherRole.site_admin)
    #     self._test(ResearcherRole.site_admin, 403, ResearcherRole.site_admin)
    
    def test_study_admin_on_none(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self._test(None, 302, ResearcherRole.researcher)
    
    def test_study_admin_on_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self._test(ResearcherRole.study_admin, 302, ResearcherRole.study_admin)
    
    def test_study_admin_on_researcher(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self._test(ResearcherRole.researcher, 302, ResearcherRole.researcher)
    
    # FIXME: test fails, need to fix data download bug on site admin users first
    # def test_study_admin_on_site_admin(self):
    #     self.set_session_study_relation(ResearcherRole.study_admin)
    #     self._test(ResearcherRole.site_admin, 403, ResearcherRole.site_admin)
    
    def test_researcher(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        self._test(ResearcherRole.researcher, 403, ResearcherRole.researcher)
        self._test(ResearcherRole.study_admin, 403, ResearcherRole.study_admin)
        self._test(None, 403, None)
        self._test(ResearcherRole.site_admin, 403, ResearcherRole.site_admin)
    
    def _test(self, r2_starting_relation, status_code, desired_relation):
        # setup researcher, do the post request
        r2 = self.generate_researcher(relation_to_session_study=r2_starting_relation)
        redirect_or_response = self.smart_post(
            study_id=self.session_study.id,
            researcher_id=r2.id,
            redirect_url=f"/edit_study/{self.session_study.id}"
        )
        # check status code, relation, and ~the redirect url.
        r2.refresh_from_db()
        self.assert_researcher_relation(r2, self.session_study, desired_relation)
        self.assertEqual(redirect_or_response.status_code, status_code)
        if isinstance(redirect_or_response, HttpResponseRedirect):
            self.assertEqual(redirect_or_response.url, f"/edit_study/{self.session_study.id}")


class TestRemoveResearcherFromStudy(ResearcherSessionTest):
    ENDPOINT_NAME = "admin_api.remove_researcher_from_study"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.edit_study"
    
    def test_site_admin(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        self._test(None, 302)
        self._test(ResearcherRole.study_admin, 302)
        self._test(ResearcherRole.researcher, 302)
        self._test(ResearcherRole.site_admin, 302)
    
    def test_study_admin(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self._test(None, 403)
        self._test(ResearcherRole.study_admin, 403)
        self._test(ResearcherRole.researcher, 302)
        self._test(ResearcherRole.site_admin, 403)
    
    def test_researcher(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        r2 = self.generate_researcher(relation_to_session_study=None)
        self.smart_post_status_code(
            403,
            study_id=self.session_study.id,
            researcher_id=r2.id,
            redirect_url=f"/edit_study/{self.session_study.id}"
        )
    
    def _test(self, r2_starting_relation, status_code):
        if r2_starting_relation == ResearcherRole.site_admin:
            r2 = self.generate_researcher(relation_to_session_study=ResearcherRole.site_admin)
        else:
            r2 = self.generate_researcher(relation_to_session_study=r2_starting_relation)
        redirect = self.smart_post(
            study_id=self.session_study.id,
            researcher_id=r2.id,
            redirect_url=f"/edit_study/{self.session_study.id}"
        )
        # needs to be a None at the end
        self.assertEqual(redirect.status_code, status_code)
        if isinstance(redirect, HttpResponseRedirect):
            self.assert_researcher_relation(r2, self.session_study, None)
            self.assertEqual(redirect.url, f"/edit_study/{self.session_study.id}")


class TestDeleteResearcher(ResearcherSessionTest):
    ENDPOINT_NAME = "admin_api.delete_researcher"
    
    def test_site_admin(self):
        self._test(302, ResearcherRole.site_admin, True)
    
    def test_study_admin(self):
        self._test(403, ResearcherRole.study_admin, False)
    
    def test_researcher(self):
        self._test(403, ResearcherRole.researcher, False)
    
    def test_no_relation(self):
        self._test(403, None, False)
    
    def test_nonexistent(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        # 0 is not a valid database key.
        self.smart_post_status_code(404, 0)
    
    def _test(self, status_code: int, relation: str, success: bool):
        self.set_session_study_relation(relation)
        r2 = self.generate_researcher()
        resp = self.smart_post_status_code(status_code, r2.id)
        self.assertEqual(Researcher.objects.filter(id=r2.id).count(), 0 if success else 1)


# FIXME: add failure case tests, user type tests
class TestSetResearcherPassword(ResearcherSessionTest):
    ENDPOINT_NAME = "admin_api.set_researcher_password"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        r2 = self.generate_researcher()
        self.smart_post(
            researcher_id=r2.id,
            password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
        )
        # we are ... teleologically correct here mimicking the code...
        r2.refresh_from_db()
        self.assertTrue(
            r2.check_password(r2.username, self.DEFAULT_RESEARCHER_PASSWORD + "1")
        )
        self.assertFalse(
            r2.check_password(r2.username, self.DEFAULT_RESEARCHER_PASSWORD)
        )


# fixme: add user type tests
class TestRenameStudy(RedirectSessionApiTest):
    ENDPOINT_NAME = "admin_api.rename_study"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.edit_study"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.site_admin)
        self.smart_post(self.session_study.id, new_study_name="hello!")
        self.session_study.refresh_from_db()
        self.assertEqual(self.session_study.name, "hello!")


class TestDownloadPage(ResearcherSessionTest):
    ENDPOINT_NAME = "admin_api.download_page"
    
    def test(self):
        # just test that it loads without breaking
        self.smart_get()


class TestPrivacyPolicy(ResearcherSessionTest):
    ENDPOINT_NAME = "admin_api.download_privacy_policy"
    
    def test(self):
        # just test that it loads without breaking
        redirect = self.smart_get()
        self.assertIsInstance(redirect, HttpResponseRedirect)


# FIXME: implpment this test beyond "it doesn't crash", and there is a known bug to follow up on too.
class TestStudyParticipantApi(ResearcherSessionTest):
    ENDPOINT_NAME = "study_api.study_participants_api"
    
    COLUMN_ORDER_KEY = "order[0][column]"
    ORDER_DIRECTION_KEY = "order[0][dir]"
    SEARCH_PARAMETER = "search[value]"
    
    @property
    def DEFAULT_PARAMETERS(self):
        return {
            "draw": 1,
            "start": 0,
            "length": 10,
            # sort, sort order, search term
            self.COLUMN_ORDER_KEY: 1,
            self.ORDER_DIRECTION_KEY: "desc",
            self.SEARCH_PARAMETER: None,
        }
    
    def test(self):
        self.smart_get(self.session_study.id, get_kwargs=self.DEFAULT_PARAMETERS)


class TestInterventionsPage(ResearcherSessionTest):
    ENDPOINT_NAME = "study_api.interventions_page"
    REDIRECT_ENDPOINT_NAME = "study_api.interventions_page"
    
    def test_get(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self.generate_intervention(self.session_study, "obscure_name_of_intervention")
        resp = self.smart_get(self.session_study.id)
        self.assert_present("obscure_name_of_intervention", resp.content)
    
    def test_post(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        resp = self.smart_post(self.session_study.id, new_intervention="ohello")
        self.assertEqual(resp.status_code, 302)
        intervention = Intervention.objects.get(study=self.session_study)
        self.assertEqual(intervention.name, "ohello")


class TestDeleteIntervention(RedirectSessionApiTest):
    ENDPOINT_NAME = "study_api.delete_intervention"
    REDIRECT_ENDPOINT_NAME = "study_api.interventions_page"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        intervention = self.generate_intervention(self.session_study, "obscure_name_of_intervention")
        self.smart_post(self.session_study.id, intervention=intervention.id)
        self.assertFalse(Intervention.objects.filter(id=intervention.id).exists())


class TestEditIntervention(RedirectSessionApiTest):
    ENDPOINT_NAME = "study_api.edit_intervention"
    REDIRECT_ENDPOINT_NAME = "study_api.interventions_page"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        intervention = self.generate_intervention(self.session_study, "obscure_name_of_intervention")
        self.smart_post(
            self.session_study.id, intervention_id=intervention.id, edit_intervention="new_name"
        )
        intervention_new = Intervention.objects.get(id=intervention.id)
        self.assertEqual(intervention.id, intervention_new.id)
        self.assertEqual(intervention_new.name, "new_name")


class TestStudyFields(RedirectSessionApiTest):
    ENDPOINT_NAME = "study_api.study_fields"
    REDIRECT_ENDPOINT_NAME = "study_api.study_fields"
    
    def test_get(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self.generate_study_field(self.session_study, "obscure_name_of_study_field")
        resp = self.smart_get(self.session_study.id)
        self.assert_present("obscure_name_of_study_field", resp.content)
    
    def test_post(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        resp = self.smart_post(self.session_study.id, new_field="ohello")
        self.assertEqual(resp.status_code, 302)
        study_field = StudyField.objects.get(study=self.session_study)
        self.assertEqual(study_field.field_name, "ohello")


class TestDeleteStudyField(RedirectSessionApiTest):
    ENDPOINT_NAME = "study_api.delete_field"
    REDIRECT_ENDPOINT_NAME = "study_api.study_fields"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        study_field = self.generate_study_field(self.session_study, "obscure_name_of_study_field")
        self.smart_post(self.session_study.id, field=study_field.id)
        self.assertFalse(StudyField.objects.filter(id=study_field.id).exists())


class TestEditStudyField(RedirectSessionApiTest):
    ENDPOINT_NAME = "study_api.edit_custom_field"
    REDIRECT_ENDPOINT_NAME = "study_api.study_fields"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        study_field = self.generate_study_field(self.session_study, "obscure_name_of_study_field")
        self.smart_post(
            self.session_study.id, field_id=study_field.id, edit_custom_field="new_name"
        )
        study_field_new = StudyField.objects.get(id=study_field.id)
        self.assertEqual(study_field.id, study_field_new.id)
        self.assertEqual(study_field_new.field_name, "new_name")


# FIXME: implement more tests of this endpoint, it is complex.
class TestNotificationHistory(ResearcherSessionTest):
    ENDPOINT_NAME = "participant_pages.notification_history"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        self.generate_archived_event(self.default_survey, self.default_participant)
        self.smart_get_status_code(200, self.session_study.id, self.default_participant.patient_id)


class TestParticipantPage(RedirectSessionApiTest):
    ENDPOINT_NAME = "participant_pages.participant_page"
    REDIRECT_ENDPOINT_NAME = "participant_pages.participant_page"
    
    def test_get(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        resp = self.smart_get(self.session_study.id, self.default_participant.patient_id)
        self.assertEqual(resp.status_code, 200)
    
    def test_post(self):
        # FIXME: implement real tests here...
        self.set_session_study_relation(ResearcherRole.study_admin)
        self.smart_post(self.session_study.id, self.default_participant.patient_id)


# FIXME: add interventions and surveys to the export tests
class TestExportStudySettingsFile(ResearcherSessionTest):
    ENDPOINT_NAME = "copy_study_api.export_study_settings_file"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.study_admin)
        # FileResponse objects stream, which means you need to iterate over `resp.streaming_content``
        resp: FileResponse = self.smart_get(self.session_study.id)
        # sanity check...
        items_to_iterate = 0
        for file_bytes in resp.streaming_content:
            items_to_iterate += 1
        self.assertEqual(items_to_iterate, 1)
        # get survey, check device_settings, surveys, interventions are all present
        output_survey: dict = json.loads(file_bytes.decode())  # make sure it is a json file
        self.assertIn("device_settings", output_survey)
        self.assertIn("surveys", output_survey)
        self.assertIn("interventions", output_survey)
        output_device_settings: dict = output_survey["device_settings"]
        real_device_settings = self.session_device_settings.as_unpacked_native_python()
        # confirm that all elements are equal for the dicts
        for k, v in output_device_settings.items():
            self.assertEqual(v, real_device_settings[k])


# FIXME: add interventions and surveys to the import tests
class TestImportStudySettingsFile(RedirectSessionApiTest):
    ENDPOINT_NAME = "copy_study_api.import_study_settings_file"
    REDIRECT_ENDPOINT_NAME = "system_admin_pages.edit_study"
    
    # other post params: device_settings, surveys
    
    def test_no_device_settings_no_surveys(self):
        resp = self._test(False, False)
        self.assert_present("Did not alter", resp.content)
        self.assert_present("Copied 0 Surveys and 0 Audio Surveys", resp.content)
    
    def test_device_settings_no_surveys(self):
        resp = self._test(True, False)
        self.assert_present("Settings with custom values.", resp.content)
        self.assert_present("Copied 0 Surveys and 0 Audio Surveys", resp.content)
    
    def test_device_settings_and_surveys(self):
        resp = self._test(True, True)
        self.assert_present("Settings with custom values.", resp.content)
        # self.assert_present("Copied 0 Surveys and 0 Audio Surveys", resp.content)
    
    def test_bad_filename(self):
        resp = self._test(True, True, ".exe", success=False)
        # FIXME: this is not present in the html, it should be
        # self.assert_present("You can only upload .json files.", resp.content)
    
    def _test(
        self, device_settings: bool, surveys: bool, extension: str = "json", success: bool = True
    ) -> HttpResponse:
        self.set_session_study_relation(ResearcherRole.site_admin)
        study2 = self.generate_study("study_2")
        self.assertEqual(self.session_device_settings.gps, True)
        self.session_device_settings.update(gps=False)
        
        # this is the function that creates the canonical study representation wrapped in a burrito
        survey_json_file = BytesIO(format_study(self.session_study).encode())
        survey_json_file.name = f"something.{extension}"  # ayup, that's how you add a name...
        
        self.smart_post(
            study2.id,
            upload=survey_json_file,
            device_settings="true" if device_settings else "false",
            surveys="true" if surveys else "false",
        )
        study2.device_settings.refresh_from_db()
        if success:
            self.assertEqual(study2.device_settings.gps, not device_settings)
        # return the page, we always need it
        return self.smart_get_redirect(study2.id)


class TestICreateSurvey(RedirectSessionApiTest):
    ENDPOINT_NAME = "survey_api.create_survey"
    REDIRECT_ENDPOINT_NAME = "survey_designer.render_edit_survey"
    
    def test_tracking(self):
        self._test(Survey.TRACKING_SURVEY)
    
    def test_audio(self):
        self._test(Survey.AUDIO_SURVEY)
    
    def test_image(self):
        self._test(Survey.IMAGE_SURVEY)
    
    def _test(self, survey_type: str):
        self.set_session_study_relation(ResearcherRole.researcher)
        self.assertEqual(Survey.objects.count(), 0)
        resp = self.smart_get(self.session_study.id, survey_type)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Survey.objects.count(), 1)
        survey: Survey = Survey.objects.get()
        self.assertEqual(survey_type, survey.survey_type)


# FIXME: add schedule removal tests to this test
class TestDeleteSurvey(RedirectSessionApiTest):
    ENDPOINT_NAME = "survey_api.delete_survey"
    REDIRECT_ENDPOINT_NAME = "admin_pages.view_study"
    
    def test(self):
        self.assertEqual(Survey.objects.count(), 0)
        self.set_session_study_relation(ResearcherRole.researcher)
        survey = self.generate_survey(self.session_study, Survey.TRACKING_SURVEY)
        self.assertEqual(Survey.objects.count(), 1)
        self.smart_post(self.session_study.id, survey.id)
        self.assertEqual(Survey.objects.count(), 1)
        self.assertEqual(Survey.objects.filter(deleted=False).count(), 0)


# FIXME: implement more details of survey object updates
class TestUpdateSurvey(ResearcherSessionTest):
    ENDPOINT_NAME = "survey_api.update_survey"
    
    def test_with_hax_to_bypass_the_hard_bit(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        survey = self.generate_survey(self.session_study, Survey.TRACKING_SURVEY)
        self.assertEqual(survey.settings, '{}')
        resp = self.smart_post(
            self.session_study.id, survey.id, content='[]', settings='[]',
            weekly_timings='[]', absolute_timings='[]', relative_timings='[]',
        )
        survey.refresh_from_db()
        self.assertEqual(survey.settings, '[]')
        self.assertEqual(resp.status_code, 201)


# fixme: add interventions and survey schedules
class TestRenderEditSurvey(ResearcherSessionTest):
    ENDPOINT_NAME = "survey_designer.render_edit_survey"
    
    def test(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        survey = self.generate_survey(self.session_study, Survey.TRACKING_SURVEY)
        self.smart_get_status_code(200, self.session_study.id, survey.id)


# FIXME: this endpoint doesn't validate the researcher on the study
# FIXME: redirect was based on referrer.
class TestResetParticipantPassword(RedirectSessionApiTest):
    ENDPOINT_NAME = "participant_administration.reset_participant_password"
    REDIRECT_ENDPOINT_NAME = "admin_pages.view_study"
    
    def test_success(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        old_password = self.default_participant.password
        self.smart_post(study_id=self.session_study.id, patient_id=self.default_participant.patient_id)
        self.default_participant.refresh_from_db()
        self.assert_present("password has been reset to",
                            self.get_redirect_content(self.session_study.id))
        self.assertNotEqual(self.default_participant.password, old_password)
    
    def test_bad_participant(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        self.smart_post(study_id=self.session_study.id, patient_id="why hello")
        self.assertFalse(Participant.objects.filter(patient_id="why hello").exists())
        self.assert_present("does not exist", self.get_redirect_content(self.session_study.id))
    
    def test_bad_study(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        study2 = self.generate_study("study2")
        self.generate_study_relation(self.session_researcher, study2, ResearcherRole.researcher)
        old_password = self.default_participant.password
        self.smart_post(study_id=study2.id, patient_id=self.default_participant.patient_id)
        self.assert_present("is not in study", self.get_redirect_content(self.session_study.id))
        self.default_participant.refresh_from_db()
        self.assertEqual(self.default_participant.password, old_password)


class TestResetDevice(RedirectSessionApiTest):
    ENDPOINT_NAME = "participant_administration.reset_device"
    REDIRECT_ENDPOINT_NAME = "admin_pages.view_study"
    
    def test_bad_study_id(self):
        self.default_participant.update(device_id="12345")
        self.set_session_study_relation(ResearcherRole.researcher)
        resp = self._smart_post(patient_id=self.default_participant.patient_id, study_id=0)
        self.assertEqual(resp.status_code, 404)
        self.default_participant.refresh_from_db()
        self.assertEqual(self.default_participant.device_id, "12345")
    
    def test_wrong_study_id(self):
        self.default_participant.update(device_id="12345")
        self.set_session_study_relation(ResearcherRole.researcher)
        study2 = self.generate_study("study2")
        self.generate_study_relation(self.session_researcher, study2, ResearcherRole.researcher)
        self.smart_post(patient_id=self.default_participant.patient_id, study_id=study2.id)
        self.assert_present("is not in study", self.get_redirect_content(self.session_study.id))
        self.assertEqual(Participant.objects.count(), 1)
        self.default_participant.refresh_from_db()
        self.assertEqual(self.default_participant.device_id, "12345")
    
    def test_bad_participant(self):
        self.default_participant.update(device_id="12345")
        self.assertEqual(Participant.objects.count(), 1)
        self.set_session_study_relation(ResearcherRole.researcher)
        self.smart_post(patient_id="invalid", study_id=self.session_study.id)
        self.assert_present("does not exist", self.get_redirect_content(self.session_study.id))
        self.default_participant.refresh_from_db()
        self.assertEqual(self.default_participant.device_id, "12345")
    
    def test_success(self):
        self.default_participant.update(device_id="12345")
        self.set_session_study_relation(ResearcherRole.researcher)
        self.smart_post(patient_id=self.default_participant.patient_id,
                        study_id=self.session_study.id)
        self.assert_present("device was reset; password is untouched",
                            self.get_redirect_content(self.session_study.id))
        self.default_participant.refresh_from_db()
        self.assertEqual(self.default_participant.device_id, "")



class TestUnregisterParticipant(RedirectSessionApiTest):
    ENDPOINT_NAME = "participant_administration.unregister_participant"
    REDIRECT_ENDPOINT_NAME = "admin_pages.view_study"
    # most of this was copy-pasted from TestResetDevice
    
    def test_bad_study_id(self):
        self.default_participant.update(unregistered=False)
        self.set_session_study_relation(ResearcherRole.researcher)
        resp = self._smart_post(patient_id=self.default_participant.patient_id, study_id=0)
        self.assertEqual(resp.status_code, 404)
        self.default_participant.refresh_from_db()
        self.assertEqual(self.default_participant.unregistered, False)
    
    def test_wrong_study_id(self):
        self.default_participant.update(unregistered=False)
        self.set_session_study_relation(ResearcherRole.researcher)
        study2 = self.generate_study("study2")
        self.generate_study_relation(self.session_researcher, study2, ResearcherRole.researcher)
        self.smart_post(patient_id=self.default_participant.patient_id, study_id=study2.id)
        self.assert_present("is not in study", self.get_redirect_content(self.session_study.id))
        self.assertEqual(Participant.objects.count(), 1)
        self.default_participant.refresh_from_db()
        self.assertEqual(self.default_participant.unregistered, False)
    
    def test_bad_participant(self):
        self.default_participant.update(unregistered=False)
        self.assertEqual(Participant.objects.count(), 1)
        self.set_session_study_relation(ResearcherRole.researcher)
        self.smart_post(patient_id="invalid", study_id=self.session_study.id)
        self.assert_present("does not exist", self.get_redirect_content(self.session_study.id))
        self.default_participant.refresh_from_db()
        self.assertEqual(self.default_participant.unregistered, False)
    
    def test_participant_unregistered_true(self):
        self.default_participant.update(unregistered=True)
        self.assertEqual(Participant.objects.count(), 1)
        self.set_session_study_relation(ResearcherRole.researcher)
        self.smart_post(
            patient_id=self.default_participant.patient_id, study_id=self.session_study.id
        )
        self.assert_present(
            "is already unregistered", self.get_redirect_content(self.session_study.id)
        )
        self.default_participant.refresh_from_db()
        self.assertEqual(self.default_participant.unregistered, True)
    
    def test_success(self):
        self.default_participant.update(unregistered=False)
        self.set_session_study_relation(ResearcherRole.researcher)
        self.smart_post(
            patient_id=self.default_participant.patient_id, study_id=self.session_study.id
        )
        self.assert_present(
            "was successfully unregisted from the study",
            self.get_redirect_content(self.session_study.id)
        )
        self.default_participant.refresh_from_db()
        self.assertEqual(self.default_participant.unregistered, True)


# FIXME: test extended database effects of generating participants
class CreateNewParticipant(RedirectSessionApiTest):
    ENDPOINT_NAME = "participant_administration.create_new_participant"
    REDIRECT_ENDPOINT_NAME = "admin_pages.view_study"
    
    @patch("api.participant_administration.s3_upload")
    @patch("api.participant_administration.create_client_key_pair")
    def test(self, create_client_keypair: MagicMock, s3_upload: MagicMock):
        # this test does not make calls to S3
        self.set_session_study_relation(ResearcherRole.researcher)
        self.assertFalse(Participant.objects.exists())
        self.smart_post(study_id=self.session_study.id)
        self.assertEqual(Participant.objects.count(), 1)
        
        content = self.get_redirect_content(self.session_study.id)
        new_participant: Participant = Participant.objects.first()
        self.assert_present("Created a new patient", content)
        self.assert_present(new_participant.patient_id, content)


class CreateManyParticipant(ResearcherSessionTest):
    ENDPOINT_NAME = "participant_administration.create_many_patients"
    
    @patch("api.participant_administration.s3_upload")
    @patch("api.participant_administration.create_client_key_pair")
    def test(self, create_client_keypair: MagicMock, s3_upload: MagicMock):
        # this test does not make calls to S3
        self.set_session_study_relation(ResearcherRole.researcher)
        self.assertFalse(Participant.objects.exists())
        
        resp: FileResponse = self.smart_post(
            self.session_study.id, desired_filename="something.csv", number_of_new_patients=10
        )
        output_file = b""
        for i, file_bytes in enumerate(resp.streaming_content, start=1):
            output_file = output_file + file_bytes
        
        self.assertEqual(i, 10)
        self.assertEqual(Participant.objects.count(), 10)
        for patient_id in Participant.objects.values_list("patient_id", flat=True                                                                                                                                                                                                                                               ):
            self.assert_present(patient_id, output_file)


class TestAPIGetStudies(DataApiTest):
    ENDPOINT_NAME = "other_researcher_apis.get_studies"
    
    def test_no_study(self):
        resp = self.smart_post_status_code(200)
        self.assertEqual(Study.objects.count(), 0)
        self.assertEqual(json.loads(resp.content), {})
    
    def test_no_study_relation(self):
        resp = self.smart_post_status_code(200)
        self.session_study
        self.assertEqual(Study.objects.count(), 1)
        self.assertEqual(json.loads(resp.content), {})
    
    def test_multiple_studies_one_relation(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        study2 = self.generate_study("study2")
        resp = self.smart_post_status_code(200)
        self.assertEqual(
            json.loads(resp.content), {self.session_study.object_id: self.DEFAULT_STUDY_NAME}
        )
    
    def test_study_relation(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        resp = self.smart_post_status_code(200)
        self.assertEqual(
            json.loads(resp.content), {self.session_study.object_id: self.DEFAULT_STUDY_NAME}
        )
    
    def test_multiple_studies(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        study2 = self.generate_study("study2")
        self.generate_study_relation(self.session_researcher, study2, ResearcherRole.researcher)
        resp = self.smart_post_status_code(200)
        self.assertEqual(
            json.loads(resp.content), {
                self.session_study.object_id: self.DEFAULT_STUDY_NAME,
                study2.object_id: study2.name
            }
        )


class TestApiCredentialCheck(DataApiTest):
    ENDPOINT_NAME = "other_researcher_apis.get_studies"
    
    def test_missing_all_parameters(self):
        # use _smart_post
        resp = self.less_smart_post()
        # 400, missing parameter
        self.assertEqual(400, resp.status_code)
    
    def test_only_secret_key(self):
        resp = self.less_smart_post(secret_key=self.session_secret_key)
        # 400, missing parameter
        self.assertEqual(400, resp.status_code)
    
    def test_only_access_key(self):
        resp = self.less_smart_post(access_key=self.session_access_key)
        # 400, missing parameter
        self.assertEqual(400, resp.status_code)
    
    def test_wrong_secret_key_db(self):
        # Weird, but keep it, useful when debugging this test.
        self.session_researcher.access_key_secret = "apples"
        self.session_researcher.save()
        resp = self.smart_post()
        # key doesn't match, forbidden
        self.assertEqual(403, resp.status_code)
    
    def test_wrong_secret_key_post(self):
        resp = self.less_smart_post(access_key="apples", secret_key=self.session_secret_key)
        # key doesn't match, forbidden
        self.assertEqual(403, resp.status_code)
    
    def test_wrong_access_key_db(self):
        # Weird, but keep it, useful when debugging this test.
        self.session_researcher.access_key_id = "apples"
        self.session_researcher.save()
        resp = self.smart_post()
        # no such user, forbidden
        self.assertEqual(403, resp.status_code)
    
    def test_wrong_access_key_post(self):
        resp = self.less_smart_post(access_key=self.session_access_key, secret_key="apples")
        # no such user, forbidden
        self.assertEqual(403, resp.status_code)
    
    def test_access_key_special_characters(self):
        self.session_access_key = "\x00" * 64
        self.smart_post_status_code(400)
    
    def test_secret_key_special_characters(self):
        self.session_secret_key = "\x00" * 64
        self.smart_post_status_code(400)
    
    def test_site_admin(self):
        self.assign_role(self.session_researcher, ResearcherRole.site_admin)
        self.smart_post_status_code(200)
    
    def test_researcher(self):
        self.assign_role(self.session_researcher, ResearcherRole.study_admin)
        self.smart_post_status_code(200)
    
    def test_study_admin(self):
        self.assign_role(self.session_researcher, ResearcherRole.researcher)
        self.smart_post_status_code(200)


class TestAPIStudyUserAccess(DataApiTest):
    ENDPOINT_NAME = "other_researcher_apis.get_users_in_study"
    
    def test_missing_all_parameters(self):
        # self.set_session_study_relation(ResearcherRole)
        # use _smart_post
        resp = self.less_smart_post()
        # 400, missing parameter
        self.assertEqual(400, resp.status_code)
    
    def test_only_secret_key(self):
        resp = self.less_smart_post(secret_key=self.session_secret_key)
        # 400, missing parameter
        self.assertEqual(400, resp.status_code)
    
    def test_only_access_key(self):
        resp = self.less_smart_post(access_key=self.session_access_key)
        # 400, missing parameter
        self.assertEqual(400, resp.status_code)
    
    def test_only_study_obj_id(self):
        resp = self.less_smart_post(study_id=self.session_study.object_id)
        # 400, missing parameter
        self.assertEqual(400, resp.status_code)
    
    def test_only_study_pk(self):
        resp = self.less_smart_post(study_pk=self.session_study.pk)
        # 400, missing parameter
        self.assertEqual(400, resp.status_code)
    
    def test_wrong_secret_key_post(self):
        resp = self.less_smart_post(
            access_key="apples", secret_key=self.session_secret_key, study_pk=self.session_study.pk
        )
        # key doesn't match, forbidden
        self.assertEqual(403, resp.status_code)
    
    def test_wrong_access_key_post(self):
        resp = self.less_smart_post(
            access_key=self.session_access_key, secret_key="apples", study_pk=self.session_study.pk
        )
        # no such user, forbidden
        self.assertEqual(403, resp.status_code)
    
    def test_no_such_study_pk(self):
        # 0 is an invalid study id
        self.smart_post_status_code(404, study_pk=0)
    
    def test_no_such_study_obj(self):
        # 0 is an invalid study id
        self.smart_post_status_code(404, study_id='a'*24)
    
    def test_bad_object_id(self):
        # 0 is an invalid study id
        self.smart_post_status_code(400, study_id='['*24)
        self.smart_post_status_code(400, study_id='a'*5)
    
    def test_access_key_special_characters(self):
        self.session_access_key = "\x00" * 64
        self.smart_post_status_code(400, study_pk=self.session_study.pk)
    
    def test_secret_key_special_characters(self):
        self.session_secret_key = "\x00" * 64
        self.smart_post_status_code(400, study_pk=self.session_study.pk)
    
    def test_site_admin(self):
        self.assign_role(self.session_researcher, ResearcherRole.site_admin)
        self.smart_post_status_code(200, study_pk=self.session_study.pk)
    
    def test_researcher(self):
        self.assign_role(self.session_researcher, ResearcherRole.study_admin)
        self.smart_post_status_code(200, study_pk=self.session_study.pk)
    
    def test_study_admin(self):
        self.assign_role(self.session_researcher, ResearcherRole.researcher)
        self.smart_post_status_code(200, study_pk=self.session_study.pk)
    
    def test_no_relation(self):
        self.assign_role(self.session_researcher, None)
        self.smart_post_status_code(403, study_pk=self.session_study.pk)


class TestGetUsersInStudy(DataApiTest):
    ENDPOINT_NAME = "other_researcher_apis.get_users_in_study"
    
    def test_no_participants(self):
        self.smart_post_status_code(200)
    
    def test_no_participants(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        resp = self.smart_post_status_code(200, study_id=self.session_study.object_id)
        self.assertEqual(resp.content, b"[]")
    
    def test_one_participant(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        self.default_participant
        resp = self.smart_post_status_code(200, study_id=self.session_study.object_id)
        self.assertEqual(resp.content, f'["{self.default_participant.patient_id}"]'.encode())
    
    def test_two_participants(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        self.default_participant
        p2 = self.generate_participant(self.session_study)
        resp = self.smart_post_status_code(200, study_id=self.session_study.object_id)
        match = f'["{self.default_participant.patient_id}", "{p2.patient_id}"]'
        self.assertEqual(resp.content, match.encode())


class TestGetData(DataApiTest):
    """ WARNING: there are heisenbugs in debugging the download data api endpoint.

    There is a generator that is conditionally present (`handle_database_query`), it can swallow
    errors. As a generater iterating over it consumes it, so printing it breaks the code.
    
    You Must Patch libs.streaming_zip.ThreadPool
        The database connection breaks throwing errors on queries that should succeed.
        The iterator inside the zip file generator generally fails, and the zip file is empty.

    You Must Patch libs.streaming_zip.s3_retrieve
        Otherwise s3_retrieve will fail due to the patch is tests.common.
    """
    
    def test_s3_patch_present(self):
        from libs import s3
        self.assertIsNone(s3.S3_BUCKET)
    
    ENDPOINT_NAME = "data_access_api.get_data"
    
    EMPTY_ZIP = b'PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    SIMPLE_FILE_CONTENTS = b"this is the file content you are looking for"
    REGISTRY_HASH = "registry_hash"
    
    # retain and usethis structure in order to force a test addition on a new file type.
    # "particip" is the DEFAULT_PARTICIPANT_NAME
    # 'u1Z3SH7l2xNsw72hN3LnYi96' is the  DEFAULT_SURVEY_OBJECT_ID
    FILE_NAMES = {                                        # ↓ that Z makes it a timzone'd datetime
        "accelerometer": ("something.csv", "2020-10-05 02:00Z",
                         f"particip/accelerometer/2020-10-05 02_00_00+00_00.csv"),
        "ambient_audio": ("something.mp4", "2020-10-05 02:00Z",
                         f"particip/ambient_audio/2020-10-05 02_00_00+00_00.mp4"),
        "app_log": ("app_log.csv", "2020-10-05 02:00Z",
                         f"particip/app_log/2020-10-05 02_00_00+00_00.csv"),
        "bluetooth": ("bluetooth.csv", "2020-10-05 02:00Z",
                         f"particip/bluetooth/2020-10-05 02_00_00+00_00.csv"),
        "calls": ("calls.csv", "2020-10-05 02:00Z",
                         f"particip/calls/2020-10-05 02_00_00+00_00.csv"),
        "devicemotion": ("devicemotion.csv", "2020-10-05 02:00Z",
                         f"particip/devicemotion/2020-10-05 02_00_00+00_00.csv"),
        "gps": ("gps.csv", "2020-10-05 02:00Z",
                         f"particip/gps/2020-10-05 02_00_00+00_00.csv"),
        "gyro": ("gyro.csv", "2020-10-05 02:00Z",
                         f"particip/gyro/2020-10-05 02_00_00+00_00.csv"),
        "identifiers": ("identifiers.csv", "2020-10-05 02:00Z",
                         f"particip/identifiers/2020-10-05 02_00_00+00_00.csv"),
        "image_survey": ("image_survey/survey_obj_id/something/something2.csv", "2020-10-05 02:00Z",
                         # patient_id/data_type/survey_id/survey_instance/name.csv
                         f"particip/image_survey/survey_obj_id/something/something2.csv"),
        "ios_log": ("ios_log.csv", "2020-10-05 02:00Z",
                         f"particip/ios_log/2020-10-05 02_00_00+00_00.csv"),
        "magnetometer": ("magnetometer.csv", "2020-10-05 02:00Z",
                         f"particip/magnetometer/2020-10-05 02_00_00+00_00.csv"),
        "power_state": ("power_state.csv", "2020-10-05 02:00Z",
                         f"particip/power_state/2020-10-05 02_00_00+00_00.csv"),
        "proximity": ("proximity.csv", "2020-10-05 02:00Z",
                         f"particip/proximity/2020-10-05 02_00_00+00_00.csv"),
        "reachability": ("reachability.csv", "2020-10-05 02:00Z",
                         f"particip/reachability/2020-10-05 02_00_00+00_00.csv"),
        "survey_answers": ("survey_obj_id/something2/something3.csv", "2020-10-05 02:00Z",
                          # expecting: patient_id/data_type/survey_id/time.csv
                         f"particip/survey_answers/something2/2020-10-05 02_00_00+00_00.csv"),
        "survey_timings": ("something1/something2/something3/something4/something5.csv", "2020-10-05 02:00Z",
                          # expecting: patient_id/data_type/survey_id/time.csv
                          f"particip/survey_timings/u1Z3SH7l2xNsw72hN3LnYi96/2020-10-05 02_00_00+00_00.csv"),
        "texts": ("texts.csv", "2020-10-05 02:00Z",
                         f"particip/texts/2020-10-05 02_00_00+00_00.csv"),
        "audio_recordings": ("audio_recordings.wav", "2020-10-05 02:00Z",
                         f"particip/audio_recordings/2020-10-05 02_00_00+00_00.wav"),
        "wifi": ("wifi.csv", "2020-10-05 02:00Z",
                         f"particip/wifi/2020-10-05 02_00_00+00_00.csv"),
        }
    
    # setting the threadpool needs to apply to each test, following this pattern because its easy.
    @patch("libs.streaming_zip.ThreadPool")
    def test_basics(self, threadpool: MagicMock):
        threadpool.return_value = DummyThreadPool()
        self._test_basics()
    
    @patch("libs.streaming_zip.ThreadPool")
    def test_downloads_and_file_naming(self, threadpool: MagicMock):
        threadpool.return_value = DummyThreadPool()
        self._test_downloads_and_file_naming()
    
    @patch("libs.streaming_zip.ThreadPool")
    def test_registry_doesnt_download(self, threadpool: MagicMock):
        threadpool.return_value = DummyThreadPool()
        self._test_registry_doesnt_download()
    
    @patch("libs.streaming_zip.ThreadPool")
    def test_time_bin(self, threadpool: MagicMock):
        threadpool.return_value = DummyThreadPool()
        self._test_time_bin()
    
    @patch("libs.streaming_zip.ThreadPool")
    def test_user_query(self, threadpool: MagicMock):
        threadpool.return_value = DummyThreadPool()
        self._test_user_query()
    
    @patch("libs.streaming_zip.ThreadPool")
    def test_data_streams(self, threadpool: MagicMock):
        threadpool.return_value = DummyThreadPool()
        self._test_data_streams()
    
    # but don't patch ThreadPool for this one
    def test_downloads_and_file_naming_heisenbug(self):
        # As far as I can tell the ThreadPool seems to screw up the connection to the test
        # database, and queries on the non-main thread either find no data or connect to the wrong
        # database (presumably your normal database?).
        # Please retain this behavior and consult me (Eli, Biblicabeebli) during review.  This means a
        # change has occurred to the multithreading, and is probably related to an obscure but known
        # memory leak in the data access api download enpoint that is relevant on large downloads. """
        try:
            self._test_downloads_and_file_naming()
        except AssertionError as e:
            # this will happen on the first file it tests, accelerometer.
            literal_string_of_error_message = "b'particip/accelerometer/2020-10-05 " \
                "02_00_00+00_00.csv' not found in b'PK\\x05\\x06\\x00\\x00\\x00\\x00\\x00" \
                "\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00'"
            
            if str(e) != literal_string_of_error_message:
                raise Exception(
                    f"\n'{literal_string_of_error_message}'\nwas not equal to\n'{str(e)}'\n"
                     "\n  You have changed something that is possibly related to "
                     "threading via a ThreadPool or DummyThreadPool"
                )
    
    def _test_basics(self):
        self.set_session_study_relation(ResearcherRole.researcher)
        resp: FileResponse = self.smart_post(study_pk=self.session_study.id)
        self.assertEqual(resp.status_code, 200)
        for i, file_bytes in enumerate(resp.streaming_content, start=1):
            pass
        self.assertEqual(i, 1)
        # this is an empty zip file as output by the api.  PK\x05\x06 is zip-speak for an empty
        # container.  Behavior can vary on how zip decompressors handle an empty zip, some fail.
        self.assertEqual(file_bytes, self.EMPTY_ZIP)
    
    @patch("libs.streaming_zip.s3_retrieve")
    def _test_downloads_and_file_naming(self, s3_retrieve: MagicMock):
        # basics
        s3_retrieve.return_value = self.SIMPLE_FILE_CONTENTS
        self.set_session_study_relation(ResearcherRole.researcher)
        
        # need to test all data types
        for data_type in ALL_DATA_STREAMS:
            path, time_bin, output_name = self.FILE_NAMES[data_type]
            file_contents = self.generate_chunkregistry_and_download(data_type, path, time_bin)
            # this is an 'in' test because the file name is part of the zip file, as cleartext
            self.assertIn(output_name.encode(), file_contents)
            self.assertIn(s3_retrieve.return_value, file_contents)
    
    @patch("libs.streaming_zip.s3_retrieve")
    def _test_data_streams(self, s3_retrieve: MagicMock):
        # basics
        s3_retrieve.return_value = self.SIMPLE_FILE_CONTENTS
        self.set_session_study_relation(ResearcherRole.researcher)
        file_path = "some_file_path.csv"
        basic_args = ("accelerometer", file_path, "2020-10-05 02:00Z")
        
        # assert normal args actually work
        file_contents = self.generate_chunkregistry_and_download(*basic_args)
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        
        # test matching data type downloads
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_data_streams='["accelerometer"]'
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        # same with only the string (no brackets, client.post handles serialization)
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_data_streams="accelerometer"
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        
        # test invalid data stream
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_data_streams='"[accelerometer,gyro]', status_code=404
        )
        
        # test valid, non-matching data type does not download
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_data_streams='["gyro"]'
        )
        self.assertEqual(file_contents, self.EMPTY_ZIP)
    
    @patch("libs.streaming_zip.s3_retrieve")
    def _test_registry_doesnt_download(self, s3_retrieve: MagicMock):
        # basics
        s3_retrieve.return_value = self.SIMPLE_FILE_CONTENTS
        self.set_session_study_relation(ResearcherRole.researcher)
        file_path = "some_file_path.csv"
        basic_args = ("accelerometer", file_path, "2020-10-05 02:00Z")
        
        # assert normal args actually work
        file_contents = self.generate_chunkregistry_and_download(*basic_args)
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        
        # test that file is not downloaded when a valid json registry is present
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, registry=json.dumps({file_path: self.REGISTRY_HASH})
        )
        self.assertEqual(file_contents, self.EMPTY_ZIP)
        
        # test that a non-matching hash does not block download.
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, registry=json.dumps({file_path: "bad hash value"})
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        
        # test bad json objects
        self.generate_chunkregistry_and_download(
            *basic_args, registry=json.dumps([self.REGISTRY_HASH]), status_code=400
        )
        self.generate_chunkregistry_and_download(
            *basic_args, registry=json.dumps([file_path]), status_code=400
        )
        # empty string is probably worth testing
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, registry="", status_code=400
        )
    
    @patch("libs.streaming_zip.s3_retrieve")
    def _test_time_bin(self, s3_retrieve: MagicMock):
        # basics
        s3_retrieve.return_value = self.SIMPLE_FILE_CONTENTS
        self.set_session_study_relation(ResearcherRole.researcher)
        basic_args = ("accelerometer", "some_file_path.csv", "2020-10-05 02:00Z")
        
        # generic request should succeed
        file_contents = self.generate_chunkregistry_and_download(*basic_args)
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        
        # the api time parameter format is "%Y-%m-%dT%H:%M:%S"
        # from a time before time_bin of chunkregistry
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_time_bin_start="2020-10-05T01:00:00",
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        
        # inner check should be equal to or after the given date
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_time_bin_start="2020-10-05T02:00:00",
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        
        # inner check should be equal to or before the given date
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_time_bin_end="2020-10-05T02:00:00",
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        
        # this should fail, start date is late
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_time_bin_start="2020-10-05T03:00:00",
        )
        self.assertEqual(file_contents, self.EMPTY_ZIP)
        
        # this should succeed, end date is after start date
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_time_bin_end="2020-10-05T03:00:00",
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        
        # should succeed, within time range
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args,
            query_time_bin_start="2020-10-05T02:00:00",
            query_time_bin_end="2020-10-05T03:00:00",
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        
        # test with bad time bins, returns no data, user error, no special case handling
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args,
            query_time_bin_start="2020-10-05T03:00:00",
            query_time_bin_end="2020-10-05T02:00:00",
        )
        self.assertEqual(file_contents, self.EMPTY_ZIP)
        
        # test inclusive
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args,
            query_time_bin_start="2020-10-05T02:00:00",
            query_time_bin_end="2020-10-05T02:00:00",
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        
        # test bad time format
        self.generate_chunkregistry_and_download(
            *basic_args, query_time_bin_start="2020-10-05 01:00:00", status_code=400
        )
    
    @patch("libs.streaming_zip.s3_retrieve")
    def _test_user_query(self, s3_retrieve: MagicMock):
        # basics
        s3_retrieve.return_value = self.SIMPLE_FILE_CONTENTS
        self.set_session_study_relation(ResearcherRole.researcher)
        basic_args = ("accelerometer", "some_file_path.csv", "2020-10-05 02:00Z")
        
        # generic request should succeed
        file_contents = self.generate_chunkregistry_and_download(*basic_args)
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        
        # Test bad username
        output_status_code = self.generate_chunkregistry_and_download(
            *basic_args, query_patient_ids='["jeff"]', status_code=404
        )
        self.assertEqual(output_status_code, 404)  # redundant, whatever
        
        # test working participant filter
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_patient_ids=[self.default_participant.patient_id],
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        # same but just the string
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_patient_ids=self.default_participant.patient_id,
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        
        # test empty patients doesn't do anything
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_patient_ids='[]',
        )
        self.assertNotEqual(file_contents, self.EMPTY_ZIP)
        self.assertIn(self.SIMPLE_FILE_CONTENTS, file_contents)
        
        # test no matching data. create user, query for that user
        self.generate_participant(self.session_study, "jeff")
        file_contents = self.generate_chunkregistry_and_download(
            *basic_args, query_patient_ids='["jeff"]',
        )
        self.assertEqual(file_contents, self.EMPTY_ZIP)
    
    def generate_chunkregistry_and_download(
        self,
        data_type: str,
        file_path: str,
        time_bin: str,
        status_code: int = 200,
        registry: bool = None,
        query_time_bin_start: str = None,
        query_time_bin_end: str = None,
        query_patient_ids: str = None,
        query_data_streams: str = None,
    ):
        post_kwargs = {"study_pk": self.session_study.id}
        generate_kwargs = {"time_bin": time_bin, "path": file_path}
        
        if data_type == SURVEY_TIMINGS:
            generate_kwargs["survey"] = self.default_survey
        
        if registry is not None:
            post_kwargs["registry"] = registry
            generate_kwargs["hash_value"] = self.REGISTRY_HASH  # strings must match
        
        if query_data_streams is not None:
            post_kwargs["data_streams"] = query_data_streams
        
        if query_patient_ids is not None:
            post_kwargs["user_ids"] = query_patient_ids
        
        if query_time_bin_start:
            post_kwargs['time_start'] = query_time_bin_start
        if query_time_bin_end:
            post_kwargs['time_end'] = query_time_bin_end
        
        self.generate_chunk_registry(
            self.session_study, self.default_participant, data_type, **generate_kwargs
        )
        resp: FileResponse = self.smart_post(**post_kwargs)
        
        # Test for a status code, dufault 200
        self.assertEqual(resp.status_code, status_code)
        if resp.status_code != 200:
            # no iteration, clear db
            ChunkRegistry.objects.all().delete()
            return resp.status_code
        
        # then iterate over the streaming output and concatenate it.
        bytes_list = []
        for i, file_bytes in enumerate(resp.streaming_content, start=1):
            bytes_list.append(file_bytes)
            # print(data_type, i, file_bytes)
        
        # database cleanup has to be after the iteration over the file contents
        ChunkRegistry.objects.all().delete()
        return b"".join(bytes_list)


class TestParticipantSetPassword(ParticipantSessionTest):
    ENDPOINT_NAME = "mobile_api.set_password"
    
    def test_no_paramaters(self):
        self.smart_post_status_code(400)
        self.session_participant.refresh_from_db()
        self.assertFalse(self.session_participant.validate_password(self.DEFAULT_PARTICIPANT_PASSWORD))
        self.assertTrue(self.session_participant.debug_validate_password(self.DEFAULT_PARTICIPANT_PASSWORD))
    
    def test_no_paramaters(self):
        self.smart_post_status_code(200, new_password="jeff")
        self.session_participant.refresh_from_db()
        # participant passwords are weird there's some hashing
        self.assertFalse(self.session_participant.validate_password("jeff"))
        self.assertTrue(self.session_participant.debug_validate_password("jeff"))


class TestGetLatestSurveys(ParticipantSessionTest):
    ENDPOINT_NAME = "mobile_api.get_latest_surveys"
    
    def test_no_surveys(self):
        resp = self.smart_post_status_code(200)
        self.assertEqual(resp.content, b"[]")
    
    def test_basic_survey(self):
        self.default_survey
        resp = self.smart_post_status_code(200)
        self.assertTrue(len(resp.content) > 100)
        output_survey = json.loads(resp.content.decode())
        basic_survey = [
            {
                '_id': self.DEFAULT_SURVEY_OBJECT_ID,
                'content': [],
                'settings': {},
                'survey_type': 'tracking_survey',
                'timings': [[], [], [], [], [], [], []]
            }
        ]
        self.assertEqual(output_survey, basic_survey)


class TestRegisterParticipant(ParticipantSessionTest):
    ENDPOINT_NAME = "mobile_api.register_user"
    
    BASIC_PARAMS = {
            'patient_id': "abc123AB",
            'phone_number': "0000000000",
            'device_id': "pretty_much anything",
            'device_os': "something",
            'os_version': "something",
            "product": "something",
            "brand": "something",
            "hardware_id": "something",
            "manufacturer": "something",
            "model": "something",
            "beiwe_version": "something",
            "new_password": "something_new"
        }
    
    def test_bad_request(self):
        self.smart_post_status_code(400)
    
    @patch("api.mobile_api.s3_upload")
    @patch("api.mobile_api.get_client_public_key_string")
    def test_success_never_registered_before(
        self, get_client_public_key_string: MagicMock, s3_upload: MagicMock
    ):
        s3_upload.return_value = None
        get_client_public_key_string.return_value = "a_private_key"
        
        # unregistered participants have no device id
        self.session_participant.update(device_id="")
        resp = self.smart_post_status_code(200, **self.BASIC_PARAMS)
        
        response_dict = json.loads(resp.content)
        self.assertEqual("a_private_key", response_dict["client_public_key"])


class TestMobileUpload(ParticipantSessionTest):
    ENDPOINT_NAME = "mobile_api.upload"
    
    @classmethod
    def setUpClass(cls) -> None:
        # pycrypto (and probably pycryptodome) requires that we re-seed the random number generation
        # if we run using the --parallel directive.
        from Crypto import Random as old_Random  # note name conflict with std lib random.Random...
        old_Random.atfork()
        return super().setUpClass()
    
    # these are some generated keys that are part of the codebase, because generating them is slow
    # and potentially a source of error.
    with open(f"{BEIWE_PROJECT_ROOT}/tests/files/private_key", 'rb') as f:
        PRIVATE_KEY = get_RSA_cipher(f.read())
    with open(f"{BEIWE_PROJECT_ROOT}/tests/files/public_key", 'rb') as f:
        PUBLIC_KEY = get_RSA_cipher(f.read())
    
    @property
    def assert_no_files_to_process(self):
        self.assertEqual(FileToProcess.objects.count(), 0)
    
    @property
    def assert_one_file_to_process(self):
        self.assertEqual(FileToProcess.objects.count(), 1)
    
    def check_decryption_key_error(self, error_shibboleth):
        self.assertEqual(DecryptionKeyError.objects.count(), 1)
        traceback = DecryptionKeyError.objects.first().traceback
        # print(traceback)
        self.assertIn(error_shibboleth, traceback)
        self.assertIn(error_shibboleth, traceback.splitlines()[-1])
    
    def test_bad_file_names(self):
        self.assert_no_files_to_process
        # responds with 200 code because device deletes file based on return
        self.smart_post_status_code(200)
        self.assert_no_files_to_process
        self.smart_post_status_code(200, file_name="rList")
        self.assert_no_files_to_process
        self.smart_post_status_code(200, file_name="PersistedInstallation")
        self.assert_no_files_to_process
        # valid file extensions: csv, json, mp4, wav, txt, jpg
        self.smart_post_status_code(200, file_name="whatever")
        self.assert_no_files_to_process
        # no file parameter
        self.smart_post_status_code(400, file_name="whatever.csv")
        self.assert_no_files_to_process
        # correct file key, should fail
        self.smart_post_status_code(200, file="some_content")
        self.assert_no_files_to_process
    
    def test_unregistered_participant(self):
        # fails with 400 if the participant is registered.  This behavior has a side effect of
        # deleting data on the device, which seems wrong.
        self.smart_post_status_code(400, file_name="whatever.csv")
        self.session_participant.update(unregistered=True)
        self.smart_post_status_code(200, file_name="whatever.csv")
        self.assert_no_files_to_process
    
    def test_file_already_present(self):
        # there is a ~complex file name test, this value will match and cause that test to succeed,
        # which makes the endpoint return early.  This test will crash with the S3 invalid bucket
        # failure mode if there is no match.
        normalized_file_name = f"{self.session_study.object_id}/whatever.csv"
        self.smart_post_status_code(400, file_name=normalized_file_name)
        ftp = self.generate_file_to_process(normalized_file_name)
        self.smart_post_status_code(200, file_name=normalized_file_name, file=object())
        self.assert_one_file_to_process
        should_be_identical = FileToProcess.objects.first()
        self.assertEqual(ftp.id, should_be_identical.id)
        self.assertEqual(ftp.last_updated, should_be_identical.last_updated)
        self.assert_one_file_to_process
    
    @patch("libs.encryption.STORE_DECRYPTION_KEY_ERRORS")  # Variable's boolean value becomes True
    def test_no_file_content(self, STORE_DECRYPTION_KEY_ERRORS: MagicMock):
        # this test will fail with the s3 invalid bucket
        self.smart_post_status_code(200, file_name="whatever.csv", file="")
        self.assertEqual(DecryptionKeyError.objects.count(), 0)
        self.assert_no_files_to_process
    
    @patch("libs.encryption.STORE_DECRYPTION_KEY_ERRORS")
    @patch("database.user_models.Participant.get_private_key")
    def test_simple_decryption_key_error(
        self, get_private_key: MagicMock, STORE_DECRYPTION_KEY_ERRORS: MagicMock
    ):
        get_private_key.return_value = self.PRIVATE_KEY
        self.smart_post_status_code(200, file_name="whatever.csv", file="some_content")
        self.assertEqual(DecryptionKeyError.objects.count(), 1)
        # This construction gets us our special padding error
        self.check_decryption_key_error("libs.security.PaddingException: Incorrect padding -- ")
        self.assert_no_files_to_process
    
    @patch("libs.encryption.STORE_DECRYPTION_KEY_ERRORS")
    @patch("database.user_models.Participant.get_private_key")
    def test_simple_decryption_key_error2(
        self, get_private_key: MagicMock, STORE_DECRYPTION_KEY_ERRORS: MagicMock
    ):
        get_private_key.return_value = self.PRIVATE_KEY
        self.smart_post_status_code(200, file_name="whatever.csv", file=b"some_content")
        self.assertEqual(DecryptionKeyError.objects.count(), 1)
        # This construction gets us our special padding error
        self.check_decryption_key_error("libs.security.Base64LengthException:")
        self.assert_no_files_to_process
    
    @patch("libs.encryption.STORE_DECRYPTION_KEY_ERRORS")
    @patch("database.user_models.Participant.get_private_key")
    def test_bad_base64_length(
        self, get_private_key: MagicMock, STORE_DECRYPTION_KEY_ERRORS: MagicMock
    ):
        get_private_key.return_value = self.PRIVATE_KEY
        self.smart_post_status_code(200, file_name="whatever.csv", file=b"some_content1")
        self.assertEqual(DecryptionKeyError.objects.count(), 1)
        # This construction gets us our special padding error
        self.check_decryption_key_error(
            "libs.security.Base64LengthException: Data provided had invalid length 2 after padding was removed."
        )
        self.assert_no_files_to_process
    
    @patch("libs.encryption.STORE_DECRYPTION_KEY_ERRORS")
    @patch("database.user_models.Participant.get_private_key")
    def test_bad_base64_key(
        self, get_private_key: MagicMock, STORE_DECRYPTION_KEY_ERRORS: MagicMock
    ):
        get_private_key.return_value = self.PRIVATE_KEY
        self.smart_post_status_code(200, file_name="whatever.csv", file="some_conten/")
        self.assertEqual(DecryptionKeyError.objects.count(), 1)
        # This construction gets us our special padding error
        self.check_decryption_key_error(
            "libs.encryption.DecryptionKeyInvalidError: Decryption key not base64 encoded:"
        )
        self.assert_no_files_to_process


class TestGraph(ParticipantSessionTest):
    ENDPOINT_NAME = "mobile_pages.fetch_graph"
    
    def test(self):
        # testing this requires setting up fake survey answers to see what renders in the javascript?
        resp = self.smart_post_status_code(200)
        self.assert_present("Rendered graph for user", resp.content)


class TestWebDataConnector(SmartRequestsTestCase):
    ENDPOINT_NAME = "tableau_api.web_data_connector"
    
    def test(self):
        resp = self.smart_get(self.session_study.object_id)
        content = resp.content.decode()
        for field_name in FINAL_SERIALIZABLE_FIELD_NAMES:
            self.assert_present(field_name, content)


class TestPushNotificationSetFCMToken(ParticipantSessionTest):
    ENDPOINT_NAME = "push_notifications_api.set_fcm_token"
    
    def test_no_params_bug(self):
        # this was a 1 at start of writing tests due to a bad default value in the declaration.
        self.assertEqual(ParticipantFCMHistory.objects.count(), 0)
        
        self.session_participant.update(push_notification_unreachable_count=1)
        # FIXME: no parameters results in a 204, it should fail with a 400.
        self.smart_post_status_code(204)
        # FIXME: THIS ASSERT IS A BUG! it should be 1!
        self.assertEqual(ParticipantFCMHistory.objects.count(), 0)
    
    def test_unregister_existing(self):
        # create a new "valid" registration token (not unregistred)
        token_1 = ParticipantFCMHistory(
            participant=self.session_participant, token="some_value", unregistered=None
        )
        token_1.save()
        self.smart_post(fcm_token="some_new_value")
        token_1.refresh_from_db()
        self.assertIsNotNone(token_1.unregistered)
        token_2 = ParticipantFCMHistory.objects.last()
        self.assertNotEqual(token_1.id, token_2.id)
        self.assertIsNone(token_2.unregistered)
    
    def test_reregister_existing_valid(self):
        # create a new "valid" registration token (not unregistred)
        token = ParticipantFCMHistory(
            participant=self.session_participant, token="some_value", unregistered=None
        )
        token.save()
        # test only the one token exists
        first_time = token.last_updated
        self.smart_post(fcm_token="some_value")
        # test remains unregistered, but token still updated
        token.refresh_from_db()
        second_time = token.last_updated
        self.assertIsNone(token.unregistered)
        self.assertNotEqual(first_time, second_time)
        
    def test_reregister_existing_unregister(self):
        # create a new "valid" registration token (not unregistred)
        token = ParticipantFCMHistory(
            participant=self.session_participant, token="some_value", unregistered=timezone.now()
        )
        token.save()
        # test only the one token exists
        first_time = token.last_updated
        self.smart_post(fcm_token="some_value")
        # test is to longer unregistred, and was updated
        token.refresh_from_db()
        second_time = token.last_updated
        self.assertIsNone(token.unregistered)
        self.assertNotEqual(first_time, second_time)
        