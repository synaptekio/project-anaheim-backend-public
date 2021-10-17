from datetime import date

from database.study_models import Study
from libs.internal_types import ResearcherRequest


def researcher_context_processor(request: ResearcherRequest):
    current_year = date.today().year  # current year is used in the footer

    # if it is a researcher endpoint (aka has the admin or researcher or study/survey authentication
    # decorators) then we need most of these variables available in the template.
    if hasattr(request, "session_researcher"):
        # the studies dropdown is on most pages
        allowed_studies_kwargs = {} if request.session_researcher.site_admin else \
            {"study_relations__researcher": request.session_researcher}

        return {
            "allowed_studies": [
                study_info_dict for study_info_dict in Study.get_all_studies_by_name()
                .filter(**allowed_studies_kwargs).values("name", "object_id", "id", "is_test")
            ],
            "is_admin": request.session_researcher.is_an_admin(),
            "site_admin": request.session_researcher.site_admin,
            "session_researcher": request.session_researcher,
            "current_year": current_year,
        }
    else:
        return {"current_year": current_year}
