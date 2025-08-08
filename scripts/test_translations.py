#!/usr/bin/env python3
"""Test all translations are working correctly."""
import os
import sys
from babel.messages.mofile import read_mo

def test_mo_file(mo_file_path, language):
    """Test if .mo file is valid and contains translations."""
    try:
        with open(mo_file_path, 'rb') as mo_file:
            catalog = read_mo(mo_file)
        
        # Count translated messages
        translated_count = 0
        total_count = 0
        
        for message in catalog:
            if message.id:  # Skip empty message (header)
                total_count += 1
                if message.string:
                    translated_count += 1
        
        print(f"✓ {language}: {translated_count}/{total_count} messages translated ({translated_count/total_count*100:.1f}%)")
        
        # Test some key messages
        key_messages = [
            'Authentication required',
            'Invalid email or password', 
            'Dashboard',
            'Login',
            'Contact created successfully'
        ]
        
        missing_translations = []
        for key_msg in key_messages:
            if key_msg not in catalog or not catalog[key_msg].string:
                missing_translations.append(key_msg)
        
        if missing_translations:
            print(f"  ⚠️  Missing translations: {', '.join(missing_translations[:3])}{'...' if len(missing_translations) > 3 else ''}")
        
        return translated_count > 0
        
    except Exception as e:
        print(f"✗ {language}: Error reading .mo file - {e}")
        return False

def main():
    """Test all translation files."""
    languages = ['en', 'de', 'uk']
    success = True
    
    print("Testing translation files...")
    print("=" * 40)
    
    for lang in languages:
        mo_file = f'app/translations/{lang}/LC_MESSAGES/messages.mo'
        
        if os.path.exists(mo_file):
            if not test_mo_file(mo_file, lang):
                success = False
        else:
            print(f"✗ {lang}: .mo file not found at {mo_file}")
            success = False
    
    print("=" * 40)
    
    if success:
        print("✅ All translation files are working correctly!")
        
        # Show language codes for reference
        print("\nLanguage codes:")
        print("  en - English (default)")
        print("  de - Deutsch (German)")
        print("  uk - Українська (Ukrainian)")
        
    else:
        print("❌ Some translation files have issues")
        print("\nTo fix issues:")
        print("1. Run: scripts\\i18n-workflow.ps1 full")
        print("2. Edit .po files in app/translations/*/LC_MESSAGES/")
        print("3. Run: python scripts/create_mo_files.py")
        sys.exit(1)

if __name__ == '__main__':
    main()