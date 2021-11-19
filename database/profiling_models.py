from datetime import timedelta

from django.db import models
from django.utils import timezone

from config.constants import (DATA_STREAM_TO_S3_FILE_NAME_STRING,
    UPLOAD_FILE_TYPE_MAPPING)
from database.models import JSONTextField, Participant, TimestampedModel
from libs.security import decode_base64, encode_base64


class EncryptionErrorMetadata(TimestampedModel):
    file_name = models.CharField(max_length=256)
    total_lines = models.PositiveIntegerField()
    number_errors = models.PositiveIntegerField()
    error_lines = JSONTextField()
    error_types = JSONTextField()
    participant = models.ForeignKey('Participant', on_delete=models.PROTECT, null=True)


class LineEncryptionError(TimestampedModel):
    AES_KEY_BAD_LENGTH = "AES_KEY_BAD_LENGTH"
    EMPTY_KEY = "EMPTY_KEY"
    INVALID_LENGTH = "INVALID_LENGTH"
    IV_BAD_LENGTH = "IV_BAD_LENGTH"
    IV_MISSING = "IV_MISSING"
    LINE_EMPTY = "LINE_EMPTY"
    LINE_IS_NONE = "LINE_IS_NONE"
    MALFORMED_CONFIG = "MALFORMED_CONFIG"
    MP4_PADDING = "MP4_PADDING"
    PADDING_ERROR = "PADDING_ERROR"
    
    ERROR_TYPE_CHOICES = (
        (AES_KEY_BAD_LENGTH, AES_KEY_BAD_LENGTH),
        (EMPTY_KEY, EMPTY_KEY),
        (INVALID_LENGTH, INVALID_LENGTH),
        (IV_BAD_LENGTH, IV_BAD_LENGTH),
        (IV_MISSING, IV_MISSING),
        (LINE_EMPTY, LINE_EMPTY),
        (LINE_IS_NONE, LINE_IS_NONE),
        (MP4_PADDING, MP4_PADDING),
        (MALFORMED_CONFIG, MALFORMED_CONFIG),
        (PADDING_ERROR, PADDING_ERROR),
    )
    
    type = models.CharField(max_length=32, choices=ERROR_TYPE_CHOICES)
    line = models.TextField(blank=True)
    base64_decryption_key = models.TextField()
    prev_line = models.TextField(blank=True)
    next_line = models.TextField(blank=True)
    participant = models.ForeignKey(Participant, null=True, on_delete=models.PROTECT)


class DecryptionKeyError(TimestampedModel):
    file_path = models.CharField(max_length=256)
    contents = models.TextField()
    traceback = models.TextField(null=True)
    participant = models.ForeignKey('Participant', on_delete=models.PROTECT, related_name='decryption_key_errors')
    
    def decode(self):
        return decode_base64(self.contents)
    
    @classmethod
    def do_create(cls, file_path: str, contents: bytes, traceback: str, participant: Participant):
        try:
            DecryptionKeyError.objects.create(
                file_path=file_path,
                contents=contents.decode(),
                traceback=traceback,
                participant=participant,
            )
        except ValueError:
            # to avoid storing 50% more data we try to store as the orig bytes, which SHOULD be
            # encoded as base64, but sometimes we get junk null characters.  sure fine whatever...
            DecryptionKeyError.objects.create(
                file_path=file_path,
                contents=encode_base64(contents),
                traceback=traceback,
                participant=participant,
            )


