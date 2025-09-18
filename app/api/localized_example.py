"""Example API endpoint demonstrating comprehensive localization features."""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _
from marshmallow import Schema, fields, ValidationError as MarshmallowValidationError

from app.models import Contact, db
from app.utils.response import (
    localized_success_response, localized_error_response, 
    business_validation_error_response, api_method_response
)
from app.utils.localized_validators import (
    LocalizedFormValidator, create_field_validator, 
    validate_api_request, APIValidationMixin
)
from app.utils.decorators import require_permission, log_api_call
import structlog

logger = structlog.get_logger()

# Create blueprint
localized_example_bp = Blueprint('localized_example', __name__, url_prefix='/api/v1/localized-example')


class ContactSchema(Schema):
    """Contact schema with localized validation."""
    first_name = fields.Str(required=False, allow_none=True)
    last_name = fields.Str(required=False, allow_none=True)
    company = fields.Str(required=False, allow_none=True)
    email = fields.Email(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True)
    contact_type = fields.Str(required=False, validate=fields.validate.OneOf(['prospect', 'customer', 'partner']))


class LocalizedContactAPI(APIValidationMixin):
    """Example API class with comprehensive localization support."""
    
    @localized_example_bp.route('/contacts', methods=['POST'])
    @jwt_required()
    @require_permission('manage_crm')
    @log_api_call('create_contact')
    def create_contact(self):
        """Create contact with comprehensive localization."""
        try:
            # Validate JSON request structure
            validation_error = self.validate_json_request(
                required_fields=[],  # No strictly required fields for this example
                optional_fields=['first_name', 'last_name', 'company', 'email', 'phone', 'contact_type']
            )
            if validation_error:
                return validation_error
            
            user = get_current_user()
            if not user or not user.tenant:
                return localized_error_response(
                    error_code='TENANT_NOT_FOUND',
                    message_key='Your organization was not found',
                    status_code=404
                )
            
            data = request.get_json()
            
            # Use Marshmallow schema validation with localization
            validated_data, validation_error = validate_api_request(ContactSchema, data)
            if validation_error:
                return validation_error
            
            # Custom business validation with localized messages
            business_errors = self._validate_contact_business_rules(validated_data, user.tenant_id)
            if business_errors:
                return business_validation_error_response(
                    field_errors=business_errors,
                    message_key='Contact validation failed'
                )
            
            # Create contact
            contact = Contact.create(
                tenant_id=user.tenant_id,
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
                company=validated_data.get('company', ''),
                email=validated_data.get('email', ''),
                phone=validated_data.get('phone', ''),
                contact_type=validated_data.get('contact_type', 'prospect')
            )
            
            logger.info(
                "Contact created",
                contact_id=contact.id,
                tenant_id=user.tenant_id,
                user_id=user.id
            )
            
            # Return localized success response
            return api_method_response(
                method='POST',
                resource='contact',
                success=True,
                data=contact.to_dict()
            )
            
        except Exception as e:
            logger.error("Failed to create contact", error=str(e), exc_info=True)
            return localized_error_response(
                error_code='INTERNAL_ERROR',
                message_key='Failed to create contact',
                status_code=500
            )
    
    def _validate_contact_business_rules(self, data: dict, tenant_id: int) -> dict:
        """Validate business rules with localized error messages."""
        errors = {}
        
        # At least one name field or company must be provided
        if not data.get('first_name') and not data.get('last_name') and not data.get('company'):
            errors['name'] = [_('At least one of first name, last name, or company is required')]
        
        # Check for duplicate email within tenant
        if data.get('email'):
            existing_contact = Contact.query.filter_by(
                tenant_id=tenant_id,
                email=data['email']
            ).first()
            
            if existing_contact:
                errors['email'] = [_('A contact with this email address already exists')]
        
        # Validate contact type
        valid_types = ['prospect', 'customer', 'partner']
        if data.get('contact_type') and data['contact_type'] not in valid_types:
            type_list = ', '.join([_(t) for t in valid_types])
            errors['contact_type'] = [_('Invalid contact type. Valid types are: {types}', types=type_list)]
        
        return errors
    
    @localized_example_bp.route('/contacts', methods=['GET'])
    @jwt_required()
    @require_permission('view_crm')
    @log_api_call('list_contacts')
    def list_contacts(self):
        """List contacts with localized pagination and filtering."""
        try:
            # Validate pagination parameters
            validation_error = self.validate_pagination_request()
            if validation_error:
                return validation_error
            
            user = get_current_user()
            if not user or not user.tenant:
                return localized_error_response(
                    error_code='TENANT_NOT_FOUND',
                    message_key='Your organization was not found',
                    status_code=404
                )
            
            # Get pagination parameters
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            
            # Get filter parameters
            contact_type = request.args.get('type')
            search = request.args.get('search')
            
            # Build query
            query = Contact.query.filter_by(tenant_id=user.tenant_id)
            
            if contact_type:
                if contact_type not in ['prospect', 'customer', 'partner']:
                    return business_validation_error_response({
                        'type': [_('Invalid contact type filter')]
                    })
                query = query.filter_by(contact_type=contact_type)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    db.or_(
                        Contact.first_name.ilike(search_term),
                        Contact.last_name.ilike(search_term),
                        Contact.company.ilike(search_term),
                        Contact.email.ilike(search_term)
                    )
                )
            
            # Execute paginated query
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            # Prepare response data with localized display fields
            contacts = []
            for contact in pagination.items:
                contact_data = contact.to_dict()
                # Localize display fields
                if contact_data.get('contact_type'):
                    contact_data['contact_type_display'] = _(contact_data['contact_type'])
                contacts.append(contact_data)
            
            # Return localized paginated response
            from app.utils.response import localized_paginated_response
            return localized_paginated_response(
                items=contacts,
                page=page,
                per_page=per_page,
                total=pagination.total,
                message_key='Contacts retrieved successfully'
            )
            
        except Exception as e:
            logger.error("Failed to list contacts", error=str(e), exc_info=True)
            return localized_error_response(
                error_code='INTERNAL_ERROR',
                message_key='Failed to retrieve contacts',
                status_code=500
            )
    
    @localized_example_bp.route('/contacts/<int:contact_id>', methods=['PUT'])
    @jwt_required()
    @require_permission('manage_crm')
    @log_api_call('update_contact')
    def update_contact(self, contact_id: int):
        """Update contact with comprehensive validation and localization."""
        try:
            user = get_current_user()
            if not user or not user.tenant:
                return localized_error_response(
                    error_code='TENANT_NOT_FOUND',
                    message_key='Your organization was not found',
                    status_code=404
                )
            
            # Find contact
            contact = Contact.query.filter_by(
                id=contact_id,
                tenant_id=user.tenant_id
            ).first()
            
            if not contact:
                return localized_error_response(
                    error_code='CONTACT_NOT_FOUND',
                    message_key='Contact not found',
                    status_code=404
                )
            
            # Validate JSON request
            validation_error = self.validate_json_request()
            if validation_error:
                return validation_error
            
            data = request.get_json()
            
            # Use custom form validator for complex validation
            validator = LocalizedFormValidator(data)
            
            # Define field validators
            if 'first_name' in data:
                validator.validate_field('first_name', [
                    create_field_validator('first_name', 'string', max_length=100)
                ])
            
            if 'last_name' in data:
                validator.validate_field('last_name', [
                    create_field_validator('last_name', 'string', max_length=100)
                ])
            
            if 'email' in data:
                validator.validate_field('email', [
                    create_field_validator('email', 'email')
                ])
            
            if 'contact_type' in data:
                validator.validate_field('contact_type', [
                    create_field_validator('contact_type', 'choice', choices=['prospect', 'customer', 'partner'])
                ])
            
            # Check validation results
            validation_response = validator.to_response()
            if validation_response:
                return validation_response
            
            # Additional business validation
            business_errors = {}
            
            # Check for duplicate email (excluding current contact)
            if data.get('email') and data['email'] != contact.email:
                existing_contact = Contact.query.filter_by(
                    tenant_id=user.tenant_id,
                    email=data['email']
                ).filter(Contact.id != contact_id).first()
                
                if existing_contact:
                    business_errors['email'] = [_('A contact with this email address already exists')]
            
            if business_errors:
                return business_validation_error_response(
                    field_errors=business_errors,
                    message_key='Contact update validation failed'
                )
            
            # Update contact
            cleaned_data = validator.get_cleaned_data()
            for field, value in cleaned_data.items():
                if hasattr(contact, field):
                    setattr(contact, field, value)
            
            db.session.commit()
            
            logger.info(
                "Contact updated",
                contact_id=contact.id,
                tenant_id=user.tenant_id,
                user_id=user.id
            )
            
            # Return localized success response
            return api_method_response(
                method='PUT',
                resource='contact',
                success=True,
                data=contact.to_dict()
            )
            
        except Exception as e:
            logger.error("Failed to update contact", error=str(e), exc_info=True)
            return localized_error_response(
                error_code='INTERNAL_ERROR',
                message_key='Failed to update contact',
                status_code=500
            )


