from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

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
    nonce = models.CharField(max_length=100, default='') # Used for QR code verification
    nonce = models.CharField(max_length=100, default='')  # Used for QR code verification
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
