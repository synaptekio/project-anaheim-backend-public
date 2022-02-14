import json
from collections import OrderedDict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

import pytz
from django.shortcuts import render
from django.utils.timezone import make_aware

from authentication.admin_authentication import authenticate_researcher_study_access
from constants.dashboard_constants import COMPLETE_DATA_STREAM_DICT, PROCESSED_DATA_STREAM_DICT
from constants.data_stream_constants import ALL_DATA_STREAMS
from constants.datetime_constants import API_DATE_FORMAT
from database.dashboard_models import DashboardColorSetting, DashboardGradient, DashboardInflection
from database.data_access_models import ChunkRegistry, PipelineRegistry
from database.study_models import Study
from database.user_models import Participant
from libs.internal_types import ParticipantQuerySet, ResearcherRequest
from middleware.abort_middleware import abort


DATETIME_FORMAT_ERROR = f"Dates and times provided to this endpoint must be formatted like this: " \
                        f"2010-11-22 ({API_DATE_FORMAT})"


@authenticate_researcher_study_access
def dashboard_page(request: ResearcherRequest, study_id: int):
    """ information for the general dashboard view for a study"""
    study = Study.get_or_404(pk=study_id)
    participants = list(Participant.objects.filter(study=study_id).values_list("patient_id", flat=True))
    return render(
        request,
        'dashboard/dashboard.html',
        context=dict(
            study=study,
            participants=participants,
            study_id=study_id,
            data_stream_dict=COMPLETE_DATA_STREAM_DICT,
            page_location='dashboard_landing',
        )
    )


@authenticate_researcher_study_access
def get_data_for_dashboard_datastream_display(
    request: ResearcherRequest, study_id: int, data_stream: str
):
    """ Parses information for the data stream dashboard view GET and POST requests left the post
    and get requests in the same function because the body of the get request relies on the
    variables set in the post request if a post request is sent --thus if a post request is sent
    we don't want all of the get request running. """
    study = Study.get_or_404(pk=study_id)
    
    # -----------------------------------  general data fetching --------------------------------------------
    participant_objects = Participant.objects.filter(study=study_id).order_by("patient_id")
    
    # --------------------- decide whether data is in Processed DB or Bytes DB -----------------------------
    if data_stream in ALL_DATA_STREAMS:
        data_exists, first_day, last_day, unique_dates, byte_streams = if_data_stream_in_ALL_DATA_STREAMS(
            request, study_id, data_stream, participant_objects
        )
    else:
        data_exists, first_day, last_day, unique_dates, byte_streams = if_data_stream_NOT_in_ALL_DATA_STREAMS(
            request, study_id, data_stream, participant_objects
        )
    
    # ---------------------------------- base case if there is no data ------------------------------------------
    if first_day is None or (not data_exists and past_url == ""):
        # TODO: test that these default values are unnecessary and fall out of above logic
        next_url, past_url = "", ""
    else:
        start, end = extract_date_args_from_request(request)
        next_url, past_url = create_next_past_urls(first_day, last_day, start=start, end=end)
    
    show_color, color_low_range, color_high_range, all_flags_list = handle_filters(
        request, study, data_stream
    )
    
    return render(
        request,
        'dashboard/data_stream_dashboard.html',
        context=dict(
            study=study,
            data_stream=COMPLETE_DATA_STREAM_DICT.get(data_stream),
            times=unique_dates,
            byte_streams=byte_streams,
            base_next_url=next_url,
            base_past_url=past_url,
            study_id=study_id,
            data_stream_dict=COMPLETE_DATA_STREAM_DICT,
            color_low_range=color_low_range,
            color_high_range=color_high_range,
            first_day=first_day,
            last_day=last_day,
            show_color=show_color,
            all_flags_list=all_flags_list,
            page_location='dashboard_data',
        )
    )

