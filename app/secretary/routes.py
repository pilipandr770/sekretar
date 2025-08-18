"""Secretary setup and management routes."""
from flask import request, jsonify, current_app
from app.secretary import secretary_bp
from app.models.company import Company, CommunicationChannel, KnowledgeDocument
from app.models.kyb_monitoring import Counterparty
from app.services.kyb_service import KYBService
from app.utils.response import success_response, error_response
from app import db
import uuid


@secretary_bp.route('/companies', methods=['POST'])
def create_company():
    """Create a new company profile."""
    try:
        data = request.get_json()
        
        if not data or not data.get('name'):
            return error_response(
                error_code='VALIDATION_ERROR',
                message='Company name is required',
                status_code=400
            )
        
        company = Company(
            name=data['name'],
            vat_number=data.get('vat_number'),
            address=data.get('address'),
            phone=data.get('phone'),
            email=data.get('email'),
            business_area=data.get('business_area'),
            ai_instructions=data.get('ai_instructions')
        )
        
        db.session.add(company)
        db.session.commit()
        
        return success_response(
            message='Company created successfully',
            data=company.to_dict(),
            status_code=201
        )
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating company: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to create company',
            status_code=500
        )


@secretary_bp.route('/companies/<company_id>', methods=['GET'])
def get_company(company_id):
    """Get company profile."""
    try:
        company = Company.query.get(company_id)
        if not company:
            return error_response(
                error_code='NOT_FOUND_ERROR',
                message='Company not found',
                status_code=404
            )
        
        # Include channels and documents count
        company_data = company.to_dict()
        company_data['channels_count'] = len(company.channels)
        company_data['documents_count'] = len(company.documents)
        company_data['counterparties_count'] = len(company.counterparties)
        
        return success_response(
            message='Company retrieved successfully',
            data=company_data
        )
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving company: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to retrieve company',
            status_code=500
        )


@secretary_bp.route('/companies/<company_id>', methods=['PUT'])
def update_company(company_id):
    """Update company profile."""
    try:
        company = Company.query.get(company_id)
        if not company:
            return error_response(
                error_code='NOT_FOUND_ERROR',
                message='Company not found',
                status_code=404
            )
        
        data = request.get_json()
        if not data:
            return error_response(
                error_code='VALIDATION_ERROR',
                message='Request body is required',
                status_code=400
            )
        
        # Update fields
        if 'name' in data:
            company.name = data['name']
        if 'vat_number' in data:
            company.vat_number = data['vat_number']
        if 'address' in data:
            company.address = data['address']
        if 'phone' in data:
            company.phone = data['phone']
        if 'email' in data:
            company.email = data['email']
        if 'business_area' in data:
            company.business_area = data['business_area']
        if 'ai_instructions' in data:
            company.ai_instructions = data['ai_instructions']
        
        db.session.commit()
        
        return success_response(
            message='Company updated successfully',
            data=company.to_dict()
        )
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating company: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to update company',
            status_code=500
        )


@secretary_bp.route('/companies/<company_id>/channels', methods=['GET'])
def get_company_channels(company_id):
    """Get communication channels for a company."""
    try:
        company = Company.query.get(company_id)
        if not company:
            return error_response(
                error_code='NOT_FOUND_ERROR',
                message='Company not found',
                status_code=404
            )
        
        channels = [channel.to_dict() for channel in company.channels]
        
        return success_response(
            message='Channels retrieved successfully',
            data=channels
        )
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving channels: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to retrieve channels',
            status_code=500
        )


@secretary_bp.route('/companies/<company_id>/channels', methods=['POST'])
def create_channel(company_id):
    """Create a communication channel."""
    try:
        company = Company.query.get(company_id)
        if not company:
            return error_response(
                error_code='NOT_FOUND_ERROR',
                message='Company not found',
                status_code=404
            )
        
        data = request.get_json()
        if not data or not data.get('channel_type'):
            return error_response(
                error_code='VALIDATION_ERROR',
                message='Channel type is required',
                status_code=400
            )
        
        # Validate channel type
        valid_types = ['phone', 'email', 'telegram', 'whatsapp', 'facebook', 'instagram', 'twitter']
        if data['channel_type'] not in valid_types:
            return error_response(
                error_code='VALIDATION_ERROR',
                message=f'Invalid channel type. Valid types: {", ".join(valid_types)}',
                status_code=400
            )
        
        channel = CommunicationChannel(
            company_id=company.id,
            channel_type=data['channel_type'],
            config=data.get('config', {}),
            enabled=data.get('enabled', True)
        )
        
        db.session.add(channel)
        db.session.commit()
        
        return success_response(
            message='Channel created successfully',
            data=channel.to_dict(),
            status_code=201
        )
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating channel: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to create channel',
            status_code=500
        )


