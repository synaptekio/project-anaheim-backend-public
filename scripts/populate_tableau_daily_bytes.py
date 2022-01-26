from collections import defaultdict

from dateutil.tz import gettz

from constants.data_stream_constants import ALL_DATA_STREAMS
from database.data_access_models import ChunkRegistry
from database.tableau_api_models import SummaryStatisticDaily
from database.user_models import Participant


def calculate_data_quantity_stats(participant: Participant):
    """ Update the SummaryStatisticDaily  stats for a participant, using ChunkRegistry data """
    daily_data_quantities = defaultdict(lambda: defaultdict(int))
    days = set()
    study_timezone = gettz(participant.study.timezone_name)
    query = ChunkRegistry.objects.filter(participant=participant) \
        .values_list('time_bin', 'data_type', 'file_size').iterator()
    
    # Construct a dict formatted like this: dict[date][data_type] = total_bytes
    for time_bin, data_type, file_size in query:
        if data_type not in ALL_DATA_STREAMS:
            raise Exception(f"unknown data type: {data_type}")
        day = time_bin.astimezone(study_timezone).date()
        days.add(day)
        daily_data_quantities[day][data_type] += file_size or 0
    
    days = list(days)
    days.sort()
    print(f"updating {len(days)} daily summaries.")
    # days_readable = ",".join(day.isoformat() for day in days)
    # print(f"updating {len(days)} daily summaries: {days_readable}")
    
    # For each date, create a DataQuantity object
    for day, day_data in daily_data_quantities.items():
        data_quantity = {"participant": participant, "date": day, "defaults": {}}
        for data_type, total_bytes in day_data.items():
            data_quantity["defaults"][f"{data_type}_bytes"] = total_bytes
        # print(day)
        SummaryStatisticDaily.objects.update_or_create(**data_quantity)


for participant in Participant.objects.all():
    print(participant.patient_id, "...", end=" ")
    calculate_data_quantity_stats(participant)