def handle_filters(request: ResearcherRequest, study: Study, data_stream: str):
    color_settings: DashboardColorSetting
    
    if request.method == "POST":
        color_low_range, color_high_range, all_flags_list =\
            set_default_settings_post_request(request, study, data_stream)
        show_color = "false" if color_low_range == 0 and color_high_range == 0 else "true"
    else:
        color_low_range, color_high_range, show_color = extract_range_args_from_request(request)
        all_flags_list = extract_flag_args_from_request(request)
    
    if DashboardColorSetting.objects.filter(data_type=data_stream, study=study).exists():
        color_settings = DashboardColorSetting.objects.get(data_type=data_stream, study=study)
        default_filters = DashboardColorSetting.get_dashboard_color_settings(color_settings)
    else:
        default_filters = ""
        color_settings = None
    
    # -------------------------------- dealing with color settings -------------------------------------------------
    # test if there are default settings saved,
    # and if there are, test if the default filters should be used or if the user has overridden them
    if default_filters != "":
        inflection_info = default_filters["inflections"]
        if all_flags_list == [] and color_high_range is None and color_low_range is None:
            # since none of the filters are set, parse default filters to pass in the default
            # settings set the values for gradient filter
            
            # backend: color_range_min, color_range_max --> frontend: color_low_range,
            # color_high_range the above is consistent throughout the back and front ends
            if color_settings.gradient_exists():
                gradient_info = default_filters["gradient"]
                color_low_range = gradient_info["color_range_min"]
                color_high_range = gradient_info["color_range_max"]
                show_color = "true"
            else:
                color_high_range, color_low_range = 0, 0
                show_color = "false"
            
            # set the values for the flag/inflection filter*s*
            # the html is expecting a list of lists for the flags [[operator, value], ... ]
            all_flags_list = [
                [flag_info["operator"], flag_info["inflection_point"]]
                for flag_info in inflection_info
            ]
    
    # change the url params from jinja t/f to python understood T/F
    show_color = True if show_color == "true" else False
    
    return show_color, color_low_range, color_high_range, all_flags_list


def if_data_stream_in_ALL_DATA_STREAMS(
    request: ResearcherRequest, study_id: int, data_stream: str, participant_objects: ParticipantQuerySet
):
    start, end = extract_date_args_from_request(request)
    first_day, last_day = dashboard_chunkregistry_date_query(study_id, data_stream)
    data_exists = False
    unique_dates = []
    byte_streams = {}
    if first_day is not None:
        stream_data = dashboard_chunkregistry_query(participant_objects, data_stream=data_stream)
        unique_dates, _, _ = get_unique_dates(start, end, first_day, last_day)
        
        # get the byte streams per date for each patient for a specific data stream for those dates
        byte_streams = dict(
            (participant.patient_id,
                [get_bytes_participant_match(stream_data[participant.patient_id], date) for date in unique_dates])
            for participant in participant_objects
        )
        # check if there is data to display
        data_exists = len([data for patient in byte_streams for data in byte_streams[patient] if data is not None]) > 0
    
    return data_exists, first_day, last_day, unique_dates, byte_streams


def if_data_stream_NOT_in_ALL_DATA_STREAMS(
    request: ResearcherRequest, study_id: int, data_stream: str, participant_objects: ParticipantQuerySet
):
    start, end = extract_date_args_from_request(request)
    first_day, last_day, stream_data = parse_processed_data(study_id, participant_objects, data_stream)
    data_exists = False
    unique_dates = []
    byte_streams = {}
    if first_day is not None:
        unique_dates, _, _ = get_unique_dates(start, end, first_day, last_day)
        
        # get the byte streams per date for each patient for a specific data stream for those dates
        byte_streams = dict(
            (participant.patient_id,
                [get_bytes_processed_data_match(stream_data[participant.patient_id], date) for date in unique_dates])
            for participant in participant_objects
        )
        # check if there is data to display
        data_exists = len([data for patient in byte_streams for data in byte_streams[patient] if data is not None]) > 0
    
    return data_exists, first_day, last_day, unique_dates, byte_streams


