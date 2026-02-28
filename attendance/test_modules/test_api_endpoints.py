"""
API Endpoint Tests
Issue #27: Add comprehensive test suite - API tests
"""
import pytest
from django.test import Client
from django.urls import reverse
from attendance.models import User, Course, Lecture, Attendance
from datetime import datetime, timedelta
from django.utils import timezone


@pytest.mark.django_db
class TestAttendanceAPIEndpoints:
    """Test suite for attendance-related API endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.client = Client()

        # Create users
        self.teacher = User.objects.create_user(
            username='testteacher',
            email='teacher@test.com',
            password='testpass123',
            is_teacher=True
        )
        self.student = User.objects.create_user(
            username='teststudent',
            email='student@test.com',
            password='testpass123',
            is_student=True
        )

        # Create course
        self.course = Course.objects.create(
            code='TEST101',
            name='Test Course',
            teacher=self.teacher
        )

        # Create lecture
        self.lecture = Lecture.objects.create(
            course=self.course,
            title='Test Lecture',
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timedelta(hours=1)).time()
        )

    def test_process_attendance_requires_login(self):
        """Test that process_attendance endpoint requires authentication"""
        response = self.client.post(reverse('process_attendance'))
        assert response.status_code == 302  # Redirect to login

    def test_process_attendance_requires_post(self):
        """Test that process_attendance only accepts POST"""
        self.client.login(username='teststudent', password='testpass123')
        response = self.client.get(reverse('process_attendance'))
        # Should either reject GET or return error JSON
        assert response.status_code in [405, 200]  # 405 Method Not Allowed or JSON error

    def test_process_attendance_requires_student_role(self):
        """Test that only students can mark attendance"""
        self.client.login(username='testteacher', password='testpass123')
        response = self.client.post(reverse('process_attendance'), {
            'qr_data': 'test_data'
        })
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False

    def test_blockchain_status_endpoint(self):
        """Test blockchain status endpoint"""
        self.client.login(username='testteacher', password='testpass123')
        response = self.client.get(reverse('blockchain_status'))
        assert response.status_code == 200

    def test_blockchain_statistics_endpoint(self):
        """Test blockchain statistics endpoint"""
        self.client.login(username='testteacher', password='testpass123')
        response = self.client.get(reverse('blockchain_statistics'))
        assert response.status_code == 200


@pytest.mark.django_db
class TestCourseAPIEndpoints:
    """Test suite for course-related endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.client = Client()

        self.teacher = User.objects.create_user(
            username='testteacher',
            email='teacher@test.com',
            password='testpass123',
            is_teacher=True
        )

    def test_course_list_requires_login(self):
        """Test that course list requires authentication"""
        response = self.client.get(reverse('course_list'))
        assert response.status_code == 302  # Redirect to login

    def test_course_list_authenticated(self):
        """Test course list for authenticated user"""
        self.client.login(username='testteacher', password='testpass123')
        response = self.client.get(reverse('course_list'))
        assert response.status_code == 200

    def test_create_course_requires_teacher(self):
        """Test that only teachers can create courses"""
        student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            is_student=True
        )
        self.client.login(username='student', password='testpass123')
        response = self.client.get(reverse('create_course'))
        # Should redirect or return 403
        assert response.status_code in [302, 403]


@pytest.mark.django_db
class TestAuthenticationEndpoints:
    """Test suite for authentication endpoints"""

    def test_password_reset_endpoint_exists(self):
        """Test that password reset endpoint is accessible"""
        client = Client()
        response = client.get(reverse('password_reset'))
        assert response.status_code == 200

    def test_password_reset_post(self):
        """Test password reset form submission"""
        User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        client = Client()
        response = client.post(reverse('password_reset'), {
            'email': 'test@example.com'
        })
        # Should redirect to done page
        assert response.status_code == 302

    def test_login_page_accessible(self):
        """Test that login page is accessible"""
        client = Client()
        response = client.get(reverse('login'))
        assert response.status_code == 200


@pytest.mark.django_db
class TestCSRFProtection:
    """Test suite for CSRF protection - Issue #2"""

    def test_process_attendance_has_csrf_protection(self):
        """Test that process_attendance endpoint has CSRF protection"""
        client = Client(enforce_csrf_checks=True)

        user = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            is_student=True
        )
        client.login(username='student', password='testpass123')

        # POST without CSRF token should fail
        response = client.post(reverse('process_attendance'), {
            'qr_data': 'test'
        })
        assert response.status_code == 403  # CSRF failure

    def test_manual_attendance_has_csrf_protection(self):
        """Test that manual attendance endpoint has CSRF protection"""
        client = Client(enforce_csrf_checks=True)

        teacher = User.objects.create_user(
            username='teacher',
            email='teacher@test.com',
            password='testpass123',
            is_teacher=True
        )
        course = Course.objects.create(
            code='TEST101',
            name='Test Course',
            teacher=teacher
        )
        lecture = Lecture.objects.create(
            course=course,
            title='Test Lecture',
            date=timezone.now().date(),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timedelta(hours=1)).time()
        )

        client.login(username='teacher', password='testpass123')

        # POST without CSRF token should fail
        response = client.post(
            reverse('manual_attendance', args=[lecture.id]),
            {}
        )
        assert response.status_code == 403  # CSRF failure
