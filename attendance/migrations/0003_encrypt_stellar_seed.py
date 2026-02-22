"""
Migration: Encrypt existing plaintext stellar_seed values.

This migration:
1. Widens the stellar_seed column from max_length=56 to max_length=200
   to accommodate the Fernet-encrypted ciphertext + 'enc:' prefix.
2. Encrypts all existing plaintext seeds in the database.

BEFORE running this migration:
- Ensure STELLAR_SEED_ENCRYPTION_KEY is set in your environment / .env file.
- Back up your database.

Generate a key if you haven't already:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Then add to .env:
    STELLAR_SEED_ENCRYPTION_KEY=<your-generated-key>
"""

from django.db import migrations, models
import django.db.models.deletion


def encrypt_existing_seeds(apps, schema_editor):
    """
    Encrypt any plaintext seeds already stored in the database.
    Seeds that already start with 'enc:' are skipped (idempotent).
    """
    # Import here so the encryption utility uses the current Django settings.
    from attendance.encryption import encrypt_seed

    User = apps.get_model('attendance', 'User')
    users_to_update = []

    for user in User.objects.exclude(stellar_seed__isnull=True).exclude(stellar_seed=''):
        if not user.stellar_seed.startswith('enc:'):
            user.stellar_seed = encrypt_seed(user.stellar_seed)
            users_to_update.append(user)

    if users_to_update:
        User.objects.bulk_update(users_to_update, ['stellar_seed'])


def decrypt_existing_seeds(apps, schema_editor):
    """
    Reverse operation: decrypt seeds back to plaintext.
    Used only if rolling back this migration.
    WARNING: This re-exposes plaintext seeds in the database.
    """
    from attendance.encryption import decrypt_seed

    User = apps.get_model('attendance', 'User')
    users_to_update = []

    for user in User.objects.exclude(stellar_seed__isnull=True).exclude(stellar_seed=''):
        if user.stellar_seed.startswith('enc:'):
            user.stellar_seed = decrypt_seed(user.stellar_seed)
            users_to_update.append(user)

    if users_to_update:
        User.objects.bulk_update(users_to_update, ['stellar_seed'])


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_attendancesession_blockchain_verified_and_more'),
    ]

    operations = [
        # Step 1: Widen the column to hold encrypted values
        migrations.AlterField(
            model_name='user',
            name='stellar_seed',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=200,
                help_text='Fernet-encrypted Stellar secret seed. Never store plaintext.',
            ),
        ),
        # Step 2: Encrypt all existing plaintext seeds
        migrations.RunPython(
            encrypt_existing_seeds,
            reverse_code=decrypt_existing_seeds,
        ),
    ]