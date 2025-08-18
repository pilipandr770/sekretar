"""Channel routes for managing communication channels."""
import asyncio
import logging
from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.channels import channels_bp
from app.channels.telegram_bot import get_telegram_bot_handler, initialize_telegram_bot
from app.services.telegram_service import get_telegram_service
from app.models import Channel, Tenant
from app.utils.response import success_response, error_response
from app.utils.decorators import tenant_required
from app.utils.database import db


@channels_bp.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """Handle Telegram webhook updates."""
    try:
        # Get update data
        update_data = request.get_json()
        if not update_data:
            return error_response(
                error_code="INVALID_REQUEST",
                message="No update data provided",
                status_code=400
            )
        
        # Use telegram service for processing
        telegram_service = get_telegram_service()
        
        # Process the update asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                telegram_service.process_webhook_update(update_data)
            )
        finally:
            loop.close()
        
        if "error" in result:
            return error_response(
                error_code="WEBHOOK_PROCESSING_ERROR",
                message=result["error"],
                status_code=500
            )
        
        return success_response(
            message="Webhook processed successfully",
            data=result
        )
        
    except Exception as e:
        current_app.logger.error(f"Telegram webhook error: {str(e)}")
        return error_response(
            error_code="WEBHOOK_ERROR",
            message="Failed to process webhook",
            status_code=500,
            details=str(e)
        )


@channels_bp.route('/telegram/setup', methods=['POST'])
@jwt_required()
@tenant_required
def setup_telegram_channel():
    """Set up Telegram channel for a tenant."""
    try:
        tenant_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        if not data or 'bot_token' not in data:
            return error_response(
                error_code="VALIDATION_ERROR",
                message="Bot token is required",
                status_code=400
            )
        
        bot_token = data['bot_token']
        channel_name = data.get('name', 'Telegram Bot')
        webhook_url = data.get('webhook_url')
        
        # Check if channel already exists
        existing_channel = Channel.query.filter_by(
            tenant_id=tenant_id,
            type='telegram'
        ).first()
        
        if existing_channel:
            return error_response(
                error_code="CHANNEL_EXISTS",
                message="Telegram channel already exists for this tenant",
                status_code=409
            )
        
        # Create channel
        channel = Channel.create_telegram_channel(
            tenant_id=tenant_id,
            name=channel_name,
            bot_token=bot_token,
            webhook_url=webhook_url
        )
        
        # Initialize bot handler
        try:
            bot_handler = get_telegram_bot_handler(bot_token, webhook_url)
            initialized = asyncio.run(bot_handler.initialize())
            
            if initialized:
                channel.mark_connected()
            else:
                channel.mark_disconnected("Failed to initialize bot")
                
        except Exception as e:
            channel.mark_disconnected(str(e))
        
        channel.save()
        
        return success_response(
            message="Telegram channel created successfully",
            data=channel.to_dict()
        )
        
    except Exception as e:
        current_app.logger.error(f"Error setting up Telegram channel: {str(e)}")
        return error_response(
            error_code="SETUP_ERROR",
            message="Failed to set up Telegram channel",
            status_code=500,
            details=str(e)
        )


