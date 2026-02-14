from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken import views as token_views
from . import api_views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'users', api_views.UserViewSet)
router.register(r'courses', api_views.CourseViewSet)
router.register(r'lectures', api_views.LectureViewSet)
router.register(r'attendance-sessions', api_views.AttendanceSessionViewSet)
router.register(r'attendances', api_views.AttendanceViewSet)

# API URL patterns
urlpatterns = [
    # DRF ViewSet routes
    path('', include(router.urls)),
    
    # Authentication
    path('auth/token/', api_views.CustomAuthToken.as_view(), name='api_token_auth'),
    
    # Attendance actions
    path('attendance/mark-qr/', api_views.mark_attendance_qr, name='api_mark_attendance_qr'),
    path('attendance/mark-manual/', api_views.mark_attendance_manual, name='api_mark_attendance_manual'),
    
    # System status
    path('blockchain/status/', api_views.blockchain_status, name='api_blockchain_status'),
    path('stats/', api_views.api_stats, name='api_stats'),
    
    # DRF browsable API
    path('auth/', include('rest_framework.urls')),
]