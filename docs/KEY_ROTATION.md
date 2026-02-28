# Encryption Key Rotation Guide

## Overview

This document describes procedures for rotating the encryption keys used to protect Stellar private keys stored in the LuminaLearn database.

## Current Encryption Architecture

LuminaLearn uses Fernet symmetric encryption to protect Stellar secret seeds:

- **Encryption Key Derivation**: The encryption key is derived from Django's `SECRET_KEY` using PBKDF2-HMAC-SHA256
- **Encrypted Field**: `User.stellar_seed_encrypted` (BinaryField)
- **Encryption Method**: Fernet (symmetric encryption from `cryptography` library)
- **Key Location**: Django `SECRET_KEY` in environment variables

## When to Rotate Keys

Rotate encryption keys when:

1. **Security Breach**: `SECRET_KEY` or database has been compromised
2. **Personnel Changes**: Staff with key access leaves the organization
3. **Scheduled Rotation**: Following security policy (recommended: annually)
4. **Cryptographic Weakness**: Vulnerabilities discovered in encryption method
5. **Compliance Requirements**: Regulatory requirements mandate rotation

## Key Rotation Procedure

### Prerequisites

- Database backup completed and verified
- Access to production environment and `SECRET_KEY`
- Downtime window scheduled (estimated: 5-15 minutes depending on user count)

### Step 1: Backup Current State

```bash
# Backup database
python manage.py dumpdata attendance.User > users_backup.json

# Backup current SECRET_KEY
echo $SECRET_KEY > secret_key_backup.txt
```

### Step 2: Create New SECRET_KEY

```python
# Generate new SECRET_KEY
from django.core.management.utils import get_random_secret_key
new_secret_key = get_random_secret_key()
print(new_secret_key)
```

Save the new key securely (password manager, KMS, etc.).

### Step 3: Create Data Migration

Create a custom Django migration to re-encrypt all stellar seeds:

```python
# attendance/migrations/XXXX_rotate_encryption_keys.py
from django.db import migrations
from cryptography.fernet import Fernet
import hashlib
import base64


def get_fernet_from_key(secret_key):
    """Derive Fernet key from SECRET_KEY"""
    derived = hashlib.pbkdf2_hmac('sha256', secret_key.encode(), b'static-salt', 100000, dklen=32)
    return Fernet(base64.urlsafe_b64encode(derived))


def rotate_encryption_keys(apps, schema_editor):
    """Re-encrypt all stellar seeds with new key"""
    User = apps.get_model('attendance', 'User')

    # Get old and new Fernet instances
    old_secret_key = os.environ.get('OLD_SECRET_KEY')
    new_secret_key = os.environ.get('SECRET_KEY')

    if not old_secret_key:
        raise ValueError("OLD_SECRET_KEY environment variable required for rotation")

    old_fernet = get_fernet_from_key(old_secret_key)
    new_fernet = get_fernet_from_key(new_secret_key)

    # Process all users with encrypted seeds
    users_updated = 0
    for user in User.objects.exclude(stellar_seed_encrypted__isnull=True):
        try:
            # Decrypt with old key
            plaintext_seed = old_fernet.decrypt(bytes(user.stellar_seed_encrypted)).decode()

            # Re-encrypt with new key
            user.stellar_seed_encrypted = new_fernet.encrypt(plaintext_seed.encode())
            user.save(update_fields=['stellar_seed_encrypted'])
            users_updated += 1

        except Exception as e:
            print(f"Error rotating key for user {user.id}: {e}")
            raise

    print(f"Successfully rotated encryption keys for {users_updated} users")


def reverse_rotation(apps, schema_editor):
    """Reverse migration - re-encrypt with old key"""
    # Similar logic but swap old/new keys
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0003_encrypt_stellar_seed'),
    ]

    operations = [
        migrations.RunPython(rotate_encryption_keys, reverse_rotation),
    ]
```

### Step 4: Execute Rotation

