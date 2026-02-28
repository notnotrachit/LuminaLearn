from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from cryptography.fernet import Fernet
import base64
import hashlib
from django.conf import settings

def _get_fernet():
    """
    Derive a stable encryption key from Django's SECRET_KEY.
    Uses PBKDF2-HMAC-SHA256 to create a Fernet-compatible key.
    """
    key_material = settings.SECRET_KEY.encode()
    derived = hashlib.pbkdf2_hmac('sha256', key_material, b'luminallearn_seed', 100_000)
    return Fernet(base64.urlsafe_b64encode(derived))

class User(AbstractUser):
    is_admin = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)
    is_student = models.BooleanField(default=False)
    stellar_public_key = models.CharField(max_length=56, blank=True, null=True)
    stellar_seed_encrypted = models.BinaryField(blank=True, null=True)  # Encrypted secret seed

    def set_stellar_seed(self, plaintext_seed: str):
        """
        Encrypt and store the stellar secret seed.
        """
        if plaintext_seed:
            f = _get_fernet()
            self.stellar_seed_encrypted = f.encrypt(plaintext_seed.encode())
        else:
            self.stellar_seed_encrypted = None

    def get_stellar_seed(self) -> str:
        """
        Decrypt and return the stellar secret seed.
        Returns None if no seed is stored.
        """
        if not self.stellar_seed_encrypted:
            return None
        f = _get_fernet()
        return f.decrypt(bytes(self.stellar_seed_encrypted)).decode()

class Course(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teaching_courses')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    roll_number = models.CharField(max_length=20)
    enrollment_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('course', 'roll_number')
    
    def __str__(self):
        return f"{self.student.username} in {self.course.code}"

class Lecture(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lectures')
    title = models.CharField(max_length=200)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    blockchain_lecture_id = models.CharField(max_length=50, blank=True, null=True)
    
    def __str__(self):
        return f"{self.course.code} - {self.title} ({self.date})"

class AttendanceSession(models.Model):
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='sessions')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    nonce = models.CharField(max_length=100, default='')  # Used for QR code verification
    is_active = models.BooleanField(default=True)
    blockchain_verified = models.BooleanField(default=False) # Whether session was recorded on blockchain
    
    def __str__(self):
        return f"{self.lecture} - {self.start_time}"
    
    @property
    def is_expired(self):
        if self.end_time is None:
            return False  # No expiry set → session is open, not expired
        return timezone.now() > self.end_time

class Attendance(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='attendances')
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='attendances', null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    blockchain_verified = models.BooleanField(default=False)
    transaction_hash = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        unique_together = ('student', 'lecture')

    def __str__(self):
        return f"{self.student.username} - {self.lecture} - {self.timestamp}"

    @property
    def explorer_url(self):
        """
        Get Stellar explorer URL for this attendance transaction.
        Issue #22: Add blockchain transaction explorer links
        """
        if not self.transaction_hash:
            return None

        from .stellar_helper import StellarHelper
        return StellarHelper.get_explorer_url(self.transaction_hash)


class FailedBlockchainTransaction(models.Model):
    """
    Queue for failed blockchain transactions that need manual retry.
    Issue #6: Add failed transaction queue for admin review
    """
    TRANSACTION_TYPES = [
        ('attendance', 'Mark Attendance'),
        ('lecture', 'Create Lecture'),
        ('course', 'Create Course'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Retry'),
        ('retrying', 'Retrying'),
        ('success', 'Retry Successful'),
        ('failed', 'Permanently Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Related objects (nullable for flexibility)
    student = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='failed_transactions'
    )
    lecture = models.ForeignKey(
        Lecture,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='failed_transactions'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='failed_transactions'
    )

    # Transaction data (JSON for flexibility)
    transaction_data = models.JSONField(
        help_text="Original transaction parameters"
    )

    # Error tracking
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    error_traceback = models.TextField(blank=True)

    # Retry tracking
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    successful_tx_hash = models.CharField(max_length=100, blank=True, null=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_transactions'
    )
    notes = models.TextField(blank=True, help_text="Admin notes")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['transaction_type', 'status']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.status} ({self.created_at})"

    def can_retry(self):
        """Check if transaction can be retried"""
        return (
            self.status in ['pending', 'failed'] and
            self.retry_count < self.max_retries
        )

    def mark_success(self, tx_hash, resolved_by=None):
        """Mark transaction as successfully retried"""
        from django.utils import timezone
        self.status = 'success'
        self.successful_tx_hash = tx_hash
        self.resolved_at = timezone.now()
        self.resolved_by = resolved_by
        self.save()

    def mark_failed(self):
        """Mark transaction as permanently failed"""
        from django.utils import timezone
        self.status = 'failed'
        self.resolved_at = timezone.now()
        self.save()
