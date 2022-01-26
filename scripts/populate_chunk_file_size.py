from database.data_access_models import ChunkRegistry
from libs.s3 import conn, S3_BUCKET
from django.utils import timezone
from django.db.models import Q
# print("start:", timezone.now())

basic_query = Q(file_size__isnull=True) | Q(file_size=0)

filters = {}

# stick study object ids here to process particular studies
study_object_ids = []
if study_object_ids:
    filters["study__object_id__in"] = study_object_ids

# this could be a huge query, use the iterator
query = ChunkRegistry.objects.filter(basic_query, **filters).values_list("pk", "chunk_path")

print("start:", timezone.now())
for i, (pk, path) in enumerate(query.iterator()):
    if i % 1000 == 0:
        print(i)
    size = conn.head_object(Bucket=S3_BUCKET, Key=path)["ContentLength"]
    ChunkRegistry.objects.filter(pk=pk).update(file_size=size)

print("end:", timezone.now())
