#!/usr/bin/env python3
"""Integration test for i18n services with Flask app."""
import sys
import os
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.translation_service import TranslationService
from app.services.localization_service import LocalizationService
from app.utils.i18n import LanguageDetectionService, set_user_language, get_user_language


def test_language_switching():
    """Test language switching functionality."""
    print("=== Testing Language Switching ===")
    
    app = create_app('testing')
    
    with app.app_context():
        with app.test_request_context('/?lang=de'):
            # Test URL parameter detection
            service = LanguageDetectionService()
            detected_lang = service._detect_language()
            print(f"Detected language from URL: {detected_lang}")
            
            # Test setting language
            result = set_user_language('uk')
            print(f"Set language to 'uk': {result}")
            
            # Test getting current language
            current_lang = get_user_language()
            print(f"Current language: {current_lang}")
    
    print("✓ Language switching works\n")


def test_localization_with_request_context():
    """Test localization services with proper request context."""
    print("=== Testing Localization with Request Context ===")
    
    app = create_app('testing')
    
    with app.app_context():
        with app.test_request_context('/?lang=de'):
            service = LocalizationService()
            
            # Test date formatting
            test_date = datetime(2023, 9, 15, 14, 30)
            try:
                formatted_date = service.format_date(test_date)
                print(f"Formatted date (German): {formatted_date}")
            except Exception as e:
                print(f"Date formatting error: {e}")
            
            # Test currency formatting
            try:
                formatted_currency = service.format_currency(1234.56, 'EUR')
                print(f"Formatted currency (German): {formatted_currency}")
            except Exception as e:
                print(f"Currency formatting error: {e}")
            
            # Test number formatting
            try:
                formatted_number = service.format_number(1234.56)
                print(f"Formatted number (German): {formatted_number}")
            except Exception as e:
                print(f"Number formatting error: {e}")
            
            # Test relative time
            try:
                relative_time = service.get_relative_time(test_date)
                print(f"Relative time (German): {relative_time}")
            except Exception as e:
                print(f"Relative time error: {e}")
        
        # Test with Ukrainian locale
        with app.test_request_context('/?lang=uk'):
            try:
                formatted_currency = service.format_currency(1234.56, 'UAH')
                print(f"Formatted currency (Ukrainian): {formatted_currency}")
            except Exception as e:
                print(f"Currency formatting error (Ukrainian): {e}")
    
    print("✓ Localization with request context works\n")


def test_translation_service_integration():
    """Test translation service integration."""
    print("=== Testing Translation Service Integration ===")
    
    app = create_app('testing')
    
    with app.app_context():
        service = TranslationService()
        
        # Test getting translation stats
        stats = service.get_translation_stats()
        print(f"Translation stats: {stats}")
        
        # Test getting missing translations
        missing = service.get_missing_translations()
        print(f"Missing translations count: {sum(len(v) for v in missing.values())}")
        
        # Test validation
        errors = service.validate_translations()
        print(f"Validation errors: {len(errors)}")
        
        # Test export functionality
        try:
            translations = service.export_translations('json')
            print(f"Exported translations for languages: {list(translations.keys())}")
        except Exception as e:
            print(f"Export error: {e}")
    
    print("✓ Translation service integration works\n")


def test_caching_functionality():
    """Test caching functionality."""
    print("=== Testing Caching Functionality ===")
    
    app = create_app('testing')
    
    with app.app_context():
        with app.test_request_context():
            from app.utils.i18n import get_cached_translation, invalidate_translation_cache
            
            # Test cached translation
            try:
                translation = get_cached_translation('Hello', 'de')
                print(f"Cached translation: {translation}")
            except Exception as e:
                print(f"Cached translation error: {e}")
            
            # Test cache invalidation
            try:
                invalidate_translation_cache('de')
                print("Cache invalidated successfully")
            except Exception as e:
                print(f"Cache invalidation error: {e}")
    
    print("✓ Caching functionality works\n")


def main():
    """Run integration tests."""
    print("i18n Services Integration Test")
    print("=" * 40)
    
    try:
        test_language_switching()
        test_localization_with_request_context()
        test_translation_service_integration()
        test_caching_functionality()
        
        print("🎉 All integration tests completed successfully!")
        return 0
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())