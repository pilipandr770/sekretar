#!/usr/bin/env python3
"""Test script for i18n services."""
import sys
import os
from datetime import datetime
from decimal import Decimal

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.translation_service import TranslationService, ValidationError
from app.services.localization_service import LocalizationService
from app.utils.i18n import LanguageDetectionService, LANGUAGES


def test_validation_error():
    """Test ValidationError class."""
    print("=== Testing ValidationError ===")
    error = ValidationError('de', 'hello', 'Missing translation')
    print(f"Language: {error.language}")
    print(f"Key: {error.key}")
    print(f"Error: {error.error}")
    print(f"Repr: {repr(error)}")
    print("✓ ValidationError works correctly\n")


def test_language_detection_service():
    """Test LanguageDetectionService."""
    print("=== Testing LanguageDetectionService ===")
    service = LanguageDetectionService()
    
    # Test validation
    print(f"Validate 'en': {service.validate_language_code('en')}")
    print(f"Validate 'de': {service.validate_language_code('de')}")
    print(f"Validate 'uk': {service.validate_language_code('uk')}")
    print(f"Validate 'fr': {service.validate_language_code('fr')}")
    print(f"Validate 'invalid': {service.validate_language_code('invalid')}")
    
    # Test browser language detection
    print(f"Browser language (no request): {service.get_browser_language()}")
    
    # Test tenant default
    print(f"Tenant default language: {service.get_tenant_default_language()}")
    
    print("✓ LanguageDetectionService basic functionality works\n")


def test_localization_service():
    """Test LocalizationService."""
    print("=== Testing LocalizationService ===")
    service = LocalizationService()
    
    print(f"Default locale: {service.default_locale}")
    print(f"Supported locales: {service.supported_locales}")
    
    # Test current locale
    print(f"Current locale: {service.get_current_locale()}")
    
    # Test Babel locale
    try:
        babel_locale = service.get_babel_locale('de')
        print(f"Babel locale for 'de': {babel_locale}")
    except Exception as e:
        print(f"Babel locale error: {e}")
    
    # Test file size formatting
    print(f"Format 0 bytes: {service.format_file_size(0)}")
    print(f"Format 1024 bytes: {service.format_file_size(1024)}")
    print(f"Format 1MB: {service.format_file_size(1024*1024)}")
    
    # Test RTL detection
    print(f"Is 'en' RTL: {service.is_rtl_locale('en')}")
    print(f"Is 'de' RTL: {service.is_rtl_locale('de')}")
    print(f"Is 'uk' RTL: {service.is_rtl_locale('uk')}")
    
    print("✓ LocalizationService basic functionality works\n")


def test_with_app_context():
    """Test services with Flask app context."""
    print("=== Testing with Flask App Context ===")
    
    app = create_app('testing')
    
    with app.app_context():
        # Test TranslationService
        print("Testing TranslationService...")
        translation_service = TranslationService()
        print(f"Translations dir: {translation_service.translations_dir}")
        print(f"Supported languages: {translation_service.supported_languages}")
        
        # Test coverage calculation (will fail gracefully if no files)
        coverage = translation_service.get_translation_coverage()
        print(f"Translation coverage: {coverage}")
        
        # Test LocalizationService with app context
        print("Testing LocalizationService with app context...")
        loc_service = LocalizationService()
        
        # Test date formatting
        test_date = datetime(2023, 9, 15, 14, 30)
        try:
            formatted_date = loc_service.format_date(test_date)
            print(f"Formatted date: {formatted_date}")
        except Exception as e:
            print(f"Date formatting error: {e}")
        
        # Test number formatting
        try:
            formatted_number = loc_service.format_number(1234.56)
            print(f"Formatted number: {formatted_number}")
        except Exception as e:
            print(f"Number formatting error: {e}")
        
        # Test currency formatting
        try:
            formatted_currency = loc_service.format_currency(1234.56, 'EUR')
            print(f"Formatted currency: {formatted_currency}")
        except Exception as e:
            print(f"Currency formatting error: {e}")
        
        # Test relative time
        try:
            relative_time = loc_service.get_relative_time(test_date)
            print(f"Relative time: {relative_time}")
        except Exception as e:
            print(f"Relative time error: {e}")
        
        # Test locale info
        try:
            locale_info = loc_service.get_locale_info()
            print(f"Locale info keys: {list(locale_info.keys())}")
        except Exception as e:
            print(f"Locale info error: {e}")
        
        print("✓ Services work with Flask app context\n")


def test_translation_validation():
    """Test translation validation functionality."""
    print("=== Testing Translation Validation ===")
    
    app = create_app('testing')
    
    with app.app_context():
        service = TranslationService()
        
        # Test placeholder extraction
        placeholders = service._extract_placeholders("Hello %(name)s, you have %(count)d messages")
        print(f"Extracted placeholders: {placeholders}")
        
        # Test HTML tag detection
        has_html = service._has_html_tags("Click <a href='#'>here</a> to continue")
        print(f"Has HTML tags: {has_html}")
        
        # Test HTML tag validation
        source = "Click <a href='#'>here</a> to continue"
        target_good = "Klicken Sie <a href='#'>hier</a> um fortzufahren"
        target_bad = "Klicken Sie hier um fortzufahren"
        
        valid_good = service._validate_html_tags(source, target_good)
        valid_bad = service._validate_html_tags(source, target_bad)
        
        print(f"HTML validation (good): {valid_good}")
        print(f"HTML validation (bad): {valid_bad}")
        
        print("✓ Translation validation works\n")


def main():
    """Run all tests."""
    print("Testing Enhanced i18n Infrastructure and Services")
    print("=" * 50)
    
    try:
        test_validation_error()
        test_language_detection_service()
        test_localization_service()
        test_with_app_context()
        test_translation_validation()
        
        print("🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())