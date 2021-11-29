
from authentication.tableau_authentication import (check_tableau_permissions,
    TableauAuthenticationFailed, TableauPermissionDenied)
from constants.tableau_api_constants import X_ACCESS_KEY_ID, X_ACCESS_KEY_SECRET
from database.security_models import ApiKey
from database.user_models import StudyRelation
from serializers.tableau_serializers import SummaryStatisticDailySerializer
from tests.common import ResearcherSessionTest, TableauAPITest


class TestNewTableauAPIKey(ResearcherSessionTest):
    ENDPOINT_NAME = "admin_pages.new_tableau_api_key"
    
    def test_new_api_key(self):
        """ Asserts that:
            -one new api key is added to the database
            -that api key is linked to the logged in researcher
            -the correct readable name is associated with the key
            -no other api keys were created associated with that researcher
            -that api key is active and has tableau access  """
        self.assertEqual(ApiKey.objects.count(), 0)
        resp = self.smart_post(readable_name="test_generated_api_key")
        self.assertEqual(ApiKey.objects.count(), 1)
        api_key = ApiKey.objects.get(readable_name="test_generated_api_key")
        self.assertEqual(api_key.researcher.id, self.session_researcher.id)
        self.assertTrue(api_key.is_active)
        self.assertTrue(api_key.has_tableau_api_permissions)


class TestDisableTableauAPIKey(TableauAPITest):
    ENDPOINT_NAME = "admin_pages.disable_tableau_api_key"
    
    def test_disable_tableau_api_key(self):
        """ Asserts that:
            -exactly one fewer active api key is present in the database
            -the api key is no longer active """
        self.assertEqual(ApiKey.objects.filter(is_active=True).count(), 1)
        self.smart_post(api_key_id=self.api_key_public)
        self.assertEqual(ApiKey.objects.filter(is_active=True).count(), 0)
        self.assertFalse(ApiKey.objects.get(access_key_id=self.api_key_public).is_active)


class TestGetTableauDaily(TableauAPITest):
    ENDPOINT_NAME = "tableau_api.get_tableau_daily"
    
    def test_summary_statistics_daily_view(self):
        # unpack the raw headers like this, they magically just work because http language is weird
        resp = self.smart_get(self.session_study.object_id, **self.raw_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'[]')


class TableauApiAuthTests(TableauAPITest):
    """ Test methods of the api authentication system """
    
    def test_check_permissions_working(self):
        # if this doesn't raise an error in has succeeded
        check_tableau_permissions(self.default_header, study_object_id=self.session_study.object_id)
    
    def test_check_permissions_none(self):
        ApiKey.objects.all().delete()
        with self.assertRaises(TableauAuthenticationFailed) as cm:
            check_tableau_permissions(
                self.default_header, study_object_id=self.session_study.object_id
            )
    
    def test_check_permissions_inactive(self):
        self.api_key.update(is_active=False)
        with self.assertRaises(TableauAuthenticationFailed) as cm:
            check_tableau_permissions(
                self.default_header, study_object_id=self.session_study.object_id
            )
    
    def test_check_permissions_bad_secret(self):
        # note that ':' does not appear in base64 encoding, preventing any collision errors based on
        # the current implementation.
        class NotRequest:
            headers = {
                X_ACCESS_KEY_ID: self.api_key_public,
                X_ACCESS_KEY_SECRET: ":::" + self.api_key_private[3:],
            }
        with self.assertRaises(TableauAuthenticationFailed) as cm:
            check_tableau_permissions(
                NotRequest, study_object_id=self.session_study.object_id
            )
    
    def test_check_permissions_no_tableau(self):
        self.api_key.update(has_tableau_api_permissions=False)
        # ApiKey.objects.filter(access_key_id=self.api_key_public).update(
        #     has_tableau_api_permissions=False
        # )
        with self.assertRaises(TableauPermissionDenied) as cm:
            check_tableau_permissions(
                self.default_header, study_object_id=self.session_study.object_id
            )
    
    def test_check_permissions_bad_study(self):
        self.assertFalse(ApiKey.objects.filter(access_key_id=" bad study id ").exists())
        with self.assertRaises(TableauPermissionDenied) as cm:
            check_tableau_permissions(
                self.default_header, study_object_id=" bad study id "
            )
    
    def test_check_permissions_no_study_permission(self):
        StudyRelation.objects.filter(
            study=self.session_study, researcher=self.session_researcher).delete()
        with self.assertRaises(TableauPermissionDenied) as cm:
            check_tableau_permissions(
                self.default_header, study_object_id=self.session_study.object_id
            )
    
    def test_summary_statistic_daily_serializer(self):
        serializer = SummaryStatisticDailySerializer()
        self.assertFalse("created_on" in serializer.fields)
        self.assertFalse("last_updated" in serializer.fields)
