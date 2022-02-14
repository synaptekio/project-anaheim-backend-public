from constants.data_stream_constants import (ACCELEROMETER, AMBIENT_AUDIO, ANDROID_LOG_FILE,
    BLUETOOTH, CALL_LOG, DEVICEMOTION, GPS, GYRO, IDENTIFIERS, IMAGE_FILE, IOS_LOG_FILE,
    MAGNETOMETER, POWER_STATE, PROXIMITY, REACHABILITY, SURVEY_ANSWERS, SURVEY_TIMINGS, TEXTS_LOG,
    VOICE_RECORDING, WIFI)


# dictionary for printing ALL data streams (processed and bytes)
COMPLETE_DATA_STREAM_DICT = {
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
