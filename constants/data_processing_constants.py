## Chunks
# This value is in seconds, it sets the time period that chunked files will be sliced into.
CHUNK_TIMESLICE_QUANTUM = 3600
# the name of the s3 folder that contains chunked data
CHUNKS_FOLDER = "CHUNKED_DATA"

BEIWE_PROJECT_ROOT = __file__.rsplit("/", 2)[0] + "/"
PROJECT_PARENT_FOLDER = BEIWE_PROJECT_ROOT.rsplit("/", 2)[0] + "/"
