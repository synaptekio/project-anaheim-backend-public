from collections import defaultdict
from datetime import date
from typing import Dict

from database.schedule_models import InterventionDate, RelativeSchedule
from database.study_models import Study


def intervention_survey_data(study: Study) -> Dict[str, Dict[str, Dict[str, str]]]:
    # this was manually tested to cover multiple interventions per survey, and multiple surveys per intervention
    intervention_dates_data = (
        InterventionDate.objects.filter(
            participant__in=study.participants.all()
        ).values_list("participant__patient_id", "intervention__name", "date")
    )
    
    intervention_name_to_survey_id = dict(
        RelativeSchedule.objects.filter(intervention__in=study.interventions.all()
                                       ).values_list("intervention__name", "survey__object_id")
    )
    
    intervention_date: date
    final_data = defaultdict(lambda: defaultdict(dict))
    # there may be participants with no intervention dates, and there may be deleted interventions?
    for patient_id, intervention_name, intervention_date in intervention_dates_data:
        try:
            survey_object_id = intervention_name_to_survey_id[intervention_name]
        except KeyError:
            continue
        if intervention_date:
            intervention_date = intervention_date.isoformat()
        final_data[patient_id][survey_object_id][intervention_name] = intervention_date
    
    # convert defaultdicts to regular dicts
    final_data = dict(final_data)
    for k1 in final_data:
        final_data[k1] = dict(final_data[k1])
    return final_data
