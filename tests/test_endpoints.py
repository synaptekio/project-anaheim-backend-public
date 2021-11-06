from unittest.mock import patch

from django.http import response
from django.urls import reverse
from database.user_models import Researcher
from tests.common import (ApiRedirectMixin, ApiSessionMixin, CommonTestCase,
    DefaultLoggedInCommonTestCase, GeneralPageMixin)

from constants.data_stream_constants import ALL_DATA_STREAMS
from constants.message_strings import (NEW_PASSWORD_8_LONG, NEW_PASSWORD_MISMATCH,
    NEW_PASSWORD_RULES_FAIL, PASSWORD_RESET_SUCCESS, TABLEAU_API_KEY_IS_DISABLED,
    TABLEAU_NO_MATCHING_API_KEY, WRONG_CURRENT_PASSWORD)
from constants.researcher_constants import ResearcherRole
from database.security_models import ApiKey


class TestLoginPages(CommonTestCase):
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
        self.default_researcher  # create the default researcher
        self.do_default_login()
        response = self.client.post(reverse("login_pages.login_page"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_pages.choose_study"))
        # this should uniquely identify the login page
        self.assertNotIn(b'<form method="POST" action="/validate_login">', response.content)

    def test_logging_in_success(self):
        self.default_researcher  # create the default researcher
        r = self.do_default_login()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("admin_pages.choose_study"))

    def test_logging_in_fail(self):
        r = self.do_default_login()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("login_pages.login_page"))

    def test_logging_out(self):
        # create the default researcher, login, logout, attempt going to main page,
        self.default_researcher
        self.do_default_login()
        self.client.get(reverse("admin_pages.logout_admin"))
        r = self.client.get(reverse("admin_pages.choose_study"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("login_pages.login_page"))


class TestViewStudy(DefaultLoggedInCommonTestCase):
    """ view_study is pretty simple, no custom content in the :
    tests push_notifications_enabled, is_site_admin, study.is_test, study.forest_enabled
    populates html elements with custom field values
    populates html elements of survey buttons
    """

    def test_view_study_no_relation(self):
        response = self.render_view_study(None)
        self.assertEqual(response.status_code, 403)

    def test_view_study_researcher(self):
        study = self.default_study
        study.update(is_test=True)

        response = self.render_view_study(ResearcherRole.researcher)
        self.assertEqual(response.status_code, 200)

        # template has several customizations, test for some relevant strings
        self.assertIn(b"This is a test study.", response.content)
        self.assertNotIn(b"This is a production study", response.content)
        study.update(is_test=False)

        response = self.render_view_study(ResearcherRole.researcher)
        self.assertNotIn(b"This is a test study.", response.content)
        self.assertIn(b"This is a production study", response.content)

    def test_view_study_study_admin(self):
        response = self.render_view_study(ResearcherRole.study_admin)
        self.assertEqual(response.status_code, 200)

    @patch('pages.admin_pages.check_firebase_instance')
    def test_view_study_site_admin(self, check_firebase_instance):
        study = self.default_study
        researcher = self.default_researcher
        researcher.update(site_admin=True)

        # test rendering with several specifc values set to observe the rendering changes
        study.update(forest_enabled=False)
        check_firebase_instance.return_value = False
        response = self.render_view_study(None)  # must be None
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Edit interventions for this study", response.content)
        self.assertNotIn(b"View Forest Task Log", response.content)

        check_firebase_instance.return_value = True
        study.update(forest_enabled=True)
        response = self.render_view_study(None)
        self.assertIn(b"Edit interventions for this study", response.content)
        self.assertIn(b"View Forest Task Log", response.content)
        # assertInHTML is several hundred times slower but has much better output when it fails...
        # self.assertInHTML("Edit interventions for this study", response.content.decode())

    def render_view_study(self, relation) -> response.HttpResponse:
        self.default_researcher
        if relation:
            self.default_study_relation(relation)
        return self.client.get(
            reverse("admin_pages.view_study", kwargs={"study_id": self.default_study.id}),
        )


class TestManageCredentials(DefaultLoggedInCommonTestCase):

    def test_manage_credentials(self):
        self.default_study
        researcher = self.default_researcher
        self.client.get(reverse("admin_pages.manage_credentials"))

        api_key = ApiKey.generate(
            researcher=researcher, has_tableau_api_permissions=True, readable_name="anyting, realy",
        )
        response = self.client.get(reverse("admin_pages.manage_credentials"))
        self.assert_present(api_key.access_key_id, response.content)


class TestResetAdminPassword(DefaultLoggedInCommonTestCase, ApiRedirectMixin):
    # test for every case and messages present on the page
    ENDPOINT_NAME = "admin_pages.reset_admin_password"

    def test_reset_admin_password_success(self):
        self.do_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD,
            new_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
            confirm_new_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
        )
        # we are ... teleologically correct here mimicking the code...
        researcher = self.default_researcher
        self.assertFalse(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD + "1"))
        # Always stick the check for the string after the check for the db mutation.
        self.assert_present(PASSWORD_RESET_SUCCESS, self.manage_credentials_content)

    def test_reset_admin_password_wrong(self):
        self.do_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
            new_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
            confirm_new_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
        )
        researcher = self.default_researcher
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertFalse(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD + "1"))
        self.assert_present(WRONG_CURRENT_PASSWORD, self.manage_credentials_content)

    def test_reset_admin_password_rules_fail(self):
        non_default = "abcdefghijklmnop"
        self.do_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD,
            new_password=non_default,
            confirm_new_password=non_default,
        )
        researcher = self.default_researcher
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertFalse(researcher.check_password(researcher.username, non_default))
        self.assert_present(NEW_PASSWORD_RULES_FAIL, self.manage_credentials_content)

    def test_reset_admin_password_too_short(self):
        non_default = "a1#"
        self.do_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD,
            new_password=non_default,
            confirm_new_password=non_default,
        )
        researcher = self.default_researcher
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertFalse(researcher.check_password(researcher.username, non_default))
        self.assert_present(NEW_PASSWORD_8_LONG, self.manage_credentials_content)

    def test_reset_admin_password_mismatch(self):
        #has to pass the length and character checks
        self.do_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD,
            new_password="aA1#aA1#aA1#",
            confirm_new_password="aA1#aA1#aA1#aA1#",
        )
        researcher = self.default_researcher
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertFalse(researcher.check_password(researcher.username, "aA1#aA1#aA1#"))
        self.assertFalse(researcher.check_password(researcher.username, "aA1#aA1#aA1#aA1#"))
        self.assert_present(NEW_PASSWORD_MISMATCH, self.manage_credentials_content)


