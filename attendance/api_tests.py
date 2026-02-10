from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import date, time
from .models import Course, Enrollment, Lecture, AttendanceSession, Attendance

User = get_user_model()

class JWTAuthenticationTestCase(APITestCase):
    """Test JWT authentication functionality"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin', 
            email='admin@test.com',
            password='testpass123',
            is_admin=True
        )
        self.teacher_user = User.objects.create_user(
            username='teacher', 
            email='teacher@test.com',
            password='testpass123',
            is_teacher=True
        )
        self.student_user = User.objects.create_user(
            username='student', 
            email='student@test.com',
            password='testpass123',
            is_student=True
        )
        
    def test_obtain_jwt_token_valid_credentials(self):
        """Test JWT token can be obtained with valid credentials"""
        url = reverse('token_obtain_pair')
        data = {
            'username': 'teacher',
            'password': 'testpass123'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
    
    def test_obtain_jwt_token_invalid_credentials(self):
        """Test JWT token is not provided with invalid credentials"""
        url = reverse('token_obtain_pair')
        data = {
            'username': 'teacher',
            'password': 'wrongpassword'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('access', response.data)
    
    def test_refresh_jwt_token(self):
        """Test JWT token refresh functionality"""
        # First get tokens
        url = reverse('token_obtain_pair')
        data = {
            'username': 'teacher',
            'password': 'testpass123'
        }
        response = self.client.post(url, data, format='json')
        refresh_token = response.data['refresh']
        
        # Now refresh
        url = reverse('token_refresh')
        data = {'refresh': refresh_token}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_protected_endpoint_without_token(self):
        """Test that protected endpoints reject requests without tokens"""
        url = reverse('api_status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_protected_endpoint_with_valid_token(self):
        """Test that protected endpoints accept requests with valid tokens"""
        # Get token
        refresh = RefreshToken.for_user(self.teacher_user)
        access_token = str(refresh.access_token)
        
        # Use token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user'], 'teacher')
        self.assertEqual(response.data['user_type'], 'teacher')
    
    def test_protected_endpoint_with_invalid_token(self):
        """Test that protected endpoints reject requests with invalid tokens"""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token')
        url = reverse('api_status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

class CourseAPITestCase(APITestCase):
    """Test Course API endpoints with JWT authentication"""
    
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            username='teacher', 
            email='teacher@test.com',
            password='testpass123',
            is_teacher=True
        )
        self.student_user = User.objects.create_user(
            username='student', 
            email='student@test.com',
            password='testpass123',
            is_student=True
        )
        self.course = Course.objects.create(
            name='Test Course',
            code='TEST101',
            teacher=self.teacher_user
        )
    
    def test_list_courses_unauthenticated(self):
        """Test that unauthenticated users can list courses (read-only)"""
        url = reverse('api_course_list_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_create_course_unauthenticated(self):
        """Test that unauthenticated users cannot create courses"""
        url = reverse('api_course_list_create')
        data = {
            'name': 'New Course',
            'code': 'NEW101'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_course_as_student(self):
        """Test that students cannot create courses"""
        refresh = RefreshToken.for_user(self.student_user)
        access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        url = reverse('api_course_list_create')
        data = {
            'name': 'New Course',
            'code': 'NEW101'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_create_course_as_teacher(self):
        """Test that teachers can create courses"""
        refresh = RefreshToken.for_user(self.teacher_user)
        access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        url = reverse('api_course_list_create')
        data = {
            'name': 'New Course',
            'code': 'NEW101'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Course')
        self.assertEqual(response.data['code'], 'NEW101')
    
    def test_update_course_as_owner(self):
        """Test that course owner can update course"""
        refresh = RefreshToken.for_user(self.teacher_user)
        access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        url = reverse('api_course_detail_update', kwargs={'pk': self.course.pk})
        data = {
            'name': 'Updated Course Name'
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class LectureAPITestCase(APITestCase):
    """Test Lecture API endpoints with JWT authentication"""
    
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            username='teacher', 
            email='teacher@test.com',
            password='testpass123',
            is_teacher=True
        )
        self.other_teacher = User.objects.create_user(
            username='other_teacher', 
            email='other@test.com',
            password='testpass123',
            is_teacher=True
        )
        self.course = Course.objects.create(
            name='Test Course',
            code='TEST101',
            teacher=self.teacher_user
        )
        self.lecture = Lecture.objects.create(
            course=self.course,
            title='Test Lecture',
            date=date.today(),
            start_time=time(10, 0),
            end_time=time(11, 0)
        )
    
    def test_create_lecture_as_course_owner(self):
        """Test that course owner can create lectures"""
        refresh = RefreshToken.for_user(self.teacher_user)
        access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        url = reverse('api_lecture_list_create')
        data = {
            'course_id': self.course.id,
            'title': 'New Lecture',
            'date': '2026-02-15',
            'start_time': '14:00:00',
            'end_time': '15:00:00'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_create_lecture_as_non_owner(self):
        """Test that non-owner teachers cannot create lectures for other's courses"""
        refresh = RefreshToken.for_user(self.other_teacher)
        access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        url = reverse('api_lecture_list_create')
        data = {
            'course_id': self.course.id,
            'title': 'New Lecture',
            'date': '2026-02-15',
            'start_time': '14:00:00',
            'end_time': '15:00:00'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class UserAPITestCase(APITestCase):
    """Test User API endpoints (read-only)"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', 
            email='test@test.com',
            password='testpass123'
        )
    
    def test_list_users_read_only(self):
        """Test that users list is read-only and accessible without auth"""
        url = reverse('api_user_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_user_detail_read_only(self):
        """Test that user detail is read-only and accessible without auth"""
        url = reverse('api_user_detail', kwargs={'pk': self.user.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')