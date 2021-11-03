from pprint import pprint
from unittest.mock import patch

from django.http import response
from django.urls import reverse
from database.security_models import ApiKey
from tests.common import CommonTestCase, DefaultLoggedInCommonTestCase

from constants.researcher_constants import ResearcherRole


class TestLoginPages(CommonTestCase):
    """ Basic authentication test, make sure that the machinery for logging a user
    in and out are functional at setting and clearing a session. """

    def test_load_login_page_while_not_logged_in(self):
        # make sure the login page loads without logging you in when it should not
        response = self.client.post(reverse("login_pages.login_page"))
        self.assertEqual(response.status_code, 200)
        # this should uniquely identify the login page
        assert b'<form method="POST" action="/validate_login">' in response.content

    def test_load_login_page_while_logged_in(self):
        # make sure the login page loads without logging you in when it should not
        self.default_researcher  # create the default researcher
        self.do_default_login()
        response = self.client.post(reverse("login_pages.login_page"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_pages.choose_study"))
        # this should uniquely identify the login page
        assert b'<form method="POST" action="/validate_login">' not in response.content

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
        study = self.default_study
        researcher = self.default_researcher
        self.client.get(reverse("admin_pages.manage_credentials"))

        api_key = ApiKey.generate(
            researcher=researcher, has_tableau_api_permissions=True, readable_name="anyting, realy",
        )
        response = self.client.get(reverse("admin_pages.manage_credentials"))
        self.assertIn(api_key.access_key_id.encode(), response.content)
