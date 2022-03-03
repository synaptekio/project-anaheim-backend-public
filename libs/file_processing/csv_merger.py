from typing import Dict, List, Set, Tuple

from botocore.exceptions import ReadTimeoutError
from cronutils import ErrorHandler
from constants.data_processing_constants import CHUNK_TIMESLICE_QUANTUM, CHUNKS_FOLDER

from constants.data_stream_constants import SURVEY_DATA_FILES
from database.data_access_models import ChunkRegistry
from database.study_models import Study
from database.survey_models import Survey
from database.user_models import Participant
from libs.file_processing.exceptions import ChunkFailedToExist, HeaderMismatchException
from libs.file_processing.utility_functions_csvs import construct_csv_string, csv_to_list, unix_time_to_string
from libs.file_processing.utility_functions_simple import (compress,
    convert_unix_to_human_readable_timestamps, ensure_sorted_by_timestamp)
from libs.s3 import s3_retrieve


class CsvMerger:
    """ This class is consumes binified data and  """
    
    def __init__(self, binified_data: Dict, error_handler: ErrorHandler, survey_id_dict: Dict):
        self.failed_ftps = set()
        self.ftps_to_retire = set()
        
        self.upload_these: List[Tuple[ChunkRegistry, str, bytes, str]] = []
        # chunk, something?, file contents, study object id
        
        # Track the earliest and latest time bins, to return them at the end of the function
        self.earliest_time_bin: int = None
        self.latest_time_bin: int = None
        
        self.binified_data = binified_data
        self.error_handler = error_handler
        self.survey_id_dict = survey_id_dict
        self.iterate()
    
    def get_retirees(self) -> Tuple[Set[int], int, int, int]:
        """ returns the ftp pks that have succeeded, the number of ftps that have failed, 
        and the earliest and the latest time bins """
        return self.ftps_to_retire.difference(self. failed_ftps), \
            len(self.failed_ftps), self.earliest_time_bin, self.latest_time_bin
    
    def iterate(self):
        for data_bin, (data_rows_list, ftp_list) in self.binified_data.items():
            with self.error_handler:
                self.inner_iterate(data_bin, data_rows_list, ftp_list)
    
    def inner_iterate(self, data_bin, data_rows_list, ftp_list):
        """  """
        try:
            study_object_id, user_id, data_type, time_bin, original_header = data_bin
            # Update earliest and latest time bins
            if self.earliest_time_bin is None or time_bin < self.earliest_time_bin:
                self.earliest_time_bin = time_bin
            if self.latest_time_bin is None or time_bin > self.latest_time_bin:
                self.latest_time_bin = time_bin
            
            # data_rows_list may be a generator; here it is evaluated
            updated_header = convert_unix_to_human_readable_timestamps(
                original_header, data_rows_list
            )
            chunk_path = construct_s3_chunk_path(study_object_id, user_id, data_type, time_bin)
            
            # two core cases
            if ChunkRegistry.objects.filter(chunk_path=chunk_path).exists():
                self.chunk_exists_case(chunk_path, study_object_id, updated_header, data_rows_list)
            else:
                self.chunk_not_exists_case(
                    chunk_path, study_object_id, updated_header, user_id, data_type,
                    original_header, time_bin, data_rows_list
                )
        
        except Exception as e:
            # Here we catch any exceptions that may have arisen, as well as the ones that we raised
            # ourselves (e.g. HeaderMismatchException). Whichever FTP we were processing when the
            # exception was raised gets added to the set of failed FTPs.
            self.failed_ftps.update(ftp_list)
            print(e)
            try:
                print(
                    f"FAILED TO UPDATE: study_id:{study_object_id}, user_id:{user_id}, "
                    f"data_type:{data_type}, time_bin:{time_bin}, header:{updated_header}"
                )
            except UnboundLocalError:
                # print something different if a variable is not defined yet
                for k in ("study_object_id", "user_id", "data_type", "time_bin", "updated_header"):
                    if k not in locals():
                        print(f"variable {k} was not defined")
            raise
        
        else:
            # If no exception was raised, the FTP has completed processing. Add it to the set of
            # retireable (i.e. completed) FTPs.
            self.ftps_to_retire.update(ftp_list)
    
    def chunk_not_exists_case(
        self, chunk_path: str, study_object_id: str, updated_header: str, user_id: str,
        data_type: str, original_header: bytes, time_bin: int, rows: List[bytes]
    ):
        ensure_sorted_by_timestamp(rows)
        new_contents = construct_csv_string(updated_header, rows)
        if data_type in SURVEY_DATA_FILES:
            # We need to keep a mapping of files to survey ids, that is handled here.
            survey_id_hash = study_object_id, user_id, data_type, original_header
            survey_id = Survey.objects.filter(
                object_id=self.survey_id_dict[survey_id_hash]
            ).values_list("pk", flat=True).get()
        else:
            survey_id = None
        
        # this object will eventually get **kwarg'd into ChunkRegistry.register_chunked_data
        chunk_params = {
            "study_id": Study.objects.filter(object_id=study_object_id).values_list("pk", flat=True).get(),
            "participant_id": Participant.objects.filter(patient_id=user_id).values_list("pk", flat=True).get(),
            "data_type": data_type,
            "chunk_path": chunk_path,
            "time_bin": time_bin,
            "survey_id": survey_id
        }
        
        self.upload_these.append(
            (chunk_params, chunk_path, compress(new_contents), study_object_id)
        )
    
    def chunk_exists_case(self, chunk_path: str, study_object_id: str, updated_header: str, rows):
        chunk = ChunkRegistry.objects.get(chunk_path=chunk_path)
        
        try:
            s3_file_data = s3_retrieve(chunk_path, study_object_id, raw_path=True)
        except ReadTimeoutError as e:
            # The following check was correct for boto 2, still need to hit with boto3 test.
            if "The specified key does not exist." == str(e):
                # This error can only occur if the processing gets actually interrupted and
                # data files fail to upload after DB entries are created.
                # Encountered this condition 11pm feb 7 2016, cause unknown, there was
                # no python stacktrace.  Best guess is mongo blew up.
                # If this happened, delete the ChunkRegistry and push this file upload to the next cycle
                chunk.remove()  # this line of code is ancient and almost definitely wrong.
                raise ChunkFailedToExist(
                    "chunk %s does not actually point to a file, deleting DB entry, should run correctly on next index."
                    % chunk_path
                )
            raise  # Raise original error if not 404 s3 error
        
        old_header, old_rows = csv_to_list(s3_file_data)
        
        if old_header != updated_header:
            # To handle the case where a file was on an hour boundary and placed in
            # two separate chunks we need to raise an error in order to retire this file. If this
            # happens AND ONE of the files DOES NOT have a header mismatch this may (
            # will?) cause data duplication in the chunked file whenever the file
            # processing occurs run.
            raise HeaderMismatchException(f'{old_header}\nvs.\n{updated_header}\nin\n{chunk_path}')
        
        old_rows = list(old_rows)
        old_rows.extend(rows)
        ensure_sorted_by_timestamp(old_rows)
        new_contents = construct_csv_string(updated_header, old_rows)
        
        self.upload_these.append((chunk, chunk_path, compress(new_contents), study_object_id))


def construct_s3_chunk_path(
    study_id: bytes, user_id: bytes, data_type: bytes, time_bin: int
) -> str:
    """ S3 file paths for chunks are of this form:
        CHUNKED_DATA/study_id/user_id/data_type/time_bin.csv """
    
    study_id = study_id.decode() if isinstance(study_id, bytes) else study_id
    user_id = user_id.decode() if isinstance(user_id, bytes) else user_id
    data_type = data_type.decode() if isinstance(data_type, bytes) else data_type
    
    return "%s/%s/%s/%s/%s.csv" % (
        CHUNKS_FOLDER, study_id, user_id, data_type,
        unix_time_to_string(time_bin * CHUNK_TIMESLICE_QUANTUM).decode()
    )
