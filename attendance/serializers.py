from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Course, Enrollment, Lecture, AttendanceSession, Attendance

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with read-only sensitive fields"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'is_admin', 'is_teacher', 'is_student', 'date_joined']
        read_only_fields = ['id', 'is_admin', 'is_teacher', 'is_student', 'date_joined']

class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course model"""
    teacher = UserSerializer(read_only=True)
    enrollments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = ['id', 'name', 'code', 'teacher', 'created_at', 'enrollments_count']
        read_only_fields = ['id', 'created_at']
    
    def get_enrollments_count(self, obj):
        return obj.enrollments.count()

class CourseWriteSerializer(serializers.ModelSerializer):
    """Write-only serializer for Course creation/updates"""
    class Meta:
        model = Course
        fields = ['name', 'code']

class EnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for Enrollment model"""
    student = UserSerializer(read_only=True)
    course = CourseSerializer(read_only=True)
    
    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'course', 'roll_number', 'enrollment_date']
        read_only_fields = ['id', 'enrollment_date']

class LectureSerializer(serializers.ModelSerializer):
    """Serializer for Lecture model"""
    course = CourseSerializer(read_only=True)
    attendances_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Lecture
        fields = ['id', 'course', 'title', 'date', 'start_time', 'end_time', 
                 'blockchain_lecture_id', 'attendances_count']
        read_only_fields = ['id', 'blockchain_lecture_id']
    
    def get_attendances_count(self, obj):
        return obj.attendances.count()

class LectureWriteSerializer(serializers.ModelSerializer):
    """Write-only serializer for Lecture creation/updates"""
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        source="course",
        write_only=True
    )
    
    class Meta:
        model = Lecture
        fields = ['title', 'date', 'start_time', 'end_time', 'course_id']

class AttendanceSessionSerializer(serializers.ModelSerializer):
    """Serializer for AttendanceSession model"""
    lecture = LectureSerializer(read_only=True)
    attendances_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceSession
        fields = ['id', 'lecture', 'start_time', 'end_time', 'is_active', 
                 'blockchain_verified', 'attendances_count']
        read_only_fields = ['id', 'start_time', 'nonce', 'blockchain_verified']
    
    def get_attendances_count(self, obj):
        return obj.attendances.count()

class AttendanceSerializer(serializers.ModelSerializer):
    """Serializer for Attendance model"""
    student = UserSerializer(read_only=True)
    lecture = LectureSerializer(read_only=True)
    session = AttendanceSessionSerializer(read_only=True)
    
    class Meta:
        model = Attendance
        fields = ['id', 'student', 'lecture', 'session', 'timestamp', 
                 'blockchain_verified', 'transaction_hash']
        read_only_fields = ['id', 'timestamp', 'blockchain_verified', 'transaction_hash']