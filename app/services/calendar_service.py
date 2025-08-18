"""Calendar service for Google Calendar integration."""
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional
import structlog

from app.services.google_oauth import GoogleOAuthService
from app.utils.exceptions import OAuthError, ExternalAPIError, ValidationError

logger = structlog.get_logger()


class CalendarService:
    """Service for calendar operations."""
    
    def __init__(self):
        """Initialize calendar service."""
        self.oauth_service = GoogleOAuthService()
    
    def list_calendars(self, user) -> List[Dict[str, Any]]:
        """List user's Google calendars."""
        try:
            service = self.oauth_service.get_calendar_service(user)
            
            # Get calendar list
            calendars_result = service.calendarList().list().execute()
            calendars = calendars_result.get('items', [])
            
            # Format calendar data
            formatted_calendars = []
            for calendar in calendars:
                formatted_calendars.append({
                    'id': calendar.get('id'),
                    'summary': calendar.get('summary'),
                    'description': calendar.get('description', ''),
                    'primary': calendar.get('primary', False),
                    'access_role': calendar.get('accessRole'),
                    'color_id': calendar.get('colorId'),
                    'background_color': calendar.get('backgroundColor'),
                    'foreground_color': calendar.get('foregroundColor'),
                    'selected': calendar.get('selected', False),
                    'time_zone': calendar.get('timeZone')
                })
            
            logger.info("Calendars listed successfully", user_id=user.id, count=len(formatted_calendars))
            return formatted_calendars
            
        except Exception as e:
            logger.error("Failed to list calendars", user_id=user.id, error=str(e))
            raise ExternalAPIError(f"Failed to retrieve calendars: {str(e)}")
    
    def list_events(
        self,
        user,
        calendar_id: str = 'primary',
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """List calendar events."""
        try:
            service = self.oauth_service.get_calendar_service(user)
            
            # Set default time range if not provided
            if not time_min:
                time_min = datetime.utcnow()
            if not time_max:
                time_max = time_min + timedelta(days=30)
            
            # Get events
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Format event data
            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                formatted_events.append({
                    'id': event.get('id'),
                    'summary': event.get('summary', 'No Title'),
                    'description': event.get('description', ''),
                    'start': start,
                    'end': end,
                    'location': event.get('location', ''),
                    'status': event.get('status'),
                    'creator': event.get('creator', {}),
                    'organizer': event.get('organizer', {}),
                    'attendees': event.get('attendees', []),
                    'html_link': event.get('htmlLink'),
                    'created': event.get('created'),
                    'updated': event.get('updated'),
                    'recurring_event_id': event.get('recurringEventId'),
                    'transparency': event.get('transparency', 'opaque')
                })
            
            logger.info(
                "Events listed successfully",
                user_id=user.id,
                calendar_id=calendar_id,
                count=len(formatted_events)
            )
            return formatted_events
            
        except Exception as e:
            logger.error(
                "Failed to list events",
                user_id=user.id,
                calendar_id=calendar_id,
                error=str(e)
            )
            raise ExternalAPIError(f"Failed to retrieve events: {str(e)}")
    
    def check_availability(
        self,
        user,
        calendar_id: str = 'primary',
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        duration: int = 60,  # minutes
        working_hours_start: str = '09:00',
        working_hours_end: str = '17:00'
    ) -> Dict[str, Any]:
        """Check calendar availability for booking."""
        try:
            # Set default time range if not provided
            if not time_min:
                time_min = datetime.utcnow()
            if not time_max:
                time_max = time_min + timedelta(days=7)
            
            # Get existing events in the time range
            existing_events = self.list_events(
                user=user,
                calendar_id=calendar_id,
                time_min=time_min,
                time_max=time_max,
                max_results=250
            )
            
            # Parse working hours
            try:
                work_start_time = datetime.strptime(working_hours_start, '%H:%M').time()
                work_end_time = datetime.strptime(working_hours_end, '%H:%M').time()
            except ValueError:
                raise ValidationError("Invalid working hours format. Use HH:MM format.")
            
            # Generate available slots
            available_slots = []
            busy_periods = []
            
            # Convert existing events to busy periods
            for event in existing_events:
                if event['transparency'] == 'transparent':
                    continue  # Skip transparent events (free time)
                
                try:
                    # Handle both datetime and date formats
                    start_str = event['start']
                    end_str = event['end']
                    
                    if 'T' in start_str:  # datetime format
                        event_start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                        event_end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                        # Convert to naive datetime for comparison
                        event_start = event_start.replace(tzinfo=None)
                        event_end = event_end.replace(tzinfo=None)
                    else:  # date format (all-day event)
                        event_start = datetime.fromisoformat(start_str)
                        event_end = datetime.fromisoformat(end_str)
                    
                    busy_periods.append((event_start, event_end))
                    
                except (ValueError, TypeError) as e:
                    logger.warning(
                        "Failed to parse event time",
                        event_id=event.get('id'),
                        error=str(e)
                    )
                    continue
            
            # Sort busy periods by start time
            busy_periods.sort(key=lambda x: x[0])
            
            # Generate time slots within working hours
            current_date = time_min.date()
            end_date = time_max.date()
            slot_duration = timedelta(minutes=duration)
            
            while current_date <= end_date:
                # Skip weekends (optional - could be configurable)
                if current_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    current_date += timedelta(days=1)
                    continue
                
                # Create datetime objects for working hours
                work_start = datetime.combine(current_date, work_start_time)
                work_end = datetime.combine(current_date, work_end_time)
                
                # Skip if work day is outside our time range
                if work_end < time_min or work_start > time_max:
                    current_date += timedelta(days=1)
                    continue
                
                # Adjust work hours to fit within requested time range
                work_start = max(work_start, time_min)
                work_end = min(work_end, time_max)
                
                # Generate slots for this day
                current_slot_start = work_start
                
                while current_slot_start + slot_duration <= work_end:
                    current_slot_end = current_slot_start + slot_duration
                    
                    # Check if slot conflicts with any busy period
                    is_available = True
                    for busy_start, busy_end in busy_periods:
                        # Check for overlap
                        if (current_slot_start < busy_end and current_slot_end > busy_start):
                            is_available = False
                            break
                    
                    if is_available:
                        available_slots.append({
                            'start': current_slot_start.isoformat(),
                            'end': current_slot_end.isoformat(),
                            'duration_minutes': duration
                        })
                    
                    # Move to next slot (15-minute intervals)
                    current_slot_start += timedelta(minutes=15)
                
                current_date += timedelta(days=1)
            
            # Check if a specific time slot is available
            is_available = True
            if time_min and time_max and (time_max - time_min).total_seconds() / 60 == duration:
                # This is a specific slot check
                for busy_start, busy_end in busy_periods:
                    if time_min < busy_end and time_max > busy_start:
                        is_available = False
                        break
            
            result = {
                'is_available': is_available,
                'available_slots': available_slots[:50],  # Limit to 50 slots
                'total_available_slots': len(available_slots),
                'busy_periods': [
                    {
                        'start': start.isoformat(),
                        'end': end.isoformat()
                    }
                    for start, end in busy_periods
                ],
                'working_hours': {
                    'start': working_hours_start,
                    'end': working_hours_end
                },
                'duration_minutes': duration,
                'time_range': {
                    'start': time_min.isoformat(),
                    'end': time_max.isoformat()
                }
            }
            
            logger.info(
                "Availability checked successfully",
                user_id=user.id,
                calendar_id=calendar_id,
                available_slots=len(available_slots),
                busy_periods=len(busy_periods)
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Failed to check availability",
                user_id=user.id,
                calendar_id=calendar_id,
                error=str(e)
            )
            raise ExternalAPIError(f"Failed to check availability: {str(e)}")
    
    def create_event(self, user, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new calendar event."""
        try:
            service = self.oauth_service.get_calendar_service(user)
            
            # Prepare event body
            event_body = {
                'summary': event_data['title'],
                'description': event_data.get('description', ''),
                'start': {
                    'dateTime': event_data['start_time'].isoformat(),
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': event_data['end_time'].isoformat(),
                    'timeZone': 'UTC'
                },
                'location': event_data.get('location', ''),
                'attendees': event_data.get('attendees', []),
                'reminders': {
                    'useDefault': True
                }
            }
            
            # Create the event
            calendar_id = event_data.get('calendar_id', 'primary')
            send_notifications = event_data.get('send_notifications', True)
            
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=event_body,
                sendNotifications=send_notifications
            ).execute()
            
            logger.info(
                "Event created successfully",
                user_id=user.id,
                event_id=created_event.get('id'),
                calendar_id=calendar_id
            )
            
            return {
                'id': created_event.get('id'),
                'summary': created_event.get('summary'),
                'description': created_event.get('description', ''),
                'start': created_event['start'].get('dateTime', created_event['start'].get('date')),
                'end': created_event['end'].get('dateTime', created_event['end'].get('date')),
                'location': created_event.get('location', ''),
                'attendees': created_event.get('attendees', []),
                'html_link': created_event.get('htmlLink'),
                'status': created_event.get('status'),
                'created': created_event.get('created'),
                'updated': created_event.get('updated')
            }
            
        except Exception as e:
            logger.error(
                "Failed to create event",
                user_id=user.id,
                error=str(e)
            )
            raise ExternalAPIError(f"Failed to create event: {str(e)}")
    
    def update_event(
        self,
        user,
        calendar_id: str,
        event_id: str,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing calendar event."""
        try:
            service = self.oauth_service.get_calendar_service(user)
            
            # Get existing event
            existing_event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update fields
            if 'title' in event_data:
                existing_event['summary'] = event_data['title']
            
            if 'description' in event_data:
                existing_event['description'] = event_data['description']
            
            if 'start_time' in event_data:
                existing_event['start'] = {
                    'dateTime': event_data['start_time'].isoformat(),
                    'timeZone': 'UTC'
                }
            
            if 'end_time' in event_data:
                existing_event['end'] = {
                    'dateTime': event_data['end_time'].isoformat(),
                    'timeZone': 'UTC'
                }
            
            if 'location' in event_data:
                existing_event['location'] = event_data['location']
            
            if 'attendees' in event_data:
                existing_event['attendees'] = event_data['attendees']
            
            # Update the event
            send_notifications = event_data.get('send_notifications', True)
            
            updated_event = service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=existing_event,
                sendNotifications=send_notifications
            ).execute()
            
            logger.info(
                "Event updated successfully",
                user_id=user.id,
                event_id=event_id,
                calendar_id=calendar_id
            )
            
            return {
                'id': updated_event.get('id'),
                'summary': updated_event.get('summary'),
                'description': updated_event.get('description', ''),
                'start': updated_event['start'].get('dateTime', updated_event['start'].get('date')),
                'end': updated_event['end'].get('dateTime', updated_event['end'].get('date')),
                'location': updated_event.get('location', ''),
                'attendees': updated_event.get('attendees', []),
                'html_link': updated_event.get('htmlLink'),
                'status': updated_event.get('status'),
                'updated': updated_event.get('updated')
            }
            
        except Exception as e:
            logger.error(
                "Failed to update event",
                user_id=user.id,
                event_id=event_id,
                calendar_id=calendar_id,
                error=str(e)
            )
            raise ExternalAPIError(f"Failed to update event: {str(e)}")
    
    def delete_event(
        self,
        user,
        calendar_id: str,
        event_id: str,
        send_notifications: bool = True
    ) -> None:
        """Delete a calendar event."""
        try:
            service = self.oauth_service.get_calendar_service(user)
            
            # Delete the event
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendNotifications=send_notifications
            ).execute()
            
            logger.info(
                "Event deleted successfully",
                user_id=user.id,
                event_id=event_id,
                calendar_id=calendar_id
            )
            
        except Exception as e:
            logger.error(
                "Failed to delete event",
                user_id=user.id,
                event_id=event_id,
                calendar_id=calendar_id,
                error=str(e)
            )
            raise ExternalAPIError(f"Failed to delete event: {str(e)}")
    
    def book_appointment(self, user, booking_data: Dict[str, Any]) -> Dict[str, Any]:
        """Book an appointment with customer details."""
        try:
            # Prepare attendees list
            attendees = []
            if booking_data.get('customer_email'):
                attendee = {
                    'email': booking_data['customer_email'],
                    'responseStatus': 'needsAction'
                }
                if booking_data.get('customer_name'):
                    attendee['displayName'] = booking_data['customer_name']
                attendees.append(attendee)
            
            # Prepare event data
            event_data = {
                'title': booking_data['title'],
                'description': booking_data.get('description', ''),
                'start_time': booking_data['start_time'],
                'end_time': booking_data['end_time'],
                'calendar_id': booking_data.get('calendar_id', 'primary'),
                'location': booking_data.get('location', ''),
                'attendees': attendees,
                'send_notifications': booking_data.get('send_notifications', True)
            }
            
            # Create the event
            event = self.create_event(user, event_data)
            
            logger.info(
                "Appointment booked successfully",
                user_id=user.id,
                event_id=event.get('id'),
                customer_email=booking_data.get('customer_email')
            )
            
            return event
            
        except Exception as e:
            logger.error(
                "Failed to book appointment",
                user_id=user.id,
                customer_email=booking_data.get('customer_email'),
                error=str(e)
            )
            raise ExternalAPIError(f"Failed to book appointment: {str(e)}")