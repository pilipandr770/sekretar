"""Calendar integration routes."""
from datetime import datetime, timedelta
from flask import request
from flask_jwt_extended import jwt_required, get_current_user
from flask_babel import gettext as _

from app.calendar import calendar_bp
from app.services.google_oauth import GoogleOAuthService
from app.services.calendar_service import CalendarService
from app.models.audit_log import AuditLog
from app.utils.decorators import log_api_call, require_permission
from app.utils.response import (
    success_response, error_response, validation_error_response
)
from app.utils.exceptions import OAuthError, ExternalAPIError, ValidationError
from app.utils.validators import validate_datetime, validate_email
import structlog

logger = structlog.get_logger()


@calendar_bp.route('/connection/status', methods=['GET'])
@jwt_required()
@log_api_call('calendar_connection_status')
def get_connection_status():
    """Get calendar connection status."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        oauth_service = GoogleOAuthService()
        
        if not oauth_service.is_configured():
            return success_response(
                message=_('Calendar connection status retrieved'),
                data={
                    'connected': False,
                    'configured': False,
                    'error': 'Google Calendar not configured'
                }
            )
        
        # Get connection status
        connection_status = {
            'connected': user.google_calendar_connected,
            'configured': True,
            'expires_at': user.google_oauth_expires_at.isoformat() if user.google_oauth_expires_at else None,
            'is_expired': user.is_google_oauth_expired() if user.google_calendar_connected else None
        }
        
        if user.google_calendar_connected:
            # Test the connection
            test_result = oauth_service.test_connection(user)
            connection_status.update(test_result)
        
        return success_response(
            message=_('Calendar connection status retrieved'),
            data=connection_status
        )
        
    except Exception as e:
        logger.error("Failed to get calendar connection status", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to get calendar connection status'),
            status_code=500
        )


@calendar_bp.route('/calendars', methods=['GET'])
@jwt_required()
@require_permission('manage_calendar')
@log_api_call('calendar_list')
def list_calendars():
    """List user's Google calendars."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        if not user.google_calendar_connected:
            return error_response(
                error_code='CALENDAR_NOT_CONNECTED',
                message=_('Google Calendar is not connected'),
                status_code=400
            )
        
        calendar_service = CalendarService()
        calendars = calendar_service.list_calendars(user)
        
        logger.info("Calendars listed successfully", user_id=user.id, count=len(calendars))
        
        return success_response(
            message=_('Calendars retrieved successfully'),
            data={
                'calendars': calendars,
                'count': len(calendars)
            }
        )
        
    except OAuthError as e:
        logger.error("OAuth error listing calendars", error=str(e))
        return error_response(
            error_code='OAUTH_ERROR',
            message=str(e),
            status_code=400
        )
    except ExternalAPIError as e:
        logger.error("External API error listing calendars", error=str(e))
        return error_response(
            error_code='EXTERNAL_API_ERROR',
            message=str(e),
            status_code=503
        )
    except Exception as e:
        logger.error("Failed to list calendars", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve calendars'),
            status_code=500
        )


