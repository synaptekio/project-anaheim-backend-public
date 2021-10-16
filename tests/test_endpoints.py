from tests.common import CommonTestCase
from pprint import pprint
from django.urls import reverse


class TestAuthentication(CommonTestCase):

    def setUp(self) -> None:
        print()
        return super().setUp()

    def test_login_page(self):
        # make sure the login page loads without logging you in when it should not
        response = self.client.post(reverse("login_pages.login_page"))
        self.assertEqual(response.status_code, 200)
        # this should uniquely identify the login page
        assert b'<form method="POST" action="/validate_login">' in response.content

    def test_logging_in_successfully(self):
        self.default_researcher  # create the default researcher
        r = self.client.post(
            reverse("login_pages.validate_login"),
            data={"username": self.RESEARCHER_NAME, "password": self.RESEARCHER_PASSWORD}
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("admin_pages.choose_study"))

    def test_logging_in_fail(self):
        r = self.client.post(
            reverse("login_pages.validate_login"),
            data={"username": self.RESEARCHER_NAME, "password": self.RESEARCHER_PASSWORD}
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("login_pages.login_page"))