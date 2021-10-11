import json
from multiprocessing.pool import ThreadPool
from typing import Tuple
from zipfile import ZIP_STORED, ZipFile

from config.constants import IMAGE_FILE, SURVEY_ANSWERS, SURVEY_TIMINGS, VOICE_RECORDING
from database.study_models import Study
from libs.s3 import s3_retrieve
from libs.streaming_bytes_io import StreamingBytesIO


class DummyError(Exception): pass


def determine_file_name(chunk):
    """ Generates the correct file name to provide the file with in the zip file.
        (This also includes the folder location files in the zip.) """
    extension = chunk["chunk_path"][-3:]  # get 3 letter file extension from the source.
    if chunk["data_type"] == SURVEY_ANSWERS:
        # add the survey_id from the file path.
        return "%s/%s/%s/%s.%s" % (chunk["participant__patient_id"], chunk["data_type"],
                                   chunk["chunk_path"].rsplit("/", 2)[1], # this is the survey id
                                   str(chunk["time_bin"]).replace(":", "_"), extension)

    elif chunk["data_type"] == IMAGE_FILE:
        # add the survey_id from the file path.
        return "%s/%s/%s/%s/%s" % (
            chunk["participant__patient_id"],
            chunk["data_type"],
            chunk["chunk_path"].rsplit("/", 3)[1],  # this is the survey id
            chunk["chunk_path"].rsplit("/", 2)[1],  # this is the instance of the user taking a survey
            chunk["chunk_path"].rsplit("/", 1)[1]
        )

    elif chunk["data_type"] == SURVEY_TIMINGS:
        # add the survey_id from the database entry.
        return "%s/%s/%s/%s.%s" % (chunk["participant__patient_id"], chunk["data_type"],
                                   chunk["survey__object_id"],  # this is the survey id
                                   str(chunk["time_bin"]).replace(":", "_"), extension)

    elif chunk["data_type"] == VOICE_RECORDING:
        # Due to a bug that was not noticed until July 2016 audio surveys did not have the survey id
        # that they were associated with.  Later versions of the app (legacy update 1 and Android 6)
        # correct this.  We can identify those files by checking for the existence of the extra /.
        # When we don't find it, we revert to original behavior.
        if chunk["chunk_path"].count("/") == 4:  #
            return "%s/%s/%s/%s.%s" % (chunk["participant__patient_id"], chunk["data_type"],
                                       chunk["chunk_path"].rsplit("/", 2)[1],  # this is the survey id
                                       str(chunk["time_bin"]).replace(":", "_"), extension)

    # all other files have this form:
    return "%s/%s/%s.%s" % (chunk['participant__patient_id'], chunk["data_type"],
                            str(chunk["time_bin"]).replace(":", "_"), extension)


def batch_retrieve_s3(chunk: dict) -> Tuple[dict, bytes]:
    """ Data is returned in the form (chunk_object, file_data). """
    return chunk, s3_retrieve(
        chunk["chunk_path"],
        study_object_id=Study.objects.get(id=chunk["study_id"]).object_id,
        raw_path=True
    )


