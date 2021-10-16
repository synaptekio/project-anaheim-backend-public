from tests.common import CommonTestCase
from pprint import pprint
from django.urls import reverse


class TestAuthentication(CommonTestCase):

    def setUp(self) -> None:
        print()  # this makes print statements during debugging tests less obnoxious
        return super().setUp()

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
