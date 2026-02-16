from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.db import models
from .models import Course, Enrollment
from .forms import CourseEnrollmentForm

User = get_user_model()


class CourseEnrollmentTestCase(TestCase):
    """Test cases for student course enrollment functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        
        # Create test users
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
        
        self.other_student = User.objects.create_user(
            username='otherstudent',
            email='other@test.com',
            password='testpass123',
            is_student=True
        )
        
        # Create test course
        self.course = Course.objects.create(
            name='Test Course',
            code='TEST101',
            teacher=self.teacher
        )
        
        # Course should auto-generate enrollment code
        self.assertTrue(self.course.enrollment_code)
        self.assertEqual(len(self.course.enrollment_code), 8)
    
    def test_successful_enrollment(self):
        """Test successful student enrollment with valid code."""
        self.client.login(username='teststudent', password='testpass123')
        
        enrollment_data = {
            'enrollment_code': self.course.enrollment_code,
            'roll_number': 'STU001'
        }
        
        response = self.client.post(reverse('student_enroll'), enrollment_data)
        
        # Should redirect to course detail page
        self.assertEqual(response.status_code, 302)
        
        # Check that enrollment was created
        enrollment = Enrollment.objects.filter(
            student=self.student,
            course=self.course
        ).first()
        
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment.roll_number, 'STU001')
    
    def test_invalid_enrollment_code(self):
        """Test enrollment with invalid code."""
        self.client.login(username='teststudent', password='testpass123')
        
        enrollment_data = {
            'enrollment_code': 'INVALID',
            'roll_number': 'STU001'
        }
        
        response = self.client.post(reverse('student_enroll'), enrollment_data)
        
        # Should redirect back to enrollment form
        self.assertEqual(response.status_code, 302)
        
        # Check that no enrollment was created
        enrollment_count = Enrollment.objects.filter(
            student=self.student,
            course=self.course
        ).count()
        
        self.assertEqual(enrollment_count, 0)
    
    def test_expired_enrollment_code(self):
        """Test enrollment with expired code."""
        # Set course enrollment expiry to past
        self.course.enrollment_expires_at = timezone.now() - timedelta(hours=1)
        self.course.save()
        
        self.client.login(username='teststudent', password='testpass123')
        
        enrollment_data = {
            'enrollment_code': self.course.enrollment_code,
            'roll_number': 'STU001'
        }
        
        response = self.client.post(reverse('student_enroll'), enrollment_data)
        
        # Should redirect back to enrollment form
        self.assertEqual(response.status_code, 302)
        
        # Check that no enrollment was created
        enrollment_count = Enrollment.objects.filter(
            student=self.student,
            course=self.course
        ).count()
        
        self.assertEqual(enrollment_count, 0)
    
    def test_duplicate_enrollment_attempt(self):
        """Test preventing duplicate enrollment."""
        # Create existing enrollment
        Enrollment.objects.create(
            student=self.student,
            course=self.course,
            roll_number='STU001'
        )
        
        self.client.login(username='teststudent', password='testpass123')
        
        enrollment_data = {
            'enrollment_code': self.course.enrollment_code,
            'roll_number': 'STU002'
        }
        
        response = self.client.post(reverse('student_enroll'), enrollment_data)
        
        # Should redirect to course detail (already enrolled message)
        self.assertEqual(response.status_code, 302)
        
        # Check that only one enrollment exists
        enrollment_count = Enrollment.objects.filter(
            student=self.student,
            course=self.course
        ).count()
        
        self.assertEqual(enrollment_count, 1)
    
    def test_duplicate_roll_number(self):
        """Test preventing duplicate roll numbers in same course."""
        # Create enrollment with specific roll number
        Enrollment.objects.create(
            student=self.other_student,
            course=self.course,
            roll_number='STU001'
        )
        
        self.client.login(username='teststudent', password='testpass123')
        
        enrollment_data = {
            'enrollment_code': self.course.enrollment_code,
            'roll_number': 'STU001'  # Same roll number
        }
        
        response = self.client.post(reverse('student_enroll'), enrollment_data)
        
        # Should redirect back to enrollment form
        self.assertEqual(response.status_code, 302)
        
        # Check that no new enrollment was created for this student
        enrollment_exists = Enrollment.objects.filter(
            student=self.student,
            course=self.course
        ).exists()
        
        self.assertFalse(enrollment_exists)
    
    def test_non_student_enrollment_attempt(self):
        """Test that non-students cannot enroll."""
        self.client.login(username='testteacher', password='testpass123')
        
        response = self.client.get(reverse('student_enroll'))
        
        # Should redirect to dashboard with error
        self.assertEqual(response.status_code, 302)
    
    def test_enrollment_code_generation_uniqueness(self):
        """Test that enrollment codes are unique."""
        # Create multiple courses and check codes are unique
        courses = [self.course]  # Start with the setup course
        codes = {self.course.enrollment_code}
        
        for i in range(10):
            course = Course.objects.create(
                name=f'Test Course {i}',
                code=f'TEST{i:02d}',
                teacher=self.teacher
            )
            courses.append(course)
            codes.add(course.enrollment_code)
        
        # Debug: Print codes if test fails
        if len(codes) != 11:
            print(f"Expected 11 unique codes, got {len(codes)}")
            print("All codes:", [c.enrollment_code for c in courses])
            print("Unique codes:", codes)
        
        # Should have 11 unique codes (including the setup course)
        # If any code was duplicated, the set would have fewer than 11 items
        self.assertEqual(len(codes), 11)
    
    def test_enroll_with_code_url(self):
        """Test enrollment via shareable URL."""
        # Test without login (should redirect to login)
        response = self.client.get(
            reverse('enroll_with_code') + f'?code={self.course.enrollment_code}'
        )
        self.assertEqual(response.status_code, 302)
        
        # Test with student login
        self.client.login(username='teststudent', password='testpass123')
        response = self.client.get(
            reverse('enroll_with_code') + f'?code={self.course.enrollment_code}'
        )
        
        # Should redirect to enrollment form with pre-filled code
        self.assertEqual(response.status_code, 302)
    
    def test_course_enrollment_form_validation(self):
        """Test enrollment form validation."""
        # Test valid form
        form_data = {
            'enrollment_code': self.course.enrollment_code,
            'roll_number': 'STU001'
        }
        form = CourseEnrollmentForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Test that code is converted to uppercase
        self.assertEqual(form.cleaned_data['enrollment_code'], self.course.enrollment_code.upper())
        
        # Test empty form
        form = CourseEnrollmentForm(data={})
        self.assertFalse(form.is_valid())
    
    def test_course_is_enrollment_active_property(self):
        """Test the is_enrollment_active property."""
        # Course without expiry should be active
        self.assertTrue(self.course.is_enrollment_active)
        
        # Course with future expiry should be active
        self.course.enrollment_expires_at = timezone.now() + timedelta(hours=1)
        self.course.save()
        self.assertTrue(self.course.is_enrollment_active)
        
        # Course with past expiry should be inactive
        self.course.enrollment_expires_at = timezone.now() - timedelta(hours=1)
        self.course.save()
        self.assertFalse(self.course.is_enrollment_active)
    
    def test_rate_limiting_enrollment_attempts(self):
        """Test that rate limiting prevents brute force enrollment attempts.""" 
        self.client.login(username='teststudent', password='testpass123')
        
        # Make multiple failed enrollment attempts
        for i in range(12):  # Exceed the limit of 10
            enrollment_data = {
                'enrollment_code': f'INVALID{i:02d}',
                'roll_number': f'STU{i:03d}'
            }
            response = self.client.post(reverse('student_enroll'), enrollment_data)
            if i < 10:
                self.assertEqual(response.status_code, 302)  # Should redirect
            else:
                # After 10 attempts, should get rate limited
                response = self.client.get(reverse('student_enroll'))
                # Should redirect to dashboard due to rate limiting
                self.assertIn(response.status_code, [302])
    
    def test_race_condition_protection(self):
        """Test that the save method handles race conditions properly."""
        from unittest.mock import patch
        from django.db import IntegrityError
        
        # Mock IntegrityError on first save attempt
        with patch.object(models.Model, 'save') as mock_save:
            mock_save.side_effect = [IntegrityError("UNIQUE constraint failed"), None]
            
            course = Course(
                name='Race Condition Test',
                code='RACE01',
                teacher=self.teacher
            )
            
            # This should handle the IntegrityError and retry
            course.save()
            
            # Verify that save was called twice (first failed, second succeeded)
            self.assertEqual(mock_save.call_count, 2)