@authenticate_researcher_study_access
def dashboard_participant_page(request: ResearcherRequest, study_id, patient_id):
    """ parses data to be displayed for the singular participant dashboard view """
    study = Study.get_or_404(pk=study_id)
    participant = Participant.get_or_404(patient_id=patient_id, study_id=study_id)
    start, end = extract_date_args_from_request(request)
    # query is optimized for bulk participants, weird case handling
    chunk_data = dashboard_chunkregistry_query(participant)
    chunks = chunk_data[participant.patient_id] if participant.patient_id in chunk_data else {}
    
    # ----------------- dates for bytes data streams -----------------------
    if chunks:
        first_day, last_day = dashboard_chunkregistry_date_query(study_id)
        _, first_date_data_entry, last_date_data_entry = \
            get_unique_dates(start, end, first_day, last_day, chunks)
    else:
        last_date_data_entry = first_date_data_entry = None
    # --------------- dates for  processed data streams -------------------
    # all_data is a list of dicts [{"time_bin": , "stream": , "processed_data": }...]
    processed_first_date_data_entry, processed_last_date_data_entry, all_data = parse_patient_processed_data(study_id, participant)
    
    # ------- decide the first date of data entry from processed AND bytes data as well as put the data together ------
    # but only if there are both processed and bytes data
    if chunks and all_data:
        if (processed_first_date_data_entry - first_date_data_entry).days < 0:
            first_date_data_entry = processed_first_date_data_entry
        if (processed_last_date_data_entry - last_date_data_entry).days < 0:
            last_date_data_entry = processed_last_date_data_entry
    if all_data and not chunks:
        first_date_data_entry = processed_first_date_data_entry
        last_date_data_entry = processed_last_date_data_entry
    
    # ---------------------- get next/past urls and unique dates, as long as data has been entered -------------------
    if chunks or all_data:
        next_url, past_url = create_next_past_urls(first_date_data_entry, last_date_data_entry, start=start, end=end)
        unique_dates, _, _ = get_unique_dates(start, end, first_date_data_entry, last_date_data_entry)
    else:
        next_url = past_url = unique_dates = None
    
    # --------------------- get all the data using the correct unique dates from both data sets ----------------------
    # get the byte data for the dates that have data collected in that week
    if all_data:
        processed_byte_streams = OrderedDict(
            (stream, [
                get_bytes_patient_processed_match(all_data, date, stream) for date in unique_dates
            ]) for stream in PROCESSED_DATA_STREAM_DICT
        )
    else:
        processed_byte_streams = None
    
    if chunks:
        byte_streams = OrderedDict(
            (stream, [
                get_bytes_data_stream_match(chunks, date, stream) for date in unique_dates
            ]) for stream in ALL_DATA_STREAMS
        )
    else:
        byte_streams = None
    
    if chunks and all_data:
        byte_streams.update(processed_byte_streams)
    elif all_data and not chunks:
        byte_streams = OrderedDict(
            (stream, [
                None for date in unique_dates
            ]) for stream in ALL_DATA_STREAMS
        )
        byte_streams.update(processed_byte_streams)
    elif chunks and not all_data:
        processed_byte_streams = OrderedDict(
            (stream, [None for date in unique_dates]) for stream in PROCESSED_DATA_STREAM_DICT
        )
        byte_streams.update(processed_byte_streams)
    # -------------------------  edge case if no data has been entered -----------------------------------
    else:
        byte_streams = {}
        unique_dates = []
        next_url = ""
        past_url = ""
        first_date_data_entry = ""
        last_date_data_entry = ""
    
    patient_ids = list(
        Participant.objects.filter(study=study_id)
            .exclude(patient_id=patient_id).values_list("patient_id", flat=True)
    )
    
    return render(
        request,
        'dashboard/participant_dashboard.html',
        context=dict(
            study=study,
            patient_id=patient_id,
            participant=participant,
            times=unique_dates,
            byte_streams=byte_streams,
            next_url=next_url,
            past_url=past_url,
            patient_ids=patient_ids,
            study_id=study_id,
            first_date_data=first_date_data_entry,
            last_date_data=last_date_data_entry,
            data_stream_dict=COMPLETE_DATA_STREAM_DICT,
            page_location='dashboard_patient',
        )
    )


