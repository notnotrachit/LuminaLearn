from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Course, Lecture, Enrollment, AttendanceSession, Attendance

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with selective field exposure"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'is_admin', 'is_teacher', 'is_student', 'stellar_public_key', 
                 'date_joined']
        read_only_fields = ['id', 'date_joined', 'stellar_public_key']
        extra_kwargs = {
            'stellar_seed': {'write_only': True}  # Never expose private key
        }


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course model"""
    teacher = UserSerializer(read_only=True)
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    enrollment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = ['id', 'name', 'code', 'teacher', 'teacher_name', 
                 'created_at', 'enrollment_count']
        read_only_fields = ['id', 'created_at', 'teacher']
        
    def get_enrollment_count(self, obj):
        return obj.enrollments.count()
        

class LectureSerializer(serializers.ModelSerializer):
    """Serializer for Lecture model"""
    course = CourseSerializer(read_only=True)
    course_id = serializers.IntegerField(write_only=True)
    attendance_count = serializers.SerializerMethodField()
    has_active_session = serializers.SerializerMethodField()
    
    class Meta:
        model = Lecture
        fields = ['id', 'title', 'date', 'start_time', 'end_time', 
                 'course', 'course_id', 'blockchain_lecture_id',
                 'attendance_count', 'has_active_session']
        read_only_fields = ['id', 'blockchain_lecture_id']
        
    def get_attendance_count(self, obj):
        return obj.attendances.count()
        
    def get_has_active_session(self, obj):
        return obj.sessions.filter(is_active=True).exists()


class EnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for Enrollment model"""
    student = UserSerializer(read_only=True)
    course = CourseSerializer(read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    
    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'course', 'roll_number', 'enrollment_date',
                 'student_name', 'course_name']
        read_only_fields = ['id', 'enrollment_date']


class AttendanceSessionSerializer(serializers.ModelSerializer):
    """Serializer for AttendanceSession model"""
    lecture = LectureSerializer(read_only=True) 
    lecture_id = serializers.IntegerField(write_only=True)
    attendance_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceSession
        fields = ['id', 'lecture', 'lecture_id', 'start_time', 'end_time', 
                 'nonce', 'is_active', 'blockchain_verified', 
                 'attendance_count', 'is_expired']
        read_only_fields = ['id', 'start_time', 'nonce', 'is_expired']
        
    def get_attendance_count(self, obj):
        return obj.attendances.count()


class AttendanceSerializer(serializers.ModelSerializer):
    """Serializer for Attendance model"""
    student = UserSerializer(read_only=True)
    lecture = LectureSerializer(read_only=True)
    session = AttendanceSessionSerializer(read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    lecture_title = serializers.CharField(source='lecture.title', read_only=True)
    course_name = serializers.CharField(source='lecture.course.name', read_only=True)
    
    class Meta:
        model = Attendance
        fields = ['id', 'student', 'lecture', 'session', 'timestamp',
                 'blockchain_verified', 'transaction_hash',
                 'student_name', 'lecture_title', 'course_name']
        read_only_fields = ['id', 'timestamp', 'student', 'blockchain_verified',
                          'transaction_hash']


class QRAttendanceSerializer(serializers.Serializer):
    """Serializer for QR code attendance marking"""
    qr_data = serializers.CharField(max_length=1000)
    
    def validate_qr_data(self, value):
        """Validate QR code data format"""
        if not value:
            raise serializers.ValidationError("QR data cannot be empty")
        return value


class AttendanceMarkSerializer(serializers.Serializer):
    """Serializer for manual attendance marking"""
    lecture_id = serializers.IntegerField()
    student_id = serializers.IntegerField(required=False)  # For manual marking by teachers
    
    def validate_lecture_id(self, value):
        """Validate that lecture exists"""
        try:
            Lecture.objects.get(id=value)
        except Lecture.DoesNotExist:
            raise serializers.ValidationError("Invalid lecture ID")
        return value
        
    def validate_student_id(self, value):
        """Validate that student exists and is a student"""
        if value:
            try:
                user = User.objects.get(id=value)
                if not user.is_student:
                    raise serializers.ValidationError("User is not a student")
            except User.DoesNotExist:
                raise serializers.ValidationError("Invalid student ID")
        return value