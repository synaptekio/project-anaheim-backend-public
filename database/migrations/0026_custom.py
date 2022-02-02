from django.db import migrations


SQL_GET_TIMINGS = """
SELECT "id", "database_survey"."timings" FROM "database_survey"
""".strip()


def initial_weekly_schedules(apps, schema_editor):
    Survey = apps.get_model('database', 'Survey')
    WeeklySchedule = apps.get_model('database', 'WeeklySchedule')
    # We are removing the timings column field and django doesn't like having the attribute accessed
    # without a custom query.
    # we then create weekly schedules, copying the content of the create_weekly_schedules function.
    #  (We can't safely call the methon in a migration.)
    for survey in Survey.objects.raw(SQL_GET_TIMINGS):
        
        if not survey.timings:
            continue
        
        if not len(survey.timings) == 7:
            # bad source data, shouldn't exist, survey is corrupted. Ignore
            continue
        
        survey.weekly_schedules.all().delete()
        
        for day in range(7):
            for seconds in survey.timings[day]:
                hour = seconds // 3600
                minute = seconds % 3600 // 60
                # using get_or_create to catch duplicate schedules
                WeeklySchedule.objects.create(
                    survey=survey, day_of_week=day, hour=hour, minute=minute
                )


class Migration(migrations.Migration):
    
    dependencies = [
        ('database', '0026_auto_20200304_2001'),
    ]
    
    operations = [
        migrations.RunPython(initial_weekly_schedules, reverse_code=migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='survey',
            name='timings',
        ),
        migrations.RemoveField(
            model_name='surveyarchive',
            name='timings',
        ),
    ]