# Note: you cannot access the request context inside a generator function
def zip_generator(files_list, construct_registry=False):
    """ Pulls in data from S3 in a multithreaded network operation, constructs a zip file of that
    data. This is a generator, advantage is it starts returning data (file by file, but wrapped
    in zip compression) almost immediately. """

    processed_files = set()
    duplicate_files = set()
    pool = ThreadPool(3)
    # 3 Threads has been heuristically determined to be a good value, it does not cause the server
    # to be overloaded, and provides more-or-less the maximum data download speed.  This was tested
    # on an m4.large instance (dual core, 8GB of ram).
    file_registry = {}

    zip_output = StreamingBytesIO()
    zip_input = ZipFile(zip_output, mode="w", compression=ZIP_STORED, allowZip64=True)

    try:
        # chunks_and_content is a list of tuples, of the chunk and the content of the file.
        # chunksize (which is a keyword argument of imap, not to be confused with Beiwe Chunks)
        # is the size of the batches that are handed to the pool. We always want to add the next
        # file to retrieve to the pool asap, so we want a chunk size of 1.
        # (In the documentation there are comments about the timeout, it is irrelevant under this construction.)
        chunks_and_content = pool.imap_unordered(batch_retrieve_s3, files_list, chunksize=1)
        total_size = 0
        for chunk, file_contents in chunks_and_content:
            if construct_registry:
                file_registry[chunk['chunk_path']] = chunk["chunk_hash"]
            file_name = determine_file_name(chunk)
            if file_name in processed_files:
                duplicate_files.add((file_name, chunk['chunk_path']))
                continue
            processed_files.add(file_name)

            zip_input.writestr(file_name, file_contents)
            # These can be large, and we don't want them sticking around in memory as we wait for the yield
            del file_contents, chunk

            x = zip_output.getvalue()
            total_size += len(x)
            # print "%s: %sK, %sM" % (random_id, total_size / 1024, total_size / 1024 / 1024)
            yield x  # yield the (compressed) file information
            del x
            zip_output.empty()

        if construct_registry:
            zip_input.writestr("registry", json.dumps(file_registry))
            yield zip_output.getvalue()
            zip_output.empty()

        # close, then yield all remaining data in the zip.
        zip_input.close()
        yield zip_output.getvalue()

    except DummyError:
        # The try-except-finally block is here to guarantee the Threadpool is closed and terminated.
        # we don't handle any errors, we just re-raise any error that shows up.
        # (with statement does not work.)
        raise
    finally:
        # We rely on the finally block to ensure that the threadpool will be closed and terminated,
        # and also to print an error to the log if we need to.
        pool.close()
        pool.terminate()


# delete zip_generator_for_pipeline only by reverting the commit
def zip_generator_for_pipeline(files_list):
    pool = ThreadPool(3)
    zip_output = StreamingBytesIO()
    zip_input = ZipFile(zip_output, mode="w", compression=ZIP_STORED, allowZip64=True)
    try:
        # chunks_and_content is a list of tuples, of the chunk and the content of the file.
        # chunksize (which is a keyword argument of imap, not to be confused with Beiwe Chunks)
        # is the size of the batches that are handed to the pool. We always want to add the next
        # file to retrieve to the pool asap, so we want a chunk size of 1.
        # (In the documentation there are comments about the timeout, it is irrelevant under this construction.)
        chunks_and_content = pool.imap_unordered(batch_retrieve_pipeline_s3, files_list, chunksize=1)
        for pipeline_upload, file_contents in chunks_and_content:
            # file_name = determine_file_name(chunk)
            zip_input.writestr("data/" + pipeline_upload.file_name, file_contents)
            # These can be large, and we don't want them sticking around in memory as we wait for the yield
            del file_contents, pipeline_upload
            yield zip_output.getvalue()  # yield the (compressed) file information
            zip_output.empty()

        # close, then yield all remaining data in the zip.
        zip_input.close()
        yield zip_output.getvalue()

    except DummyError:
        # The try-except-finally block is here to guarantee the Threadpool is closed and terminated.
        # we don't handle any errors, we just re-raise any error that shows up.
        # (with statement does not work.)
        raise
    finally:
        # We rely on the finally block to ensure that the threadpool will be closed and terminated,
        # and also to print an error to the log if we need to.
        pool.close()
        pool.terminate()


def batch_retrieve_pipeline_s3(pipeline_upload):
    """ Data is returned in the form (chunk_object, file_data). """
    study = Study.objects.get(id = pipeline_upload.study_id)
    return pipeline_upload, s3_retrieve(pipeline_upload.s3_path,
                                        study.object_id,
                                        raw_path=True)



# class dummy_threadpool():
#     def imap_unordered(self, *args, **kwargs): #the existence of that self variable is key
#         # we actually want to cut off any threadpool args, which is conveniently easy because map does not use kwargs!
#         return map(*args)
#     def terminate(self): pass
#     def close(self): pass