@calendar_bp.route('/events', methods=['GET'])
@jwt_required()
@require_permission('manage_calendar')
@log_api_call('calendar_events_list')
def list_events():
    """List calendar events."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        if not user.google_calendar_connected:
            return error_response(
                error_code='CALENDAR_NOT_CONNECTED',
                message=_('Google Calendar is not connected'),
                status_code=400
            )
        
        # Parse query parameters
        calendar_id = request.args.get('calendar_id', 'primary')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        max_results = request.args.get('max_results', 50, type=int)
        
        # Validate date parameters
        time_min = None
        time_max = None
        
        if start_date:
            try:
                time_min = validate_datetime(start_date)
            except ValidationError as e:
                return validation_error_response(
                    field='start_date',
                    message=str(e)
                )
        else:
            # Default to current time
            time_min = datetime.utcnow()
        
        if end_date:
            try:
                time_max = validate_datetime(end_date)
            except ValidationError as e:
                return validation_error_response(
                    field='end_date',
                    message=str(e)
                )
        else:
            # Default to 30 days from start
            time_max = time_min + timedelta(days=30)
        
        # Validate max_results
        if max_results < 1 or max_results > 250:
            return validation_error_response(
                field='max_results',
                message=_('Max results must be between 1 and 250')
            )
        
        calendar_service = CalendarService()
        events = calendar_service.list_events(
            user=user,
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results
        )
        
        logger.info(
            "Events listed successfully",
            user_id=user.id,
            calendar_id=calendar_id,
            count=len(events)
        )
        
        return success_response(
            message=_('Events retrieved successfully'),
            data={
                'events': events,
                'count': len(events),
                'calendar_id': calendar_id,
                'time_range': {
                    'start': time_min.isoformat(),
                    'end': time_max.isoformat()
                }
            }
        )
        
    except OAuthError as e:
        logger.error("OAuth error listing events", error=str(e))
        return error_response(
            error_code='OAUTH_ERROR',
            message=str(e),
            status_code=400
        )
    except ExternalAPIError as e:
        logger.error("External API error listing events", error=str(e))
        return error_response(
            error_code='EXTERNAL_API_ERROR',
            message=str(e),
            status_code=503
        )
    except Exception as e:
        logger.error("Failed to list events", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to retrieve events'),
            status_code=500
        )


@calendar_bp.route('/availability', methods=['GET'])
@jwt_required()
@require_permission('manage_calendar')
@log_api_call('calendar_availability')
def check_availability():
    """Check calendar availability for booking."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        if not user.google_calendar_connected:
            return error_response(
                error_code='CALENDAR_NOT_CONNECTED',
                message=_('Google Calendar is not connected'),
                status_code=400
            )
        
        # Parse query parameters
        calendar_id = request.args.get('calendar_id', 'primary')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        duration = request.args.get('duration', 60, type=int)  # minutes
        working_hours_start = request.args.get('working_hours_start', '09:00')
        working_hours_end = request.args.get('working_hours_end', '17:00')
        
        # Validate required parameters
        if not start_date:
            return validation_error_response(
                field='start_date',
                message=_('Start date is required')
            )
        
        if not end_date:
            return validation_error_response(
                field='end_date',
                message=_('End date is required')
            )
        
        # Validate date parameters
        try:
            time_min = validate_datetime(start_date)
            time_max = validate_datetime(end_date)
        except ValidationError as e:
            return validation_error_response(
                field='date',
                message=str(e)
            )
        
        # Validate duration
        if duration < 15 or duration > 480:  # 15 minutes to 8 hours
            return validation_error_response(
                field='duration',
                message=_('Duration must be between 15 and 480 minutes')
            )
        
        calendar_service = CalendarService()
        availability = calendar_service.check_availability(
            user=user,
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            duration=duration,
            working_hours_start=working_hours_start,
            working_hours_end=working_hours_end
        )
        
        logger.info(
            "Availability checked successfully",
            user_id=user.id,
            calendar_id=calendar_id,
            available_slots=len(availability['available_slots'])
        )
        
        return success_response(
            message=_('Availability checked successfully'),
            data=availability
        )
        
    except OAuthError as e:
        logger.error("OAuth error checking availability", error=str(e))
        return error_response(
            error_code='OAUTH_ERROR',
            message=str(e),
            status_code=400
        )
    except ExternalAPIError as e:
        logger.error("External API error checking availability", error=str(e))
        return error_response(
            error_code='EXTERNAL_API_ERROR',
            message=str(e),
            status_code=503
        )
    except Exception as e:
        logger.error("Failed to check availability", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to check availability'),
            status_code=500
        )


