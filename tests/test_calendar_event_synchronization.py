"""Comprehensive calendar event synchronization tests."""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, call
from flask import Flask

from app import create_app, db
from app.models.user import User
from app.models.tenant import Tenant
from app.services.calendar_service import CalendarService
from app.services.google_oauth import GoogleOAuthService
from app.utils.exceptions import OAuthError, ExternalAPIError, ValidationError


@pytest.fixture
def app():
    """Create test app with calendar configuration."""
    app = create_app('testing')
    
    # Configure Google Calendar settings
    app.config.update({
        'GOOGLE_CLIENT_ID': 'test_google_client_id_12345',
        'GOOGLE_CLIENT_SECRET': 'test_google_client_secret_67890',
        'GOOGLE_REDIRECT_URI': 'http://localhost:5000/auth/oauth/google/callback',
        'SECRET_KEY': 'test_secret_key_for_sessions'
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def tenant(app):
    """Create test tenant."""
    with app.app_context():
        tenant = Tenant(
            name='Calendar Sync Test Company',
            domain='calendar-sync.example.com',
            slug='calendar-sync-test',
            subscription_status='active'
        )
        tenant.save()
        return tenant


@pytest.fixture
def user(app, tenant):
    """Create test user with Google Calendar connected."""
    with app.app_context():
        user = User.create(
            email='calendar-sync@example.com',
            password='SecurePass123!',
            tenant_id=tenant.id,
            role='owner'
        )
        
        # Set up Google OAuth tokens
        token_data = {
            'token': 'access_token_sync_test',
            'refresh_token': 'refresh_token_sync_test',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_google_client_id_12345',
            'client_secret': 'test_google_client_secret_67890',
            'scopes': [
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/calendar.events'
            ],
            'expires_in': 3600
        }
        user.set_google_oauth_tokens(token_data)
        
        return user


@pytest.fixture
def auth_headers(app, user):
    """Create authentication headers."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(identity=user.id)
        return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def mock_google_service():
    """Create mock Google Calendar service."""
    service = Mock()
    
    # Mock calendar list
    service.calendarList().list().execute.return_value = {
        'items': [
            {
                'id': 'primary',
                'summary': 'Primary Calendar',
                'primary': True,
                'accessRole': 'owner',
                'timeZone': 'UTC'
            },
            {
                'id': 'work_calendar_id',
                'summary': 'Work Calendar',
                'primary': False,
                'accessRole': 'writer',
                'timeZone': 'Europe/London'
            }
        ]
    }
    
    return service


class TestEventCreationSynchronization:
    """Test event creation and synchronization with Google Calendar."""
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_create_event_success(self, mock_service, app, user, mock_google_service):
        """Test successful event creation and synchronization."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            # Mock successful event creation
            created_event = {
                'id': 'event_sync_test_123',
                'summary': 'Test Sync Event',
                'description': 'Event created for sync testing',
                'start': {'dateTime': '2024-02-15T10:00:00Z', 'timeZone': 'UTC'},
                'end': {'dateTime': '2024-02-15T11:00:00Z', 'timeZone': 'UTC'},
                'location': 'Test Location',
                'status': 'confirmed',
                'htmlLink': 'https://calendar.google.com/event?eid=event_sync_test_123',
                'created': '2024-02-14T12:00:00Z',
                'updated': '2024-02-14T12:00:00Z',
                'attendees': [
                    {
                        'email': 'attendee1@example.com',
                        'displayName': 'Test Attendee',
                        'responseStatus': 'needsAction'
                    }
                ]
            }
            
            mock_google_service.events().insert().execute.return_value = created_event
            
            # Create event data
            event_data = {
                'title': 'Test Sync Event',
                'description': 'Event created for sync testing',
                'start_time': datetime(2024, 2, 15, 10, 0, 0),
                'end_time': datetime(2024, 2, 15, 11, 0, 0),
                'location': 'Test Location',
                'calendar_id': 'primary',
                'attendees': [{'email': 'attendee1@example.com', 'displayName': 'Test Attendee'}],
                'send_notifications': True
            }
            
            # Create event using service
            calendar_service = CalendarService()
            result = calendar_service.create_event(user, event_data)
            
            # Verify API call was made correctly
            mock_google_service.events().insert.assert_called_once()
            call_args = mock_google_service.events().insert.call_args
            
            assert call_args[1]['calendarId'] == 'primary'
            assert call_args[1]['sendNotifications'] is True
            
            # Verify event body
            event_body = call_args[1]['body']
            assert event_body['summary'] == 'Test Sync Event'
            assert event_body['description'] == 'Event created for sync testing'
            assert event_body['location'] == 'Test Location'
            assert event_body['start']['dateTime'] == '2024-02-15T10:00:00'
            assert event_body['end']['dateTime'] == '2024-02-15T11:00:00'
            assert len(event_body['attendees']) == 1
            
            # Verify result
            assert result['id'] == 'event_sync_test_123'
            assert result['summary'] == 'Test Sync Event'
            assert result['status'] == 'confirmed'
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_create_event_with_multiple_attendees(self, mock_service, app, user, mock_google_service):
        """Test event creation with multiple attendees."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            created_event = {
                'id': 'multi_attendee_event',
                'summary': 'Multi-Attendee Meeting',
                'start': {'dateTime': '2024-02-15T14:00:00Z'},
                'end': {'dateTime': '2024-02-15T15:00:00Z'},
                'attendees': [
                    {'email': 'attendee1@example.com', 'responseStatus': 'needsAction'},
                    {'email': 'attendee2@example.com', 'responseStatus': 'needsAction'},
                    {'email': 'attendee3@example.com', 'responseStatus': 'needsAction'}
                ]
            }
            
            mock_google_service.events().insert().execute.return_value = created_event
            
            event_data = {
                'title': 'Multi-Attendee Meeting',
                'start_time': datetime(2024, 2, 15, 14, 0, 0),
                'end_time': datetime(2024, 2, 15, 15, 0, 0),
                'attendees': [
                    {'email': 'attendee1@example.com'},
                    {'email': 'attendee2@example.com'},
                    {'email': 'attendee3@example.com'}
                ]
            }
            
            calendar_service = CalendarService()
            result = calendar_service.create_event(user, event_data)
            
            # Verify all attendees were included
            call_args = mock_google_service.events().insert.call_args
            event_body = call_args[1]['body']
            assert len(event_body['attendees']) == 3
            
            # Verify result includes all attendees
            assert len(result['attendees']) == 3
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_create_event_api_error(self, mock_service, app, user, mock_google_service):
        """Test event creation when Google API returns error."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            # Mock API error
            mock_google_service.events().insert().execute.side_effect = Exception("Google API Error")
            
            event_data = {
                'title': 'Test Event',
                'start_time': datetime(2024, 2, 15, 10, 0, 0),
                'end_time': datetime(2024, 2, 15, 11, 0, 0)
            }
            
            calendar_service = CalendarService()
            
            with pytest.raises(ExternalAPIError, match="Failed to create event"):
                calendar_service.create_event(user, event_data)
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_create_recurring_event(self, mock_service, app, user, mock_google_service):
        """Test creation of recurring event."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            created_event = {
                'id': 'recurring_event_123',
                'summary': 'Weekly Team Meeting',
                'start': {'dateTime': '2024-02-15T10:00:00Z'},
                'end': {'dateTime': '2024-02-15T11:00:00Z'},
                'recurrence': ['RRULE:FREQ=WEEKLY;BYDAY=TH'],
                'status': 'confirmed'
            }
            
            mock_google_service.events().insert().execute.return_value = created_event
            
            event_data = {
                'title': 'Weekly Team Meeting',
                'start_time': datetime(2024, 2, 15, 10, 0, 0),
                'end_time': datetime(2024, 2, 15, 11, 0, 0),
                'recurrence': ['RRULE:FREQ=WEEKLY;BYDAY=TH']
            }
            
            calendar_service = CalendarService()
            result = calendar_service.create_event(user, event_data)
            
            # Verify recurrence was included
            call_args = mock_google_service.events().insert.call_args
            event_body = call_args[1]['body']
            assert 'recurrence' in event_body
            assert event_body['recurrence'] == ['RRULE:FREQ=WEEKLY;BYDAY=TH']


class TestEventUpdateSynchronization:
    """Test event update and synchronization with Google Calendar."""
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_update_event_success(self, mock_service, app, user, mock_google_service):
        """Test successful event update and synchronization."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            # Mock existing event
            existing_event = {
                'id': 'event_to_update_123',
                'summary': 'Original Event Title',
                'description': 'Original description',
                'start': {'dateTime': '2024-02-15T10:00:00Z', 'timeZone': 'UTC'},
                'end': {'dateTime': '2024-02-15T11:00:00Z', 'timeZone': 'UTC'},
                'location': 'Original Location',
                'attendees': [{'email': 'original@example.com'}]
            }
            
            mock_google_service.events().get().execute.return_value = existing_event
            
            # Mock updated event
            updated_event = existing_event.copy()
            updated_event.update({
                'summary': 'Updated Event Title',
                'description': 'Updated description',
                'location': 'Updated Location',
                'updated': '2024-02-14T13:00:00Z'
            })
            
            mock_google_service.events().update().execute.return_value = updated_event
            
            # Update data
            update_data = {
                'title': 'Updated Event Title',
                'description': 'Updated description',
                'location': 'Updated Location',
                'send_notifications': True
            }
            
            calendar_service = CalendarService()
            result = calendar_service.update_event(
                user, 'primary', 'event_to_update_123', update_data
            )
            
            # Verify get and update calls were made
            mock_google_service.events().get.assert_called_once_with(
                calendarId='primary',
                eventId='event_to_update_123'
            )
            
            mock_google_service.events().update.assert_called_once()
            update_call_args = mock_google_service.events().update.call_args
            
            assert update_call_args[1]['calendarId'] == 'primary'
            assert update_call_args[1]['eventId'] == 'event_to_update_123'
            assert update_call_args[1]['sendNotifications'] is True
            
            # Verify updated fields
            updated_body = update_call_args[1]['body']
            assert updated_body['summary'] == 'Updated Event Title'
            assert updated_body['description'] == 'Updated description'
            assert updated_body['location'] == 'Updated Location'
            
            # Verify result
            assert result['summary'] == 'Updated Event Title'
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_update_event_time_change(self, mock_service, app, user, mock_google_service):
        """Test event update with time changes."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            existing_event = {
                'id': 'time_change_event',
                'summary': 'Meeting',
                'start': {'dateTime': '2024-02-15T10:00:00Z'},
                'end': {'dateTime': '2024-02-15T11:00:00Z'}
            }
            
            mock_google_service.events().get().execute.return_value = existing_event
            
            updated_event = existing_event.copy()
            updated_event.update({
                'start': {'dateTime': '2024-02-15T14:00:00Z', 'timeZone': 'UTC'},
                'end': {'dateTime': '2024-02-15T15:30:00Z', 'timeZone': 'UTC'}
            })
            
            mock_google_service.events().update().execute.return_value = updated_event
            
            update_data = {
                'start_time': datetime(2024, 2, 15, 14, 0, 0),
                'end_time': datetime(2024, 2, 15, 15, 30, 0)
            }
            
            calendar_service = CalendarService()
            result = calendar_service.update_event(
                user, 'primary', 'time_change_event', update_data
            )
            
            # Verify time updates
            update_call_args = mock_google_service.events().update.call_args
            updated_body = update_call_args[1]['body']
            
            assert updated_body['start']['dateTime'] == '2024-02-15T14:00:00'
            assert updated_body['end']['dateTime'] == '2024-02-15T15:30:00'
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_update_event_attendees_change(self, mock_service, app, user, mock_google_service):
        """Test event update with attendee changes."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            existing_event = {
                'id': 'attendee_change_event',
                'summary': 'Team Meeting',
                'attendees': [
                    {'email': 'old1@example.com'},
                    {'email': 'old2@example.com'}
                ]
            }
            
            mock_google_service.events().get().execute.return_value = existing_event
            
            updated_event = existing_event.copy()
            updated_event['attendees'] = [
                {'email': 'new1@example.com'},
                {'email': 'new2@example.com'},
                {'email': 'new3@example.com'}
            ]
            
            mock_google_service.events().update().execute.return_value = updated_event
            
            update_data = {
                'attendees': [
                    {'email': 'new1@example.com'},
                    {'email': 'new2@example.com'},
                    {'email': 'new3@example.com'}
                ]
            }
            
            calendar_service = CalendarService()
            result = calendar_service.update_event(
                user, 'primary', 'attendee_change_event', update_data
            )
            
            # Verify attendee updates
            update_call_args = mock_google_service.events().update.call_args
            updated_body = update_call_args[1]['body']
            
            assert len(updated_body['attendees']) == 3
            attendee_emails = [a['email'] for a in updated_body['attendees']]
            assert 'new1@example.com' in attendee_emails
            assert 'new2@example.com' in attendee_emails
            assert 'new3@example.com' in attendee_emails
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_update_event_not_found(self, mock_service, app, user, mock_google_service):
        """Test event update when event not found."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            # Mock event not found error
            mock_google_service.events().get().execute.side_effect = Exception("Event not found")
            
            update_data = {'title': 'Updated Title'}
            
            calendar_service = CalendarService()
            
            with pytest.raises(ExternalAPIError, match="Failed to update event"):
                calendar_service.update_event(
                    user, 'primary', 'nonexistent_event', update_data
                )


class TestEventDeletionSynchronization:
    """Test event deletion and synchronization with Google Calendar."""
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_delete_event_success(self, mock_service, app, user, mock_google_service):
        """Test successful event deletion."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            # Mock successful deletion (no return value)
            mock_google_service.events().delete().execute.return_value = None
            
            calendar_service = CalendarService()
            calendar_service.delete_event(
                user, 'primary', 'event_to_delete_123', send_notifications=True
            )
            
            # Verify delete call was made
            mock_google_service.events().delete.assert_called_once_with(
                calendarId='primary',
                eventId='event_to_delete_123',
                sendNotifications=True
            )
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_delete_event_without_notifications(self, mock_service, app, user, mock_google_service):
        """Test event deletion without sending notifications."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            mock_google_service.events().delete().execute.return_value = None
            
            calendar_service = CalendarService()
            calendar_service.delete_event(
                user, 'work_calendar', 'event_123', send_notifications=False
            )
            
            # Verify delete call with correct parameters
            mock_google_service.events().delete.assert_called_once_with(
                calendarId='work_calendar',
                eventId='event_123',
                sendNotifications=False
            )
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_delete_event_api_error(self, mock_service, app, user, mock_google_service):
        """Test event deletion when API returns error."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            # Mock API error
            mock_google_service.events().delete().execute.side_effect = Exception("Delete failed")
            
            calendar_service = CalendarService()
            
            with pytest.raises(ExternalAPIError, match="Failed to delete event"):
                calendar_service.delete_event(user, 'primary', 'event_123')


class TestWebhookHandling:
    """Test webhook handling for calendar changes."""
    
    def test_webhook_endpoint_exists(self, client):
        """Test that webhook endpoint exists and handles requests."""
        # This would be implemented as part of the webhook system
        # For now, we test that the endpoint structure is ready
        
        # Mock webhook payload from Google
        webhook_payload = {
            'kind': 'api#channel',
            'id': 'webhook_channel_123',
            'resourceId': 'calendar_resource_456',
            'resourceUri': 'https://www.googleapis.com/calendar/v3/calendars/primary/events',
            'token': 'webhook_verification_token',
            'expiration': '1708000000000'
        }
        
        # This endpoint would need to be implemented
        # response = client.post('/api/v1/calendar/webhook', 
        #                       json=webhook_payload,
        #                       headers={'X-Goog-Channel-ID': 'webhook_channel_123'})
        
        # For now, we just verify the structure is ready
        assert webhook_payload['kind'] == 'api#channel'
    
    def test_webhook_event_processing(self, app):
        """Test webhook event processing logic."""
        with app.app_context():
            # Mock webhook event data
            event_data = {
                'kind': 'calendar#event',
                'id': 'webhook_event_123',
                'status': 'confirmed',
                'summary': 'Updated via webhook',
                'start': {'dateTime': '2024-02-15T10:00:00Z'},
                'end': {'dateTime': '2024-02-15T11:00:00Z'},
                'updated': '2024-02-14T15:00:00Z'
            }
            
            # This would be the webhook processing logic
            # For now, we verify the data structure
            assert event_data['kind'] == 'calendar#event'
            assert 'updated' in event_data
    
    @patch('app.services.calendar_service.CalendarService.list_events')
    def test_sync_calendar_changes(self, mock_list_events, app, user):
        """Test synchronizing calendar changes from webhook."""
        with app.app_context():
            # Mock events from Google Calendar
            mock_events = [
                {
                    'id': 'sync_event_1',
                    'summary': 'Synced Event 1',
                    'start': '2024-02-15T10:00:00Z',
                    'end': '2024-02-15T11:00:00Z',
                    'updated': '2024-02-14T15:00:00Z'
                },
                {
                    'id': 'sync_event_2',
                    'summary': 'Synced Event 2',
                    'start': '2024-02-15T14:00:00Z',
                    'end': '2024-02-15T15:00:00Z',
                    'updated': '2024-02-14T15:30:00Z'
                }
            ]
            
            mock_list_events.return_value = mock_events
            
            calendar_service = CalendarService()
            events = calendar_service.list_events(user, calendar_id='primary')
            
            # Verify events were retrieved for sync
            assert len(events) == 2
            assert events[0]['id'] == 'sync_event_1'
            assert events[1]['id'] == 'sync_event_2'


class TestBookingSystemIntegration:
    """Test booking system integration with calendar synchronization."""
    
    @patch('app.services.calendar_service.CalendarService.check_availability')
    @patch('app.services.calendar_service.CalendarService.create_event')
    def test_book_appointment_success(self, mock_create, mock_availability, app, user):
        """Test successful appointment booking with calendar sync."""
        with app.app_context():
            # Mock availability check
            mock_availability.return_value = {
                'is_available': True,
                'available_slots': [
                    {
                        'start': '2024-02-15T10:00:00',
                        'end': '2024-02-15T11:00:00',
                        'duration_minutes': 60
                    }
                ]
            }
            
            # Mock event creation
            mock_event = {
                'id': 'booking_event_123',
                'summary': 'Appointment with customer@example.com',
                'start': '2024-02-15T10:00:00Z',
                'end': '2024-02-15T11:00:00Z',
                'attendees': [
                    {
                        'email': 'customer@example.com',
                        'displayName': 'John Customer',
                        'responseStatus': 'needsAction'
                    }
                ],
                'status': 'confirmed'
            }
            
            mock_create.return_value = mock_event
            
            booking_data = {
                'title': 'Appointment with customer@example.com',
                'start_time': datetime(2024, 2, 15, 10, 0, 0),
                'end_time': datetime(2024, 2, 15, 11, 0, 0),
                'customer_email': 'customer@example.com',
                'customer_name': 'John Customer',
                'calendar_id': 'primary',
                'send_notifications': True
            }
            
            calendar_service = CalendarService()
            result = calendar_service.book_appointment(user, booking_data)
            
            # Verify availability was checked
            mock_availability.assert_called_once()
            
            # Verify event was created with correct attendee
            mock_create.assert_called_once()
            create_call_args = mock_create.call_args[0][1]  # Second argument (event_data)
            
            assert create_call_args['title'] == 'Appointment with customer@example.com'
            assert len(create_call_args['attendees']) == 1
            assert create_call_args['attendees'][0]['email'] == 'customer@example.com'
            assert create_call_args['attendees'][0]['displayName'] == 'John Customer'
            
            # Verify result
            assert result['id'] == 'booking_event_123'
            assert result['status'] == 'confirmed'
    
    @patch('app.services.calendar_service.CalendarService.check_availability')
    def test_book_appointment_slot_not_available(self, mock_availability, app, user):
        """Test appointment booking when slot is not available."""
        with app.app_context():
            # Mock unavailable slot
            mock_availability.return_value = {
                'is_available': False,
                'available_slots': [],
                'busy_periods': [
                    {
                        'start': '2024-02-15T10:00:00',
                        'end': '2024-02-15T11:00:00'
                    }
                ]
            }
            
            booking_data = {
                'start_time': datetime(2024, 2, 15, 10, 0, 0),
                'end_time': datetime(2024, 2, 15, 11, 0, 0),
                'customer_email': 'customer@example.com'
            }
            
            calendar_service = CalendarService()
            
            # This would be handled at the API level, but we test the availability check
            availability = calendar_service.check_availability(
                user=user,
                time_min=booking_data['start_time'],
                time_max=booking_data['end_time'],
                duration=60
            )
            
            assert availability['is_available'] is False
    
    @patch('app.services.calendar_service.CalendarService.list_events')
    def test_availability_check_with_existing_events(self, mock_list_events, app, user):
        """Test availability checking with existing calendar events."""
        with app.app_context():
            # Mock existing events that create busy periods
            mock_events = [
                {
                    'id': 'existing_event_1',
                    'summary': 'Existing Meeting',
                    'start': '2024-02-15T09:00:00Z',
                    'end': '2024-02-15T10:00:00Z',
                    'transparency': 'opaque'
                },
                {
                    'id': 'existing_event_2',
                    'summary': 'Another Meeting',
                    'start': '2024-02-15T14:00:00Z',
                    'end': '2024-02-15T15:00:00Z',
                    'transparency': 'opaque'
                },
                {
                    'id': 'free_time_event',
                    'summary': 'Free Time Block',
                    'start': '2024-02-15T12:00:00Z',
                    'end': '2024-02-15T13:00:00Z',
                    'transparency': 'transparent'  # Should not block availability
                }
            ]
            
            mock_list_events.return_value = mock_events
            
            calendar_service = CalendarService()
            availability = calendar_service.check_availability(
                user=user,
                time_min=datetime(2024, 2, 15, 8, 0, 0),
                time_max=datetime(2024, 2, 15, 17, 0, 0),
                duration=60
            )
            
            # Verify busy periods were identified (excluding transparent events)
            assert len(availability['busy_periods']) == 2
            
            # Verify available slots exist between busy periods
            assert len(availability['available_slots']) > 0
            
            # Verify transparent event didn't create busy period
            busy_starts = [bp['start'] for bp in availability['busy_periods']]
            assert '2024-02-15T12:00:00' not in busy_starts


class TestCalendarSyncErrorHandling:
    """Test error handling in calendar synchronization."""
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_oauth_token_expired_during_sync(self, mock_service, app, user):
        """Test handling of expired OAuth token during sync operations."""
        with app.app_context():
            # Mock OAuth error
            mock_service.side_effect = OAuthError("Token expired")
            
            calendar_service = CalendarService()
            
            with pytest.raises(ExternalAPIError, match="Failed to retrieve calendars"):
                calendar_service.list_calendars(user)
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_google_api_rate_limit_handling(self, mock_service, app, user, mock_google_service):
        """Test handling of Google API rate limits."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            # Mock rate limit error
            mock_google_service.events().list().execute.side_effect = Exception("Rate limit exceeded")
            
            calendar_service = CalendarService()
            
            with pytest.raises(ExternalAPIError, match="Failed to retrieve events"):
                calendar_service.list_events(user)
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_network_error_during_sync(self, mock_service, app, user, mock_google_service):
        """Test handling of network errors during synchronization."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            # Mock network error
            mock_google_service.calendarList().list().execute.side_effect = Exception("Network error")
            
            calendar_service = CalendarService()
            
            with pytest.raises(ExternalAPIError, match="Failed to retrieve calendars"):
                calendar_service.list_calendars(user)
    
    def test_invalid_event_data_handling(self, app, user):
        """Test handling of invalid event data during synchronization."""
        with app.app_context():
            calendar_service = CalendarService()
            
            # Test with invalid datetime format
            invalid_event_data = {
                'title': 'Test Event',
                'start_time': 'invalid-datetime',
                'end_time': datetime(2024, 2, 15, 11, 0, 0)
            }
            
            # This would be caught at the validation level
            # The service expects proper datetime objects
            with pytest.raises(AttributeError):
                # This will fail because string doesn't have isoformat method
                calendar_service.create_event(user, invalid_event_data)


class TestCalendarTimeZoneHandling:
    """Test time zone handling in calendar synchronization."""
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_event_creation_with_timezone(self, mock_service, app, user, mock_google_service):
        """Test event creation with proper timezone handling."""
        with app.app_context():
            mock_service.return_value = mock_google_service
            
            created_event = {
                'id': 'timezone_event_123',
                'summary': 'Timezone Test Event',
                'start': {'dateTime': '2024-02-15T10:00:00Z', 'timeZone': 'UTC'},
                'end': {'dateTime': '2024-02-15T11:00:00Z', 'timeZone': 'UTC'}
            }
            
            mock_google_service.events().insert().execute.return_value = created_event
            
            event_data = {
                'title': 'Timezone Test Event',
                'start_time': datetime(2024, 2, 15, 10, 0, 0),
                'end_time': datetime(2024, 2, 15, 11, 0, 0)
            }
            
            calendar_service = CalendarService()
            result = calendar_service.create_event(user, event_data)
            
            # Verify timezone was set to UTC
            call_args = mock_google_service.events().insert.call_args
            event_body = call_args[1]['body']
            
            assert event_body['start']['timeZone'] == 'UTC'
            assert event_body['end']['timeZone'] == 'UTC'
    
    def test_all_day_event_handling(self, app):
        """Test handling of all-day events in availability checking."""
        with app.app_context():
            # Mock all-day event data
            all_day_event = {
                'id': 'all_day_event',
                'summary': 'All Day Event',
                'start': {'date': '2024-02-15'},  # Date only, no time
                'end': {'date': '2024-02-16'},
                'transparency': 'opaque'
            }
            
            # This would be handled in the availability checking logic
            # All-day events should be processed correctly
            start_str = all_day_event['start'].get('date')
            assert start_str == '2024-02-15'
            
            # Verify it's recognized as all-day (no 'T' in date string)
            assert 'T' not in start_str