def parse_processed_data(study_id: int, participant_objects: ParticipantQuerySet, data_stream: str):
    """ get a list of dicts (pipeline_chunks) of the patient's data and extract the data for the data
    stream we want stream_data = OrderedDict(participant.patient_id: {"time_bin": _,
    "processed_data": _}, ...) this structure is similar to the stream_data structure in
    get_data_for_dashboard_data_stream_display since they perform similar functions. """
    first = True
    data_exists = False
    first_day = None
    last_day = None
    stream_data = OrderedDict()
    for participant in participant_objects:
        pipeline_chunks = dashboard_pipelineregistry_query(study_id, participant.id)
        list_of_dicts_data = []
        if pipeline_chunks is not None:
            for chunk in pipeline_chunks:
                if data_stream in chunk and "day" in chunk and chunk[data_stream] != "NA":
                    time_bin = datetime.strptime(chunk["day"], API_DATE_FORMAT).date()
                    data_exists = True
                    if first:
                        first_day = time_bin
                        last_day = time_bin
                        first = False
                    else:
                        if (time_bin - first_day).days < 0:
                            first_day = time_bin
                        elif (time_bin - last_day).days > 0:
                            last_day = time_bin
                    # check to see if the data should be a float or an int
                    if chunk[data_stream].find(".") == -1:
                        processed_data = int(chunk[data_stream])
                    else:
                        processed_data = float(chunk[data_stream])
                    list_of_dicts_data.append({"time_bin": time_bin, "processed_data": processed_data})
        
        stream_data[participant.patient_id] = None if not data_exists else list_of_dicts_data
        data_exists = False  # you need to reset this
    return first_day, last_day, stream_data


def parse_patient_processed_data(study_id: int, participant: Participant):
    """ Create a list of dicts of processed data for one patient.
    [{"time_bin": , "processed_data": , "data_stream": ,}...]
    if there is no data for a patient first_day and last_day will be None, all_data will be a [] """
    first = True
    first_day = None
    last_day = None
    pipeline_chunks = dashboard_pipelineregistry_query(study_id, participant.id)
    all_data = []
    if pipeline_chunks is not None:
        for chunk in pipeline_chunks:
            if "day" in chunk:
                time_bin = datetime.strptime(chunk["day"], API_DATE_FORMAT).date()
                if first:
                    first_day = time_bin
                    last_day = time_bin
                    first = False
                else:
                    if (time_bin - first_day).days < 0:
                        first_day = time_bin
                    elif (time_bin - last_day).days > 0:
                        last_day = time_bin
                for stream_key in chunk:
                    if stream_key in PROCESSED_DATA_STREAM_DICT and chunk[stream_key] != "NA":
                        if chunk[stream_key].find(".") == -1:
                            processed_data = int(chunk[stream_key])
                        else:
                            processed_data = float(chunk[stream_key])
                        all_data.append({"time_bin": time_bin, "processed_data": processed_data, "data_stream": stream_key})
    return first_day, last_day, all_data


