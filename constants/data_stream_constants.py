## Constants for for the keys in DATA_STREAM_TO_S3_FILE_NAME_STRING
ACCELEROMETER = "accelerometer"
AMBIENT_AUDIO = "ambient_audio"
ANDROID_LOG_FILE = "app_log"
BLUETOOTH = "bluetooth"
CALL_LOG = "calls"
DEVICEMOTION = "devicemotion"
GPS = "gps"
GYRO = "gyro"
IDENTIFIERS = "identifiers"
IMAGE_FILE = "image_survey"
IOS_LOG_FILE = "ios_log"
MAGNETOMETER = "magnetometer"
POWER_STATE = "power_state"
PROXIMITY = "proximity"
REACHABILITY = "reachability"
SURVEY_ANSWERS = "survey_answers"
SURVEY_TIMINGS = "survey_timings"
TEXTS_LOG = "texts"
VOICE_RECORDING = "audio_recordings"
WIFI = "wifi"

# dictionary for printing PROCESSED data streams for frontend
# necessary even with the complete data stream dict for parsing data from the backend
PROCESSED_DATA_STREAM_DICT = {
    "responsiveness": "Responsiveness",
    "outgoing_calllengths": "Outgoing Call Lengths",
    "call_indegree": "Call In Degree",
    "incoming_calllengths": "Incoming Call Lengths",
    "reciprocity": "Reciprocity",
    "call_outdegree": "Call Out Degree",
    "incoming_calls": "Incoming Calls",
    "outgoing_calls": "Outgoing Calls",
    "outgoing_textlengths": "Outgoing Text Lengths",
    "text_indegree": "Text In Degree",
    "incoming_textlengths": "Incoming Text Lengths",
    "text_outdegree": "Text Out Degree",
    "incoming_texts": "Incoming Texts",
    "outgoing_texts": "Outgoing Texts",
    "RoG_km": "RoG (km)",
    "MaxDiam_km": "Maximum Diameter (km)",
    "StdFlightDur_min": "Standard Flight Duration (min)",
    "AvgFlightLen_km": "Average Flight Length (km)",
    "Hometime_hrs": "Home Time (hours)",
    "AvgFlightDur_min": "Average Flight Duration (min)",
    "DistTravelled_km": "Distance Travelled (km)",
    "StdFlightLen_km": "Standard Flight Length (km)",
    "MaxHomeDist_km": "Maximum Home Distance (km)",
}

# dictionary for printing ALL data streams (processed and bytes)
COMPLETE_DATA_STREAM_DICT = {
    "responsiveness": "Responsiveness",
    "outgoing_calllengths": "Outgoing Call Lengths",
    "call_indegree": "Call In Degree",
    "incoming_calllengths": "Incoming Call Lengths",
    "reciprocity": "Reciprocity",
    "call_outdegree": "Call Out Degree",
    "incoming_calls": "Incoming Calls",
    "outgoing_calls": "Outgoing Calls",
    "outgoing_textlengths": "Outgoing Text Lengths",
    "text_indegree": "Text In Degree",
    "incoming_textlengths": "Incoming Text Lengths",
    "text_outdegree": "Text Out Degree",
    "incoming_texts": "Incoming Texts",
    "outgoing_texts": "Outgoing Texts",
    "RoG_km": "RoG (km)",
    "MaxDiam_km": "Maximum Diameter (km)",
    "StdFlightDur_min": "Standard Flight Duration (min)",
    "AvgFlightLen_km": "Average Flight Length (km)",
    "Hometime_hrs": "Home Time (hours)",
    "AvgFlightDur_min": "Average Flight Duration (min)",
    "DistTravelled_km": "Distance Travelled (km)",
    "StdFlightLen_km": "Standard Flight Length (km)",
    "MaxHomeDist_km": "Maximum Home Distance (km)",
    ACCELEROMETER: "Accelerometer (bytes)",
    AMBIENT_AUDIO: "Ambient Audio Recording (bytes)",
    ANDROID_LOG_FILE: "Android Log File (bytes)",
    BLUETOOTH: "Bluetooth (bytes)",
    CALL_LOG: "Call Log (bytes)",
    DEVICEMOTION: "Device Motion (bytes)",
    GPS: "GPS (bytes)",
    GYRO: "Gyro (bytes)",
    IDENTIFIERS: "Identifiers (bytes)",
    IMAGE_FILE: "Image Survey (bytes)",
    IOS_LOG_FILE: "iOS Log File (bytes)",
    MAGNETOMETER: "Magnetometer (bytes)",
    POWER_STATE: "Power State (bytes)",
    PROXIMITY: "Proximity (bytes)",
    REACHABILITY: "Reachability (bytes)",
    SURVEY_ANSWERS: "Survey Answers (bytes)",
    SURVEY_TIMINGS: "Survey Timings (bytes)",
    TEXTS_LOG: "Text Log (bytes)",
    VOICE_RECORDING: "Audio Recordings (bytes)",
    WIFI: "Wifi (bytes)",
}

