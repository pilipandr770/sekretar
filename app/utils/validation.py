"""Validation utilities for API endpoints."""
from flask import request
from flask_babel import gettext as _
from app.utils.exceptions import ValidationError


def validate_json(request_obj, required_fields=None):
    """Validate JSON request data."""
    if not request_obj.is_json:
        raise ValidationError(_('Request must be JSON'))
    
    data = request_obj.get_json()
    if data is None:
        raise ValidationError(_('Invalid JSON data'))
    
    if required_fields:
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValidationError(
                _('Missing required fields: %(fields)s', 
                  fields=', '.join(missing_fields))
            )
    
    return data


def validate_pagination(request_obj, max_per_page=100):
    """Validate and return pagination parameters."""
    try:
        page = int(request_obj.args.get('page', 1))
        per_page = int(request_obj.args.get('per_page', 20))
    except (ValueError, TypeError):
        raise ValidationError(_('Invalid pagination parameters'))
    
    if page < 1:
        raise ValidationError(_('Page number must be positive'))
    
    if per_page < 1:
        raise ValidationError(_('Per page value must be positive'))
    
    if per_page > max_per_page:
        raise ValidationError(
            _('Per page value cannot exceed %(max)d', max=max_per_page)
        )
    
    offset = (page - 1) * per_page
    return page, per_page, offset