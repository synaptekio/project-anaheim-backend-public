import urls

from database.study_models import Study
from database.survey_models import Survey
from database.user_models import Participant, Researcher
from tests.common import CommonTestCase


class TestDefaults(CommonTestCase):
    
    def test_defaults(self):
        researcher = self.session_researcher
        participant = self.default_participant()
        study = self.session_study
        survey = self.session_survey
        assert Researcher.objects.filter(pk=researcher.pk).exists()
        assert Participant.objects.filter(pk=participant.pk).exists()
        assert Study.objects.filter(pk=study.pk).exists()
        assert Survey.objects.filter(pk=survey.pk).exists()


class TestUrls(CommonTestCase):
    
    def test(self):
        # this is a consistency test - all endpoint names really should reflect reality with a name
        # composed of "module_name.function_name"
        for url in urls.urlpatterns:
            
            if url.default_args == {'default_args': {'document_root': 'frontend/static/'}}:
                continue
            declared_module_name, declared_function_name = url.name.split(".")
            actual_callback_name = url.callback.__name__
            callback_module_name = url.callback.__module__.split(".")[-1]
            self.assertEqual(actual_callback_name, declared_function_name)
            self.assertEqual(declared_module_name, callback_module_name)
