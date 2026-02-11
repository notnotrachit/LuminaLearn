from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('admin/signup/', views.AdminSignUpView.as_view(), name='admin_signup'),
    path('teacher/signup/', views.teacher_signup, name='teacher_signup'),
    path('student/signup/', views.StudentSignUpView.as_view(), name='student_signup'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Course Management
    path('courses/', views.course_list, name='course_list'),
    path('courses/create/', views.create_course, name='create_course'),
    path('courses/<int:pk>/', views.course_detail, name='course_detail'),
    
    # Lecture and Attendance
    path('lectures/<int:pk>/', views.lecture_detail, name='lecture_detail'),
    path('attendance/scan/', views.scan_attendance, name='scan_attendance'),
    path('attendance/process/', views.process_attendance, name='process_attendance'),
    path('attendance/sessions/<int:session_id>/close/', views.close_attendance_session, name='close_attendance_session'),
    path('attendance/manual/<int:lecture_id>/', views.manual_attendance, name='manual_attendance'),
    
    # User Management
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('students/', views.student_list, name='student_list'),
    
    # Add the blockchain connection check URL
    path('blockchain/status/', views.check_blockchain_connection, name='blockchain_status'),
    
    # Add blockchain statistics URL
    path('blockchain/statistics/', views.blockchain_statistics, name='blockchain_statistics'),
    
    # Cache monitoring (admin only)
    path('admin/cache-stats/', views.cache_stats, name='cache_stats'),
] 