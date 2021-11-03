from django.http import response
from django.urls import reverse
from constants.researcher_constants import ResearcherRole
from tests.common import CommonTestCase
from pprint import pprint

class TestAuthentication(CommonTestCase):

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


class TestAdminPages(CommonTestCase):

    def setUp(self) -> None:
        self.default_researcher
        self.do_default_login()  # setup the default user, we always need it.
        return super().setUp()

    def test_render_view_study_researcher(self):
        response = self._render_view_study(ResearcherRole.researcher)
        self.assertEqual(response.status_code, 200)

    def test_render_view_study_site_admin(self):
        researcher = self.default_researcher
        researcher.site_admin = True
        researcher.save()
        response = self._render_view_study(None)
        self.assertEqual(response.status_code, 200)

    def test_render_view_study_study_admin(self):
        response = self._render_view_study(ResearcherRole.study_admin)
        self.assertEqual(response.status_code, 200)

    def test_render_view_study_no_relation(self):
        response = self._render_view_study(None)
        self.assertEqual(response.status_code, 403)

    def _render_view_study(self, relation) -> response.HttpResponse:
        self.default_researcher
        if relation:
            self.default_study_relation(relation)
        return self.client.get(
            reverse("admin_pages.view_study", kwargs={"study_id": self.default_study.id}),
        )
