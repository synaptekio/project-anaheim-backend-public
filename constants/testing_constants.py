from constants.researcher_constants import ResearcherRole


HOST = "localhost.localdomain"
PORT = 54321

BASE_URL = f"http://{HOST}:{PORT}"
TEST_PASSWORD = "1"
TEST_STUDY_NAME = "automated_test_study"
TEST_STUDY_ENCRYPTION_KEY = "11111111111111111111111111111111"
TEST_USERNAME = "automated_test_user"

# ALL_ROLE_PERMUTATIONS is generated from this:
# ALL_ROLE_PERMUTATIONS = tuple(
# from constants.researcher_constants import ResearcherRole
# from itertools import permutations
#     two_options for two_options in permutations(
#     (SITE_ADMIN, ResearcherRole.study_admin, ResearcherRole.researcher, None), 2)
# )

ALL_ROLE_PERMUTATIONS = (
    ('site_admin', 'study_admin'),
    ('site_admin', 'study_researcher'),
    ('site_admin', None),
    ('study_admin', 'site_admin'),
    ('study_admin', 'study_researcher'),
    ('study_admin', None),
    ('study_researcher', 'site_admin'),
    ('study_researcher', 'study_admin'),
    ('study_researcher', None),
    (None, 'site_admin'),
    (None, 'study_admin'),
    (None, 'study_researcher'),
)

SITE_ADMIN = "site_admin"
REAL_ROLES = (ResearcherRole.study_admin, ResearcherRole.researcher)
ALL_TESTING_ROLES = (ResearcherRole.study_admin, ResearcherRole.researcher, SITE_ADMIN, None)
ADMIN_ROLES = (ResearcherRole.study_admin, SITE_ADMIN)


BACKEND_CERT = """{
    "type": "service_account",
    "project_id": "some id",
    "private_key_id": "numbers and letters",
    "private_key": "-----BEGIN PRIVATE KEY-----omg a key-----END PRIVATE KEY-----",
    "client_email": "firebase-adminsdk *serviceaccountinfo*",
    "client_id": "NUMBERS!",
    "auth_uri": "https://an_account_oauth",
    "token_uri": "https://an_account/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "some_neato_cert_url"
}"""


IOS_CERT = \
"""<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
    <key>CLIENT_ID</key>
    <string>some url id</string>
    <key>REVERSED_CLIENT_ID</key>
    <string>id url some</string>
    <key>API_KEY</key>
    <string>gibberish</string>
    <key>GCM_SENDER_ID</key>
    <string>number junk</string>
    <key>PLIST_VERSION</key>
    <string>1</string>
    <key>BUNDLE_ID</key>
    <string>an bundle eye dee</string>
    <key>PROJECT_ID</key>
    <string>name with a number</string>
    <key>STORAGE_BUCKET</key>
    <string>something dot appspot.com</string>
    <key>IS_ADS_ENABLED</key>
    <false></false>
    <key>IS_ANALYTICS_ENABLED</key>
    <false></false>
    <key>IS_APPINVITE_ENABLED</key>
    <true></true>
    <key>IS_GCM_ENABLED</key>
    <true></true>
    <key>IS_SIGNIN_ENABLED</key>
    <true></true>
    <key>GOOGLE_APP_ID</key>
    <string>obscure base64 with colon separaters</string>
    <key>DATABASE_URL</key>
    <string>https://something.firebaseio.com</string>
    </dict>
    </plist>"""

ANDROID_CERT = """{
"project_info": {
    "project_number": "an large number",
    "firebase_url": "https://some_identifier.firebaseio.com",
    "project_id": "some_identifier",
    "storage_bucket": "some_identifier.appspot.com"},
"client": [{
    "client_info": {
    "mobilesdk_app_id": "inscrutable colon separated bas64",
    "android_client_info": {"package_name": "org.beiwe.app"}
    },
    "oauth_client": [
    {"client_id": "some_client_id",
    "client_type": 3}
    ],
    "api_key": [{"current_key": "a key!"}],
    "services": {
    "appinvite_service": {
        "other_platform_oauth_client": [
        {"client_id": "some_client_id", "client_type": 3},
        {"client_id": "more.junk.apps.googleusercontent.com",
        "client_type": 2, "ios_info": {"bundle_id": "an_bundle_id"}}
    ]}
    }
}, {"client_info": {
    "mobilesdk_app_id": "inscrutable colon separated bas64",
    "android_client_info": {"package_name": "package name!"}
    },
    "oauth_client": [
        {"client_id": "some_client_id", "client_type": 3}
    ],
    "api_key": [{"current_key": "base64 junk"}],
    "services": {
        "appinvite_service": {
        "other_platform_oauth_client": [{
            "client_id": "some_client_id",
            "client_type": 3
            },{
            "client_id": "some-identifier.apps.googleusercontent.com",
            "client_type": 2,
            "ios_info": {"bundle_id": "another bundle id"}
            }
        ]}
    }
    }],
"configuration_version": "1"
}"""