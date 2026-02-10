#!/usr/bin/env python
"""
Test script to create sample data for DRF API testing
"""
import os
import sys
import django

# Add the Django project directory to the Python path
sys.path.append('c:/Users/ABHINAV KUMAR/Desktop/LuminaLearn')

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_system.settings')
django.setup()

from attendance.models import User, Course, Lecture, Enrollment, AttendanceSession
from rest_framework.authtoken.models import Token
from django.utils import timezone
from datetime import datetime, time, timedelta

def create_test_data():
    print("Creating test data...")
    
    # Create test admin user
    admin, created = User.objects.get_or_create(
        username='admin_test',
        defaults={
            'email': 'admin@test.com',
            'first_name': 'Admin',
            'last_name': 'User',
            'is_admin': True,
            'is_staff': True,
            'is_superuser': True,
        }
    )
    if created:
        admin.set_password('testpass123')
        admin.save()
        print("✓ Created admin user")
    else:
        print("✓ Admin user already exists")
    
    # Create auth token for admin
    token, created = Token.objects.get_or_create(user=admin)
    print(f"✓ Admin token: {token.key}")
    
    # Create test teacher
    teacher, created = User.objects.get_or_create(
        username='teacher_test',
        defaults={
            'email': 'teacher@test.com',
            'first_name': 'Teacher',
            'last_name': 'User',
            'is_teacher': True,
            'stellar_public_key': 'GTEST123TEACHER456789',
            'stellar_seed': 'STEST123TEACHER456789',
        }
    )
    if created:
        teacher.set_password('testpass123')
        teacher.save()
        print("✓ Created teacher user")
    else:
        print("✓ Teacher user already exists")
    
    # Create auth token for teacher
    token, created = Token.objects.get_or_create(user=teacher)
    print(f"✓ Teacher token: {token.key}")
    
    # Create test student
    student, created = User.objects.get_or_create(
        username='student_test',
        defaults={
            'email': 'student@test.com',
            'first_name': 'Student',
            'last_name': 'User',
            'is_student': True,
            'stellar_public_key': 'GTEST123STUDENT456789',
            'stellar_seed': 'STEST123STUDENT456789',
        }
    )
    if created:
        student.set_password('testpass123')
        student.save()
        print("✓ Created student user")
    else:
        print("✓ Student user already exists")
    
    # Create auth token for student
    token, created = Token.objects.get_or_create(user=student)
    print(f"✓ Student token: {token.key}")
    
    # Create test course
    course, created = Course.objects.get_or_create(
        code='CS101',
        defaults={
            'name': 'Introduction to Computer Science',
            'teacher': teacher,
        }
    )
    if created:
        print("✓ Created test course")
    else:
        print("✓ Test course already exists")
    
    # Enroll student in course
    enrollment, created = Enrollment.objects.get_or_create(
        student=student,
        course=course,
        defaults={'roll_number': 'ST001'}
    )
    if created:
        print("✓ Enrolled student in course")
    else:
        print("✓ Student already enrolled")
    
    # Create test lecture
    lecture, created = Lecture.objects.get_or_create(
        course=course,
        title='Introduction to Programming',
        defaults={
            'date': timezone.now().date(),
            'start_time': time(10, 0),
            'end_time': time(11, 30),
        }
    )
    if created:
        print("✓ Created test lecture")
    else:
        print("✓ Test lecture already exists")
    
    print("\n" + "="*50)
    print("TEST DATA SUMMARY:")
    print("="*50)
    print(f"Admin: admin_test / testpass123")
    print(f"Teacher: teacher_test / testpass123") 
    print(f"Student: student_test / testpass123")
    print(f"Course: {course.code} - {course.name}")
    print(f"Lecture: {lecture.title}")
    print("="*50)
    
    return {
        'admin': admin,
        'teacher': teacher,
        'student': student,
        'course': course,
        'lecture': lecture
    }

if __name__ == '__main__':
    try:
        data = create_test_data()
        print("\n✅ Test data creation completed successfully!")
    except Exception as e:
        print(f"\n❌ Error creating test data: {e}")
        import traceback
        traceback.print_exc()