```bash
# Set both old and new keys temporarily
export OLD_SECRET_KEY="<current_secret_key>"
export SECRET_KEY="<new_secret_key>"

# Run migration
python manage.py migrate

# Verify rotation succeeded
python manage.py shell
>>> from attendance.models import User
>>> user = User.objects.first()
>>> user.get_stellar_seed()  # Should decrypt successfully
```

### Step 5: Cleanup

```bash
# Remove OLD_SECRET_KEY from environment
unset OLD_SECRET_KEY

# Update environment configuration permanently
# (e.g., update .env, AWS Parameter Store, etc.)

# Verify application still works
python manage.py check --deploy
```

### Step 6: Verify and Monitor

```python
# Test decryption for sample users
from attendance.models import User

test_users = User.objects.filter(stellar_seed_encrypted__isnull=False)[:5]
for user in test_users:
    try:
        seed = user.get_stellar_seed()
        print(f"✓ User {user.username}: Decryption successful")
    except Exception as e:
        print(f"✗ User {user.username}: Decryption failed - {e}")
```

## Emergency Rollback

If rotation fails:

```bash
# Restore database from backup
python manage.py loaddata users_backup.json

# Restore old SECRET_KEY
export SECRET_KEY="<old_secret_key_from_backup>"

# Restart application
systemctl restart luminalearn
```

## Automated Key Rotation (Future Enhancement)

For production systems, consider implementing:

1. **Key Management Service (KMS)**: Use AWS KMS, Google Cloud KMS, or HashiCorp Vault
2. **Envelope Encryption**: Encrypt data with Data Encryption Key (DEK), encrypt DEK with Key Encryption Key (KEK)
3. **Key Versioning**: Support multiple key versions simultaneously during rotation
4. **Automated Rotation**: Schedule automatic key rotation with zero downtime

Example KMS integration:

```python
import boto3

def get_fernet_from_kms():
    """Get encryption key from AWS KMS"""
    kms = boto3.client('kms')

    # Generate or retrieve data key
    response = kms.generate_data_key(
        KeyId='alias/luminalearn-encryption-key',
        KeySpec='AES_256'
    )

    # Use plaintext key for Fernet
    return Fernet(base64.urlsafe_b64encode(response['Plaintext'][:32]))
```

## Security Best Practices

1. **Never commit keys** to version control
2. **Use different keys** for development, staging, and production
3. **Audit key access**: Log all access to encryption keys
4. **Regular rotation schedule**: Rotate keys at least annually
5. **Multi-person authorization**: Require multiple approvals for key changes
6. **Secure key storage**: Use KMS or hardware security modules (HSM) in production

## Compliance Considerations

- **PCI DSS**: Requires cryptographic key rotation at least annually
- **GDPR**: Encryption key management is part of "appropriate technical measures"
- **SOC 2**: Key rotation procedures must be documented and followed

## Support and Troubleshooting

### Common Issues

**Issue**: "Invalid token" error after rotation
- **Cause**: Old key still being used
- **Solution**: Verify `SECRET_KEY` environment variable is updated

**Issue**: Some users can't decrypt seeds
- **Cause**: Migration didn't process all users
- **Solution**: Re-run migration or manually re-encrypt affected users

**Issue**: Application won't start after rotation
- **Cause**: `SECRET_KEY` not properly set
- **Solution**: Check environment configuration, restart services

### Contact

For assistance with key rotation:
- **Security Team**: security@luminalearn.example.com
- **DevOps Team**: devops@luminalearn.example.com
- **Emergency Hotline**: +1-XXX-XXX-XXXX

## Audit Log Template

Maintain a log of all key rotations:

```
Date: YYYY-MM-DD
Reason: <scheduled/breach/compliance>
Performed By: <name>
Old Key ID: <last 8 chars>
New Key ID: <last 8 chars>
Users Affected: <count>
Downtime: <minutes>
Verification: <passed/failed>
Notes: <any issues encountered>
```

## References

- [NIST SP 800-57: Key Management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [Django SECRET_KEY Best Practices](https://docs.djangoproject.com/en/4.2/ref/settings/#secret-key)
- [Fernet Specification](https://github.com/fernet/spec/blob/master/Spec.md)