class TestResetDownloadApiCredentials(DefaultLoggedInCommonTestCase, ApiRedirectMixin):
    ENDPOINT_NAME = "admin_pages.reset_download_api_credentials"

    def test_reset(self):
        self.assertIsNone(self.default_researcher.access_key_id)
        self.do_post()
        self.assertIsNotNone(self.default_researcher.access_key_id)
        self.assert_present("Your Data-Download API access credentials have been reset",
                             self.manage_credentials_content)


class TestNewTableauApiKey(DefaultLoggedInCommonTestCase, ApiRedirectMixin):
    ENDPOINT_NAME = "admin_pages.new_tableau_api_key"
    # FIXME: when NewApiKeyForm does anything develop a test for naming the key, probably more.
    #  (need to review the tableau tests)
    def test_reset(self):
        self.assertIsNone(self.default_researcher.api_keys.first())
        self.do_post()
        self.assertIsNotNone(self.default_researcher.api_keys.first())
        self.assert_present("New Tableau API credentials have been generated for you",
                             self.manage_credentials_content)


# admin_pages.disable_tableau_api_key
class TestDisableTableauApiKey(DefaultLoggedInCommonTestCase, ApiRedirectMixin):
    ENDPOINT_NAME = "admin_pages.disable_tableau_api_key"

    def test_disable_success(self):
        # basic test
        api_key = ApiKey.generate(
            researcher=self.default_researcher,
            has_tableau_api_permissions=True,
            readable_name="something",
        )
        self.do_post(api_key_id=api_key.access_key_id)
        self.assertFalse(self.default_researcher.api_keys.first().is_active)
        content = self.manage_credentials_content
        self.assert_present(api_key.access_key_id, content)
        self.assert_present("is now disabled", content)

    def test_no_match(self):
        # fail with empty and fail with success
        self.do_post(api_key_id="abc")
        self.assert_present(TABLEAU_NO_MATCHING_API_KEY, self.manage_credentials_content)
        api_key = ApiKey.generate(
            researcher=self.default_researcher,
            has_tableau_api_permissions=True,
            readable_name="something",
        )
        self.do_post(api_key_id="abc")
        api_key.refresh_from_db()
        self.assertTrue(api_key.is_active)
        self.assert_present(TABLEAU_NO_MATCHING_API_KEY, self.manage_credentials_content)

    def test_already_disabled(self):
        api_key = ApiKey.generate(
            researcher=self.default_researcher,
            has_tableau_api_permissions=True,
            readable_name="something",
        )
        api_key.update(is_active=False)
        self.do_post(api_key_id=api_key.access_key_id)
        api_key.refresh_from_db()
        self.assertFalse(api_key.is_active)
        self.assert_present(TABLEAU_API_KEY_IS_DISABLED, self.manage_credentials_content)