ALL_DATA_STREAMS = [
    ACCELEROMETER,
    AMBIENT_AUDIO,
    ANDROID_LOG_FILE,
    BLUETOOTH,
    CALL_LOG,
    DEVICEMOTION,
    GPS,
    GYRO,
    IDENTIFIERS,
    IMAGE_FILE,
    IOS_LOG_FILE,
    MAGNETOMETER,
    POWER_STATE,
    PROXIMITY,
    REACHABILITY,
    SURVEY_ANSWERS,
    SURVEY_TIMINGS,
    TEXTS_LOG,
    VOICE_RECORDING,
    WIFI,
]

SURVEY_DATA_FILES = [SURVEY_ANSWERS, SURVEY_TIMINGS]

UPLOAD_FILE_TYPE_MAPPING = {
    "accel": ACCELEROMETER,
    "bluetoothLog": BLUETOOTH,
    "callLog": CALL_LOG,
    "devicemotion": DEVICEMOTION,
    "gps": GPS,
    "gyro": GYRO,
    "logFile": ANDROID_LOG_FILE,
    "magnetometer": MAGNETOMETER,
    "powerState": POWER_STATE,
    "reachability": REACHABILITY,
    "surveyAnswers": SURVEY_ANSWERS,
    "surveyTimings": SURVEY_TIMINGS,
    "textsLog": TEXTS_LOG,
    "voiceRecording": VOICE_RECORDING,
    "wifiLog": WIFI,
    "proximity": PROXIMITY,
    "ios_log": IOS_LOG_FILE,
    "imageSurvey": IMAGE_FILE,
    "ambientAudio": AMBIENT_AUDIO,
    "identifiers": IDENTIFIERS,  # not processed through data upload.
}

# this is mostly used for debugging and scripting
REVERSE_UPLOAD_FILE_TYPE_MAPPING = {v: k for k, v in UPLOAD_FILE_TYPE_MAPPING.items()}

# Used for debugging and reverse lookups.
DATA_STREAM_TO_S3_FILE_NAME_STRING = {
    ACCELEROMETER: "accel",
    BLUETOOTH: "bluetoothLog",
    CALL_LOG: "callLog",
    GPS: "gps",
    IDENTIFIERS: "identifiers",
    ANDROID_LOG_FILE: "logFile",
    POWER_STATE: "powerState",
    SURVEY_ANSWERS: "surveyAnswers",
    SURVEY_TIMINGS: "surveyTimings",
    TEXTS_LOG: "textsLog",
    VOICE_RECORDING: "voiceRecording",
    WIFI: "wifiLog",
    PROXIMITY: "proximity",
    GYRO: "gyro",
    MAGNETOMETER: "magnetometer",
    DEVICEMOTION: "devicemotion",
    REACHABILITY: "reachability",
    IOS_LOG_FILE: "ios/log",
    IMAGE_FILE: "imageSurvey",
    AMBIENT_AUDIO: "ambientAudio",
}

CHUNKABLE_FILES = {
    ACCELEROMETER,
    BLUETOOTH,
    CALL_LOG,
    GPS,
    IDENTIFIERS,
    ANDROID_LOG_FILE,
    POWER_STATE,
    SURVEY_TIMINGS,
    TEXTS_LOG,
    WIFI,
    PROXIMITY,
    GYRO,
    MAGNETOMETER,
    DEVICEMOTION,
    REACHABILITY,
    IOS_LOG_FILE
}

DEVICE_IDENTIFIERS_HEADER = "patient_id,MAC,phone_number,device_id,device_os,os_version,product,brand,hardware_id,manufacturer,model,beiwe_version\n"