class UploadTracking(TimestampedModel):
    file_path = models.CharField(max_length=256)
    file_size = models.PositiveIntegerField()
    timestamp = models.DateTimeField()
    participant = models.ForeignKey('Participant', on_delete=models.PROTECT, related_name='upload_trackers')
    
    @classmethod
    def re_add_files_to_process(cls, number=100):
        """ Re-adds the most recent [number] files that have been uploaded recently to FiletToProcess.
            (this is fairly optimized because it is part of debugging file processing) """
        from database.data_access_models import FileToProcess
        uploads = cls.objects.order_by("-created_on").values_list(
            "file_path", "participant__study_id", "participant_id"
        )[:number]
        new_ftps = []
        participant_cache = {}  # uhg need to cache participants...
        for i, (file_path, study_id, participant_id) in enumerate(uploads):
            if participant_id in participant_cache:
                participant = participant_cache[participant_id]
            else:
                participant = Participant.objects.get(id=participant_id)
                participant_cache[participant_id] = participant
            
            if i % 10 == 0:
                print(i, sep="... ")
            
            if FileToProcess.objects.filter(s3_file_path__icontains=file_path).exists():
                print(f"skipping {file_path}, appears to already be present")
                continue
            
            new_ftps.append(FileToProcess(
                s3_file_path=file_path,
                study_id=study_id,
                participant=participant
            ))
        FileToProcess.objects.bulk_create(
            new_ftps
        )
        # FileToProcess.append_file_for_processing(
        #     # file_path, study_object_id, **kwargs
        #     file_path,
        #     # participant__study__object_id,
        #     participant=participant,
        # )
    
    @classmethod
    def add_files_to_process2(cls, limit=25):
        """ Re-adds the most recent [limit] files that have been uploaded recently to FiletToProcess.
            (this is fairly optimized because it is part of debugging file processing) """
        from database.data_access_models import FileToProcess
        
        upload_queries = []
        for ds in DATA_STREAM_TO_S3_FILE_NAME_STRING.values():
            if ds == "identifiers":
                continue
            query = (
                cls.objects.order_by("-created_on")
                    .filter(file_path__contains=ds)
                    .values_list("file_path",
                                 "participant__study_id",
                                 "participant__study__object_id",
                                 "participant_id")[:limit]
            )
            upload_queries.append((ds, query))
        
        new_ftps = []
        # participant_cache = {}  # uhg need to cache participants...
        file_paths_wandered = set(FileToProcess.objects.values_list("s3_file_path", flat=True))
        for file_type, uploads_query in upload_queries:
            print(file_type)
            for i, (file_path, study_id, object_id, participant_id) in enumerate(uploads_query):
                
                if i % 10 == 0 or i == limit-1:
                    print(i+1 if i == limit-1 else i, sep="... ",)
                
                if file_path in file_paths_wandered:
                    continue
                else:
                    file_paths_wandered.add(file_path)
                
                new_ftps.append(FileToProcess(
                    s3_file_path=object_id + "/" + file_path,
                    study_id=study_id,
                    participant_id=participant_id
                ))
        FileToProcess.objects.bulk_create(new_ftps)
    
    
    @classmethod
    def get_trailing_count(cls, time_delta):
        return cls.objects.filter(timestamp__gte=timezone.now() - time_delta).count()
    
    
    @classmethod
    def weekly_stats(cls, days=7, get_usernames=False):
        ALL_FILETYPES = UPLOAD_FILE_TYPE_MAPPING.values()
        if get_usernames:
            data = {filetype: {"megabytes": 0., "count": 0, "users": set()} for filetype in ALL_FILETYPES}
        else:
            data = {filetype: {"megabytes": 0., "count": 0} for filetype in ALL_FILETYPES}
        
        data["totals"] = {}
        data["totals"]["total_megabytes"] = 0
        data["totals"]["total_count"] = 0
        data["totals"]["users"] = set()
        days_delta = timezone.now() - timedelta(days=days)
        # .values is a huge speedup, .iterator isn't but it does let us print progress realistically
        query = UploadTracking.objects.filter(timestamp__gte=days_delta).values(
                "file_path", "file_size", "participant"
        ).iterator()
        
        for i, upload in enumerate(query):
            # global stats
            data["totals"]["total_count"] += 1
            data["totals"]["total_megabytes"] += upload["file_size"]/ 1024. / 1024.
            data["totals"]["users"].add(upload["participant"])
            
            # get data stream type from file_path (woops, ios log broke this code, fixed)
            path_extraction = upload["file_path"].split("/", 2)[1]
            if path_extraction == "ios":
                path_extraction = "ios_log"
            
            file_type = UPLOAD_FILE_TYPE_MAPPING[path_extraction]
            # update per-data-stream information
            data[file_type]["megabytes"] += upload["file_size"]/ 1024. / 1024.
            data[file_type]["count"] += 1
            
            if get_usernames:
                data[file_type]["users"].add(upload["participant"])
            if i % 10000 == 0:
                print("processed %s uploads..." % i)
        
        data["totals"]["user_count"] = len(data["totals"]["users"])
        
        if not get_usernames:  # purge usernames if we don't need them.
            del data["totals"]["users"]
        
        return data