@channels_bp.route('/telegram/test', methods=['POST'])
@jwt_required()
@tenant_required
def test_telegram_connection():
    """Test Telegram bot connection."""
    try:
        tenant_id = get_jwt_identity()
        
        # Get Telegram channel
        channel = Channel.query.filter_by(
            tenant_id=tenant_id,
            type='telegram'
        ).first()
        
        if not channel:
            return error_response(
                error_code="CHANNEL_NOT_FOUND",
                message="Telegram channel not found",
                status_code=404
            )
        
        # Test connection
        bot_token = channel.get_config('bot_token')
        if not bot_token:
            return error_response(
                error_code="INVALID_CONFIG",
                message="Bot token not configured",
                status_code=400
            )
        
        try:
            bot_handler = get_telegram_bot_handler(bot_token)
            # Test bot info
            bot_info = asyncio.run(bot_handler.bot.get_me())
            
            # Update channel status
            channel.mark_connected()
            channel.save()
            
            return success_response(
                message="Telegram connection test successful",
                data={
                    "bot_info": {
                        "id": bot_info.id,
                        "username": bot_info.username,
                        "first_name": bot_info.first_name,
                        "can_join_groups": bot_info.can_join_groups,
                        "can_read_all_group_messages": bot_info.can_read_all_group_messages,
                        "supports_inline_queries": bot_info.supports_inline_queries
                    },
                    "connection_status": "connected"
                }
            )
            
        except Exception as e:
            channel.mark_disconnected(str(e))
            channel.save()
            
            return error_response(
                error_code="CONNECTION_TEST_FAILED",
                message="Telegram connection test failed",
                status_code=500,
                details=str(e)
            )
        
    except Exception as e:
        current_app.logger.error(f"Error testing Telegram connection: {str(e)}")
        return error_response(
            error_code="TEST_ERROR",
            message="Failed to test Telegram connection",
            status_code=500,
            details=str(e)
        )


@channels_bp.route('/telegram/webhook/set', methods=['POST'])
@jwt_required()
@tenant_required
def set_telegram_webhook():
    """Set Telegram webhook URL."""
    try:
        tenant_id = get_jwt_identity()
        data = request.get_json()
        
        webhook_url = data.get('webhook_url') if data else None
        if not webhook_url:
            webhook_url = current_app.config.get('TELEGRAM_WEBHOOK_URL')
        
        if not webhook_url:
            return error_response(
                error_code="VALIDATION_ERROR",
                message="Webhook URL is required",
                status_code=400
            )
        
        # Get Telegram channel
        channel = Channel.query.filter_by(
            tenant_id=tenant_id,
            type='telegram'
        ).first()
        
        if not channel:
            return error_response(
                error_code="CHANNEL_NOT_FOUND",
                message="Telegram channel not found",
                status_code=404
            )
        
        # Set webhook
        bot_token = channel.get_config('bot_token')
        bot_handler = get_telegram_bot_handler(bot_token, webhook_url)
        
        success = asyncio.run(bot_handler.set_webhook())
        
        if success:
            # Update channel config
            channel.set_config('webhook_url', webhook_url)
            channel.save()
            
            return success_response(
                message="Webhook set successfully",
                data={"webhook_url": webhook_url}
            )
        else:
            return error_response(
                error_code="WEBHOOK_SET_FAILED",
                message="Failed to set webhook",
                status_code=500
            )
        
    except Exception as e:
        current_app.logger.error(f"Error setting Telegram webhook: {str(e)}")
        return error_response(
            error_code="WEBHOOK_ERROR",
            message="Failed to set webhook",
            status_code=500,
            details=str(e)
        )


@channels_bp.route('/telegram/webhook/remove', methods=['POST'])
@jwt_required()
@tenant_required
def remove_telegram_webhook():
    """Remove Telegram webhook."""
    try:
        tenant_id = get_jwt_identity()
        
        # Get Telegram channel
        channel = Channel.query.filter_by(
            tenant_id=tenant_id,
            type='telegram'
        ).first()
        
        if not channel:
            return error_response(
                error_code="CHANNEL_NOT_FOUND",
                message="Telegram channel not found",
                status_code=404
            )
        
        # Remove webhook
        bot_token = channel.get_config('bot_token')
        bot_handler = get_telegram_bot_handler(bot_token)
        
        success = asyncio.run(bot_handler.remove_webhook())
        
        if success:
            # Update channel config
            channel.set_config('webhook_url', None)
            channel.save()
            
            return success_response(
                message="Webhook removed successfully"
            )
        else:
            return error_response(
                error_code="WEBHOOK_REMOVE_FAILED",
                message="Failed to remove webhook",
                status_code=500
            )
        
    except Exception as e:
        current_app.logger.error(f"Error removing Telegram webhook: {str(e)}")
        return error_response(
            error_code="WEBHOOK_ERROR",
            message="Failed to remove webhook",
            status_code=500,
            details=str(e)
        )


