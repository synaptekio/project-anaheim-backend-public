from typing import Optional

from constants.researcher_constants import ResearcherRole
from database.study_models import Study
from database.survey_models import Survey
from database.tableau_api_models import ForestParam
from database.user_models import Participant, Researcher, StudyRelation
from libs.security import generate_easy_alphanumeric_string


class ReferenceObjectMixin:
    DEFAULT_RESEARCHER_NAME = "researcher"
    DEFAULT_RESEARCHER_PASSWORD = "abcABC123!@#"
    DEFAULT_STUDY_NAME = "teststudy"
    DEFAULT_SURVEY_OBJECT_ID = 'u1Z3SH7l2xNsw72hN3LnYi96'

    # for all defaults make sure to maintain the pattern that includes the use of the save function

    @property
    def default_forest_params(self) -> ForestParam:
        try:
            return self._default_forest_params
        except AttributeError:
            pass
        # there is an actual default ForestParams defined in a migration.
        self._default_forest_params = ForestParam.objects.get(default=True)
        return self._default_forest_params

    @property
    def default_study(self) -> Study:
        try:
            return self._default_study
        except AttributeError:
            pass
        study = Study(
            name=self.DEFAULT_STUDY_NAME,
            encryption_key="thequickbrownfoxjumpsoverthelazy",
            object_id="2Mwjb91zSWzHgOrQahEvlu5v",
            is_test=True,
            timezone_name="America/New_York",
            deleted=False,
            forest_enabled=True,
            forest_param=self.default_forest_params,
        )
        study.save()
        self._default_study = study
        return study

    def default_study_relation(self, relation: str = ResearcherRole.researcher) -> StudyRelation:
        try:
            return self._default_study_relation
        except AttributeError:
            self._default_study_relation = self.generate_study_relation(
                self.default_researcher, self.default_study, relation
            )
            return self._default_study_relation

    def generate_study_relation(self, researcher: Researcher, study: Study, relation: str) -> StudyRelation:
        relation = StudyRelation(researcher=researcher, study=study, relationship=relation)
        relation.save()
        return relation

    # Researcher
    @property
    def default_researcher(self) -> Researcher:
        try:
            return self._default_researcher
        except AttributeError:
            pass
        self._default_researcher = self.generate_researcher(self.DEFAULT_RESEARCHER_NAME)
        return self._default_researcher

    def generate_researcher(self, name: Optional[str] = None) -> Researcher:
        researcher = Researcher(
            username=name or generate_easy_alphanumeric_string(),
            password='zsk387ts02hDMRAALwL2SL3nVHFgMs84UcZRYIQWYNQ=',
            salt='hllJauvRYDJMQpXQKzTdwQ==',  # these will get immediately overwritten
            site_admin=False,
            is_batch_user=False,
        )
        # set password saves
        researcher.set_password(self.DEFAULT_RESEARCHER_PASSWORD)
        return researcher

    @property
    def default_participant(self) -> Participant:
        try:
            return self._default_participant
        except AttributeError:
            pass
        participant = Participant(
            patient_id="particip",
            device_id='_xjeWARoRevoDoL9OKDwRMpYcDhuAxm4nwedUgABxWA=',
            password='2oWT7-6Su2WMDRWpclT0q2glam7AD5taUzHIWRnO490=',
            salt='1NB2kCxOOYzayIYGZYlhHw==',
            os_type="ANDROID",
            timezone_name="America/New_York",
            push_notification_unreachable_count=0,
            deleted=False,
            study=self.default_study,
        )
        participant.save()
        self._default_participant = participant
        return participant

    @property
    def default_survey(self) -> Survey:
        try:
            self._default_survey
        except AttributeError:
            pass
        survey = Survey(
            study=self.default_study,
            survey_type=Survey.TRACKING_SURVEY,
            object_id=self.DEFAULT_SURVEY_OBJECT_ID,
        )
        survey.save()
        self._default_survey = survey
        return survey

    # @property
    # def default_device_settings(self):
    #     # TODO: this should go off of the defaults in the database table
    #     return {
    #         'about_page_text': "irrelevant string 1",
    #         'accelerometer': True,
    #         'accelerometer_off_duration_seconds': 10,
    #         'accelerometer_on_duration_seconds': 10,
    #         'allow_upload_over_cellular_data': False,
    #         'bluetooth': False,
    #         'bluetooth_global_offset_seconds': 0,
    #         'bluetooth_on_duration_seconds': 60,
    #         'bluetooth_total_duration_seconds': 300,
    #         'call_clinician_button_text': "irrelevant string 2",
    #         'calls': True,
    #         'check_for_new_surveys_frequency_seconds': 21600,
    #         'consent_form_text': "irrelevant string 3",
    #         'consent_sections': "{}", # needs to be a de/serializeable json object
    #         'create_new_data_files_frequency_seconds': 900,
    #         'devicemotion': False,
    #         'devicemotion_off_duration_seconds': 600,
    #         'devicemotion_on_duration_seconds': 60,
    #         'gps': True,
    #         'gps_off_duration_seconds': 600,
    #         'gps_on_duration_seconds': 60,
    #         'gyro': False,
    #         'gyro_off_duration_seconds': 600,
    #         'gyro_on_duration_seconds': 60,
    #         'magnetometer': False,
    #         'magnetometer_off_duration_seconds': 600,
    #         'magnetometer_on_duration_seconds': 60,
    #         'power_state': True,
    #         'proximity': False,
    #         'reachability': True,
    #         'seconds_before_auto_logout': 600,
    #         'survey_submit_success_toast_text': "irrelevant string 4",
    #         'texts': True,
    #         'upload_data_files_frequency_seconds': 3600,
    #         'voice_recording_max_time_length_seconds': 240,
    #         'wifi': True,
    #         'wifi_log_frequency_seconds': 300
    #     }
