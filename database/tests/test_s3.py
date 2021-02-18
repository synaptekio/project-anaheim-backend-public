from django.test import TransactionTestCase

from database.study_models import Study
from libs.s3 import s3_upload, s3_retrieve


class TestRoutes(TransactionTestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    # def test_s3_upload(self):
    #     study = Study(object_id='0vsvxgyx5skpI0ndOSAk1Duf',
    #                   encryption_key='aabbccddefggiijjkklmnoppqqrrsstt',
    #                   name='TEST_STUDY_FOR_TESTS')
    #     study.save()
    #     test_data = "THIS IS TEST DATA"
    #     s3_upload("test_file_for_tests.txt", test_data, study.object_id)
    #     s3_data = s3_retrieve("test_file_for_tests.txt", study.object_id)
    #     self.assertEqual(s3_data, test_data)