@channels_bp.route('/telegram/send', methods=['POST'])
@jwt_required()
@tenant_required
def send_telegram_message():
    """Send message via Telegram bot."""
    try:
        tenant_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        if not data or 'chat_id' not in data or 'message' not in data:
            return error_response(
                error_code="VALIDATION_ERROR",
                message="Chat ID and message are required",
                status_code=400
            )
        
        chat_id = data['chat_id']
        message = data['message']
        parse_mode = data.get('parse_mode', 'HTML')
        
        # Get Telegram channel
        channel = Channel.query.filter_by(
            tenant_id=tenant_id,
            type='telegram'
        ).first()
        
        if not channel:
            return error_response(
                error_code="CHANNEL_NOT_FOUND",
                message="Telegram channel not found",
                status_code=404
            )
        
        # Send message
        bot_token = channel.get_config('bot_token')
        bot_handler = get_telegram_bot_handler(bot_token)
        
        try:
            sent_message = asyncio.run(
                bot_handler.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=parse_mode
                )
            )
            
            # Update channel statistics
            channel.increment_sent()
            channel.save()
            
            return success_response(
                message="Message sent successfully",
                data={
                    "message_id": sent_message.message_id,
                    "chat_id": sent_message.chat_id,
                    "date": sent_message.date.isoformat()
                }
            )
            
        except Exception as e:
            return error_response(
                error_code="MESSAGE_SEND_FAILED",
                message="Failed to send message",
                status_code=500,
                details=str(e)
            )
        
    except Exception as e:
        current_app.logger.error(f"Error sending Telegram message: {str(e)}")
        return error_response(
            error_code="SEND_ERROR",
            message="Failed to send message",
            status_code=500,
            details=str(e)
        )


@channels_bp.route('/telegram/status', methods=['GET'])
@jwt_required()
@tenant_required
def get_telegram_status():
    """Get Telegram channel status."""
    try:
        tenant_id = get_jwt_identity()
        
        # Get Telegram channel
        channel = Channel.query.filter_by(
            tenant_id=tenant_id,
            type='telegram'
        ).first()
        
        if not channel:
            return error_response(
                error_code="CHANNEL_NOT_FOUND",
                message="Telegram channel not found",
                status_code=404
            )
        
        # Get bot info if connected
        bot_info = None
        if channel.is_connected:
            try:
                bot_token = channel.get_config('bot_token')
                bot_handler = get_telegram_bot_handler(bot_token)
                bot_data = asyncio.run(bot_handler.bot.get_me())
                
                bot_info = {
                    "id": bot_data.id,
                    "username": bot_data.username,
                    "first_name": bot_data.first_name,
                    "can_join_groups": bot_data.can_join_groups,
                    "can_read_all_group_messages": bot_data.can_read_all_group_messages,
                    "supports_inline_queries": bot_data.supports_inline_queries
                }
            except Exception as e:
                current_app.logger.warning(f"Could not get bot info: {str(e)}")
        
        return success_response(
            message="Telegram status retrieved successfully",
            data={
                "channel": channel.to_dict(),
                "bot_info": bot_info,
                "webhook_url": channel.get_config('webhook_url'),
                "statistics": {
                    "messages_received": channel.messages_received,
                    "messages_sent": channel.messages_sent,
                    "total_messages": channel.messages_received + channel.messages_sent
                }
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"Error getting Telegram status: {str(e)}")
        return error_response(
            error_code="STATUS_ERROR",
            message="Failed to get Telegram status",
            status_code=500,
            details=str(e)
        )

@channels_bp.route('/signal/setup')
@jwt_required()
@tenant_required
def signal_setup():
    """Signal integration setup page."""
    from flask import render_template
    return render_template('channels/signal_setup.html')