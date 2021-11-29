from django.core.exceptions import ValidationError

from database.study_models import DeviceSettings, Study
from tests.common import CommonTestCase


# This file contains some minimal tests of some models.  They are old, they were written before 
# components of helpers.py or common.py were substantially developed for the endpoint tests.
# If these tests fail please review the tests in their entirety.  At time of writing this comment
# there is no plan to extend these tests substantially, but the tests do pass.

class StudyModelTests(CommonTestCase):

    # Study model tests:
    def test_study_create_with_object_id(self):
        self.default_forest_params  # creating studies will fail if this isn't populated in db.
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
        self.default_forest_params  # creating studies will fail if this isn't populated in db.
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
        self.default_forest_params  # creating studies will fail if this isn't populated in db.
        study_names = ['My studies', 'MY STUDY', 'my_study', 'your study']
        encryption_key = 'aabbccddeeffgghhiijjkkllmmnnoopp'
        for name in study_names:
            good_study = Study.create_with_object_id(name=name, encryption_key=encryption_key)

        self.assertIn(good_study, Study.get_all_studies_by_name())
        self.assertEqual(list(Study.get_all_studies_by_name().values_list('name', flat=True)), study_names)

        bad_study = Study.create_with_object_id(name='name', encryption_key=encryption_key, deleted=True)
        self.assertNotIn(bad_study, Study.get_all_studies_by_name())