@calendar_bp.route('/events', methods=['POST'])
@jwt_required()
@require_permission('manage_calendar')
@log_api_call('calendar_event_create')
def create_event():
    """Create a new calendar event."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        if not user.google_calendar_connected:
            return error_response(
                error_code='CALENDAR_NOT_CONNECTED',
                message=_('Google Calendar is not connected'),
                status_code=400
            )
        
        data = request.get_json()
        if not data:
            return validation_error_response(
                field='body',
                message=_('Request body is required')
            )
        
        # Validate required fields
        required_fields = ['title', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data:
                return validation_error_response(
                    field=field,
                    message=_(f'{field.replace("_", " ").title()} is required')
                )
        
        # Validate datetime fields
        try:
            start_time = validate_datetime(data['start_time'])
            end_time = validate_datetime(data['end_time'])
        except ValidationError as e:
            return validation_error_response(
                field='datetime',
                message=str(e)
            )
        
        # Validate time range
        if start_time >= end_time:
            return validation_error_response(
                field='time_range',
                message=_('Start time must be before end time')
            )
        
        # Validate attendees if provided
        attendees = data.get('attendees', [])
        if attendees:
            for i, attendee in enumerate(attendees):
                if isinstance(attendee, str):
                    # Convert string email to attendee object
                    try:
                        validate_email(attendee)
                        attendees[i] = {'email': attendee}
                    except ValidationError:
                        return validation_error_response(
                            field=f'attendees[{i}]',
                            message=_('Invalid email address')
                        )
                elif isinstance(attendee, dict):
                    if 'email' not in attendee:
                        return validation_error_response(
                            field=f'attendees[{i}]',
                            message=_('Attendee email is required')
                        )
                    try:
                        validate_email(attendee['email'])
                    except ValidationError:
                        return validation_error_response(
                            field=f'attendees[{i}].email',
                            message=_('Invalid email address')
                        )
        
        # Prepare event data
        event_data = {
            'title': data['title'],
            'description': data.get('description', ''),
            'start_time': start_time,
            'end_time': end_time,
            'calendar_id': data.get('calendar_id', 'primary'),
            'attendees': attendees,
            'location': data.get('location', ''),
            'send_notifications': data.get('send_notifications', True)
        }
        
        calendar_service = CalendarService()
        event = calendar_service.create_event(user, event_data)
        
        # Log event creation
        AuditLog.log_user_action(
            user=user,
            action='calendar_event_create',
            resource_type='calendar_event',
            resource_id=event.get('id'),
            metadata={
                'title': event_data['title'],
                'calendar_id': event_data['calendar_id'],
                'attendee_count': len(attendees)
            }
        )
        
        logger.info(
            "Calendar event created successfully",
            user_id=user.id,
            event_id=event.get('id'),
            title=event_data['title']
        )
        
        return success_response(
            message=_('Event created successfully'),
            data={'event': event},
            status_code=201
        )
        
    except ValidationError as e:
        return validation_error_response(
            field='validation',
            message=str(e)
        )
    except OAuthError as e:
        logger.error("OAuth error creating event", error=str(e))
        return error_response(
            error_code='OAUTH_ERROR',
            message=str(e),
            status_code=400
        )
    except ExternalAPIError as e:
        logger.error("External API error creating event", error=str(e))
        return error_response(
            error_code='EXTERNAL_API_ERROR',
            message=str(e),
            status_code=503
        )
    except Exception as e:
        logger.error("Failed to create event", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to create event'),
            status_code=500
        )


@calendar_bp.route('/events/<event_id>', methods=['PUT'])
@jwt_required()
@require_permission('manage_calendar')
@log_api_call('calendar_event_update')
def update_event(event_id):
    """Update an existing calendar event."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        if not user.google_calendar_connected:
            return error_response(
                error_code='CALENDAR_NOT_CONNECTED',
                message=_('Google Calendar is not connected'),
                status_code=400
            )
        
        data = request.get_json()
        if not data:
            return validation_error_response(
                field='body',
                message=_('Request body is required')
            )
        
        # Validate datetime fields if provided
        if 'start_time' in data:
            try:
                data['start_time'] = validate_datetime(data['start_time'])
            except ValidationError as e:
                return validation_error_response(
                    field='start_time',
                    message=str(e)
                )
        
        if 'end_time' in data:
            try:
                data['end_time'] = validate_datetime(data['end_time'])
            except ValidationError as e:
                return validation_error_response(
                    field='end_time',
                    message=str(e)
                )
        
        # Validate time range if both times provided
        if 'start_time' in data and 'end_time' in data:
            if data['start_time'] >= data['end_time']:
                return validation_error_response(
                    field='time_range',
                    message=_('Start time must be before end time')
                )
        
        calendar_id = data.get('calendar_id', 'primary')
        
        calendar_service = CalendarService()
        event = calendar_service.update_event(user, calendar_id, event_id, data)
        
        # Log event update
        AuditLog.log_user_action(
            user=user,
            action='calendar_event_update',
            resource_type='calendar_event',
            resource_id=event_id,
            metadata={
                'calendar_id': calendar_id,
                'updated_fields': list(data.keys())
            }
        )
        
        logger.info(
            "Calendar event updated successfully",
            user_id=user.id,
            event_id=event_id,
            calendar_id=calendar_id
        )
        
        return success_response(
            message=_('Event updated successfully'),
            data={'event': event}
        )
        
    except ValidationError as e:
        return validation_error_response(
            field='validation',
            message=str(e)
        )
    except OAuthError as e:
        logger.error("OAuth error updating event", error=str(e))
        return error_response(
            error_code='OAUTH_ERROR',
            message=str(e),
            status_code=400
        )
    except ExternalAPIError as e:
        logger.error("External API error updating event", error=str(e))
        return error_response(
            error_code='EXTERNAL_API_ERROR',
            message=str(e),
            status_code=503
        )
    except Exception as e:
        logger.error("Failed to update event", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to update event'),
            status_code=500
        )


