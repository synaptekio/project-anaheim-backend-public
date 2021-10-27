# Researcher User Types
class ResearcherRole(object):
    # site_admin = "site_admin"  # site admin is not a study relationship
    study_admin = "study_admin"
    researcher = "study_researcher"


ALL_RESEARCHER_TYPES = (ResearcherRole.study_admin, ResearcherRole.researcher)
