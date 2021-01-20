from database.study_models import Study
from database.survey_models import Survey
from database.user_models import Researcher

# this is a minor cleanup of useful components from the django transition tests, it needs to be updated.

class ReferenceObjectMixin:

    REFERENCE_RESEARCHER_NAME = "researcher"

    # Researcher
    @property
    def _reference_researcher_defaults(self) -> dict:
        """ Provide a copy of a reference object sourced from the original mongo database.
        password: ' ' """
        return {
            'username': self.REFERENCE_RESEARCHER_NAME,
            'password': 'zsk387ts02hDMRAALwL2SL3nVHFgMs84UcZRYIQWYNQ=',
            'salt': 'hllJauvRYDJMQpXQKzTdwQ==',
            'site_admin': False,
            'is_batch_user': False
        }

    @property
    def _reference_api_key_defaults(self) -> dict:
        """ secret key: 8EG4DFk0pVqohtidrBJyIi1mGr5hBjnX3dShRGhCBt9h2WibBDEzLmbog51YlBzI
            This was manually generated. """
        return {
            'access_key_id': 'gVsTj58RsUqPkA8P7YiIyJhLLdjSdty6VvFkPo3/cerMqaB1/l8Q4j6MhE5suRW7',
            'access_key_secret': 'J2mld58erwwdY60bcUE6ItrViimeEJFLO_xDJZ-kqOE=',
            'access_key_secret_salt': 'GmI_vejug29uZz4WpDofcA==',
        }

    @property
    def get_default_researcher(self):
        researcher, created = Researcher.objects.get_or_create("researcher")
        # ... not even prototyped yet

    # Participant
    @property
    def reference_participant_dict(self) -> dict:
        return {
            '_id': "someparticipant7",
            'device_id': '_xjeWARoRevoDoL9OKDwRMpYcDhuAxm4nwedUgABxWA=',
            'password': '2oWT7-6Su2WMDRWpclT0q2glam7AD5taUzHIWRnO490=',
            'salt': '1NB2kCxOOYzayIYGZYlhHw==',
            # 'study_id': ReferenceRequired,
            'os_type': "ANDROID"
        }

    # Study
    @property
    def reference_study(self):
        return {
            'name': 'something, anything',
            'encryption_key': '12345678901234567890123456789012',
            'deleted': False,
            # '_id': ObjectId('556677889900aabbccddeeff'),
            # # The rest are refactored totally
            # 'admins': ReferenceReversed,
            # 'device_settings': ReferenceReversed,
            # 'super_admins': ReferenceReversed,
            # 'surveys': ReferenceReversed
        }

    # Survey
    @property
    def reference_survey(self):
        return {
            'content': [{'prompt': ''}],
            'settings': {'audio_survey_type': 'compressed',
                          'bit_rate': 64000,
                          'trigger_on_first_download': True},
            'survey_type': 'audio_survey',
            'timings': [[], [], [], [], [], [], []]
        }

    @property
    def reference_device_settings(self):
        # TODO: this should go off of the defaults in the database table
        return {
            'about_page_text': "irrelevant string 1",
            'accelerometer': True,
            'accelerometer_off_duration_seconds': 10,
            'accelerometer_on_duration_seconds': 10,
            'allow_upload_over_cellular_data': False,
            'bluetooth': False,
            'bluetooth_global_offset_seconds': 0,
            'bluetooth_on_duration_seconds': 60,
            'bluetooth_total_duration_seconds': 300,
            'call_clinician_button_text': "irrelevant string 2",
            'calls': True,
            'check_for_new_surveys_frequency_seconds': 21600,
            'consent_form_text': "irrelevant string 3",
            'consent_sections': "{}", # needs to be a de/serializeable json object
            'create_new_data_files_frequency_seconds': 900,
            'devicemotion': False,
            'devicemotion_off_duration_seconds': 600,
            'devicemotion_on_duration_seconds': 60,
            'gps': True,
            'gps_off_duration_seconds': 600,
            'gps_on_duration_seconds': 60,
            'gyro': False,
            'gyro_off_duration_seconds': 600,
            'gyro_on_duration_seconds': 60,
            'magnetometer': False,
            'magnetometer_off_duration_seconds': 600,
            'magnetometer_on_duration_seconds': 60,
            'power_state': True,
            'proximity': False,
            'reachability': True,
            'seconds_before_auto_logout': 600,
            'survey_submit_success_toast_text': "irrelevant string 4",
            'texts': True,
            'upload_data_files_frequency_seconds': 3600,
            'voice_recording_max_time_length_seconds': 240,
            'wifi': True,
            'wifi_log_frequency_seconds': 300
        }