@calendar_bp.route('/events/<event_id>', methods=['DELETE'])
@jwt_required()
@require_permission('manage_calendar')
@log_api_call('calendar_event_delete')
def delete_event(event_id):
    """Delete a calendar event."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        if not user.google_calendar_connected:
            return error_response(
                error_code='CALENDAR_NOT_CONNECTED',
                message=_('Google Calendar is not connected'),
                status_code=400
            )
        
        calendar_id = request.args.get('calendar_id', 'primary')
        send_notifications = request.args.get('send_notifications', 'true').lower() == 'true'
        
        calendar_service = CalendarService()
        calendar_service.delete_event(user, calendar_id, event_id, send_notifications)
        
        # Log event deletion
        AuditLog.log_user_action(
            user=user,
            action='calendar_event_delete',
            resource_type='calendar_event',
            resource_id=event_id,
            metadata={
                'calendar_id': calendar_id,
                'send_notifications': send_notifications
            }
        )
        
        logger.info(
            "Calendar event deleted successfully",
            user_id=user.id,
            event_id=event_id,
            calendar_id=calendar_id
        )
        
        return success_response(
            message=_('Event deleted successfully')
        )
        
    except OAuthError as e:
        logger.error("OAuth error deleting event", error=str(e))
        return error_response(
            error_code='OAUTH_ERROR',
            message=str(e),
            status_code=400
        )
    except ExternalAPIError as e:
        logger.error("External API error deleting event", error=str(e))
        return error_response(
            error_code='EXTERNAL_API_ERROR',
            message=str(e),
            status_code=503
        )
    except Exception as e:
        logger.error("Failed to delete event", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to delete event'),
            status_code=500
        )


@calendar_bp.route('/book', methods=['POST'])
@jwt_required()
@require_permission('manage_calendar')
@log_api_call('calendar_book_appointment')
def book_appointment():
    """Book an appointment slot."""
    try:
        user = get_current_user()
        if not user:
            return error_response(
                error_code='AUTHENTICATION_ERROR',
                message=_('Authentication required'),
                status_code=401
            )
        
        if not user.google_calendar_connected:
            return error_response(
                error_code='CALENDAR_NOT_CONNECTED',
                message=_('Google Calendar is not connected'),
                status_code=400
            )
        
        data = request.get_json()
        if not data:
            return validation_error_response(
                field='body',
                message=_('Request body is required')
            )
        
        # Validate required fields
        required_fields = ['start_time', 'end_time', 'customer_email']
        for field in required_fields:
            if field not in data:
                return validation_error_response(
                    field=field,
                    message=_(f'{field.replace("_", " ").title()} is required')
                )
        
        # Validate datetime fields
        try:
            start_time = validate_datetime(data['start_time'])
            end_time = validate_datetime(data['end_time'])
        except ValidationError as e:
            return validation_error_response(
                field='datetime',
                message=str(e)
            )
        
        # Validate customer email
        try:
            validate_email(data['customer_email'])
        except ValidationError:
            return validation_error_response(
                field='customer_email',
                message=_('Invalid email address')
            )
        
        # Validate time range
        if start_time >= end_time:
            return validation_error_response(
                field='time_range',
                message=_('Start time must be before end time')
            )
        
        # Prepare booking data
        booking_data = {
            'title': data.get('title', _('Appointment with {email}').format(email=data['customer_email'])),
            'description': data.get('description', ''),
            'start_time': start_time,
            'end_time': end_time,
            'calendar_id': data.get('calendar_id', 'primary'),
            'customer_email': data['customer_email'],
            'customer_name': data.get('customer_name', ''),
            'location': data.get('location', ''),
            'send_notifications': data.get('send_notifications', True)
        }
        
        calendar_service = CalendarService()
        
        # Check availability first
        availability = calendar_service.check_availability(
            user=user,
            calendar_id=booking_data['calendar_id'],
            time_min=start_time,
            time_max=end_time,
            duration=int((end_time - start_time).total_seconds() / 60)
        )
        
        if not availability['is_available']:
            return error_response(
                error_code='SLOT_NOT_AVAILABLE',
                message=_('The requested time slot is not available'),
                status_code=409
            )
        
        # Create the appointment
        event = calendar_service.book_appointment(user, booking_data)
        
        # Log appointment booking
        AuditLog.log_user_action(
            user=user,
            action='calendar_appointment_book',
            resource_type='calendar_event',
            resource_id=event.get('id'),
            metadata={
                'customer_email': booking_data['customer_email'],
                'calendar_id': booking_data['calendar_id'],
                'duration_minutes': int((end_time - start_time).total_seconds() / 60)
            }
        )
        
        logger.info(
            "Appointment booked successfully",
            user_id=user.id,
            event_id=event.get('id'),
            customer_email=booking_data['customer_email']
        )
        
        return success_response(
            message=_('Appointment booked successfully'),
            data={'event': event},
            status_code=201
        )
        
    except ValidationError as e:
        return validation_error_response(
            field='validation',
            message=str(e)
        )
    except OAuthError as e:
        logger.error("OAuth error booking appointment", error=str(e))
        return error_response(
            error_code='OAUTH_ERROR',
            message=str(e),
            status_code=400
        )
    except ExternalAPIError as e:
        logger.error("External API error booking appointment", error=str(e))
        return error_response(
            error_code='EXTERNAL_API_ERROR',
            message=str(e),
            status_code=503
        )
    except Exception as e:
        logger.error("Failed to book appointment", error=str(e), exc_info=True)
        return error_response(
            error_code='INTERNAL_ERROR',
            message=_('Failed to book appointment'),
            status_code=500
        )