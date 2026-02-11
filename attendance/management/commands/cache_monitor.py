"""
Django management command for cache monitoring and management.

Usage:
    python manage.py cache_monitor --status          # Show cache status
    python manage.py cache_monitor --stats           # Show cache statistics  
    python manage.py cache_monitor --clear           # Clear all cache
    python manage.py cache_monitor --test            # Test cache functionality
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import caches
from django.conf import settings
from attendance.cache_utils import CacheManager
import time
import json


class Command(BaseCommand):
    help = 'Monitor and manage cache system for LuminaLearn application'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show cache backend status',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show detailed cache statistics',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all cache entries',
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test cache functionality',
        )
        parser.add_argument(
            '--warmup',
            action='store_true',
            help='Warm up cache with common queries',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('LuminaLearn Cache Management Tool\n' + '=' * 40)
        )

        if options['status']:
            self.show_status()
        elif options['stats']:
            self.show_statistics()
        elif options['clear']:
            self.clear_cache()
        elif options['test']:
            self.test_cache()
        elif options['warmup']:
            self.warmup_cache()
        else:
            self.show_help()

    def show_status(self):
        """Show cache backend status"""
        self.stdout.write('\n🔍 Cache Backend Status:')
        
        try:
            # Check default cache
            cache_backend = CacheManager.get_cache_backend()
            backend_type = type(cache_backend).__name__
            
            self.stdout.write(f'  Backend Type: {backend_type}')
            
            # Test connectivity
            test_key = 'management_test'
            test_value = 'test_' + str(int(time.time()))
            
            cache_backend.set(test_key, test_value, 10)
            retrieved_value = cache_backend.get(test_key)
            
            if retrieved_value == test_value:
                self.stdout.write(self.style.SUCCESS('  ✓ Cache connectivity: OK'))
                cache_backend.delete(test_key)
            else:
                self.stdout.write(self.style.ERROR('  ✗ Cache connectivity: FAILED'))
                
            # Show cache configuration
            self.stdout.write('\n📋 Cache Configuration:')
            cache_config = getattr(settings, 'CACHES', {}).get('default', {})
            for key, value in cache_config.items():
                if key != 'OPTIONS':  # Skip complex options for readability
                    self.stdout.write(f'  {key}: {value}')
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error checking cache status: {str(e)}'))

    def show_statistics(self):
        """Show detailed cache statistics"""
        self.stdout.write('\n📊 Cache Statistics:')
        
        try:
            cache_backend = CacheManager.get_cache_backend()
            
            # Test some common cache keys
            common_keys = [
                CacheManager.generate_cache_key(CacheManager.COURSE_LIST_PREFIX),
                CacheManager.generate_cache_key(CacheManager.STUDENT_LIST_PREFIX),
                CacheManager.generate_cache_key(CacheManager.BLOCKCHAIN_STATUS_PREFIX),
                CacheManager.generate_cache_key(CacheManager.LECTURE_SCHEDULE_PREFIX),
            ]
            
            hits = 0
            misses = 0
            
            self.stdout.write('\n  Key Status:')
            for key in common_keys:
                try:
                    value = cache_backend.get(key)
                    if value is not None:
                        hits += 1
                        status = self.style.SUCCESS('HIT')
                    else:
                        misses += 1
                        status = self.style.WARNING('MISS')
                    
                    self.stdout.write(f'    {key[:60]}... : {status}')
                except Exception as e:
                    self.stdout.write(f'    {key[:60]}... : {self.style.ERROR("ERROR")}')
            
            # Calculate hit ratio
            total = hits + misses
            if total > 0:
                hit_ratio = (hits / total) * 100
                self.stdout.write(f'\n  Hit Ratio: {hit_ratio:.1f}% ({hits}/{total})')
            
            # Show timeout configurations
            self.stdout.write('\n  Timeout Configuration:')
            timeouts = {
                'Course List': getattr(settings, 'CACHE_TIMEOUT_COURSE_LIST', 600),
                'Student List': getattr(settings, 'CACHE_TIMEOUT_STUDENT_LIST', 300),
                'Lecture Detail': getattr(settings, 'CACHE_TIMEOUT_LECTURE_DETAIL', 1200),
                'Blockchain Status': getattr(settings, 'CACHE_TIMEOUT_BLOCKCHAIN_STATUS', 180),
            }
            
            for cache_type, timeout in timeouts.items():
                self.stdout.write(f'    {cache_type}: {timeout} seconds')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error retrieving statistics: {str(e)}'))

    def clear_cache(self):
        """Clear all cache entries"""
        self.stdout.write('\n🗑️  Clearing Cache:')
        
        try:
            cache_backend = CacheManager.get_cache_backend() 
            cache_backend.clear()
            self.stdout.write(self.style.SUCCESS('  ✓ Cache cleared successfully'))
            
            # Also try to clear fallback cache
            try:
                fallback_cache = caches['fallback']
                fallback_cache.clear()
                self.stdout.write(self.style.SUCCESS('  ✓ Fallback cache cleared successfully'))
            except:
                pass  # Fallback cache might not exist or be clearable
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Error clearing cache: {str(e)}'))

    def test_cache(self):
        """Test cache functionality"""
        self.stdout.write('\n🧪 Testing Cache Functionality:')
        
        try:
            cache_backend = CacheManager.get_cache_backend()
            
            # Test 1: Basic set/get
            self.stdout.write('  Test 1: Basic set/get operations...')
            test_key = 'test_basic'
            test_value = {'data': 'test', 'timestamp': time.time()}
            
            cache_backend.set(test_key, test_value, 60)
            retrieved = cache_backend.get(test_key)
            
            if retrieved and retrieved.get('data') == 'test':
                self.stdout.write(self.style.SUCCESS('    ✓ Basic operations: PASSED'))
            else:
                self.stdout.write(self.style.ERROR('    ✗ Basic operations: FAILED'))
                
            # Test 2: Expiration
            self.stdout.write('  Test 2: Cache expiration...')
            expire_key = 'test_expire'
            cache_backend.set(expire_key, 'expire_test', 1)  # 1 second
            time.sleep(1.5)
            expired_value = cache_backend.get(expire_key)
            
            if expired_value is None:
                self.stdout.write(self.style.SUCCESS('    ✓ Expiration: PASSED'))
            else:
                self.stdout.write(self.style.WARNING('    ⚠ Expiration: May not be working properly'))
                
            # Test 3: Delete operations
            self.stdout.write('  Test 3: Delete operations...')
            delete_key = 'test_delete'
            cache_backend.set(delete_key, 'delete_test', 60)
            cache_backend.delete(delete_key)
            deleted_value = cache_backend.get(delete_key)
            
            if deleted_value is None:
                self.stdout.write(self.style.SUCCESS('    ✓ Delete operations: PASSED'))
            else:
                self.stdout.write(self.style.ERROR('    ✗ Delete operations: FAILED'))
                
            # Cleanup test keys
            cache_backend.delete(test_key)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Error during cache testing: {str(e)}'))

    def warmup_cache(self):
        """Warm up cache with common queries"""
        self.stdout.write('\n🔥 Warming up Cache:')
        
        try:
            from attendance.models import Course, User, Lecture
            
            # Warm up course list
            self.stdout.write('  Warming up course list cache...')
            courses = list(Course.objects.all())
            cache_key = CacheManager.generate_cache_key(CacheManager.COURSE_LIST_PREFIX)
            CacheManager.set_cached(cache_key, courses, getattr(settings, 'CACHE_TIMEOUT_COURSE_LIST', 600))
            
            # Warm up student list
            self.stdout.write('  Warming up student list cache...')
            students = list(User.objects.filter(is_student=True))
            cache_key = CacheManager.generate_cache_key(CacheManager.STUDENT_LIST_PREFIX)
            CacheManager.set_cached(cache_key, students, getattr(settings, 'CACHE_TIMEOUT_STUDENT_LIST', 300))
            
            # Warm up lecture schedule
            self.stdout.write('  Warming up lecture schedule cache...')
            lectures = list(Lecture.objects.all().order_by('-date', '-start_time'))
            cache_key = CacheManager.generate_cache_key(CacheManager.LECTURE_SCHEDULE_PREFIX)
            CacheManager.set_cached(cache_key, lectures, getattr(settings, 'CACHE_TIMEOUT_LECTURE_DETAIL', 1200))
            
            self.stdout.write(self.style.SUCCESS('  ✓ Cache warmup completed'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Error during cache warmup: {str(e)}'))

    def show_help(self):
        """Show available commands"""
        self.stdout.write('\n📖 Available Commands:')
        self.stdout.write('  --status     Show cache backend status')
        self.stdout.write('  --stats      Show detailed cache statistics')
        self.stdout.write('  --clear      Clear all cache entries')
        self.stdout.write('  --test       Test cache functionality')
        self.stdout.write('  --warmup     Warm up cache with common queries')
        self.stdout.write('\nExample: python manage.py cache_monitor --status')