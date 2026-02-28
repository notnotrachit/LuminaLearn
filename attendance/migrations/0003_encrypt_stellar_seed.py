# Generated migration for Bug #1: Encrypt stellar_seed storage

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_attendancesession_blockchain_verified_and_more'),
    ]

    operations = [
        # Add new encrypted field
        migrations.AddField(
            model_name='user',
            name='stellar_seed_encrypted',
            field=models.BinaryField(blank=True, null=True),
        ),
        # Remove old plaintext field
        migrations.RemoveField(
            model_name='user',
            name='stellar_seed',
        ),
    ]
