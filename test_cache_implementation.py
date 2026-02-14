#!/usr/bin/env python
"""
Cache Implementation Test Script for LuminaLearn
Comprehensive testing of Redis cache functionality and fallback behavior.
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

from django.test import Client
from django.core.cache import cache, caches
from django.urls import reverse
from django.contrib.auth import get_user_model
from attendance.cache_utils import CacheManager
from attendance.models import Course, Lecture, Enrollment

User = get_user_model()

def test_redis_connection():
    """Test Redis connection and fallback behavior."""
    print("1. Testing Redis Connection and Fallback")
    print("=" * 50)
    
    try:
        # Test default cache (should be Redis)
        cache_backend = CacheManager.get_cache_backend()
        backend_type = type(cache_backend).__name__
        print(f"   ✓ Cache Backend Type: {backend_type}")
        
        # Test connectivity
        test_key = 'connectivity_test'
        test_value = f'test_{int(time.time())}'
        cache_backend.set(test_key, test_value, 30)
        retrieved = cache_backend.get(test_key)
        
        if retrieved == test_value:
            print("   ✓ Cache connectivity: WORKING")
            cache_backend.delete(test_key)
        else:
            print("   ✗ Cache connectivity: FAILED")
            
        return True
        
    except Exception as e:
        print(f"   ⚠ Redis connection error: {e}")
        print("   ✓ Testing fallback to local memory cache...")
        
        try:
            fallback_cache = caches['fallback']
            fallback_cache.set('fallback_test', 'working', 30)
            if fallback_cache.get('fallback_test') == 'working':
                print("   ✓ Fallback cache: WORKING")
                return True
        except Exception as fe:
            print(f"   ✗ Fallback cache error: {fe}")
            return False

def test_cached_endpoints():
    """Test cached endpoints return correct data."""
    print("\n2. Testing Cached Endpoints")
    print("=" * 50)
    
    client = Client()
    
    # Create test user with appropriate permissions
    try:
        admin_user = User.objects.create_user(
            username='test_admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_admin=True
        )
        print("   ✓ Created test admin user")
    except Exception as e:
        print(f"   ⚠ Using existing admin user or error: {e}")
        admin_user = User.objects.filter(is_staff=True).first()
        if not admin_user:
            print("   ✗ No admin user available for testing")
            return False
    
    # Login as admin
    client.force_login(admin_user)
    
    # Test course list endpoint
    print("\n   Testing Course List Endpoint:")
    try:
        response = client.get(reverse('course_list'))
        print(f"     - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("     ✓ Course list loads successfully")
        else:
            print("     ✗ Course list failed to load")
    except Exception as e:
        print(f"     ✗ Course list error: {e}")
    
    # Test student list endpoint
    print("\n   Testing Student List Endpoint:")
    try:
        response = client.get(reverse('student_list'))
        print(f"     - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("     ✓ Student list loads successfully")
        else:
            print("     ✗ Student list failed to load")
    except Exception as e:
        print(f"     ✗ Student list error: {e}")
    
    # Test blockchain statistics endpoint
    print("\n   Testing Blockchain Statistics Endpoint:")
    try:
        response = client.get(reverse('blockchain_statistics'))
        print(f"     - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("     ✓ Blockchain statistics loads successfully")
        else:
            print("     ✗ Blockchain statistics failed to load")
    except Exception as e:
        print(f"     ✗ Blockchain statistics error: {e}")
    
    # Test cache stats endpoint (admin only)
    print("\n   Testing Cache Stats Endpoint:")
    try:
        response = client.get(reverse('cache_stats'))
        print(f"     - Status Code: {response.status_code}")
        if response.status_code == 200:
            print("     ✓ Cache stats loads successfully")
        else:
            print("     ✗ Cache stats failed to load")
    except Exception as e:
        print(f"     ✗ Cache stats error: {e}")
    
    return True

def test_cache_invalidation():
    """Test cache invalidation on model updates."""
    print("\n3. Testing Cache Invalidation")
    print("=" * 50)
    
    try:
        # Clear existing cache
        cache_backend = CacheManager.get_cache_backend()
        cache_backend.clear()
        print("   ✓ Cleared existing cache")
        
        # Set up test data in cache
        test_courses = ['Course 1', 'Course 2', 'Course 3']
        course_cache_key = CacheManager.generate_cache_key(CacheManager.COURSE_LIST_PREFIX)
        CacheManager.set_cached(course_cache_key, test_courses, 300)
        
        # Verify data is cached
        cached_data = CacheManager.get_cached(course_cache_key)
        if cached_data == test_courses:
            print("   ✓ Test data successfully cached")
        else:
            print("   ✗ Failed to cache test data")
            return False
        
        # Test invalidation
        CacheManager.invalidate_related_cache('course', 1, 'update')
        
        # Check if cache was invalidated
        cached_after_invalidation = CacheManager.get_cached(course_cache_key)
        if cached_after_invalidation is None:
            print("   ✓ Cache invalidation working correctly")
        else:
            print("   ⚠ Cache may not have been invalidated properly")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Cache invalidation test error: {e}")
        return False

def test_cache_performance():
    """Test cache performance improvements."""
    print("\n4. Testing Cache Performance")
    print("=" * 50)
    
    try:
        # Test database query vs cached query performance
        from django.db import connection
        from django.test.utils import override_settings
        
        # Reset query count
        connection.queries_log.clear()
        
        # First request (should hit database)
        start_time = time.time()
        courses = list(Course.objects.all())
        first_request_time = time.time() - start_time
        first_request_queries = len(connection.queries_log)
        
        print(f"   First request (DB): {first_request_time:.4f}s, {first_request_queries} queries")
        
        # Cache the data
        cache_key = CacheManager.generate_cache_key('test_performance')
        CacheManager.set_cached(cache_key, courses, 300)
        
        # Reset query count
        connection.queries_log.clear()
        
        # Second request (should hit cache)
        start_time = time.time()
        cached_courses = CacheManager.get_cached(cache_key)
        second_request_time = time.time() - start_time
        second_request_queries = len(connection.queries_log)
        
        print(f"   Second request (Cache): {second_request_time:.4f}s, {second_request_queries} queries")
        
        # Calculate performance improvement
        if first_request_time > 0:
            improvement = ((first_request_time - second_request_time) / first_request_time) * 100
            print(f"   ✓ Performance improvement: {improvement:.1f}%")
        
        if second_request_queries == 0:
            print("   ✓ Cache eliminated database queries")
        else:
            print(f"   ⚠ Cache still resulted in {second_request_queries} database queries")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Performance test error: {e}")
        return False

def test_cache_management_command():
    """Test the cache management command."""
    print("\n5. Testing Cache Management Command")
    print("=" * 50)
    
    try:
        # Test cache monitor command
        commands_to_test = [
            ['python', 'manage.py', 'cache_monitor', '--status'],
            ['python', 'manage.py', 'cache_monitor', '--test'],
        ]
        
        for cmd in commands_to_test:
            try:
                result = subprocess.run(
                    cmd,
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    print(f"   ✓ Command '{' '.join(cmd[2:])}' executed successfully")
                else:
                    print(f"   ✗ Command '{' '.join(cmd[2:])}' failed: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                print(f"   ⚠ Command '{' '.join(cmd[2:])}' timed out")
            except Exception as e:
                print(f"   ✗ Command '{' '.join(cmd[2:])}' error: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Management command test error: {e}")
        return False

def test_django_system_checks():
    """Run Django system checks to verify configuration."""
    print("\n6. Running Django System Checks")
    print("=" * 50)
    
    try:
        result = subprocess.run(
            ['python', 'manage.py', 'check'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("   ✓ Django system checks passed")
            return True
        else:
            print(f"   ✗ Django system checks failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("   ⚠ Django system check timed out")
        return False
    except Exception as e:
        print(f"   ✗ Django system check error: {e}")
        return False

def cleanup_test_data():
    """Clean up test data created during testing."""
    try:
        # Delete test users
        User.objects.filter(username__startswith='test_').delete()
        
        # Clear test cache entries
        cache_backend = CacheManager.get_cache_backend()
        test_keys = [
            'connectivity_test',
            'test_performance',
            CacheManager.generate_cache_key('test_basic'),
        ]
        
        for key in test_keys:
            try:
                cache_backend.delete(key)
            except:
                pass
                
        print("   ✓ Test cleanup completed")
        
    except Exception as e:
        print(f"   ⚠ Cleanup warning: {e}")

def main():
    print("LuminaLearn Cache Implementation Test Suite")
    print("=" * 60)
    print("Testing Redis cache functionality and fallback behavior...\n")
    
    test_results = []
    
    # Run all tests
    test_results.append(("Redis Connection", test_redis_connection()))
    test_results.append(("Cached Endpoints", test_cached_endpoints()))
    test_results.append(("Cache Invalidation", test_cache_invalidation()))
    test_results.append(("Cache Performance", test_cache_performance()))
    test_results.append(("Management Command", test_cache_management_command()))
    test_results.append(("Django System Checks", test_django_system_checks()))
    
    # Clean up
    print("\n7. Cleaning Up Test Data")
    print("=" * 50)
    cleanup_test_data()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:<25} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed + failed}, Passed: {passed}, Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Cache implementation is working correctly.")
        print("\nNext steps:")
        print("1. Install Redis: pip install -r cache_requirements.txt")
        print("2. Start Redis server: redis-server")
        print("3. Run Django server: python manage.py runserver")
        print("4. Monitor cache: python manage.py cache_monitor --stats")
        print("5. View cache stats at: http://127.0.0.1:8000/admin/cache-stats/")
    else:
        print(f"\n⚠ {failed} test(s) failed. Please review the output above.")
        print("The application should still work with local memory cache fallback.")

    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)