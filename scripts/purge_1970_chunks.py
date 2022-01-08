from constants.data_stream_constants import AMBIENT_AUDIO, IMAGE_FILE, VOICE_RECORDING
from database.data_access_models import ChunkRegistry

from datetime import datetime
import pytz

# Onnela Lab, the first deployment, went live after this date, and it may be early by a whole year.
# Any uploaded data from before this is due to a user manually setting the date on their phone,
# or it is corrupted data.
earlist_possible_data = datetime(year=2014, month=8, day=1, tzinfo=pytz.utc)
query = ChunkRegistry.objects.filter(time_bin__lt=earlist_possible_data) \
    .exclude(data_type__in=[IMAGE_FILE, AMBIENT_AUDIO, VOICE_RECORDING])

bad_chunks = []

print("\nSearching for clearly corrupted ChunkRegistries...\n")

# we don't detect some all bad files, but there are a few easy patterns that should fix all
# header mismatch exceptions due to unix-epoch start collisions.
# (The real fix for this should be to detect the case at upload)
print("\n\nThese files were found to include either corrupted or otherwise unusable data:")
for chunk in query.order_by("time_bin"):
    header: bytes = chunk.s3_retrieve().splitlines()[0]
    
    # if the header starts with a comma that means the timestamp will be interpreted as 1970.
    # this is invariably junk (data without a timestamp is useless), delete it.
    if header.startswith(b","):
        print(f"{chunk.chunk_path}:")
        print(f"\tincomplete: {chunk.time_bin.isoformat()}: '{header.decode()}'")
        bad_chunks.append(chunk)
        continue
    
    # headers are english, and never have any extended unicode range characters.
    # there are several ways to do this, the least-obscure is to test for characters that are above
    # 127 in their ordinal (byte) value.
    for c in header:
        if c > 127:
            print(f"{chunk.chunk_path}:")
            print(f"\tcorrupted: {chunk.time_bin.isoformat()}: {header}")
            bad_chunks.append(chunk)
            continue

if bad_chunks:
    y_n = input("\nEnter 'y' to delete the above ChunkRegistries: ")
    
    if y_n.lower() == "y":
        print("success case")
        ChunkRegistry.objects.filter(pk__in=[chunk.pk for chunk in bad_chunks]).delete()
else:
    print("No obviously corrupted chunk registries were found.")