@secretary_bp.route('/companies/<company_id>/counterparties', methods=['GET'])
def get_counterparties(company_id):
    """Get counterparties for a company."""
    try:
        company = Company.query.get(company_id)
        if not company:
            return error_response(
                error_code='NOT_FOUND_ERROR',
                message='Company not found',
                status_code=404
            )
        
        counterparties = [cp.to_dict() for cp in company.counterparties]
        
        return success_response(
            message='Counterparties retrieved successfully',
            data=counterparties
        )
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving counterparties: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to retrieve counterparties',
            status_code=500
        )


@secretary_bp.route('/companies/<company_id>/counterparties', methods=['POST'])
def create_counterparty(company_id):
    """Create a new counterparty."""
    try:
        company = Company.query.get(company_id)
        if not company:
            return error_response(
                error_code='NOT_FOUND_ERROR',
                message='Company not found',
                status_code=404
            )
        
        data = request.get_json()
        if not data or not data.get('name'):
            return error_response(
                error_code='VALIDATION_ERROR',
                message='Counterparty name is required',
                status_code=400
            )
        
        counterparty = Counterparty(
            company_id=company.id,
            name=data['name'],
            vat_number=data.get('vat_number'),
            address=data.get('address'),
            country_code=data.get('country_code'),
            lei_code=data.get('lei_code'),
            registration_number=data.get('registration_number')
        )
        
        db.session.add(counterparty)
        db.session.commit()
        
        # Trigger KYB check if auto-check is enabled
        if data.get('auto_check', True):
            try:
                kyb_result = KYBService.perform_full_kyb_check(str(counterparty.id))
                counterparty_data = counterparty.to_dict()
                counterparty_data['kyb_result'] = kyb_result
            except Exception as e:
                current_app.logger.error(f"KYB check failed: {str(e)}")
                counterparty_data = counterparty.to_dict()
                counterparty_data['kyb_result'] = {'error': 'KYB check failed'}
        else:
            counterparty_data = counterparty.to_dict()
        
        return success_response(
            message='Counterparty created successfully',
            data=counterparty_data,
            status_code=201
        )
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating counterparty: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to create counterparty',
            status_code=500
        )


@secretary_bp.route('/counterparties/<counterparty_id>/kyb-check', methods=['POST'])
def perform_kyb_check(counterparty_id):
    """Perform KYB check for a counterparty."""
    try:
        counterparty = Counterparty.query.get(counterparty_id)
        if not counterparty:
            return error_response(
                error_code='NOT_FOUND_ERROR',
                message='Counterparty not found',
                status_code=404
            )
        
        result = KYBService.perform_full_kyb_check(counterparty_id)
        
        return success_response(
            message='KYB check completed',
            data=result
        )
        
    except Exception as e:
        current_app.logger.error(f"Error performing KYB check: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to perform KYB check',
            status_code=500
        )


@secretary_bp.route('/companies/<company_id>/kyb-summary', methods=['GET'])
def get_kyb_summary(company_id):
    """Get KYB summary for a company."""
    try:
        company = Company.query.get(company_id)
        if not company:
            return error_response(
                error_code='NOT_FOUND_ERROR',
                message='Company not found',
                status_code=404
            )
        
        summary = KYBService.get_counterparty_summary(company_id)
        
        return success_response(
            message='KYB summary retrieved successfully',
            data=summary
        )
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving KYB summary: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to retrieve KYB summary',
            status_code=500
        )


@secretary_bp.route('/vat-check', methods=['POST'])
def quick_vat_check():
    """Quick VAT number check without saving to database."""
    try:
        data = request.get_json()
        if not data or not data.get('vat_number') or not data.get('country_code'):
            return error_response(
                error_code='VALIDATION_ERROR',
                message='VAT number and country code are required',
                status_code=400
            )
        
        result = KYBService.check_vat_number(
            data['vat_number'],
            data['country_code']
        )
        
        return success_response(
            message='VAT check completed',
            data=result
        )
        
    except Exception as e:
        current_app.logger.error(f"Error performing VAT check: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to perform VAT check',
            status_code=500
        )


@secretary_bp.route('/monitoring/run', methods=['POST'])
def run_monitoring():
    """Manually trigger monitoring tasks."""
    try:
        from app.services.monitoring_service import MonitoringService
        
        result = MonitoringService.schedule_monitoring_tasks()
        
        return success_response(
            message='Monitoring tasks completed',
            data=result
        )
        
    except Exception as e:
        current_app.logger.error(f"Error running monitoring: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to run monitoring tasks',
            status_code=500
        )


@secretary_bp.route('/companies/<company_id>/monitoring-report', methods=['GET'])
def get_monitoring_report(company_id):
    """Get monitoring report for a company."""
    try:
        from app.services.monitoring_service import MonitoringService
        
        company = Company.query.get(company_id)
        if not company:
            return error_response(
                error_code='NOT_FOUND_ERROR',
                message='Company not found',
                status_code=404
            )
        
        report = MonitoringService.generate_monitoring_report(company_id)
        
        return success_response(
            message='Monitoring report generated',
            data=report
        )
        
    except Exception as e:
        current_app.logger.error(f"Error generating monitoring report: {str(e)}")
        return error_response(
            error_code='INTERNAL_ERROR',
            message='Failed to generate monitoring report',
            status_code=500
        )