class TestDashboard(DefaultLoggedInCommonTestCase, GeneralPageMixin):
    ENDPOINT_NAME = "dashboard_api.dashboard_page"

    def test_dashboard(self):
        # default user and default study already instantiated
        self.default_study_relation(ResearcherRole.researcher)
        resp = self.do_get(str(self.default_study.id))
        self.assertEqual(resp.status_code, 200)
        self.assert_present("Choose a participant or data stream to view", resp.content)


# FIXME: dashboard is going to require a fixture to populate data.
class TestDashboardStream(DefaultLoggedInCommonTestCase):

    # dashboard_api.get_data_for_dashboard_datastream_display
    def test_data_streams(self):
        # test is currently limited to rendering the page for each data stream but with no data in it
        self.default_researcher
        self.default_study_relation()
        for data_stream in ALL_DATA_STREAMS:
            url = reverse(
                "dashboard_api.get_data_for_dashboard_datastream_display",
                kwargs=dict(study_id=self.default_study.id, data_stream=data_stream),
            )
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)

    # dashboard_api.get_data_for_dashboard_patient_display
    def test_patient_display(self):
        # this page renders with almost no data
        self.default_researcher
        self.default_study_relation()
        url = reverse(
            "dashboard_api.get_data_for_dashboard_patient_display",
            kwargs=dict(study_id=self.default_study.id, patient_id=self.default_participant.patient_id),
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)


# system_admin_pages.manage_researchers
class TestManageResearchers(DefaultLoggedInCommonTestCase, GeneralPageMixin):
    ENDPOINT_NAME = "system_admin_pages.manage_researchers"

    def test_researcher(self):
        self.default_researcher
        self.default_study_relation
        resp = self.do_get()
        self.assertEqual(resp.status_code, 403)

    def test_study_admin(self):
        self.default_researcher
        self.default_study_relation(ResearcherRole.study_admin)
        resp = self.do_get()
        self.assertEqual(resp.status_code, 200)

    def test_site_admin(self):
        self.default_researcher.update(site_admin=True)
        resp = self.do_get()
        self.assertEqual(resp.status_code, 200)

    def test_render_study_admin(self):
        self.default_researcher
        self.default_study_relation(ResearcherRole.study_admin)
        self._test_render_with_researchers()
        # make sure that site admins are not present
        r4 = self.generate_researcher()
        r4.update(site_admin=True)
        resp = self.do_get()
        self.assert_not_present(r4.username, resp.content)
        self.assertEqual(resp.status_code, 200)
        # make sure that unaffiliated researchers are not present
        r5 = self.generate_researcher()
        resp = self.do_get()
        self.assert_not_present(r5.username, resp.content)
        self.assertEqual(resp.status_code, 200)

    def test_render_site_admin(self):
        self.default_researcher.update(site_admin=True)
        self._test_render_with_researchers()
        # make sure that site admins ARE present
        r4 = self.generate_researcher()
        r4.update(site_admin=True)
        resp = self.do_get()
        self.assert_present(r4.username, resp.content)
        self.assertEqual(resp.status_code, 200)
        # make sure that unaffiliated researchers ARE present
        r5 = self.generate_researcher()
        resp = self.do_get()
        self.assert_present(r5.username, resp.content)
        self.assertEqual(resp.status_code, 200)

    def _test_render_with_researchers(self):
        # render the page with a regular user
        r2 = self.generate_researcher()
        self.generate_study_relation(r2, self.default_study, ResearcherRole.researcher)
        resp = self.do_get()
        self.assertEqual(resp.status_code, 200)
        self.assert_present(r2.username, resp.content)

        # render with 2 reseaorchers
        r3 = self.generate_researcher()
        self.generate_study_relation(r3, self.default_study, ResearcherRole.researcher)
        resp = self.do_get()
        self.assert_present(r2.username, resp.content)
        self.assert_present(r3.username, resp.content)
        self.assertEqual(resp.status_code, 200)



