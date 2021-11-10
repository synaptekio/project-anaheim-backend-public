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
#     ("site_admin", ResearcherRole.study_admin, ResearcherRole.researcher, None), 2)
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

REAL_ROLES = (ResearcherRole.study_admin, ResearcherRole.researcher)
ALL_TESTING_ROLES = (ResearcherRole.study_admin, ResearcherRole.researcher, "site_admin", None)
ADMIN_ROLES = (ResearcherRole.study_admin, "site_admin")
