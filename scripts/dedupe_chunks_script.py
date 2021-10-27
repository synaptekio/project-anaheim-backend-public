# add the root of the project into the path to allow cd-ing into this folder and running the script.
from os.path import abspath
from sys import path

path.insert(0, abspath(__file__).rsplit('/', 2)[0])
from typing import List

from collections import Counter

from constants.data_stream_constants import CHUNKABLE_FILES
from database.data_access_models import ChunkRegistry, FileToProcess

print("""
This script can take quite a while to run, it depends on the size of the ChunkRegistry database table.
It is STRONGLY recommended that you disable data processing before executing this script.
(ssh and run processing-stop, run processing-start when the script has finished.)

Finding duplicate file chunks. This needs to be done in a memory-safe, so it could take several minutes.
When the initial database query operation finishes you will start seeing additional output.

This script is incremental.  You can stop it at any time and restart it later.

DO NOT RUN MULTIPLE INSTANCES OF THIS SCRIPT AT THE SAME TIME.
""")


from django.db.migrations.executor import MigrationExecutor
from django.db import connections, DEFAULT_DB_ALIAS

connection = connections[DEFAULT_DB_ALIAS]
connection.prepare_database()
applied_migrations = set(migration_name for _, migration_name in MigrationExecutor(connection).loader.applied_migrations)
if "0025_auto_20200106_2153.py" in applied_migrations:
    print("\nYour chunk paths are already unique.\n")
    exit(0)

DEBUG = False

if DEBUG:
    print("\nRUNNING IN DEBUG MODE, NO DESTRUCTIVE ACTIONS WILL BE TAKEN.\n")


def run():
    duplicate_chunks, duplicate_media = get_duplicates()

    for media_file in duplicate_media:
        remove_all_but_one_chunk(media_file)

    fix_duplicates(duplicate_chunks)


def get_duplicates() -> (List[str], List[str]):
    print("Getting duplicates...")
    # counter = Counter(ChunkRegistry.objects.values_list("chunk_path", flat=True).iterator()).most_common()
    counter = Counter(ChunkRegistry.objects.values_list("chunk_path", flat=True)).most_common()

    duplicate_chunks = []
    duplicate_media = []
    for chunk_path, count in counter:
        if count == 1:
            break

        if chunk_path.endswith(".csv"):
            duplicate_chunks.append(chunk_path)
        else:
            duplicate_media.append(chunk_path)

    print(f"Discovered {len(duplicate_media)} duplicate media file(s) and {len(duplicate_chunks)} duplicate chunked file(s).")

    return duplicate_chunks, duplicate_media


def fix_duplicates(duplicate_chunks):
    for path in duplicate_chunks:

        # deconstruct relevant information from chunk path, clean it
        path_components = path.split("/")
        if len(path_components) == 5:
            _, study_obj_id, username, data_stream, timestamp = path.split("/")
        elif len(path_components) == 4:
            study_obj_id, username, data_stream, timestamp = path.split("/")
        else:
            print("You appear to have an invalid file path.  Please report this error to https://github.com/onnela-lab/beiwe-backend/issues")
            raise Exception("invalid_path: %s" % path)

        # not all files are chunkable, they will require different logic.
        if data_stream not in CHUNKABLE_FILES:
            remove_all_but_one_chunk(path)
            continue
        else:
            try:
                FileToProcess.reprocess_originals_from_chunk_path(path)
            except Exception as e:
                if "did not find any matching files" in str(e):
                    pass
                else:
                    raise
            remove_all_but_one_chunk(path)



def remove_all_but_one_chunk(chunk_path: str):
    chunk_ids = list(ChunkRegistry.objects.filter(chunk_path=chunk_path).values_list("id", flat=True))

    if len(chunk_ids) in [0, 1]:
        raise Exception("This s not possible, are you running multiple instances of this script?")

    # the lowest oldest id is probably the oldest.  It is ~most likely that users who have downloaded
    # data have newer chunk hash values, so we will ensure the
    chunk_ids.sort()
    remaining_id = chunk_ids.pop()
    print(remaining_id)
    print(f"Deleting {len(chunk_ids)} duplicate instance(s) for {chunk_path}.")
    if not DEBUG:
        ChunkRegistry.objects.filter(id__in=chunk_ids).delete()


if __name__ == "__main__":
    run()
