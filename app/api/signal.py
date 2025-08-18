"""Signal integration API endpoints."""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, ValidationError

from app.models import Channel, Tenant, User
from app.services.signal_cli_service import get_signal_cli_service
from app.utils.database import db
from app.utils.response import success_response, error_response
from app.utils.auth import require_permission
import structlog

logger = structlog.get_logger()

signal_bp = Blueprint('signal', __name__)


class SignalInstallSchema(Schema):
    """Schema for Signal CLI installation."""
    version = fields.Str(load_default="latest")


class SignalRegisterSchema(Schema):
    """Schema for Signal phone number registration."""
    phone_number = fields.Str(required=True)
    captcha = fields.Str(load_default=None)


class SignalVerifySchema(Schema):
    """Schema for Signal phone number verification."""
    phone_number = fields.Str(required=True)
    verification_code = fields.Str(required=True)


class SignalChannelSchema(Schema):
    """Schema for creating Signal channel."""
    phone_number = fields.Str(required=True)
    name = fields.Str(load_default=None)
    auto_response = fields.Bool(load_default=True)
    polling_interval = fields.Int(load_default=2)


@signal_bp.route('/status', methods=['GET'])
@jwt_required()
@require_permission('channels:read')
def get_signal_status():
    """Get Signal CLI installation and service status."""
    try:
        signal_service = get_signal_cli_service()
        
        # Get installation status
        installation_status = signal_service.get_installation_status()
        
        # Get tenant's Signal channels
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        channels = Channel.query.filter_by(
            tenant_id=user.tenant_id,
            type="signal"
        ).all()
        
        channel_info = []
        for channel in channels:
            channel_info.append({
                "id": channel.id,
                "name": channel.name,
                "phone_number": channel.config.get("phone_number"),
                "is_active": channel.is_active,
                "created_at": channel.created_at.isoformat()
            })
        
        return success_response({
            "installation": installation_status,
            "channels": channel_info
        })
        
    except Exception as e:
        logger.error("Failed to get Signal status", error=str(e))
        return error_response(
            error_code="SIGNAL_STATUS_ERROR",
            message="Failed to get Signal status",
            details=str(e)
        )


@signal_bp.route('/install', methods=['POST'])
@jwt_required()
@require_permission('channels:manage')
def install_signal_cli():
    """Install Signal CLI."""
    try:
        schema = SignalInstallSchema()
        data = schema.load(request.get_json() or {})
        
        signal_service = get_signal_cli_service()
        
        # Check if already installed
        if signal_service.is_installed:
            return success_response({
                "message": "Signal CLI is already installed"
            })
        
        # Install Signal CLI
        import asyncio
        success, message = asyncio.run(signal_service.install_signal_cli(data["version"]))
        
        if success:
            logger.info("Signal CLI installed successfully", version=data["version"])
            return success_response({
                "message": message,
                "installation_status": signal_service.get_installation_status()
            })
        else:
            logger.error("Signal CLI installation failed", message=message)
            return error_response(
                error_code="SIGNAL_INSTALL_FAILED",
                message=message
            )
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message="Invalid input data",
            details=e.messages
        )
    except Exception as e:
        logger.error("Error installing Signal CLI", error=str(e))
        return error_response(
            error_code="SIGNAL_INSTALL_ERROR",
            message="Failed to install Signal CLI",
            details=str(e)
        )


@signal_bp.route('/register', methods=['POST'])
@jwt_required()
@require_permission('channels:manage')
def register_phone_number():
    """Register a phone number with Signal."""
    try:
        schema = SignalRegisterSchema()
        data = schema.load(request.get_json())
        
        signal_service = get_signal_cli_service()
        
        if not signal_service.is_installed:
            return error_response(
                error_code="SIGNAL_NOT_INSTALLED",
                message="Signal CLI is not installed. Please install it first."
            )
        
        # Register phone number
        import asyncio
        success, message = asyncio.run(signal_service.register_phone_number(
            data["phone_number"], 
            data.get("captcha")
        ))
        
        if success:
            logger.info("Phone number registration initiated", 
                       phone_number=data["phone_number"])
            return success_response({
                "message": message,
                "phone_number": data["phone_number"],
                "next_step": "verification"
            })
        else:
            logger.error("Phone number registration failed", 
                        phone_number=data["phone_number"], message=message)
            return error_response(
                error_code="SIGNAL_REGISTRATION_FAILED",
                message=message
            )
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message="Invalid input data",
            details=e.messages
        )
    except Exception as e:
        logger.error("Error registering phone number", error=str(e))
        return error_response(
            error_code="SIGNAL_REGISTRATION_ERROR",
            message="Failed to register phone number",
            details=str(e)
        )