def set_default_settings_post_request(request: ResearcherRequest, study: Study, data_stream: str):
    all_flags_list = argument_grabber(request, "all_flags_list", "[]")
    color_high_range = argument_grabber(request, "color_high_range", 0)
    color_low_range = argument_grabber(request, "color_low_range", 0)
    
    # convert parameters from unicode to correct types
    # if they didn't save a gradient we don't want to save garbage
    all_flags_list = json.loads(all_flags_list)
    if color_high_range == "0" and color_low_range == "0":
        color_low_range, color_high_range = 0, 0
        bool_create_gradient = False
    else:
        bool_create_gradient = True
        color_low_range = int(json.loads(color_low_range))
        color_high_range = int(json.loads(color_high_range))
    
    # try to get a DashboardColorSetting object and check if it exists
    if DashboardColorSetting.objects.filter(data_type=data_stream, study=study).exists():
        # case: a default settings model already exists; delete the inflections associated with it
        settings: DashboardColorSetting = DashboardColorSetting.objects.get(data_type=data_stream, study=study)
        settings.inflections.all().delete()
        if settings.gradient_exists():
            settings.gradient.delete()
        
        if bool_create_gradient:
            # create new gradient
            gradient, _ = DashboardGradient.objects.get_or_create(dashboard_color_setting=settings)
            gradient.color_range_max = color_high_range
            gradient.color_range_min = color_low_range
            gradient.save()
        
        # create new inflections
        for flag in all_flags_list:
            # all_flags_list looks like this: [[operator, inflection_point], ...]
            inflection = DashboardInflection.objects.create(dashboard_color_setting=settings, operator=flag[0])
            inflection.operator = flag[0]
            inflection.inflection_point = flag[1]
            inflection.save()
        settings.save()
    else:
        # this is the case if a default settings does not yet exist
        # create a new dashboard color setting in memory
        settings = DashboardColorSetting.objects.create(data_type=data_stream, study=study)
        
        # create new gradient
        if bool_create_gradient:
            gradient = DashboardGradient.objects.create(dashboard_color_setting=settings)
            gradient.color_range_max = color_high_range
            gradient.color_range_min = color_low_range
        
        # create new inflections
        for flag in all_flags_list:
            inflection = DashboardInflection.objects.create(dashboard_color_setting=settings, operator=flag[0])
            inflection.operator = flag[0]
            inflection.inflection_point = flag[1]
        
        # save the dashboard color setting to the backend (currently is just in memory)
        settings.save()
    
    return color_low_range, color_high_range, all_flags_list


def get_unique_dates(start, end, first_day, last_day, chunks=None):
    """ create a list of all the unique days in which data was recorded for this study """
    first_date_data_entry = last_date_data_entry = None
    if chunks:
        all_dates = sorted(
            chunk["time_bin"].date() for chunk in chunks if chunk["time_bin"].date() >= first_day
            # must be >= first day bc there are some point for 1970 that get filtered out bc obv are garbage
        )
        
        # create a list of all of the valid days in this study
        first_date_data_entry = all_dates[0]
        last_date_data_entry = all_dates[-1]
    
    # validate start date is before end date
    if (start and end) and (end.date() - start.date()).days < 0:
        temp = start
        start = end
        end = temp
    
    # unique_dates is all of the dates for the week we are showing
    if start is None:  # if start is none default to end
        end_num = min((last_day - first_day).days + 1, 7)
        unique_dates = [(last_day - timedelta(days=end_num - 1)) + timedelta(days=date) for date in range(end_num)]
        # unique_dates = [(first_day + timedelta(days=date)) for date in range(end_num)]
    elif end is None:
        # if end is none default to 7 days
        end_num = min((last_day - start.date()).days + 1, 7)
        unique_dates = [(start.date() + timedelta(days=date)) for date in range(end_num)]
    elif (start.date() - first_day).days < 0:
        # case: out of bounds at beginning to keep the duration the same
        end_num = (end.date() - first_day).days + 1
        unique_dates = [(first_day + timedelta(days=date)) for date in range(end_num)]
    elif (last_day - end.date()).days < 0:
        # case: out of bounds at end to keep the duration the same
        end_num = (last_day - start.date()).days + 1
        unique_dates = [(start.date() + timedelta(days=date)) for date in range(end_num)]
    else:
        # case: if they specify both start and end
        end_num = (end.date() - start.date()).days + 1
        unique_dates = [(start.date() + timedelta(days=date)) for date in range(end_num)]
    
    return unique_dates, first_date_data_entry, last_date_data_entry


