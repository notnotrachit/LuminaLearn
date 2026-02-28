from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication
    path('admin/signup/', views.AdminSignUpView.as_view(), name='admin_signup'),
    path('teacher/signup/', views.teacher_signup, name='teacher_signup'),
    path('student/signup/', views.StudentSignUpView.as_view(), name='student_signup'),

    # Password Reset (Issue #12)
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='attendance/password_reset_form.html',
             email_template_name='attendance/password_reset_email.html',
             subject_template_name='attendance/password_reset_subject.txt',
             success_url='/password-reset/done/'
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='attendance/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='attendance/password_reset_confirm.html',
             success_url='/password-reset-complete/'
         ),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='attendance/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    
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
] 