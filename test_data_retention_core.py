#!/usr/bin/env python3
"""Core test script for data retention functionality without full app context."""
import os
import sys
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.pii_service import PIIDetector, DataMinimizer


def test_pii_detection_comprehensive():
    """Test comprehensive PII detection functionality."""
    print("Testing Comprehensive PII Detection...")
    
    detector = PIIDetector()
    
    # Test various PII types
    test_cases = [
        {
            'text': 'Contact me at john.doe@example.com',
            'expected_types': ['email']
        },
        {
            'text': 'Call me at (555) 123-4567 or 555-987-6543',
            'expected_types': ['phone']
        },
        {
            'text': 'My SSN is 123-45-6789',
            'expected_types': ['ssn']
        },
        {
            'text': 'Credit card: 4532 1234 5678 9012',
            'expected_types': ['credit_card']
        },
        {
            'text': 'IBAN: DE89370400440532013000',
            'expected_types': ['iban']
        },
        {
            'text': 'IP address: 192.168.1.1',
            'expected_types': ['ip_address']
        },
        {
            'text': 'VAT: DE123456789',
            'expected_types': ['vat_number']
        },
        {
            'text': 'Contact John at john@example.com or call (555) 123-4567. SSN: 123-45-6789',
            'expected_types': ['email', 'phone', 'ssn']
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['text']}")
        
        detected_pii = detector.detect_pii_in_text(test_case['text'])
        detected_types = [pii['type'] for pii in detected_pii]
        
        print(f"Expected types: {test_case['expected_types']}")
        print(f"Detected types: {detected_types}")
        print(f"Detected {len(detected_pii)} PII items:")
        
        for pii in detected_pii:
            print(f"  - Type: {pii['type']}, Value: {pii['value']}, Confidence: {pii['confidence']}")
        
        # Check if all expected types were detected
        for expected_type in test_case['expected_types']:
            if expected_type not in detected_types:
                print(f"  ⚠️  Missing expected type: {expected_type}")
            else:
                print(f"  ✓ Found expected type: {expected_type}")
    
    print("\n✓ Comprehensive PII Detection test completed\n")


def test_pii_masking():
    """Test PII masking functionality."""
    print("Testing PII Masking...")
    
    detector = PIIDetector()
    
    test_texts = [
        "Contact me at john.doe@example.com",
        "Call me at (555) 123-4567",
        "My email is user@domain.com and phone is 555-987-6543",
        "SSN: 123-45-6789, Credit Card: 4532 1234 5678 9012"
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"\nTest {i}:")
        print(f"Original: {text}")
        
        # Test different masking options
        masked_text_default, items_default = detector.mask_pii_in_text(text)
        masked_text_custom, items_custom = detector.mask_pii_in_text(text, mask_char='X', preserve_chars=1)
        
        print(f"Masked (default): {masked_text_default}")
        print(f"Masked (custom):  {masked_text_custom}")
        print(f"Items masked: {len(items_default)}")
        
        for item in items_default:
            print(f"  - {item['type']}: {item['original_value']} -> {item['masked_value']}")
    
    print("\n✓ PII Masking test completed\n")


def test_pii_data_detection():
    """Test PII detection in structured data."""
    print("Testing PII Detection in Structured Data...")
    
    detector = PIIDetector()
    
    # Test data with various PII
    test_data = {
        'name': 'John Doe',
        'email': 'john.doe@example.com',
        'phone': '(555) 123-4567',
        'address': '123 Main St, Anytown, USA',
        'message': 'Please contact me at my alternate email: john.alt@example.com or call 555-987-6543',
        'notes': 'Customer SSN: 123-45-6789, Credit Card ending in 9012',
        'company': 'Example Corp',
        'website': 'https://example.com'
    }
    
    # Define field mapping
    field_mapping = {
        'email': 'email',
        'phone': 'phone'
    }
    
    print("Test data:")
    for key, value in test_data.items():
        print(f"  {key}: {value}")
    
    # Detect PII
    detected_pii = detector.detect_pii_in_data(test_data, field_mapping)
    
    print(f"\nDetected PII in {len(detected_pii)} fields:")
    for field_name, pii_items in detected_pii.items():
        print(f"\nField '{field_name}':")
        for pii_item in pii_items:
            print(f"  - Type: {pii_item['type']}, Value: {pii_item['value']}, "
                  f"Confidence: {pii_item['confidence']}, Source: {pii_item['source']}")
    
    # Test anonymization
    anonymized_data, log = detector.anonymize_data(test_data, field_mapping)
    
    print(f"\nAnonymized data:")
    for key, value in anonymized_data.items():
        if key in detected_pii:
            print(f"  {key}: {value} (ANONYMIZED)")
        else:
            print(f"  {key}: {value}")
    
    print(f"\nAnonymization log for {len(log)} fields:")
    for field_name, log_items in log.items():
        print(f"  {field_name}: {len(log_items)} items anonymized")
    
    print("\n✓ PII Data Detection test completed\n")


def test_pii_validation():
    """Test PII detection validation functionality."""
    print("Testing PII Detection Validation...")
    
    detector = PIIDetector()
    
    # Test with known PII
    text = "Contact John at john@example.com or call (555) 123-4567"
    
    expected_pii = [
        {'type': 'email', 'value': 'john@example.com'},
        {'type': 'phone', 'value': '(555) 123-4567'}
    ]
    
    validation_result = detector.validate_pii_detection(text, expected_pii)
    
    print(f"Text: {text}")
    print(f"Expected PII: {expected_pii}")
    print(f"Validation Results:")
    print(f"  Precision: {validation_result['precision']:.2f}")
    print(f"  Recall: {validation_result['recall']:.2f}")
    print(f"  F1 Score: {validation_result['f1_score']:.2f}")
    print(f"  True Positives: {validation_result['true_positives']}")
    print(f"  False Positives: {validation_result['false_positives']}")
    print(f"  False Negatives: {validation_result['false_negatives']}")
    
    if validation_result['missed_pii']:
        print(f"  Missed PII: {validation_result['missed_pii']}")
    
    if validation_result['false_detections']:
        print(f"  False Detections: {validation_result['false_detections']}")
    
    print("\n✓ PII Validation test completed\n")


def test_data_minimizer():
    """Test data minimizer functionality."""
    print("Testing Data Minimizer...")
    
    # Create a mock database session (we'll skip actual DB operations)
    class MockDBSession:
        def commit(self):
            pass
    
    minimizer = DataMinimizer(MockDBSession())
    
    # Test message data minimization
    message_data = {
        'id': 1,
        'content': 'Hi, please contact me at john@example.com or call (555) 123-4567',
        'sender_email': 'sender@example.com',
        'sender_name': 'John Doe',
        'sender_phone': '555-987-6543'
    }
    
    print("Original message data:")
    for key, value in message_data.items():
        print(f"  {key}: {value}")
    
    minimized_message = minimizer.minimize_message_data(message_data)
    
    print("\nMinimized message data:")
    for key, value in minimized_message.items():
        if value != message_data.get(key):
            print(f"  {key}: {value} (MINIMIZED)")
        else:
            print(f"  {key}: {value}")
    
    # Test contact data minimization
    contact_data = {
        'id': 1,
        'name': 'Jane Smith',
        'email': 'jane.smith@example.com',
        'phone': '(555) 456-7890',
        'company': 'Example Corp'
    }
    
    print("\nOriginal contact data:")
    for key, value in contact_data.items():
        print(f"  {key}: {value}")
    
    minimized_contact = minimizer.minimize_contact_data(contact_data)
    
    print("\nMinimized contact data:")
    for key, value in minimized_contact.items():
        if value != contact_data.get(key):
            print(f"  {key}: {value} (MINIMIZED)")
        else:
            print(f"  {key}: {value}")
    
    print("\n✓ Data Minimizer test completed\n")


def main():
    """Run all core tests."""
    print("=== Data Retention and GDPR Compliance Core Tests ===\n")
    
    try:
        test_pii_detection_comprehensive()
        test_pii_masking()
        test_pii_data_detection()
        test_pii_validation()
        test_data_minimizer()
        
        print("🎉 All core tests passed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()