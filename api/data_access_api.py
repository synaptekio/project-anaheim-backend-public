import json
from datetime import datetime

from dateutil import tz
from django.db.models import QuerySet
from django.http.response import FileResponse
from django.utils.timezone import make_aware
from django.views.decorators.http import require_http_methods

from authentication.data_access_authentication import api_study_credential_check
from constants.data_access_api_constants import CHUNK_FIELDS
from constants.data_stream_constants import ALL_DATA_STREAMS
from constants.datetime_constants import API_TIME_FORMAT
from database.data_access_models import ChunkRegistry
from database.user_models import Participant
from libs.internal_types import ApiStudyResearcherRequest
from libs.streaming_zip import zip_generator
from middleware.abort_middleware import abort


ENABLE_DATA_API_DEBUG = False

def log(*args, **kwargs):
    if ENABLE_DATA_API_DEBUG:
        print(*args, **kwargs)


@require_http_methods(['POST', "GET"])
@api_study_credential_check(block_test_studies=True)
def get_data(request: ApiStudyResearcherRequest):
    """ Required: access key, access secret, study_id
    JSON blobs: data streams, users - default to all
    Strings: date-start, date-end - format as "YYYY-MM-DDThh:mm:ss"
    optional: top-up = a file (registry.dat)
    cases handled:
        missing creds or study, invalid researcher or study, researcher does not have access
        researcher creds are invalid
    Returns a zip file of all data files found by the query. """
    
    # FIXME: this comment:
    # (Flask automatically returns a 400 response if a parameter is accessed
    #    but does not exist in request.POST() )
    
    query_args = {}
    determine_data_streams_for_db_query(request, query_args)
    determine_users_for_db_query(request, query_args)
    determine_time_range_for_db_query(request, query_args)
    
    # Do query! (this is actually a generator, it can only be iterated over once)
    get_these_files = handle_database_query(
        request.api_study.pk, query_args, registry_dict=parse_registry(request)
    )
    return FileResponse(
        zip_generator(get_these_files, construct_registry='web_form' not in request.POST),
        content_type="zip",
        as_attachment='web_form' in request.POST,
        filename="data.zip",
    )

# @require_http_methods(["GET", "POST"])
# @api_study_credential_check()
# def pipeline_data_download(request: ApiStudyResearcherRequest):
#     # the following two cases are for difference in content wrapping between the CLI script and
#     # the download page.
#     if 'tags' in request.POST:
#         try:
#             tags = json.loads(request.POST['tags'])
#         except ValueError:
#             tags = request.POST.getlist('tags')
#         query = PipelineUpload.objects.filter(study__id=request.api_study.id, tags__tag__in=tags)
#     else:
#         query = PipelineUpload.objects.filter(study__id=request.api_study.id)

#     return StreamingHttpResponse(
#         request,
#         zip_generator_for_pipeline(query),
#         mimetype="zip",
#         headers={'Content-Disposition': 'attachment; filename="data.zip"'}
#     )


def parse_registry(request: ApiStudyResearcherRequest):
    """ Parses the provided registry.dat file and returns a dictionary of chunk
    file names and hashes.  (The registry file is just a json dictionary containing
    a list of file names and hashes.) """
    registry = request.POST.get("registry", None)
    if registry is None:
        log("no registry")
        return None
    
    try:
        ret = json.loads(registry)
    except ValueError:
        log("bad json registry")
        return abort(400)
    
    if not isinstance(ret, dict):
        log("json was not a dict")
        return abort(400)
    
    return ret


def str_to_datetime(time_string):
    """ Translates a time string to a datetime object, raises a 400 if the format is wrong."""
    try:
        return make_aware(datetime.strptime(time_string, API_TIME_FORMAT), tz.UTC)
    except ValueError as e:
        if "does not match format" in str(e):
            log("does not match format")
            log(str(e))
            return abort(400)
        raise  # not best practice but I'm okay with a potential 500 error alerting us to new cases


#########################################################################################
############################ DB Query For Data Download #################################
#########################################################################################

def determine_data_streams_for_db_query(request: ApiStudyResearcherRequest, query_dict: dict):
    """ Determines, from the html request, the data streams that should go into the database query.
    Modifies the provided query object accordingly, there is no return value
    Throws a 404 if the data stream provided does not exist. """
    if 'data_streams' in request.POST:
        # the following two cases are for difference in content wrapping between
        # the CLI script and the download page.
        try:
            query_dict['data_types'] = json.loads(request.POST['data_streams'])
        except ValueError:
            log("did not receive json data streams")
            query_dict['data_types'] = request.POST.getlist('data_streams')
        
        for data_stream in query_dict['data_types']:
            if data_stream not in ALL_DATA_STREAMS:
                log("invalid data stream:", data_stream)
                return abort(404)


def determine_users_for_db_query(request: ApiStudyResearcherRequest, query: dict):
    """ Determines, from the html request, the users that should go into the database query.
    Modifies the provided query object accordingly, there is no return value.
    Throws a 404 if a user provided does not exist. """
    if 'user_ids' in request.POST:
        try:
            query['user_ids'] = [user for user in json.loads(request.POST['user_ids'])]
        except ValueError:
            query['user_ids'] = request.POST.getlist('user_ids')
        
        # Ensure that all user IDs are patient_ids of actual Participants
        if not Participant.objects.filter(patient_id__in=query['user_ids']).count() == len(query['user_ids']):
            log("invalid participant")
            return abort(404)


def determine_time_range_for_db_query(request: ApiStudyResearcherRequest, query: dict):
    """ Determines, from the html request, the time range that should go into the database query.
    Modifies the provided query object accordingly, there is no return value.
    Throws a 404 if a user provided does not exist. """
    if 'time_start' in request.POST:
        query['start'] = str_to_datetime(request.POST['time_start'])
    if 'time_end' in request.POST:
        query['end'] = str_to_datetime(request.POST['time_end'])


def handle_database_query(study_id: int, query_dict: dict, registry_dict: dict = None) -> QuerySet:
    """ Runs the database query and returns a QuerySet. """
    chunks = ChunkRegistry.get_chunks_time_range(study_id, **query_dict)
    
    if not registry_dict:
        return chunks.values(*CHUNK_FIELDS)
    
    # If there is a registry, we need to filter on the chunks
    else:
        # Get all chunks whose path and hash are both in the registry
        possible_registered_chunks = chunks \
            .filter(chunk_path__in=registry_dict, chunk_hash__in=registry_dict.values()) \
            .values('pk', 'chunk_path', 'chunk_hash')
        
        # determine those chunks that we do not want present in the download
        # (get a list of pks that have hashes that don't match the database)
        registered_chunk_pks = [
            c['pk'] for c in possible_registered_chunks
            if registry_dict[c['chunk_path']] == c['chunk_hash']
        ]
        
        # add the exclude and return the queryset
        return chunks.exclude(pk__in=registered_chunk_pks).values(*CHUNK_FIELDS)
