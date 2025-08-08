"""Validation utilities."""
import re
from typing import Any, Dict, List, Optional
from marshmallow import Schema, ValidationError as MarshmallowValidationError
from app.utils.errors import ValidationError


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate phone number format."""
    # Basic international phone number validation
    pattern = r'^\+?[1-9]\d{1,14}$'
    return bool(re.match(pattern, phone.replace(' ', '').replace('-', '')))


def validate_vat_number(vat_number: str, country_code: str = None) -> bool:
    """Validate VAT number format."""
    if not vat_number:
        return False
    
    # Remove spaces and convert to uppercase
    vat_clean = vat_number.replace(' ', '').upper()
    
    # Basic VAT number patterns by country
    patterns = {
        'DE': r'^DE\d{9}$',  # Germany
        'FR': r'^FR[A-Z0-9]{2}\d{9}$',  # France
        'GB': r'^GB\d{9}$|^GB\d{12}$|^GBGD\d{3}$|^GBHA\d{3}$',  # UK
        'IT': r'^IT\d{11}$',  # Italy
        'ES': r'^ES[A-Z0-9]\d{7}[A-Z0-9]$',  # Spain
        'NL': r'^NL\d{9}B\d{2}$',  # Netherlands
        'BE': r'^BE0\d{9}$',  # Belgium
        'AT': r'^ATU\d{8}$',  # Austria
        'PL': r'^PL\d{10}$',  # Poland
        'CZ': r'^CZ\d{8,10}$',  # Czech Republic
    }
    
    if country_code and country_code in patterns:
        return bool(re.match(patterns[country_code], vat_clean))
    
    # Generic VAT number validation (2-letter country code + digits/letters)
    return bool(re.match(r'^[A-Z]{2}[A-Z0-9]{2,12}$', vat_clean))


def validate_lei_code(lei_code: str) -> bool:
    """Validate LEI (Legal Entity Identifier) code format."""
    if not lei_code:
        return False
    
    # LEI is 20 characters: 4-char prefix + 2-char country + 2-char checksum + 10-char entity
    pattern = r'^[A-Z0-9]{4}[A-Z]{2}[A-Z0-9]{2}[A-Z0-9]{10}$'
    return bool(re.match(pattern, lei_code.upper()))


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
    """Validate that required fields are present and not empty."""
    missing_fields = []
    empty_fields = []
    
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
        elif not data[field] or (isinstance(data[field], str) and not data[field].strip()):
            empty_fields.append(field)
    
    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            details={'missing_fields': missing_fields}
        )
    
    if empty_fields:
        raise ValidationError(
            f"Empty required fields: {', '.join(empty_fields)}",
            details={'empty_fields': empty_fields}
        )


def validate_schema(schema: Schema, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate data against Marshmallow schema."""
    try:
        return schema.load(data)
    except MarshmallowValidationError as e:
        raise ValidationError(
            "Validation failed",
            details={'validation_errors': e.messages}
        )


def validate_pagination_params(page: Any, per_page: Any, max_per_page: int = 100) -> tuple:
    """Validate and normalize pagination parameters."""
    try:
        page = int(page) if page else 1
        per_page = int(per_page) if per_page else 20
    except (ValueError, TypeError):
        raise ValidationError("Invalid pagination parameters")
    
    if page < 1:
        raise ValidationError("Page number must be positive")
    
    if per_page < 1:
        raise ValidationError("Per page value must be positive")
    
    if per_page > max_per_page:
        raise ValidationError(f"Per page value cannot exceed {max_per_page}")
    
    return page, per_page


def validate_date_range(start_date: Any, end_date: Any) -> None:
    """Validate date range."""
    if start_date and end_date:
        if start_date > end_date:
            raise ValidationError("Start date cannot be after end date")


def validate_file_upload(file, allowed_extensions: List[str], max_size: int) -> None:
    """Validate file upload."""
    if not file or not file.filename:
        raise ValidationError("No file provided")
    
    # Check file extension
    if '.' not in file.filename:
        raise ValidationError("File must have an extension")
    
    extension = file.filename.rsplit('.', 1)[1].lower()
    if extension not in allowed_extensions:
        raise ValidationError(
            f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Check file size (if file has seek method)
    if hasattr(file, 'seek'):
        file.seek(0, 2)  # Seek to end
        size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if size > max_size:
            raise ValidationError(f"File size exceeds maximum allowed size of {max_size} bytes")


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """Sanitize string input."""
    if not isinstance(value, str):
        return str(value)
    
    # Strip whitespace
    value = value.strip()
    
    # Truncate if max_length specified
    if max_length and len(value) > max_length:
        value = value[:max_length]
    
    return value


def validate_json_structure(data: Any, required_keys: List[str] = None) -> None:
    """Validate JSON structure."""
    if not isinstance(data, dict):
        raise ValidationError("Data must be a JSON object")
    
    if required_keys:
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise ValidationError(
                f"Missing required keys: {', '.join(missing_keys)}",
                details={'missing_keys': missing_keys}
            )


class BaseValidator:
    """Base validator class."""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.errors = {}
    
    def add_error(self, field: str, message: str):
        """Add validation error."""
        if field not in self.errors:
            self.errors[field] = []
        self.errors[field].append(message)
    
    def is_valid(self) -> bool:
        """Check if validation passed."""
        return len(self.errors) == 0
    
    def validate(self) -> Dict[str, Any]:
        """Perform validation and return cleaned data."""
        self.run_validation()
        
        if not self.is_valid():
            raise ValidationError(
                "Validation failed",
                details={'validation_errors': self.errors}
            )
        
        return self.get_cleaned_data()
    
    def run_validation(self):
        """Override this method to implement validation logic."""
        pass
    
    def get_cleaned_data(self) -> Dict[str, Any]:
        """Override this method to return cleaned data."""
        return self.data