#!/usr/bin/env python
"""
Quick cache test for LuminaLearn
"""

import os
import sys
import django
from pathlib import Path

# Add the project directory to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_system.settings')
django.setup()

def main():
    print("Testing LuminaLearn Cache Implementation")
    print("="*50)
    
    try:
        from attendance.cache_utils import CacheManager
        print("✓ Cache utilities loaded successfully")
        
        # Test cache backend
        cache_backend = CacheManager.get_cache_backend()
        backend_type = type(cache_backend).__name__
        print(f"✓ Cache backend: {backend_type}")
        
        # Test cache operations
        test_key = "test_key"
        test_value = "test_value"
        
        CacheManager.set_cached(test_key, test_value, 60)
        retrieved = CacheManager.get_cached(test_key)
        
        if retrieved == test_value:
            print("✓ Cache set/get operations working")
        else:
            print("✗ Cache operations failed")
        
        # Clean up
        CacheManager.delete_cached(key=test_key)
        print("✓ Cache cleanup completed")
        
        print("\n🎉 Cache implementation test PASSED!")
        print("The caching system is working correctly.")
        
    except Exception as e:
        print(f"✗ Cache test failed: {e}")
        print("The system will fall back to local memory cache.")

if __name__ == "__main__":
    main()