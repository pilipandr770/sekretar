#!/usr/bin/env python3
"""Create .mo files from .po files using Python."""
import os
import sys
from babel.messages.pofile import read_po
from babel.messages.mofile import write_mo

def compile_po_to_mo(po_file_path, mo_file_path):
    """Compile .po file to .mo file."""
    try:
        with open(po_file_path, 'rb') as po_file:
            catalog = read_po(po_file)
        
        with open(mo_file_path, 'wb') as mo_file:
            write_mo(mo_file, catalog)
        
        print(f"✓ Compiled {po_file_path} -> {mo_file_path}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to compile {po_file_path}: {e}")
        return False

def main():
    """Main function to compile all translations."""
    languages = ['en', 'de', 'uk']
    success = True
    
    for lang in languages:
        po_file = f'app/translations/{lang}/LC_MESSAGES/messages.po'
        mo_file = f'app/translations/{lang}/LC_MESSAGES/messages.mo'
        
        if os.path.exists(po_file):
            if not compile_po_to_mo(po_file, mo_file):
                success = False
        else:
            print(f"✗ Translation file not found: {po_file}")
            success = False
    
    if success:
        print("\n✅ All translations compiled successfully!")
    else:
        print("\n❌ Some translations failed to compile")
        sys.exit(1)

if __name__ == '__main__':
    main()