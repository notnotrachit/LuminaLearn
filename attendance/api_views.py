from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from .models import Course, Enrollment, Lecture, AttendanceSession, Attendance
from .serializers import (
    UserSerializer, CourseSerializer, CourseWriteSerializer,
    EnrollmentSerializer, LectureSerializer, LectureWriteSerializer,
    AttendanceSessionSerializer, AttendanceSerializer
)

User = get_user_model()

class IsTeacherOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow teachers to edit courses and lectures.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.is_teacher

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if hasattr(obj, 'teacher'):
            return obj.teacher == request.user
        if hasattr(obj, 'course'):
            return obj.course.teacher == request.user
        return obj.user == request.user

# User Views
class UserListAPIView(generics.ListAPIView):
    """List all users - read-only endpoint"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class UserDetailAPIView(generics.RetrieveAPIView):
    """Retrieve user details - read-only endpoint"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

# Course Views
class CourseListCreateAPIView(generics.ListCreateAPIView):
    """List courses (all users) and create courses (teachers only)"""
    queryset = Course.objects.all()
    permission_classes = [IsTeacherOrReadOnly]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CourseWriteSerializer
        return CourseSerializer
    
    def perform_create(self, serializer):
        serializer.save(teacher=self.request.user)

class CourseDetailUpdateAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve and update course details (teachers only for updates)"""
    queryset = Course.objects.all()
    permission_classes = [IsTeacherOrReadOnly, IsOwnerOrReadOnly]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return CourseWriteSerializer
        return CourseSerializer

# Enrollment Views
class EnrollmentListCreateAPIView(generics.ListCreateAPIView):
    """List enrollments and create new enrollments"""
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_teacher:
            return Enrollment.objects.filter(course__teacher=self.request.user)
        elif self.request.user.is_student:
            return Enrollment.objects.filter(student=self.request.user)
        return Enrollment.objects.all()
    
    def perform_create(self, serializer):
        if self.request.user.is_student:
            course_id = self.request.data.get('course_id')
            course = get_object_or_404(Course, id=course_id)
            roll_number = self.request.data.get('roll_number')
            serializer.save(student=self.request.user, course=course, roll_number=roll_number)
        else:
            return Response(
                {"detail": "Only students can enroll in courses."}, 
                status=status.HTTP_403_FORBIDDEN
            )

# Lecture Views
class LectureListCreateAPIView(generics.ListCreateAPIView):
    """List lectures and create new lectures (teachers only)"""
    permission_classes = [IsTeacherOrReadOnly]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LectureWriteSerializer
        return LectureSerializer
    
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_teacher:
            return Lecture.objects.filter(course__teacher=self.request.user)
        return Lecture.objects.all()
    
    def perform_create(self, serializer):
        course_id = self.request.data.get('course_id')
        course = get_object_or_404(Course, id=course_id, teacher=self.request.user)
        serializer.save(course=course)

class LectureDetailUpdateAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve and update lecture details (teachers only for updates)"""
    queryset = Lecture.objects.all()
    permission_classes = [IsTeacherOrReadOnly, IsOwnerOrReadOnly]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return LectureWriteSerializer
        return LectureSerializer

# Attendance Session Views
class AttendanceSessionListAPIView(generics.ListAPIView):
    """List attendance sessions"""
    serializer_class = AttendanceSessionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_teacher:
            return AttendanceSession.objects.filter(lecture__course__teacher=self.request.user)
        elif self.request.user.is_student:
            enrolled_courses = Enrollment.objects.filter(student=self.request.user).values_list('course', flat=True)
            return AttendanceSession.objects.filter(lecture__course__in=enrolled_courses)
        return AttendanceSession.objects.all()

# Attendance Views
class AttendanceListAPIView(generics.ListAPIView):
    """List attendance records"""
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_teacher:
            return Attendance.objects.filter(lecture__course__teacher=self.request.user)
        elif self.request.user.is_student:
            return Attendance.objects.filter(student=self.request.user)
        return Attendance.objects.all()

# API Status endpoint for testing authentication
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_status(request):
    """Simple authenticated endpoint to test JWT authentication"""
    return Response({
        'status': 'authenticated',
        'user': request.user.username,
        'user_type': 'admin' if request.user.is_admin else 'teacher' if request.user.is_teacher else 'student',
        'message': 'JWT authentication is working correctly'
    })