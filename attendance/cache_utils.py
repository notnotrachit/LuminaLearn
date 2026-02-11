"""
Cache utilities for LuminaLearn application.
Provides caching decorators, cache key management, and graceful fallback handling.
"""

import functools
import logging
from django.core.cache import cache, caches
from django.conf import settings
from django.http import JsonResponse
import hashlib
import json

# Set up cache logging
logger = logging.getLogger('lumina_learn.cache')

class CacheManager:
    """
    Cache manager with graceful fallback and monitoring capabilities.
    """
    
    # Cache key prefixes for different data types
    COURSE_LIST_PREFIX = 'course_list'
    COURSE_DETAIL_PREFIX = 'course_detail'
    STUDENT_LIST_PREFIX = 'student_list'
    LECTURE_DETAIL_PREFIX = 'lecture_detail'
    LECTURE_SCHEDULE_PREFIX = 'lecture_schedule'
    ENROLLMENT_PREFIX = 'enrollment'
    BLOCKCHAIN_STATUS_PREFIX = 'blockchain_status'
    
    @classmethod
    def get_cache_backend(cls):
        """
        Get cache backend with graceful fallback to local memory cache.
        """
        try:
            # Test Redis connection
            default_cache = caches['default']
            default_cache.get('__test__', None)
            return default_cache
        except Exception as e:
            logger.warning(f"Redis cache unavailable, falling back to local memory cache: {e}")
            return caches['fallback']
    
    @classmethod
    def generate_cache_key(cls, prefix, *args, **kwargs):
        """
        Generate a consistent cache key from prefix and arguments.
        """
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(hashlib.md5(json.dumps(arg, sort_keys=True).encode()).hexdigest()[:8])
            else:
                key_parts.append(str(arg))
        
        # Add keyword arguments
        for k, v in sorted(kwargs.items()):
            if isinstance(v, (dict, list)):
                key_parts.append(f"{k}_{hashlib.md5(json.dumps(v, sort_keys=True).encode()).hexdigest()[:8]}")
            else:
                key_parts.append(f"{k}_{v}")
        
        return ':'.join(key_parts)
    
    @classmethod
    def get_cached(cls, key, default=None):
        """
        Get value from cache with monitoring.
        """
        try:
            cache_backend = cls.get_cache_backend()
            value = cache_backend.get(key, default)
            
            if value is not None:
                logger.info(f"Cache HIT: {key}")
            else:
                logger.info(f"Cache MISS: {key}")
            
            return value
        except Exception as e:
            logger.error(f"Cache GET error for key {key}: {e}")
            return default
    
    @classmethod
    def set_cached(cls, key, value, timeout=None):
        """
        Set value in cache with monitoring.
        """
        try:
            cache_backend = cls.get_cache_backend()
            cache_backend.set(key, value, timeout)
            logger.info(f"Cache SET: {key} (timeout: {timeout}s)")
        except Exception as e:
            logger.error(f"Cache SET error for key {key}: {e}")
    
    @classmethod
    def delete_cached(cls, key_pattern=None, key=None):
        """
        Delete cache entry or entries matching pattern.
        """
        try:
            cache_backend = cls.get_cache_backend()
            
            if key:
                cache_backend.delete(key)
                logger.info(f"Cache DELETE: {key}")
            elif key_pattern:
                # For pattern-based deletion, we'll need to implement this
                # based on the specific cache backend capabilities
                if hasattr(cache_backend, 'delete_pattern'):
                    cache_backend.delete_pattern(key_pattern)
                    logger.info(f"Cache DELETE pattern: {key_pattern}")
                else:
                    logger.warning(f"Pattern deletion not supported for current cache backend")
        except Exception as e:
            logger.error(f"Cache DELETE error for key/pattern {key or key_pattern}: {e}")
    
    @classmethod
    def invalidate_related_cache(cls, model_name, instance_id=None, action='update'):
        """
        Invalidate cache entries related to a specific model instance.
        """
        try:
            if model_name.lower() == 'course':
                # Invalidate course-related caches
                cls.delete_cached(key=cls.generate_cache_key(cls.COURSE_LIST_PREFIX))
                if instance_id:
                    cls.delete_cached(key=cls.generate_cache_key(cls.COURSE_DETAIL_PREFIX, instance_id))
                    # Also invalidate enrollment data for this course
                    cls.delete_cached(key=cls.generate_cache_key(cls.STUDENT_LIST_PREFIX, f'course_{instance_id}'))
                    cls.delete_cached(key=cls.generate_cache_key(cls.ENROLLMENT_PREFIX, f'course_{instance_id}'))
                
            elif model_name.lower() == 'lecture':
                if instance_id:
                    cls.delete_cached(key=cls.generate_cache_key(cls.LECTURE_DETAIL_PREFIX, instance_id))
                    cls.delete_cached(key=cls.generate_cache_key(cls.LECTURE_SCHEDULE_PREFIX))
                
            elif model_name.lower() == 'enrollment':
                # Invalidate student and course related caches
                cls.delete_cached(key=cls.generate_cache_key(cls.STUDENT_LIST_PREFIX))
                cls.delete_cached(key=cls.generate_cache_key(cls.COURSE_LIST_PREFIX))
                if instance_id:
                    cls.delete_cached(key=cls.generate_cache_key(cls.ENROLLMENT_PREFIX, instance_id))
                
            elif model_name.lower() == 'user':
                # Invalidate student lists
                cls.delete_cached(key=cls.generate_cache_key(cls.STUDENT_LIST_PREFIX))
            
            logger.info(f"Invalidated cache for {model_name} (ID: {instance_id}, action: {action})")
            
        except Exception as e:
            logger.error(f"Cache invalidation error for {model_name}: {e}")


def cached_view(timeout=300, key_prefix=None, vary_on=None):
    """
    Decorator to cache view results.
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for cache key
        vary_on: List of request parameters to include in cache key
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key
            cache_key_parts = [key_prefix or func.__name__]
            cache_key_parts.extend([str(arg) for arg in args])
            
            # Add vary_on parameters
            if vary_on:
                for param in vary_on:
                    value = request.GET.get(param) or request.POST.get(param)
                    if value:
                        cache_key_parts.append(f"{param}_{value}")
            
            # Include user role in cache key for permissioned content
            if hasattr(request, 'user') and request.user.is_authenticated:
                cache_key_parts.append(f"user_role_{getattr(request.user, 'role', 'unknown')}")
            
            cache_key = CacheManager.generate_cache_key(*cache_key_parts)
            
            # Try to get from cache
            cached_result = CacheManager.get_cached(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute view function
            result = func(request, *args, **kwargs)
            
            # Cache the result if it's successful
            if hasattr(result, 'status_code') and result.status_code == 200:
                CacheManager.set_cached(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def cached_data(timeout=300, key_prefix=None):
    """
    Decorator to cache data/query results.
    
    Args:
        timeout: Cache timeout in seconds  
        key_prefix: Prefix for cache key
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = CacheManager.generate_cache_key(
                key_prefix or func.__name__, 
                *args, 
                **kwargs
            )
            
            # Try to get from cache
            cached_result = CacheManager.get_cached(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache the result
            CacheManager.set_cached(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def cache_on_auth_change(sender, **kwargs):
    """
    Signal handler to invalidate caches when user authentication changes.
    """
    try:
        CacheManager.delete_cached(CacheManager.generate_cache_key('user_auth'))
        logger.info("Invalidated user authentication caches")
    except Exception as e:
        logger.error(f"Error invalidating user auth caches: {e}")