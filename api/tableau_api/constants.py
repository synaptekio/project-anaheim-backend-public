from django.db.models.fields import (BooleanField, CharField, DateField, DateTimeField, FloatField,
    IntegerField, TextField)


SERIALIZABLE_FIELD_NAMES = [
    # Metadata
    "date",
    "participant_id",
    "study_id",

    # Data quantities
    "beiwe_accelerometer_bytes",
    "beiwe_ambient_audio_bytes",
    "beiwe_app_log_bytes",
    "beiwe_bluetooth_bytes",
    "beiwe_calls_bytes",
    "beiwe_devicemotion_bytes",
    "beiwe_gps_bytes",
    "beiwe_gyro_bytes",
    "beiwe_identifiers_bytes",
    "beiwe_image_survey_bytes",
    "beiwe_ios_log_bytes",
    "beiwe_magnetometer_bytes",
    "beiwe_power_state_bytes",
    "beiwe_proximity_bytes",
    "beiwe_reachability_bytes",
    "beiwe_survey_answers_bytes",
    "beiwe_survey_timings_bytes",
    "beiwe_texts_bytes",
    "beiwe_audio_recordings_bytes",
    "beiwe_wifi_bytes",

    # GPS
    "jasmine_distance_diameter",
    "jasmine_distance_from_home",
    "jasmine_distance_traveled",
    "jasmine_flight_distance_average",
    "jasmine_flight_distance_stddev",
    "jasmine_flight_duration_average",
    "jasmine_flight_duration_stddev",
    "jasmine_gps_data_missing_duration",
    "jasmine_home_duration",
    "jasmine_gyration_radius",
    "jasmine_significant_location_count",
    "jasmine_significant_location_entropy",
    "jasmine_pause_time",
    "jasmine_obs_duration",
    "jasmine_obs_day",
    "jasmine_obs_night",
    "jasmine_total_flight_time",
    "jasmine_av_pause_duration",
    "jasmine_sd_pause_duration",

    # Texts
    "willow_incoming_text_count",
    "willow_incoming_text_degree",
    "willow_incoming_text_length",
    "willow_outgoing_text_count",
    "willow_outgoing_text_degree",
    "willow_outgoing_text_length",
    "willow_incoming_text_reciprocity",
    "willow_outgoing_text_reciprocity",
    "willow_outgoing_MMS_count",
    "willow_incoming_MMS_count",

    # Calls
    "willow_incoming_call_count",
    "willow_incoming_call_degree",
    "willow_incoming_call_duration",
    "willow_outgoing_call_count",
    "willow_outgoing_call_degree",
    "willow_outgoing_call_duration",
    "willow_missed_call_count",
    "willow_missed_callers",
]

SERIALIZABLE_FIELD_NAMES_DROPDOWN = [(f, f) for f in SERIALIZABLE_FIELD_NAMES]

VALID_QUERY_PARAMETERS = [
    "end_date",
    "fields",
    "limit",
    "order_direction",
    "ordered_by",
    "participant_ids",
    "start_date",
    "study_id",
]

# maps django fields to tableau data types. All fields not included here are interpreted as string data in tableau
# note that this process considers subclasses, so all subclasses of DateFields will appear in tableau as a data
FIELD_TYPE_MAP = [
    (IntegerField, 'tableau.dataTypeEnum.int'),
    (FloatField, 'tableau.dataTypeEnum.float'),
    (DateTimeField, 'tableau.dataTypeEnum.datetime'),
    (DateField, 'tableau.dataTypeEnum.date'),
    (BooleanField, 'tableau.dataTypeEnum.bool'),
    (CharField, 'tableau.dataTypeEnum.string'),
    (TextField, 'tableau.dataTypeEnum.string'),
]


X_ACCESS_KEY_ID = "X-Access-Key-Id"
X_ACCESS_KEY_SECRET = "X-Access-Key-Secret"

# general error messages
CREDENTIALS_NOT_VALID_ERROR_MESSAGE = "Credentials not valid"
HEADER_IS_REQUIRED = "This header is required"
RESOURCE_NOT_FOUND = "resource not found"

# permissions errors
APIKEY_NO_ACCESS_MESSAGE = "ApiKey does not have access to Tableau API"
NO_STUDY_PROVIDED_MESSAGE = "No study id specified"
NO_STUDY_FOUND_MESSAGE = "No matching study found"
RESEARCHER_NOT_ALLOWED = "Researcher does not have permission to view that study"
STUDY_HAS_FOREST_DISABLED_MESSAGE = "Study does not have forest enabled"