def create_next_past_urls(first_day: date, last_day: date, start: date, end: date) -> Tuple[str, str]:
    """ set the URLs of the next/past pages for patient and data stream dashboard """
    # note: in the "if" cases, the dates are intentionally allowed outside the data collection date
    # range so that the duration stays the same if you page backwards instead of resetting
    # to the number currently shown
    
    if start and end:
        duration = (end.date() - start.date()).days
    else:
        duration = 6
        start = datetime.combine(last_day - timedelta(days=6), datetime.min.time())
        end = datetime.combine(last_day, datetime.min.time())
    
    if 0 < (start.date() - first_day).days < duration:
        past_url = "?start=" + (start.date() - timedelta(days=(duration + 1))).strftime(API_DATE_FORMAT) + \
                   "&end=" + (start.date() - timedelta(days=1)).strftime(API_DATE_FORMAT)
    
    elif (start.date() - first_day).days <= 0:
        past_url = ""
    else:
        past_url = "?start=" + (start.date() - timedelta(days=duration + 1)).strftime(API_DATE_FORMAT) + \
                    "&end=" + (start.date() - timedelta(days=1)).strftime(API_DATE_FORMAT)
    if (last_day - timedelta(days=duration + 1)) < end.date() < (last_day - timedelta(days=1)):
        next_url = "?start=" + (end.date() + timedelta(days=1)).strftime(API_DATE_FORMAT) + "&end=" + \
                   (end.date() + timedelta(days=(duration + 1))).strftime(API_DATE_FORMAT)
    elif (last_day - end.date()).days <= 0:
        next_url = ""
    else:
        next_url = "?start=" + \
                   (start.date() + timedelta(days=duration + 1)).strftime(API_DATE_FORMAT) + "&end=" + \
                   (end.date() + timedelta(days=duration + 1)).strftime(API_DATE_FORMAT)
    return next_url, past_url


def get_bytes_data_stream_match(chunks, date, stream):
    """ returns byte value for correct chunk based on data stream and type comparisons"""
    all_bytes = None
    for chunk in chunks:
        if (chunk["time_bin"]).date() == date and chunk["data_stream"] == stream:
            if all_bytes is None:
                all_bytes = chunk.get("bytes", 0) or 0
            else:
                all_bytes += chunk.get("bytes", 0) or 0
    if all_bytes is not None:
        return all_bytes
    else:
        return None


def get_bytes_participant_match(stream_data: List[Dict[str, datetime]], a_date: date):
    all_bytes = None
    for data_point in stream_data:
        if (data_point["time_bin"]).date() == a_date:
            if all_bytes is None:
                all_bytes = data_point.get("bytes", 0) or 0
            else:
                all_bytes += data_point.get("bytes", 0) or 0
    if all_bytes is not None:
        return all_bytes
    else:
        return None


def get_bytes_processed_data_match(participant_data: List[Dict[str, datetime]], a_date: date):
    # participant_data is a list of dicts which hold {time_bin: _, processed_data: _}
    # there should only ever be one data_point corresponding to a specific date per patient
    # if no data exists, return None -- if the participant_data object is none, there is no data for this data
    # stream for this participant
    if participant_data is not None:
        for data_point in participant_data:
            if(data_point["time_bin"]) == a_date:
                return data_point["processed_data"]
    return None


def get_bytes_patient_processed_match(participant_data, a_date: date, stream: str):
    # participant_data is a list of dicts which hold {time_bin: _, processed_data: _, stream:, _}
    # there should only ever be one data_point corresponding to a specific date per patient
    # if no data exists, return None -- if the participant_data object is none, there is no data for this data
    # stream for this participant
    if participant_data is not None:
        for data_point in participant_data:
            if (data_point["time_bin"]) == a_date and data_point["data_stream"] == stream:
                return data_point["processed_data"]
    return None


def dashboard_chunkregistry_date_query(study_id: int, data_stream: str = None):
    """ gets the first and last days in the study excluding 1/1/1970 bc that is obviously an error and makes
    the frontend annoying to use """
    unix_epoch_start_sorta = make_aware(datetime(1970, 1, 2), pytz.utc)
    kwargs = {"study_id": study_id}
    if data_stream:
        kwargs["data_type"] = data_stream
    
    # this as queries with .first() and .last() is slow even as size of all_time_bins grows.
    all_time_bins: List[datetime] = list(
        ChunkRegistry.objects.filter(**kwargs).exclude(time_bin__lt=unix_epoch_start_sorta)
        .order_by("time_bin").values_list("time_bin", flat=True)
    )
    
    # default behavior for 1 or 0 time_bins
    if len(all_time_bins) < 2:
        return None, None
    
    return all_time_bins[0].date(), all_time_bins[-1].date()


