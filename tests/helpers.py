from config.constants import ResearcherRole
from database.study_models import Study
from database.survey_models import Survey
from database.tableau_api_models import ForestParam
from database.user_models import Participant, Researcher, StudyRelation


# this is a minor cleanup of useful components from the django transition tests, it needs to be updated.

class ReferenceObjectMixin:

    RESEARCHER_NAME = "researcher"
    STUDY_NAME = "teststudy"
    SURVEY_OBJECT_ID = 'u1Z3SH7l2xNsw72hN3LnYi96'

    @property
    def default_forest_params(self):
        try:
            return ForestParam.objects.get(default=True)
        except ForestParam.DoesNotExist:
            pass

        ForestParam(
            default=True,
            notes="notes",
            name="name",
            jasmine_json_string="[]",
            willow_json_string="[]",
        ).save()
        return self.default_forest_params

    @property
    def default_study(self):
        try:
            return Study.objects.get(name=self.STUDY_NAME)
        except Study.DoesNotExist:
            pass
        study = Study(
            name="teststudy",
            encryption_key="thequickbrownfoxjumpsoverthelazy",
            object_id="2Mwjb91zSWzHgOrQahEvlu5v",
            is_test=True,
            timezone_name="America/New_York",
            deleted=False,
            forest_enabled=True,
            forest_param=self.default_forest_params,
        )
        study.save()
        return study

    # Researcher
    @property
    def default_researcher(self) -> Researcher:
        try:
            return Researcher.objects.get(username=self.RESEARCHER_NAME)
        except Researcher.DoesNotExist:
            pass
        researcher = Researcher(
            username=self.RESEARCHER_NAME,
            password='zsk387ts02hDMRAALwL2SL3nVHFgMs84UcZRYIQWYNQ=',
            salt='hllJauvRYDJMQpXQKzTdwQ==',
            site_admin=False,
            is_batch_user=False,
            access_key_id='gVsTj58RsUqPkA8P7YiIyJhLLdjSdty6VvFkPo3/cerMqaB1/l8Q4j6MhE5suRW7',
            access_key_secret='J2mld58erwwdY60bcUE6ItrViimeEJFLO_xDJZ-kqOE=',
            access_key_secret_salt='GmI_vejug29uZz4WpDofcA==',
        )
        researcher.save()
        StudyRelation.objects.create(
            researcher=researcher, relationship=ResearcherRole.researcher, study=self.default_study
        )
        return researcher

    @property
    def default_participant(self) -> Participant:
        try:
            return Participant.objects.get(patient_id="participant")
        except Participant.DoesNotExist:
            pass
        participant = Participant(
            patient_id="particip",
            device_id='_xjeWARoRevoDoL9OKDwRMpYcDhuAxm4nwedUgABxWA=',
            password='2oWT7-6Su2WMDRWpclT0q2glam7AD5taUzHIWRnO490=',
            salt='1NB2kCxOOYzayIYGZYlhHw==',
            os_type="ANDROID",
            timezone_name="America/New_York",
            push_notification_unreachable_count=0,
            deleted=True,
            study=self.default_study,
        )
        participant.save()
        return participant


    @property
    def default_survey(self):
        try:
            return Survey.objects.get(object_id=self.SURVEY_OBJECT_ID)
        except Survey.DoesNotExist:
            pass
        survey = Survey(
            study=self.default_study,
            survey_type=Survey.TRACKING_SURVEY,
            object_id=self.SURVEY_OBJECT_ID,
        )
        survey.save()
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


