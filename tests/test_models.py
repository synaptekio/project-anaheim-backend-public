from django.core.exceptions import ValidationError

from database.models import *
from database.tests.common import CommonTestCase

# Fixme: everything in this file
#   needs to be rewritten, written, and reviewed.  No work has occurred on this code since django
#   transition, everything is out of date.

class ResearcherModelTests(CommonTestCase):

    def test_researcher_create_with_password(self): raise NotImplementedError

    def test_researcher_check_password(self): raise NotImplementedError

    def test_researcher_validate_password(self): raise NotImplementedError

    def test_researcher_set_password(self): raise NotImplementedError

    def test_researcher_elevate_to_admin(self): raise NotImplementedError

    def test_researcher_validate_access_credentials(self): raise NotImplementedError

    def test_researcher_reset_access_credentials(self): raise NotImplementedError


class ParticipantModelTests(CommonTestCase):

    def test_participant_create(self): raise NotImplementedError

    def test_participant_debug_validate_password(self): raise NotImplementedError

    def test_participant_validate_password(self): raise NotImplementedError

    def test_participant_reset_password(self): raise NotImplementedError

    def test_participant_set_device(self): raise NotImplementedError

    def test_participant_set_os_type(self): raise NotImplementedError

    def test_participant_clear_device(self): raise NotImplementedError

    def test_participant_set_password(self): raise NotImplementedError


class StudyModelTests(CommonTestCase):

    # Study model tests:
    def test_study_create_with_object_id(self):
        self.assertEqual(Study.objects.count(), 0)
        self.assertEqual(DeviceSettings.objects.count(), 0)
        study_name = 'my study'
        encryption_key = 'aabbccddeeffgghhiijjkkllmmnnoopp'
        Study.create_with_object_id(name=study_name, encryption_key=encryption_key)
        new_study = Study.objects.get()
        new_ds = DeviceSettings.objects.get()
        self.assertEqual(Study.objects.count(), 1)
        self.assertEqual(DeviceSettings.objects.count(), 1)
        self.assertEqual(new_study.name, study_name)
        self.assertEqual(new_study.encryption_key, encryption_key)
        self.assertEqual(len(new_study.object_id), 24)
        self.assertEqual(new_study.device_settings, new_ds)
        self.assertFalse(new_study.deleted)

    def test_study_validation(self):
        study_name = 'my study'
        good_encryption_key = 'aabbccddeeffgghhiijjkkllmmnnoopp'
        short_encryption_key = 'aabbccddeeffgghhiijjkkllmm'
        long_encryption_key = 'aabbccddeeffgghhiijjkkllmmnnooppqqrrsstt'
        with self.assertRaises(ValidationError):
            Study.create_with_object_id(name=study_name, encryption_key=short_encryption_key)
        with self.assertRaises(ValidationError):
            Study.create_with_object_id(name=study_name, encryption_key=long_encryption_key)

        bad_object_id = 'I am too long to be an ObjectID'
        with self.assertRaises(ValidationError):
            Study.objects.create(
                name=study_name, encryption_key=good_encryption_key, object_id=bad_object_id
            )

        Study.create_with_object_id(name=study_name, encryption_key=good_encryption_key)
        with self.assertRaises(ValidationError):
            Study.create_with_object_id(name=study_name, encryption_key=good_encryption_key)

    def test_get_all_studies_by_name(self):
        study_names = ['My studies', 'MY STUDY', 'my_study', 'your study']
        encryption_key = 'aabbccddeeffgghhiijjkkllmmnnoopp'
        for name in study_names:
            good_study = Study.create_with_object_id(name=name, encryption_key=encryption_key)

        self.assertIn(good_study, Study.get_all_studies_by_name())
        self.assertEqual(list(Study.get_all_studies_by_name().values_list('name', flat=True)), study_names)

        bad_study = Study.create_with_object_id(name='name', encryption_key=encryption_key, deleted=True)
        self.assertNotIn(bad_study, Study.get_all_studies_by_name())

    def test_add_researcher(self): raise NotImplementedError

    def test_remove_researcher(self): raise NotImplementedError

    def test_add_survey(self): raise NotImplementedError

    def reference_participant(self): pass

    def translated_reference_participant(self): pass

    def create_django_reference_participant(self): pass

    def compare_participant(self, researcher): pass


class SurveyModelTests(CommonTestCase):
    pass


class DeviceSettingsTests(CommonTestCase):
    pass


class DataAccessModelTests(CommonTestCase):

    # ChunkRegistry model tests:
    def test_add_new_chunk(self): raise NotImplementedError

    def test_get_chunks_time_range(self): raise NotImplementedError

    def test_update_chunk_hash(self): raise NotImplementedError

    def test_low_memory_update_chunk_hash(self): raise NotImplementedError


# class ProfilingModelTests(CommonTestCase):
#
#     # Upload model tests
#     def test_get_trailing(self): raise NotImplementedError
#
#     def test_get_trailing_count(self): raise NotImplementedError
#
#     def test_weekly_stats(self): raise NotImplementedError
#
#     # DecryptionKeyError tests
#     def decode(self): pass
