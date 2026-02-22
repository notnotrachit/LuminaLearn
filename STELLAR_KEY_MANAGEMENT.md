# Stellar Seed Key Management & Rotation Guide

## Overview

Stellar secret seeds are encrypted at rest using Fernet symmetric encryption
(`cryptography` library). The encryption key is stored in the environment
variable `STELLAR_SEED_ENCRYPTION_KEY`, never in the codebase.

---

## Initial Setup

### 1. Generate an encryption key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Add to your `.env` file

```
STELLAR_SEED_ENCRYPTION_KEY=<your-generated-key>
```

### 3. Run migrations

```bash
python manage.py migrate attendance 0003_encrypt_stellar_seed
```

This will encrypt any existing plaintext seeds in the database automatically.

---

## Key Rotation

Key rotation means replacing the current encryption key with a new one and
re-encrypting all seeds with the new key.

### When to rotate

- Suspected key compromise
- Staff with key access leaves the team
- Periodic rotation policy (recommended: every 90 days in production)

### Steps

#### 1. Generate a new key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### 2. Back up your database

```bash
# SQLite
cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d)
```

#### 3. Run the rotation management command

```bash
python manage.py rotate_stellar_seed_key \
    --old-key <current-STELLAR_SEED_ENCRYPTION_KEY> \
    --new-key <newly-generated-key>
```

This command (see `attendance/management/commands/rotate_stellar_seed_key.py`):
- Decrypts every seed with the old key
- Re-encrypts it with the new key
- Saves atomically — no window where seeds are plaintext

#### 4. Update your environment

Replace `STELLAR_SEED_ENCRYPTION_KEY` in your `.env` / secrets manager with the new key.

#### 5. Restart the application

The new key takes effect on next startup.

---

## Management Command

Create `attendance/management/commands/rotate_stellar_seed_key.py`:

```python
from django.core.management.base import BaseCommand
from django.db import transaction
from cryptography.fernet import Fernet
from attendance.models import User


class Command(BaseCommand):
    help = 'Rotate the Stellar seed encryption key.'

    def add_arguments(self, parser):
        parser.add_argument('--old-key', required=True)
        parser.add_argument('--new-key', required=True)

    def handle(self, *args, **options):
        old_fernet = Fernet(options['old_key'].encode())
        new_fernet = Fernet(options['new_key'].encode())

        users = User.objects.exclude(_stellar_seed__isnull=True).exclude(_stellar_seed='')
        rotated = 0

        with transaction.atomic():
            for user in users:
                raw = user._stellar_seed
                if not raw:
                    continue
                # Decrypt with old key
                if raw.startswith('enc:'):
                    plaintext = old_fernet.decrypt(raw[4:].encode()).decode()
                else:
                    plaintext = raw  # legacy plaintext
                # Re-encrypt with new key
                user._stellar_seed = 'enc:' + new_fernet.encrypt(plaintext.encode()).decode()
                user.save(update_fields=['_stellar_seed'])
                rotated += 1

        self.stdout.write(self.style.SUCCESS(f'Rotated {rotated} seeds successfully.'))
```

---

## Security Notes

- The `STELLAR_SEED_ENCRYPTION_KEY` must **never** be committed to version control.
- Ensure `.env` is listed in `.gitignore`.
- In production, store the key in a secrets manager (AWS Secrets Manager, HashiCorp Vault,
  GCP Secret Manager) rather than a plain `.env` file.
- The `enc:` prefix on stored values allows the code to distinguish encrypted values from
  any legacy plaintext values, making the migration safe to run more than once (idempotent).