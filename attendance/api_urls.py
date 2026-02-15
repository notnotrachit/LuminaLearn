from django.urls import path
from . import api_views

urlpatterns = [
    # API status endpoint for testing authentication
    path('status/', api_views.api_status, name='api_status'),
    
    # User endpoints (read-only)
    path('users/', api_views.UserListAPIView.as_view(), name='api_user_list'),
    path('users/<int:pk>/', api_views.UserDetailAPIView.as_view(), name='api_user_detail'),
    
    # Course endpoints
    path('courses/', api_views.CourseListCreateAPIView.as_view(), name='api_course_list_create'),
    path('courses/<int:pk>/', api_views.CourseDetailUpdateAPIView.as_view(), name='api_course_detail_update'),
    
    # Enrollment endpoints  
    path('enrollments/', api_views.EnrollmentListCreateAPIView.as_view(), name='api_enrollment_list_create'),
    
    # Lecture endpoints
    path('lectures/', api_views.LectureListCreateAPIView.as_view(), name='api_lecture_list_create'),
    path('lectures/<int:pk>/', api_views.LectureDetailUpdateAPIView.as_view(), name='api_lecture_detail_update'),
    
    # Attendance session endpoints
    path('attendance-sessions/', api_views.AttendanceSessionListAPIView.as_view(), name='api_attendance_session_list'),
    
    # Attendance endpoints
    path('attendances/', api_views.AttendanceListAPIView.as_view(), name='api_attendance_list'),
]