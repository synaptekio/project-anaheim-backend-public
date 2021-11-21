# -*- coding: utf-8 -*-
from django.db import migrations


def convert_batch_users(apps, schema_editor):
    # permanently removed feature, remove in any migration squash.
    # Researcher = apps.get_model('database', 'Researcher')
    # for researcher in Researcher.objects.all():
    #     if researcher.username.startswith("BATCH USER"):
    #         researcher.is_batch_user = True
    #         researcher.save()
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('database', '0023_auto_20191003_1928'),
    ]

    operations = [
        migrations.RunPython(convert_batch_users),
    ]
