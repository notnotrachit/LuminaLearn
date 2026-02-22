"""
Encryption utility for sensitive fields (stellar_seed).

Uses Fernet symmetric encryption from the cryptography library.
The encryption key must be set via the STELLAR_SEED_ENCRYPTION_KEY
environment variable.

Generating a key (run once, store in .env):
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def get_fernet():
    """
    Return a Fernet instance using the encryption key from settings.
    Raises ImproperlyConfigured if key is missing or invalid.
    """
    key = getattr(settings, 'STELLAR_SEED_ENCRYPTION_KEY', None)
    if not key:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "STELLAR_SEED_ENCRYPTION_KEY must be set in environment variables."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_seed(plaintext_seed: str) -> str:
    """
    Encrypt a Stellar secret seed.

    Args:
        plaintext_seed: The raw Stellar secret seed string.

    Returns:
        Encrypted seed as a UTF-8 string (prefixed with 'enc:' to distinguish
        encrypted values from any legacy plaintext values in the database).
    """
    if not plaintext_seed:
        return plaintext_seed
    # Already encrypted — do not double-encrypt
    if plaintext_seed.startswith('enc:'):
        return plaintext_seed
    fernet = get_fernet()
    encrypted = fernet.encrypt(plaintext_seed.encode())
    return 'enc:' + encrypted.decode()


def decrypt_seed(stored_value: str) -> str:
    """
    Decrypt a stored Stellar secret seed.

    Args:
        stored_value: The value stored in the database (may be encrypted or
                      legacy plaintext).

    Returns:
        The original plaintext seed string.
    """
    if not stored_value:
        return stored_value
    # Legacy plaintext value — return as-is (will be encrypted on next save)
    if not stored_value.startswith('enc:'):
        return stored_value
    fernet = get_fernet()
    try:
        decrypted = fernet.decrypt(stored_value[4:].encode())
        return decrypted.decode()
    except InvalidToken:
        raise ValueError(
            "Failed to decrypt stellar_seed. The STELLAR_SEED_ENCRYPTION_KEY "
            "may be incorrect or the value may be corrupted."
        )