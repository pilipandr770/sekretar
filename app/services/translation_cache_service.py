"""
Translation caching service for production optimization.
"""

import os
import json
import time
import hashlib
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from flask import current_app
from flask_caching import Cache
import redis
from babel import Locale
from babel.messages import Catalog
from babel.messages.pofile import read_po
from babel.messages.mofile import read_mo

class TranslationCacheService:
    """Service for caching and optimizing translation performance."""
    
    def __init__(self, cache: Cache = None, redis_client: redis.Redis = None):
        self.cache = cache
        self.redis_client = redis_client
        self._memory_cache = {}
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'loads': 0,
            'errors': 0
        }
    
    def get_translation(self, key: str, locale: str, fallback_locale: str = 'en') -> Optional[str]:
        """Get translation with multi-level caching."""
        cache_key = f"i18n:{locale}:{key}"
        
        # Level 1: Memory cache (fastest)
        if cache_key in self._memory_cache:
            self._cache_stats['hits'] += 1
            return self._memory_cache[cache_key]
        
        # Level 2: Redis cache
        if self.redis_client:
            try:
                cached_value = self.redis_client.get(cache_key)
                if cached_value:
                    translation = cached_value.decode('utf-8')
                    self._memory_cache[cache_key] = translation
                    self._cache_stats['hits'] += 1
                    return translation
            except Exception as e:
                current_app.logger.warning(f"Redis cache error: {e}")
                self._cache_stats['errors'] += 1
        
        # Level 3: Flask-Caching (if available)
        if self.cache:
            try:
                translation = self.cache.get(cache_key)
                if translation:
                    self._memory_cache[cache_key] = translation
                    if self.redis_client:
                        self.redis_client.setex(cache_key, 3600, translation)
                    self._cache_stats['hits'] += 1
                    return translation
            except Exception as e:
                current_app.logger.warning(f"Flask cache error: {e}")
                self._cache_stats['errors'] += 1
        
        # Cache miss - load from translation files
        self._cache_stats['misses'] += 1
        translation = self._load_translation_from_file(key, locale, fallback_locale)
        
        if translation:
            self._store_in_all_caches(cache_key, translation)
        
        return translation
    
    def _load_translation_from_file(self, key: str, locale: str, fallback_locale: str) -> Optional[str]:
        """Load translation from .mo files."""
        try:
            # Try primary locale
            translation = self._get_from_mo_file(key, locale)
            if translation:
                return translation
            
            # Try fallback locale
            if locale != fallback_locale:
                translation = self._get_from_mo_file(key, fallback_locale)
                if translation:
                    return translation
            
            # Return key as fallback
            return key
            
        except Exception as e:
            current_app.logger.error(f"Error loading translation for {key} ({locale}): {e}")
            self._cache_stats['errors'] += 1
            return key
    
    def _get_from_mo_file(self, key: str, locale: str) -> Optional[str]:
        """Get translation from compiled .mo file."""
        mo_path = os.path.join(
            current_app.root_path,
            'translations',
            locale,
            'LC_MESSAGES',
            'messages.mo'
        )
        
        if not os.path.exists(mo_path):
            return None
        
        try:
            with open(mo_path, 'rb') as f:
                catalog = read_mo(f)
                message = catalog.get(key)
                if message and message.string:
                    return message.string
        except Exception as e:
            current_app.logger.warning(f"Error reading .mo file {mo_path}: {e}")
        
        return None
    
    def _store_in_all_caches(self, cache_key: str, translation: str):
        """Store translation in all available cache layers."""
        # Memory cache
        self._memory_cache[cache_key] = translation
        
        # Redis cache (1 hour TTL)
        if self.redis_client:
            try:
                self.redis_client.setex(cache_key, 3600, translation)
            except Exception as e:
                current_app.logger.warning(f"Redis cache store error: {e}")
        
        # Flask cache (1 hour TTL)
        if self.cache:
            try:
                self.cache.set(cache_key, translation, timeout=3600)
            except Exception as e:
                current_app.logger.warning(f"Flask cache store error: {e}")
    
    def preload_translations(self, locales: List[str] = None) -> Dict[str, int]:
        """Preload translations into cache for better performance."""
        if not locales:
            locales = ['en', 'de', 'uk']
        
        results = {}
        
        for locale in locales:
            try:
                count = self._preload_locale_translations(locale)
                results[locale] = count
                current_app.logger.info(f"Preloaded {count} translations for {locale}")
            except Exception as e:
                current_app.logger.error(f"Error preloading {locale} translations: {e}")
                results[locale] = 0
        
        return results
    
    def _preload_locale_translations(self, locale: str) -> int:
        """Preload all translations for a specific locale."""
        mo_path = os.path.join(
            current_app.root_path,
            'translations',
            locale,
            'LC_MESSAGES',
            'messages.mo'
        )
        
        if not os.path.exists(mo_path):
            return 0
        
        count = 0
        try:
            with open(mo_path, 'rb') as f:
                catalog = read_mo(f)
                
                for message in catalog:
                    if message.id and message.string:
                        cache_key = f"i18n:{locale}:{message.id}"
                        self._store_in_all_caches(cache_key, message.string)
                        count += 1
        
        except Exception as e:
            current_app.logger.error(f"Error preloading {locale}: {e}")
            raise
        
        return count
    
    def invalidate_cache(self, locale: str = None, key: str = None):
        """Invalidate translation cache."""
        if key and locale:
            # Invalidate specific translation
            cache_key = f"i18n:{locale}:{key}"
            self._invalidate_key(cache_key)
        elif locale:
            # Invalidate all translations for locale
            pattern = f"i18n:{locale}:*"
            self._invalidate_pattern(pattern)
        else:
            # Invalidate all translations
            pattern = "i18n:*"
            self._invalidate_pattern(pattern)
    
    def _invalidate_key(self, cache_key: str):
        """Invalidate a specific cache key."""
        # Memory cache
        self._memory_cache.pop(cache_key, None)
        
        # Redis cache
        if self.redis_client:
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                current_app.logger.warning(f"Redis invalidation error: {e}")
        
        # Flask cache
        if self.cache:
            try:
                self.cache.delete(cache_key)
            except Exception as e:
                current_app.logger.warning(f"Flask cache invalidation error: {e}")
    
    def _invalidate_pattern(self, pattern: str):
        """Invalidate cache keys matching pattern."""
        # Memory cache
        keys_to_remove = [k for k in self._memory_cache.keys() if self._matches_pattern(k, pattern)]
        for key in keys_to_remove:
            del self._memory_cache[key]
        
        # Redis cache
        if self.redis_client:
            try:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as e:
                current_app.logger.warning(f"Redis pattern invalidation error: {e}")
        
        # Flask cache doesn't support pattern deletion easily
        # Would need to track keys separately for this
    
    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern (simple * wildcard support)."""
        if '*' not in pattern:
            return key == pattern
        
        pattern_parts = pattern.split('*')
        if len(pattern_parts) == 2:
            prefix, suffix = pattern_parts
            return key.startswith(prefix) and key.endswith(suffix)
        
        return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = (self._cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'loads': self._cache_stats['loads'],
            'errors': self._cache_stats['errors'],
            'hit_rate': round(hit_rate, 2),
            'memory_cache_size': len(self._memory_cache),
            'redis_available': self.redis_client is not None,
            'flask_cache_available': self.cache is not None
        }
    
    def warm_cache(self) -> Dict[str, Any]:
        """Warm up the cache with commonly used translations."""
        start_time = time.time()
        
        # Common translation keys to preload
        common_keys = [
            'Welcome', 'Login', 'Logout', 'Save', 'Cancel', 'Delete', 'Edit',
            'Create', 'Update', 'Search', 'Filter', 'Export', 'Import',
            'Settings', 'Profile', 'Dashboard', 'Users', 'Admin', 'Help',
            'Error', 'Success', 'Warning', 'Info', 'Loading', 'Please wait',
            'Invalid email address', 'Password must be at least 8 characters',
            'User created successfully', 'User updated successfully',
            'Authentication required', 'Access denied'
        ]
        
        locales = ['en', 'de', 'uk']
        warmed_count = 0
        
        for locale in locales:
            for key in common_keys:
                translation = self.get_translation(key, locale)
                if translation:
                    warmed_count += 1
        
        duration = time.time() - start_time
        
        return {
            'warmed_translations': warmed_count,
            'duration_seconds': round(duration, 3),
            'locales': locales,
            'common_keys_count': len(common_keys)
        }
    
    def get_translation_file_info(self) -> Dict[str, Any]:
        """Get information about translation files."""
        locales = ['en', 'de', 'uk']
        file_info = {}
        
        for locale in locales:
            mo_path = os.path.join(
                current_app.root_path,
                'translations',
                locale,
                'LC_MESSAGES',
                'messages.mo'
            )
            
            po_path = os.path.join(
                current_app.root_path,
                'translations',
                locale,
                'LC_MESSAGES',
                'messages.po'
            )
            
            info = {
                'mo_exists': os.path.exists(mo_path),
                'po_exists': os.path.exists(po_path),
                'mo_size': 0,
                'po_size': 0,
                'mo_modified': None,
                'po_modified': None,
                'message_count': 0
            }
            
            if info['mo_exists']:
                stat = os.stat(mo_path)
                info['mo_size'] = stat.st_size
                info['mo_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            if info['po_exists']:
                stat = os.stat(po_path)
                info['po_size'] = stat.st_size
                info['po_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                
                # Count messages in .po file
                try:
                    with open(po_path, 'rb') as f:
                        catalog = read_po(f)
                        info['message_count'] = len([m for m in catalog if m.id])
                except Exception as e:
                    current_app.logger.warning(f"Error reading {po_path}: {e}")
            
            file_info[locale] = info
        
        return file_info


# Global cache service instance
_cache_service = None

def get_translation_cache_service() -> TranslationCacheService:
    """Get or create the global translation cache service."""
    global _cache_service
    
    if _cache_service is None:
        from flask import current_app
        
        # Get cache instances
        cache = getattr(current_app, 'cache', None)
        redis_client = getattr(current_app, 'redis', None)
        
        _cache_service = TranslationCacheService(cache=cache, redis_client=redis_client)
    
    return _cache_service

def init_translation_cache(app):
    """Initialize translation cache service with Flask app."""
    global _cache_service
    
    cache = getattr(app, 'cache', None)
    redis_client = getattr(app, 'redis', None)
    
    _cache_service = TranslationCacheService(cache=cache, redis_client=redis_client)
    
    # Warm up cache on startup if in production
    if app.config.get('ENV') == 'production':
        with app.app_context():
            try:
                result = _cache_service.warm_cache()
                app.logger.info(f"Translation cache warmed: {result}")
            except Exception as e:
                app.logger.error(f"Failed to warm translation cache: {e}")
    
    return _cache_service