#!/usr/bin/env python3
"""
Script to update template translations by wrapping hardcoded strings in translation functions.
This script focuses on the most common patterns and user-facing strings.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

def update_template_translations():
    """Update templates with proper translation functions."""
    
    # Common patterns to translate
    translation_patterns = [
        # Button text
        (r'<button[^>]*>([^<]+)</button>', r'<button\1>{{ _("\2") }}</button>'),
        # Link text (but not URLs)
        (r'<a[^>]*>([A-Z][^<>{}]+)</a>', r'<a\1>{{ _("\2") }}</a>'),
        # Form labels
        (r'<label[^>]*>([^<>{}]+)</label>', r'<label\1>{{ _("\2") }}</label>'),
        # Placeholder attributes
        (r'placeholder="([^"]+)"', r'placeholder="{{ _(\'\\1\') }}"'),
        # Title attributes
        (r'title="([^"]+)"', r'title="{{ _(\'\\1\') }}"'),
        # Option text
        (r'<option[^>]*>([A-Z][^<>{}]+)</option>', r'<option\1>{{ _("\2") }}</option>'),
        # Heading text
        (r'<h[1-6][^>]*>([^<>{}]+)</h[1-6]>', r'<h\1>{{ _("\2") }}</h\1>'),
        # Paragraph text (simple cases)
        (r'<p[^>]*>([A-Z][^<>{}]+)</p>', r'<p\1>{{ _("\2") }}</p>'),
    ]
    
    # Templates to update (focusing on most important ones)
    templates_to_update = [
        'app/templates/components/error_display.html',
        'app/templates/channels/signal_setup.html',
        'app/templates/main/kyb_dashboard.html',
        'app/templates/main/secretary_setup.html',
        'app/templates/docs/api_tester.html',
        'app/templates/widget_demo.html'
    ]
    
    for template_path in templates_to_update:
        if os.path.exists(template_path):
            print(f"Updating {template_path}...")
            update_single_template(template_path)
        else:
            print(f"Template not found: {template_path}")

def update_single_template(template_path: str):
    """Update a single template with translation functions."""
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply basic translation patterns
        content = apply_basic_translations(content)
        
        # Apply template-specific updates
        if 'error_display.html' in template_path:
            content = update_error_display_template(content)
        elif 'signal_setup.html' in template_path:
            content = update_signal_setup_template(content)
        elif 'kyb_dashboard.html' in template_path:
            content = update_kyb_dashboard_template(content)
        elif 'secretary_setup.html' in template_path:
            content = update_secretary_setup_template(content)
        elif 'api_tester.html' in template_path:
            content = update_api_tester_template(content)
        elif 'widget_demo.html' in template_path:
            content = update_widget_demo_template(content)
        
        # Only write if content changed
        if content != original_content:
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Updated {template_path}")
        else:
            print(f"  - No changes needed for {template_path}")
            
    except Exception as e:
        print(f"  ✗ Error updating {template_path}: {e}")

def apply_basic_translations(content: str) -> str:
    """Apply basic translation patterns to content."""
    
    # Common hardcoded strings to translate
    basic_translations = {
        # Status messages
        'Loading...': '{{ _("Loading...") }}',
        'Error': '{{ _("Error") }}',
        'Success': '{{ _("Success") }}',
        'Warning': '{{ _("Warning") }}',
        'Info': '{{ _("Info") }}',
        
        # Common actions
        'Save': '{{ _("Save") }}',
        'Cancel': '{{ _("Cancel") }}',
        'Delete': '{{ _("Delete") }}',
        'Edit': '{{ _("Edit") }}',
        'Add': '{{ _("Add") }}',
        'Remove': '{{ _("Remove") }}',
        'Update': '{{ _("Update") }}',
        'Create': '{{ _("Create") }}',
        'Submit': '{{ _("Submit") }}',
        'Reset': '{{ _("Reset") }}',
        'Clear': '{{ _("Clear") }}',
        'Search': '{{ _("Search") }}',
        'Filter': '{{ _("Filter") }}',
        'Sort': '{{ _("Sort") }}',
        'Export': '{{ _("Export") }}',
        'Import': '{{ _("Import") }}',
        'Download': '{{ _("Download") }}',
        'Upload': '{{ _("Upload") }}',
        
        # Common labels
        'Name': '{{ _("Name") }}',
        'Email': '{{ _("Email") }}',
        'Phone': '{{ _("Phone") }}',
        'Address': '{{ _("Address") }}',
        'Description': '{{ _("Description") }}',
        'Status': '{{ _("Status") }}',
        'Type': '{{ _("Type") }}',
        'Category': '{{ _("Category") }}',
        'Date': '{{ _("Date") }}',
        'Time': '{{ _("Time") }}',
        'Created': '{{ _("Created") }}',
        'Updated': '{{ _("Updated") }}',
        'Modified': '{{ _("Modified") }}',
        
        # Common states
        'Active': '{{ _("Active") }}',
        'Inactive': '{{ _("Inactive") }}',
        'Enabled': '{{ _("Enabled") }}',
        'Disabled': '{{ _("Disabled") }}',
        'Online': '{{ _("Online") }}',
        'Offline': '{{ _("Offline") }}',
        'Connected': '{{ _("Connected") }}',
        'Disconnected': '{{ _("Disconnected") }}',
        'Available': '{{ _("Available") }}',
        'Unavailable': '{{ _("Unavailable") }}',
        'Pending': '{{ _("Pending") }}',
        'Approved': '{{ _("Approved") }}',
        'Rejected': '{{ _("Rejected") }}',
        'Completed': '{{ _("Completed") }}',
        'Failed': '{{ _("Failed") }}',
        
        # Navigation
        'Home': '{{ _("Home") }}',
        'Back': '{{ _("Back") }}',
        'Next': '{{ _("Next") }}',
        'Previous': '{{ _("Previous") }}',
        'Continue': '{{ _("Continue") }}',
        'Finish': '{{ _("Finish") }}',
        'Close': '{{ _("Close") }}',
        'Open': '{{ _("Open") }}',
        
        # Common messages
        'No data available': '{{ _("No data available") }}',
        'No results found': '{{ _("No results found") }}',
        'Please wait...': '{{ _("Please wait...") }}',
        'Processing...': '{{ _("Processing...") }}',
        'Saving...': '{{ _("Saving...") }}',
        'Loading data...': '{{ _("Loading data...") }}',
    }
    
    # Apply word boundary replacements to avoid partial matches
    for original, translated in basic_translations.items():
        # Skip if already translated
        if translated in content:
            continue
        
        # Use word boundaries for exact matches
        pattern = r'\b' + re.escape(original) + r'\b'
        content = re.sub(pattern, translated, content)
    
    return content

def update_error_display_template(content: str) -> str:
    """Update error display template with translations."""
    
    # Add extends and title block if missing
    if '{% extends' not in content:
        content = '{% extends "base.html" %}\n\n' + content
    
    if '{% block title %}' not in content:
        title_block = '{% block title %}{{ _("Error") }} - {{ _("AI Secretary") }}{% endblock %}\n\n'
        content = content.replace('{% extends "base.html" %}\n\n', '{% extends "base.html" %}\n\n' + title_block)
    
    # Translate common error messages
    error_translations = {
        'An error occurred': '{{ _("An error occurred") }}',
        'Page not found': '{{ _("Page not found") }}',
        'Access denied': '{{ _("Access denied") }}',
        'Server error': '{{ _("Server error") }}',
        'Network error': '{{ _("Network error") }}',
        'Timeout error': '{{ _("Timeout error") }}',
        'Authentication required': '{{ _("Authentication required") }}',
        'Permission denied': '{{ _("Permission denied") }}',
        'Invalid request': '{{ _("Invalid request") }}',
        'Service unavailable': '{{ _("Service unavailable") }}',
    }
    
    for original, translated in error_translations.items():
        content = content.replace(f'"{original}"', f'"{translated}"')
        content = content.replace(f"'{original}'", f"'{translated}'")
        content = content.replace(f'>{original}<', f'>{translated}<')
    
    return content

def update_signal_setup_template(content: str) -> str:
    """Update Signal setup template with translations."""
    
    # Add extends and title block if missing
    if '{% extends' not in content:
        content = '{% extends "base.html" %}\n\n' + content
    
    if '{% block title %}' not in content:
        title_block = '{% block title %}{{ _("Signal Setup") }} - {{ _("AI Secretary") }}{% endblock %}\n\n'
        content = content.replace('{% extends "base.html" %}\n\n', '{% extends "base.html" %}\n\n' + title_block)
    
    # Signal-specific translations
    signal_translations = {
        'Signal Integration Setup': '{{ _("Signal Integration Setup") }}',
        'Phone Number': '{{ _("Phone Number") }}',
        'Verification Code': '{{ _("Verification Code") }}',
        'Link Device': '{{ _("Link Device") }}',
        'QR Code': '{{ _("QR Code") }}',
        'Device Linking': '{{ _("Device Linking") }}',
        'Registration': '{{ _("Registration") }}',
        'Verification': '{{ _("Verification") }}',
        'Setup Complete': '{{ _("Setup Complete") }}',
        'Connection Test': '{{ _("Connection Test") }}',
        'Auto Response': '{{ _("Auto Response") }}',
        'Message Handling': '{{ _("Message Handling") }}',
    }
    
    for original, translated in signal_translations.items():
        content = content.replace(f'"{original}"', f'"{translated}"')
        content = content.replace(f"'{original}'", f"'{translated}'")
        content = content.replace(f'>{original}<', f'>{translated}<')
    
    return content

def update_kyb_dashboard_template(content: str) -> str:
    """Update KYB dashboard template with translations."""
    
    # Add extends and title block if missing
    if '{% extends' not in content:
        content = '{% extends "base.html" %}\n\n' + content
    
    if '{% block title %}' not in content:
        title_block = '{% block title %}{{ _("KYB Dashboard") }} - {{ _("AI Secretary") }}{% endblock %}\n\n'
        content = content.replace('{% extends "base.html" %}\n\n', '{% extends "base.html" %}\n\n' + title_block)
    
    # KYB-specific translations
    kyb_translations = {
        'KYB Dashboard': '{{ _("KYB Dashboard") }}',
        'Counterparty Monitoring': '{{ _("Counterparty Monitoring") }}',
        'Risk Assessment': '{{ _("Risk Assessment") }}',
        'Compliance Status': '{{ _("Compliance Status") }}',
        'Sanctions Screening': '{{ _("Sanctions Screening") }}',
        'VAT Verification': '{{ _("VAT Verification") }}',
        'Company Information': '{{ _("Company Information") }}',
        'Legal Entity': '{{ _("Legal Entity") }}',
        'Business Registration': '{{ _("Business Registration") }}',
        'Verification Status': '{{ _("Verification Status") }}',
        'Risk Level': '{{ _("Risk Level") }}',
        'Last Updated': '{{ _("Last Updated") }}',
        'Add Counterparty': '{{ _("Add Counterparty") }}',
        'View Details': '{{ _("View Details") }}',
        'Update Information': '{{ _("Update Information") }}',
        'High Risk': '{{ _("High Risk") }}',
        'Medium Risk': '{{ _("Medium Risk") }}',
        'Low Risk': '{{ _("Low Risk") }}',
        'Verified': '{{ _("Verified") }}',
        'Unverified': '{{ _("Unverified") }}',
        'Under Review': '{{ _("Under Review") }}',
    }
    
    for original, translated in kyb_translations.items():
        content = content.replace(f'"{original}"', f'"{translated}"')
        content = content.replace(f"'{original}'", f"'{translated}'")
        content = content.replace(f'>{original}<', f'>{translated}<')
    
    return content

def update_secretary_setup_template(content: str) -> str:
    """Update secretary setup template with translations."""
    
    # Add extends and title block if missing
    if '{% extends' not in content:
        content = '{% extends "base.html" %}\n\n' + content
    
    if '{% block title %}' not in content:
        title_block = '{% block title %}{{ _("Secretary Setup") }} - {{ _("AI Secretary") }}{% endblock %}\n\n'
        content = content.replace('{% extends "base.html" %}\n\n', '{% extends "base.html" %}\n\n' + title_block)
    
    # Secretary-specific translations
    secretary_translations = {
        'AI Secretary Setup': '{{ _("AI Secretary Setup") }}',
        'Configuration': '{{ _("Configuration") }}',
        'Communication Channels': '{{ _("Communication Channels") }}',
        'AI Settings': '{{ _("AI Settings") }}',
        'Response Templates': '{{ _("Response Templates") }}',
        'Auto Reply': '{{ _("Auto Reply") }}',
        'Working Hours': '{{ _("Working Hours") }}',
        'Out of Office': '{{ _("Out of Office") }}',
        'Escalation Rules': '{{ _("Escalation Rules") }}',
        'Knowledge Base': '{{ _("Knowledge Base") }}',
        'Training Data': '{{ _("Training Data") }}',
        'Model Selection': '{{ _("Model Selection") }}',
        'Temperature': '{{ _("Temperature") }}',
        'Max Tokens': '{{ _("Max Tokens") }}',
        'System Prompt': '{{ _("System Prompt") }}',
        'Personality': '{{ _("Personality") }}',
        'Language Model': '{{ _("Language Model") }}',
        'Response Style': '{{ _("Response Style") }}',
    }
    
    for original, translated in secretary_translations.items():
        content = content.replace(f'"{original}"', f'"{translated}"')
        content = content.replace(f"'{original}'", f"'{translated}'")
        content = content.replace(f'>{original}<', f'>{translated}<')
    
    return content

def update_api_tester_template(content: str) -> str:
    """Update API tester template with translations."""
    
    # Add extends and title block if missing
    if '{% extends' not in content:
        content = '{% extends "base.html" %}\n\n' + content
    
    if '{% block title %}' not in content:
        title_block = '{% block title %}{{ _("API Tester") }} - {{ _("AI Secretary") }}{% endblock %}\n\n'
        content = content.replace('{% extends "base.html" %}\n\n', '{% extends "base.html" %}\n\n' + title_block)
    
    # API-specific translations
    api_translations = {
        'API Tester': '{{ _("API Tester") }}',
        'Endpoint': '{{ _("Endpoint") }}',
        'Method': '{{ _("Method") }}',
        'Headers': '{{ _("Headers") }}',
        'Parameters': '{{ _("Parameters") }}',
        'Request Body': '{{ _("Request Body") }}',
        'Response': '{{ _("Response") }}',
        'Status Code': '{{ _("Status Code") }}',
        'Response Time': '{{ _("Response Time") }}',
        'Send Request': '{{ _("Send Request") }}',
        'Clear': '{{ _("Clear") }}',
        'Copy': '{{ _("Copy") }}',
        'Authentication': '{{ _("Authentication") }}',
        'Bearer Token': '{{ _("Bearer Token") }}',
        'API Key': '{{ _("API Key") }}',
        'Content Type': '{{ _("Content Type") }}',
        'JSON': '{{ _("JSON") }}',
        'XML': '{{ _("XML") }}',
        'Form Data': '{{ _("Form Data") }}',
        'Query String': '{{ _("Query String") }}',
    }
    
    for original, translated in api_translations.items():
        content = content.replace(f'"{original}"', f'"{translated}"')
        content = content.replace(f"'{original}'", f"'{translated}'")
        content = content.replace(f'>{original}<', f'>{translated}<')
    
    return content

def update_widget_demo_template(content: str) -> str:
    """Update widget demo template with translations."""
    
    # Add extends and title block if missing
    if '{% extends' not in content:
        content = '{% extends "base.html" %}\n\n' + content
    
    if '{% block title %}' not in content:
        title_block = '{% block title %}{{ _("Widget Demo") }} - {{ _("AI Secretary") }}{% endblock %}\n\n'
        content = content.replace('{% extends "base.html" %}\n\n', '{% extends "base.html" %}\n\n' + title_block)
    
    # Widget-specific translations
    widget_translations = {
        'Widget Demo': '{{ _("Widget Demo") }}',
        'Chat Widget': '{{ _("Chat Widget") }}',
        'Customization': '{{ _("Customization") }}',
        'Preview': '{{ _("Preview") }}',
        'Color Scheme': '{{ _("Color Scheme") }}',
        'Position': '{{ _("Position") }}',
        'Size': '{{ _("Size") }}',
        'Welcome Message': '{{ _("Welcome Message") }}',
        'Placeholder Text': '{{ _("Placeholder Text") }}',
        'Send Button': '{{ _("Send Button") }}',
        'Minimize': '{{ _("Minimize") }}',
        'Maximize': '{{ _("Maximize") }}',
        'Close': '{{ _("Close") }}',
        'Type a message': '{{ _("Type a message") }}',
        'Send': '{{ _("Send") }}',
        'Online': '{{ _("Online") }}',
        'Offline': '{{ _("Offline") }}',
        'Typing...': '{{ _("Typing...") }}',
        'Message sent': '{{ _("Message sent") }}',
        'Connection error': '{{ _("Connection error") }}',
    }
    
    for original, translated in widget_translations.items():
        content = content.replace(f'"{original}"', f'"{translated}"')
        content = content.replace(f"'{original}'", f"'{translated}'")
        content = content.replace(f'>{original}<', f'>{translated}<')
    
    return content

if __name__ == '__main__':
    print("Updating template translations...")
    update_template_translations()
    print("Template translation update complete!")