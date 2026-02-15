from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import secrets
import string

class User(AbstractUser):
    is_admin = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)
    is_student = models.BooleanField(default=False)
    stellar_public_key = models.CharField(max_length=56, blank=True, null=True)
    stellar_seed = models.CharField(max_length=56, blank=True, null=True)  # This should be encrypted in production

class Course(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teaching_courses')
    created_at = models.DateTimeField(auto_now_add=True)
    enrollment_code = models.CharField(max_length=12, unique=True, blank=True, null=True)
    enrollment_expires_at = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.enrollment_code:
            self.enrollment_code = self.generate_enrollment_code()
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_enrollment_code(cls):
        """Generate a secure random alphanumeric enrollment code."""
        while True:
            # Generate 8-character alphanumeric code (uppercase letters and digits)
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if not cls.objects.filter(enrollment_code=code).exists():
                return code
    
    @property
    def is_enrollment_active(self):
        """Check if enrollment is currently active (not expired)."""
        if self.enrollment_expires_at is None:
            return True
        return timezone.now() < self.enrollment_expires_at

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
    end_time = models.DateTimeField()
    nonce = models.CharField(max_length=100) # Used for QR code verification
    is_active = models.BooleanField(default=True)
    blockchain_verified = models.BooleanField(default=False) # Whether session was recorded on blockchain
    
    def __str__(self):
        return f"{self.lecture} - {self.start_time}"
    
    @property
    def is_expired(self):
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
