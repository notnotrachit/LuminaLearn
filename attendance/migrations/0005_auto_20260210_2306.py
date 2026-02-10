from django.db import migrations, models
from django.utils import timezone

class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0004_merge_20250429_1926'),
    ]

    operations = [
        # Fix the end_time field that was incorrectly set to 'True' string
        migrations.AlterField(
            model_name='attendancesession',
            name='end_time',
            field=models.DateTimeField(),
        ),
    ]
