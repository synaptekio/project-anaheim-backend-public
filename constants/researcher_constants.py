# Researcher User Types
class ResearcherRole:
    study_admin = "study_admin"
    researcher = "study_researcher"
    
    # site_admin is not a study _relationship_, but we need a canonical string for it somewhere.
    # You are a site admin if 'site_admin' is true on your Researcher model.
    site_admin = "site_admin"


ALL_RESEARCHER_TYPES = (ResearcherRole.study_admin, ResearcherRole.researcher)
