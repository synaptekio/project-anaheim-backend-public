from unittest.mock import patch

from django.http import response
from django.urls import reverse
from tests.common import CommonTestCase, DefaultLoggedInCommonTestCase, GeneralApiMixin

from constants.message_strings import (NEW_PASSWORD_8_LONG, NEW_PASSWORD_MISMATCH,
    NEW_PASSWORD_RULES_FAIL, PASSWORD_RESET_SUCCESS, WRONG_CURRENT_PASSWORD)
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
        self.assertPresentIn(api_key.access_key_id, response.content)


class TestResetAdminPassword(DefaultLoggedInCommonTestCase, GeneralApiMixin):
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
        self.assertPresentIn(PASSWORD_RESET_SUCCESS, self.manage_credentials_content)

    def test_reset_admin_password_wrong(self):
        self.do_post(
            current_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
            new_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
            confirm_new_password=self.DEFAULT_RESEARCHER_PASSWORD + "1",
        )
        researcher = self.default_researcher
        self.assertTrue(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD))
        self.assertFalse(researcher.check_password(researcher.username, self.DEFAULT_RESEARCHER_PASSWORD + "1"))
        self.assertPresentIn(WRONG_CURRENT_PASSWORD, self.manage_credentials_content)

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
        self.assertPresentIn(NEW_PASSWORD_RULES_FAIL, self.manage_credentials_content)

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
        self.assertPresentIn(NEW_PASSWORD_8_LONG, self.manage_credentials_content)

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
        self.assertPresentIn(NEW_PASSWORD_MISMATCH, self.manage_credentials_content)


class TestResetDownloadApiCredentials(DefaultLoggedInCommonTestCase, GeneralApiMixin):
    ENDPOINT_NAME = "admin_pages.reset_download_api_credentials"

    def test_reset(self):
        self.assertIsNone(self.default_researcher.access_key_id)
        self.do_post()
        self.assertIsNotNone(self.default_researcher.access_key_id)
        self.assertPresentIn("Your Data-Download API access credentials have been reset",
                             self.manage_credentials_content)


class TestNewTableauApiKey(DefaultLoggedInCommonTestCase, GeneralApiMixin):
    ENDPOINT_NAME = "admin_pages.new_tableau_api_key"
    # FIXME: when NewApiKeyForm does anything develop a test for naming the key.
    def test_reset(self):
        self.assertIsNone(self.default_researcher.api_keys.first())
        self.do_post()
        self.assertIsNotNone(self.default_researcher.api_keys.first())
        self.assertPresentIn("New Tableau API credentials have been generated for you",
                             self.manage_credentials_content)



