#!/usr/bin/env python3
"""
Script to extract translatable strings from HTML templates and identify missing translations.
This script will help identify hardcoded strings that need to be wrapped in translation functions.
"""

import os
import re
from pathlib import Path
from typing import Set, List, Dict

def find_hardcoded_strings_in_template(file_path: str) -> List[str]:
    """Find hardcoded strings in a template file that should be translated."""
    hardcoded_strings = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Patterns to identify hardcoded strings that should be translated
    patterns = [
        # Text in HTML elements (excluding already translated ones)
        r'>\s*([A-Z][^<>{}\n]+[a-zA-Z])\s*<',
        # Placeholder attributes
        r'placeholder\s*=\s*["\']([^"\']+)["\']',
        # Title attributes
        r'title\s*=\s*["\']([^"\']+)["\']',
        # Alt attributes
        r'alt\s*=\s*["\']([^"\']+)["\']',
        # Value attributes for buttons
        r'<(?:button|input)[^>]*value\s*=\s*["\']([^"\']+)["\']',
        # Text content in JavaScript strings
        r'["\']([A-Z][^"\']*[a-zA-Z])["\'](?=\s*[,;)])',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            # Skip if already translated
            if '{{' in match or '{%' in match:
                continue
            # Skip if it's a variable or code
            if any(char in match for char in ['(', ')', '{', '}', '[', ']', '=', ':', ';']):
                continue
            # Skip if it's too short or looks like code
            if len(match.strip()) < 3 or match.strip().isdigit():
                continue
            # Skip common non-translatable strings
            skip_strings = ['UTF-8', 'HTTP', 'API', 'URL', 'ID', 'CSS', 'JS', 'HTML', 'JSON', 'XML']
            if any(skip in match.upper() for skip in skip_strings):
                continue
            
            hardcoded_strings.append(match.strip())
    
    return list(set(hardcoded_strings))

def find_existing_translations(file_path: str) -> List[str]:
    """Find existing translation calls in a template."""
    translations = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find {{ _('...') }} patterns
    pattern = r'{{\s*_\(["\']([^"\']+)["\']\)\s*}}'
    matches = re.findall(pattern, content)
    translations.extend(matches)
    
    # Find {{ _l('...') }} patterns
    pattern = r'{{\s*_l\(["\']([^"\']+)["\']\)\s*}}'
    matches = re.findall(pattern, content)
    translations.extend(matches)
    
    return translations

def analyze_templates():
    """Analyze all templates for translation coverage."""
    template_dir = Path('app/templates')
    results = {}
    
    for template_file in template_dir.rglob('*.html'):
        rel_path = str(template_file.relative_to(template_dir))
        
        hardcoded = find_hardcoded_strings_in_template(str(template_file))
        existing = find_existing_translations(str(template_file))
        
        results[rel_path] = {
            'hardcoded_strings': hardcoded,
            'existing_translations': existing,
            'needs_attention': len(hardcoded) > 0
        }
    
    return results

def generate_report():
    """Generate a report of translation coverage."""
    results = analyze_templates()
    
    print("=== Template Translation Coverage Report ===\n")
    
    total_templates = len(results)
    templates_needing_work = sum(1 for r in results.values() if r['needs_attention'])
    
    print(f"Total templates: {total_templates}")
    print(f"Templates needing translation work: {templates_needing_work}")
    print(f"Coverage: {((total_templates - templates_needing_work) / total_templates * 100):.1f}%\n")
    
    for template_path, data in results.items():
        if data['needs_attention']:
            print(f"📄 {template_path}")
            print(f"   Existing translations: {len(data['existing_translations'])}")
            print(f"   Hardcoded strings found: {len(data['hardcoded_strings'])}")
            
            if data['hardcoded_strings']:
                print("   Strings to translate:")
                for string in data['hardcoded_strings'][:5]:  # Show first 5
                    print(f"     - '{string}'")
                if len(data['hardcoded_strings']) > 5:
                    print(f"     ... and {len(data['hardcoded_strings']) - 5} more")
            print()
    
    # Show templates that are already well translated
    well_translated = [path for path, data in results.items() if not data['needs_attention']]
    if well_translated:
        print("✅ Templates with good translation coverage:")
        for template in well_translated:
            print(f"   - {template}")

if __name__ == '__main__':
    generate_report()