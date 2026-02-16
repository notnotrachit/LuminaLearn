# This migration was intentionally written by hand to add enrollment-related fields.
# It is a simple schema-only change (no data migration) and is safe for Django to apply.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0004_merge_20250429_1926'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='enrollment_code',
            field=models.CharField(blank=True, max_length=12, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='course',
            name='enrollment_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]