# Initialize the API class
localized_contact_api = LocalizedContactAPI()


@localized_example_bp.route('/validation-demo', methods=['POST'])
@jwt_required()
def validation_demo():
    """Demonstrate various validation error localizations."""
    data = request.get_json() or {}
    
    # Create form validator
    validator = LocalizedFormValidator(data)
    
    # Validate different field types
    validator.validate_field('required_field', [
        create_field_validator('required_field', 'string', required=True)
    ])
    
    validator.validate_field('email_field', [
        create_field_validator('email_field', 'email')
    ])
    
    validator.validate_field('number_field', [
        create_field_validator('number_field', 'integer', min_value=1, max_value=100)
    ])
    
    validator.validate_field('choice_field', [
        create_field_validator('choice_field', 'choice', choices=['option1', 'option2', 'option3'])
    ])
    
    validator.validate_field('text_field', [
        create_field_validator('text_field', 'string', min_length=5, max_length=50)
    ])
    
    # Return validation results
    if validator.is_valid():
        return localized_success_response(
            message_key='All validations passed',
            data=validator.get_cleaned_data()
        )
    else:
        return validator.to_response()


@localized_example_bp.route('/error-demo/<error_type>', methods=['GET'])
@jwt_required()
def error_demo(error_type: str):
    """Demonstrate different types of localized error responses."""
    
    if error_type == 'validation':
        return business_validation_error_response({
            'field1': [_('This field has an error')],
            'field2': [_('Another validation error'), _('Multiple errors possible')]
        })
    
    elif error_type == 'not_found':
        return localized_error_response(
            error_code='RESOURCE_NOT_FOUND',
            message_key='The requested {resource} was not found',
            resource=_('item'),
            status_code=404
        )
    
    elif error_type == 'business':
        return localized_error_response(
            error_code='BUSINESS_RULE_VIOLATION',
            message_key='Business rule violated: {rule}',
            rule=_('Maximum limit exceeded'),
            status_code=422
        )
    
    elif error_type == 'permission':
        return localized_error_response(
            error_code='INSUFFICIENT_PERMISSIONS',
            message_key='You do not have permission to {action}',
            action=_('perform this action'),
            status_code=403
        )
    
    else:
        return localized_error_response(
            error_code='INVALID_ERROR_TYPE',
            message_key='Unknown error type: {type}',
            type=error_type,
            status_code=400
        )