class TestEditResearcher(DefaultLoggedInCommonTestCase, GeneralPageMixin):
    ENDPOINT_NAME = "system_admin_pages.edit_researcher"

    # render self
    def test_render_for_self_as_researcher(self):
        # should fail
        self.default_study_relation()
        resp = self.do_get(self.default_researcher.id)
        self.assertEqual(resp.status_code, 403)

    def test_render_for_self_as_study_admin(self):
        # ensure it renders (buttons will be disabled)
        self.default_study_relation(ResearcherRole.study_admin)
        resp = self.do_get(self.default_researcher.id)
        self.assertEqual(resp.status_code, 200)

    def test_render_for_self_as_site_admin(self):
        # ensure it renders (buttons will be disabled)
        self.default_researcher.update(site_admin=True)
        resp = self.do_get(self.default_researcher.id)
        self.assertEqual(resp.status_code, 200)

    def test_render_for_researcher_as_researcher(self):
        # should fail
        self.default_study_relation()
        # set up, test when not on study
        r2 = self.generate_researcher()
        resp = self.do_get(r2.id)
        self.assertEqual(resp.status_code, 403)
        self.assert_not_present(r2.username, resp.content)
        # attach other researcher and try again
        self.generate_study_relation(r2, self.default_study, ResearcherRole.researcher)
        self.assertEqual(resp.status_code, 403)
        self.assert_not_present(r2.username, resp.content)

    # study admin, renders
    def test_render_valid_researcher_as_study_admin(self):
        self.default_study_relation(ResearcherRole.study_admin)
        self._test_render_generic_under_study()

    def test_render_researcher_with_no_study_as_study_admin(self):
        self.default_study_relation(ResearcherRole.study_admin)
        self._test_render_researcher_with_no_study()

    # site admin, renders
    def test_render_valid_researcher_as_site_admin(self):
        self.default_researcher.update(site_admin=True)
        self._test_render_generic_under_study()

    def test_render_researcher_with_no_study_as_site_admin(self):
        self.default_researcher.update(site_admin=True)
        self._test_render_researcher_with_no_study()

    def _test_render_generic_under_study(self):
        r2 = self.generate_researcher()
        self.generate_study_relation(r2, self.default_study, ResearcherRole.researcher)
        resp = self.do_get(r2.id)
        self.assertEqual(resp.status_code, 200)
        self.assert_present(r2.username, resp.content)

    def _test_render_researcher_with_no_study(self):
        r2 = self.generate_researcher()
        resp = self.do_get(r2.id)
        self.assertEqual(resp.status_code, 200)
        self.assert_present(r2.username, resp.content)


class TestElevateResearcher(DefaultLoggedInCommonTestCase, ApiSessionMixin):
    ENDPOINT_NAME = "system_admin_pages.elevate_researcher"
    # this one is tedious.

    def test_self_as_researcher_on_study(self):
        self.default_researcher
        self.default_study_relation(ResearcherRole.researcher)
        self.do_basic_test(self.default_researcher, 403)

    def test_self_as_study_admin_on_study(self):
        self.default_researcher
        self.default_study_relation(ResearcherRole.study_admin)
        self.do_basic_test(self.default_researcher, 403)

    def test_researcher_as_study_admin_on_study(self):
        # this is the only case that succeeds.
        self.default_researcher
        self.default_study_relation(ResearcherRole.study_admin)
        r2 = self.generate_researcher()
        relation = self.generate_study_relation(r2, self.default_study, ResearcherRole.researcher)
        self.do_basic_test(r2, 302)
        relation.refresh_from_db()
        self.assertEqual(relation.relationship, ResearcherRole.study_admin)

    def test_study_admin_as_study_admin_on_study(self):
        self.default_researcher
        self.default_study_relation(ResearcherRole.study_admin)
        r2 = self.generate_researcher()
        relation = self.generate_study_relation(r2, self.default_study, ResearcherRole.study_admin)
        self.do_basic_test(r2, 403)
        relation.refresh_from_db()
        self.assertEqual(relation.relationship, ResearcherRole.study_admin)

    def test_site_admin_as_study_admin_on_study(self):
        self.default_researcher
        self.default_study_relation(ResearcherRole.study_admin)
        r2 = self.generate_researcher()
        r2.update(site_admin=True)
        self.do_basic_test(r2, 403)
        self.assertFalse(r2.study_relations.filter(study=self.default_study).exists())

    def test_site_admin_as_site_admin(self):
        self.default_researcher.update(site_admin=True)
        r2 = self.generate_researcher()
        r2.update(site_admin=True)
        self.do_basic_test(r2, 403)
        self.assertFalse(r2.study_relations.filter(study=self.default_study).exists())


