#!/usr/bin/env python
"""
Password Reset Functionality Test Script
Run this after starting the Django development server to verify functionality.
"""

import os
import sys
import django
import subprocess
import time
from pathlib import Path

# Add the project directory to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_system.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()

def test_password_reset_functionality():
    """
    Test the password reset functionality
    """
    print("Testing Password Reset Functionality\n")
    print("=" * 50)
    
    # Create a test client
    client = Client()
    
    # Test 1: Check if password reset form loads
    print("1. Testing password reset form access...")
    response = client.get(reverse('password_reset'))
    if response.status_code == 200:
        print("   ✓ Password reset form loads successfully")
    else:
        print(f"   ✗ Password reset form failed to load (status: {response.status_code})")
    
    # Test 2: Check if login page has forgot password link
    print("\n2. Testing login page forgot password link...")
    response = client.get(reverse('login'))
    if 'password_reset' in response.content.decode():
        print("   ✓ Login page contains forgot password link")
    else:
        print("   ✗ Login page missing forgot password link")
    
    # Test 3: Test password reset submission with invalid email
    print("\n3. Testing password reset with invalid email...")
    response = client.post(reverse('password_reset'), {
        'email': 'nonexistent@test.com'
    })
    if response.status_code == 302:  # Should redirect to done page
        print("   ✓ Password reset form handles invalid email correctly")
    else:
        print(f"   ✗ Unexpected response for invalid email (status: {response.status_code})")
    
    # Test 4: Create a test user and test with valid email
    print("\n4. Testing password reset with valid email...")
    test_user = User.objects.create_user(
        username='testuser',
        email='testuser@test.com',
        password='testpass123'
    )
    
    response = client.post(reverse('password_reset'), {
        'email': 'testuser@test.com'
    })
    if response.status_code == 302:
        print("   ✓ Password reset form processes valid email correctly")
    else:
        print(f"   ✗ Unexpected response for valid email (status: {response.status_code})")
    
    # Test 5: Test rate limiting
    print("\n5. Testing rate limiting...")
    attempts = 0
    for i in range(7):  # Try to exceed the rate limit
        response = client.post(reverse('password_reset'), {
            'email': 'testuser@test.com'
        })
        attempts += 1
        if response.status_code != 302:
            print(f"   ✓ Rate limiting activated after {attempts} attempts")
            break
    else:
        print("   ⚠ Rate limiting may not be working (completed 7 attempts)")
    
    # Clean up test user
    test_user.delete()
    
    print("\n" + "=" * 50)
    print("Password Reset Test Complete!")
    print("\nNext steps:")
    print("1. Start the Django development server: python manage.py runserver")
    print("2. Visit http://127.0.0.1:8000/login/")
    print("3. Click 'Forgot your password?' link")
    print("4. Test with a real user account")
    print("5. Check console output for password reset emails")

def check_django_server():
    """Check if Django development server is running"""
    try:
        import requests
        response = requests.get('http://127.0.0.1:8000/', timeout=2)
        return True
    except:
        return False

def main():
    print("LuminaLearn Password Reset Test Suite")
    print("===================================\n")
    
    # Check if server is running
    if check_django_server():
        print("✓ Django development server is running")
    else:
        print("⚠ Django development server not detected")
        print("  Start it with: python manage.py runserver")
    
    print("\nRunning functionality tests...")
    test_password_reset_functionality()
    
    print("\nManual testing checklist:")
    print("□ Password reset form renders correctly")
    print("□ Email is sent when valid user submits reset request") 
    print("□ Invalid emails don't reveal account existence")
    print("□ Reset token validation works")
    print("□ Password update succeeds")
    print("□ Rate limiting prevents abuse")
    print("□ Server runs without configuration errors")

if __name__ == "__main__":
    main()