# Fixme: start and end dates are never used
def dashboard_chunkregistry_query(
    participants: ParticipantQuerySet, data_stream: str = None, start: date = None, end: date = None
):
    """ Queries ChunkRegistry based on the provided parameters and returns a list of dictionaries
    with 3 keys: bytes, data_stream, and time_bin. """
    if isinstance(participants, Participant):
        kwargs = {"participant": participants}
    else:
        kwargs = {"participant_id__in": participants}
    
    if start:
        kwargs["time_bin__gte"] = start
    if end:
        kwargs["time_bin__lte"] = end
    if data_stream:
        kwargs["data_type"] = data_stream
    
    # rename the data_type and file_size fields in the db query itself for speed
    chunks = ChunkRegistry.objects.filter(**kwargs).extra(
        select={'data_stream': 'data_type', 'bytes': 'file_size'}
    ).values("participant__patient_id", "bytes", "data_stream", "time_bin")
    return {d.pop("participant__patient_id"): d for d in chunks}


def dashboard_pipelineregistry_query(study_id: int, participant_id: int):
    """ Queries Pipeline based on the provided parameters and returns a list of dicts with
    an id (which is ignored), a "day", and a bunch of strings which are data streams """
    # pipeline_chunks looks like this: [{day: 3/4/4, "data_stream1": 36634, "data_stream2": 2525}, ... ]
    pipeline_data = PipelineRegistry.objects.filter(study_id=study_id, participant__id=participant_id).order_by(
        "uploaded_at").last()
    if pipeline_data is not None:
        pipeline_chunks = json.loads(json.dumps(pipeline_data.processed_data)) # I feel like this shouldn't work but idk
        if pipeline_chunks:
            return pipeline_chunks
    
    return None


def extract_date_args_from_request(request: ResearcherRequest):
    """ Gets start and end arguments from GET/POST params, throws 400 on date formatting errors. """
    start = argument_grabber(request, "start", None)
    end = argument_grabber(request, "end", None)
    try:
        if start:
            start = datetime.strptime(start, API_DATE_FORMAT)
        if end:
            end = datetime.strptime(end, API_DATE_FORMAT)
    except ValueError as e:
        return abort(400, DATETIME_FORMAT_ERROR)
    
    return start, end


def extract_range_args_from_request(request: ResearcherRequest):
    """ Gets minimum and maximum arguments from GET/POST params """
    color_low_range = argument_grabber(request, "color_low", None)
    color_high_range = argument_grabber(request, "color_high", None)
    show_color = argument_grabber(request, "show_color", True)
    return color_low_range, color_high_range, show_color


def extract_flag_args_from_request(request: ResearcherRequest):
    """ Gets minimum and maximum arguments from GET/POST params, returns None if the object is None or empty """
    all_flags_string = argument_grabber(request, "flags", "")
    all_flags_list = []
    # parse to create a dict of flags
    flags_separated = all_flags_string.split('*')
    for flag in flags_separated:
        if flag != "":
            flag_apart = flag.split(',')
            string = flag_apart[0]
            all_flags_list.append([string, int(flag_apart[1])])
    return all_flags_list


def extract_data_stream_args_from_request(request: ResearcherRequest) -> str or None:
    """ Gets data stream if it is provided as a request POST or GET parameter,
    throws 400 errors on unknown data streams. """
    data_stream = argument_grabber(request, "data_stream", None)
    if data_stream:
        if data_stream not in ALL_DATA_STREAMS:
            return abort(400, "unrecognized data stream '%s'" % data_stream)
    return data_stream


def argument_grabber(request: ResearcherRequest, key: str, default: Any = None) -> str or None:
    return request.GET.get(key, request.POST.get(key, default))