@signal_bp.route('/verify', methods=['POST'])
@jwt_required()
@require_permission('channels:manage')
def verify_phone_number():
    """Verify phone number with SMS code."""
    try:
        schema = SignalVerifySchema()
        data = schema.load(request.get_json())
        
        signal_service = get_signal_cli_service()
        
        if not signal_service.is_installed:
            return error_response(
                error_code="SIGNAL_NOT_INSTALLED",
                message="Signal CLI is not installed. Please install it first."
            )
        
        # Verify phone number
        import asyncio
        success, message = asyncio.run(signal_service.verify_phone_number(
            data["phone_number"],
            data["verification_code"]
        ))
        
        if success:
            logger.info("Phone number verified successfully", 
                       phone_number=data["phone_number"])
            
            # Get account info
            account_info = asyncio.run(signal_service.get_account_info(data["phone_number"]))
            
            return success_response({
                "message": message,
                "phone_number": data["phone_number"],
                "account_info": account_info,
                "next_step": "create_channel"
            })
        else:
            logger.error("Phone number verification failed", 
                        phone_number=data["phone_number"], message=message)
            return error_response(
                error_code="SIGNAL_VERIFICATION_FAILED",
                message=message
            )
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message="Invalid input data",
            details=e.messages
        )
    except Exception as e:
        logger.error("Error verifying phone number", error=str(e))
        return error_response(
            error_code="SIGNAL_VERIFICATION_ERROR",
            message="Failed to verify phone number",
            details=str(e)
        )


@signal_bp.route('/channels', methods=['POST'])
@jwt_required()
@require_permission('channels:manage')
def create_signal_channel():
    """Create a Signal channel for the tenant."""
    try:
        schema = SignalChannelSchema()
        data = schema.load(request.get_json())
        
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        signal_service = get_signal_cli_service()
        
        # Check if phone number is registered
        import asyncio
        accounts = asyncio.run(signal_service.list_accounts())
        if data["phone_number"] not in accounts:
            return error_response(
                error_code="PHONE_NOT_REGISTERED",
                message="Phone number is not registered with Signal. Please register and verify it first."
            )
        
        # Check if channel already exists
        existing_channel = Channel.query.filter_by(
            tenant_id=user.tenant_id,
            type="signal"
        ).filter(
            Channel.config.op('->>')('phone_number') == data["phone_number"]
        ).first()
        
        if existing_channel:
            return error_response(
                error_code="CHANNEL_EXISTS",
                message="Signal channel for this phone number already exists"
            )
        
        # Create channel
        channel = Channel(
            tenant_id=user.tenant_id,
            name=data.get("name") or f"Signal ({data['phone_number']})",
            type="signal",
            config={
                "phone_number": data["phone_number"],
                "auto_response": data["auto_response"],
                "polling_interval": data["polling_interval"],
                "enabled": True
            },
            is_active=True
        )
        
        db.session.add(channel)
        db.session.commit()
        
        logger.info("Signal channel created", 
                   tenant_id=user.tenant_id, 
                   channel_id=channel.id,
                   phone_number=data["phone_number"])
        
        return success_response({
            "message": "Signal channel created successfully",
            "channel": {
                "id": channel.id,
                "name": channel.name,
                "phone_number": data["phone_number"],
                "config": channel.config,
                "created_at": channel.created_at.isoformat()
            }
        })
        
    except ValidationError as e:
        return error_response(
            error_code="VALIDATION_ERROR",
            message="Invalid input data",
            details=e.messages
        )
    except Exception as e:
        logger.error("Error creating Signal channel", error=str(e))
        db.session.rollback()
        return error_response(
            error_code="CHANNEL_CREATION_ERROR",
            message="Failed to create Signal channel",
            details=str(e)
        )