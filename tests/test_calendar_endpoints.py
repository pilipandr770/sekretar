"""Tests for calendar endpoints."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from flask import json

from app import create_app, db
from app.models.user import User
from app.models.tenant import Tenant
from app.services.calendar_service import CalendarService
from app.utils.exceptions import OAuthError, ExternalAPIError


@pytest.fixture
def app():
    """Create test app."""
    app = create_app('testing')
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
            name='Test Tenant',
            domain='test.example.com',
            slug='test-tenant',
            subscription_status='active'
        )
        tenant.save()
        return tenant


@pytest.fixture
def user(app, tenant):
    """Create test user with Google Calendar connected."""
    with app.app_context():
        user = User.create(
            email='test@example.com',
            password='password123',
            tenant_id=tenant.id,
            role='owner'
        )
        
        # Set up Google OAuth tokens
        token_data = {
            'token': 'access_token',
            'refresh_token': 'refresh_token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'scopes': ['https://www.googleapis.com/auth/calendar'],
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


class TestCalendarConnectionStatus:
    """Test calendar connection status endpoint."""
    
    def test_connection_status_not_authenticated(self, client):
        """Test connection status without authentication."""
        response = client.get('/api/v1/calendar/connection/status')
        assert response.status_code == 401
    
    def test_connection_status_not_configured(self, client, auth_headers):
        """Test connection status when OAuth not configured."""
        with patch('app.services.google_oauth.GoogleOAuthService.is_configured', return_value=False):
            response = client.get('/api/v1/calendar/connection/status', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['data']['connected'] is False
            assert data['data']['configured'] is False
    
    @patch('app.services.google_oauth.GoogleOAuthService.test_connection')
    @patch('app.services.google_oauth.GoogleOAuthService.is_configured')
    def test_connection_status_connected(self, mock_configured, mock_test, client, auth_headers):
        """Test connection status when connected."""
        mock_configured.return_value = True
        mock_test.return_value = {
            'connected': True,
            'calendar_count': 3,
            'primary_calendar': {'id': 'primary', 'summary': 'Test Calendar'}
        }
        
        response = client.get('/api/v1/calendar/connection/status', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['connected'] is True
        assert data['data']['configured'] is True
        assert data['data']['calendar_count'] == 3


class TestCalendarList:
    """Test calendar list endpoint."""
    
    def test_list_calendars_not_authenticated(self, client):
        """Test list calendars without authentication."""
        response = client.get('/api/v1/calendar/calendars')
        assert response.status_code == 401
    
    def test_list_calendars_not_connected(self, client, auth_headers, user):
        """Test list calendars when not connected."""
        user.google_calendar_connected = False
        user.save()
        
        response = client.get('/api/v1/calendar/calendars', headers=auth_headers)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'CALENDAR_NOT_CONNECTED'
    
    @patch('app.services.calendar_service.CalendarService.list_calendars')
    def test_list_calendars_success(self, mock_list, client, auth_headers):
        """Test successful calendar listing."""
        mock_calendars = [
            {
                'id': 'primary',
                'summary': 'Primary Calendar',
                'primary': True,
                'access_role': 'owner'
            },
            {
                'id': 'calendar2',
                'summary': 'Work Calendar',
                'primary': False,
                'access_role': 'writer'
            }
        ]
        mock_list.return_value = mock_calendars
        
        response = client.get('/api/v1/calendar/calendars', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['count'] == 2
        assert len(data['data']['calendars']) == 2
        assert data['data']['calendars'][0]['id'] == 'primary'
    
    @patch('app.services.calendar_service.CalendarService.list_calendars')
    def test_list_calendars_oauth_error(self, mock_list, client, auth_headers):
        """Test calendar listing with OAuth error."""
        mock_list.side_effect = OAuthError("Token expired")
        
        response = client.get('/api/v1/calendar/calendars', headers=auth_headers)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'OAUTH_ERROR'


class TestCalendarEvents:
    """Test calendar events endpoints."""
    
    def test_list_events_not_authenticated(self, client):
        """Test list events without authentication."""
        response = client.get('/api/v1/calendar/events')
        assert response.status_code == 401
    
    def test_list_events_not_connected(self, client, auth_headers, user):
        """Test list events when not connected."""
        user.google_calendar_connected = False
        user.save()
        
        response = client.get('/api/v1/calendar/events', headers=auth_headers)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'CALENDAR_NOT_CONNECTED'
    
    @patch('app.services.calendar_service.CalendarService.list_events')
    def test_list_events_success(self, mock_list, client, auth_headers):
        """Test successful event listing."""
        mock_events = [
            {
                'id': 'event1',
                'summary': 'Test Event',
                'start': '2024-01-15T10:00:00Z',
                'end': '2024-01-15T11:00:00Z',
                'location': 'Office'
            }
        ]
        mock_list.return_value = mock_events
        
        response = client.get('/api/v1/calendar/events')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['count'] == 1
        assert len(data['data']['events']) == 1
        assert data['data']['events'][0]['id'] == 'event1'
    
    def test_list_events_invalid_date(self, client, auth_headers):
        """Test list events with invalid date parameter."""
        response = client.get('/api/v1/calendar/events?start_date=invalid-date')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    def test_list_events_invalid_max_results(self, client, auth_headers):
        """Test list events with invalid max_results parameter."""
        response = client.get('/api/v1/calendar/events?max_results=300')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'


class TestCalendarAvailability:
    """Test calendar availability endpoint."""
    
    def test_check_availability_not_authenticated(self, client):
        """Test availability check without authentication."""
        response = client.get('/api/v1/calendar/availability')
        assert response.status_code == 401
    
    def test_check_availability_missing_dates(self, client, auth_headers):
        """Test availability check without required dates."""
        response = client.get('/api/v1/calendar/availability')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    @patch('app.services.calendar_service.CalendarService.check_availability')
    def test_check_availability_success(self, mock_check, client, auth_headers):
        """Test successful availability check."""
        mock_availability = {
            'is_available': True,
            'available_slots': [
                {
                    'start': '2024-01-15T10:00:00',
                    'end': '2024-01-15T11:00:00',
                    'duration_minutes': 60
                }
            ],
            'total_available_slots': 1,
            'busy_periods': [],
            'working_hours': {'start': '09:00', 'end': '17:00'},
            'duration_minutes': 60
        }
        mock_check.return_value = mock_availability
        
        start_date = '2024-01-15T09:00:00'
        end_date = '2024-01-15T17:00:00'
        
        response = client.get(
            f'/api/v1/calendar/availability?start_date={start_date}&end_date={end_date}'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['is_available'] is True
        assert len(data['data']['available_slots']) == 1
    
    def test_check_availability_invalid_duration(self, client, auth_headers):
        """Test availability check with invalid duration."""
        start_date = '2024-01-15T09:00:00'
        end_date = '2024-01-15T17:00:00'
        
        response = client.get(
            f'/api/v1/calendar/availability?start_date={start_date}&end_date={end_date}&duration=500'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'


class TestCreateEvent:
    """Test create event endpoint."""
    
    def test_create_event_not_authenticated(self, client):
        """Test create event without authentication."""
        response = client.post('/api/v1/calendar/events')
        assert response.status_code == 401
    
    def test_create_event_not_connected(self, client, auth_headers, user):
        """Test create event when not connected."""
        user.google_calendar_connected = False
        user.save()
        
        response = client.post('/api/v1/calendar/events', json={})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'CALENDAR_NOT_CONNECTED'
    
    def test_create_event_missing_data(self, client, auth_headers):
        """Test create event without required data."""
        response = client.post('/api/v1/calendar/events')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    def test_create_event_missing_fields(self, client, auth_headers):
        """Test create event with missing required fields."""
        event_data = {
            'title': 'Test Event'
            # Missing start_time and end_time
        }
        
        response = client.post('/api/v1/calendar/events', json=event_data)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    def test_create_event_invalid_time_range(self, client, auth_headers):
        """Test create event with invalid time range."""
        event_data = {
            'title': 'Test Event',
            'start_time': '2024-01-15T11:00:00',
            'end_time': '2024-01-15T10:00:00'  # End before start
        }
        
        response = client.post('/api/v1/calendar/events', json=event_data)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    @patch('app.services.calendar_service.CalendarService.create_event')
    def test_create_event_success(self, mock_create, client, auth_headers):
        """Test successful event creation."""
        mock_event = {
            'id': 'event123',
            'summary': 'Test Event',
            'start': '2024-01-15T10:00:00Z',
            'end': '2024-01-15T11:00:00Z',
            'status': 'confirmed'
        }
        mock_create.return_value = mock_event
        
        event_data = {
            'title': 'Test Event',
            'start_time': '2024-01-15T10:00:00',
            'end_time': '2024-01-15T11:00:00',
            'description': 'Test description',
            'attendees': ['attendee@example.com']
        }
        
        response = client.post('/api/v1/calendar/events', json=event_data)
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['data']['event']['id'] == 'event123'
        assert data['data']['event']['summary'] == 'Test Event'
    
    def test_create_event_invalid_attendee_email(self, client, auth_headers):
        """Test create event with invalid attendee email."""
        event_data = {
            'title': 'Test Event',
            'start_time': '2024-01-15T10:00:00',
            'end_time': '2024-01-15T11:00:00',
            'attendees': ['invalid-email']
        }
        
        response = client.post('/api/v1/calendar/events', json=event_data)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'


class TestUpdateEvent:
    """Test update event endpoint."""
    
    def test_update_event_not_authenticated(self, client):
        """Test update event without authentication."""
        response = client.put('/api/v1/calendar/events/event123')
        assert response.status_code == 401
    
    @patch('app.services.calendar_service.CalendarService.update_event')
    def test_update_event_success(self, mock_update, client, auth_headers):
        """Test successful event update."""
        mock_event = {
            'id': 'event123',
            'summary': 'Updated Event',
            'start': '2024-01-15T10:00:00Z',
            'end': '2024-01-15T11:00:00Z'
        }
        mock_update.return_value = mock_event
        
        update_data = {
            'title': 'Updated Event',
            'description': 'Updated description'
        }
        
        response = client.put('/api/v1/calendar/events/event123', json=update_data)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['event']['summary'] == 'Updated Event'
    
    def test_update_event_invalid_time_range(self, client, auth_headers):
        """Test update event with invalid time range."""
        update_data = {
            'start_time': '2024-01-15T11:00:00',
            'end_time': '2024-01-15T10:00:00'
        }
        
        response = client.put('/api/v1/calendar/events/event123', json=update_data)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'


class TestDeleteEvent:
    """Test delete event endpoint."""
    
    def test_delete_event_not_authenticated(self, client):
        """Test delete event without authentication."""
        response = client.delete('/api/v1/calendar/events/event123')
        assert response.status_code == 401
    
    @patch('app.services.calendar_service.CalendarService.delete_event')
    def test_delete_event_success(self, mock_delete, client, auth_headers):
        """Test successful event deletion."""
        mock_delete.return_value = None
        
        response = client.delete('/api/v1/calendar/events/event123')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'deleted successfully' in data['message']


class TestBookAppointment:
    """Test book appointment endpoint."""
    
    def test_book_appointment_not_authenticated(self, client):
        """Test book appointment without authentication."""
        response = client.post('/api/v1/calendar/book')
        assert response.status_code == 401
    
    def test_book_appointment_missing_fields(self, client, auth_headers):
        """Test book appointment with missing required fields."""
        booking_data = {
            'start_time': '2024-01-15T10:00:00'
            # Missing end_time and customer_email
        }
        
        response = client.post('/api/v1/calendar/book', json=booking_data)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    def test_book_appointment_invalid_email(self, client, auth_headers):
        """Test book appointment with invalid customer email."""
        booking_data = {
            'start_time': '2024-01-15T10:00:00',
            'end_time': '2024-01-15T11:00:00',
            'customer_email': 'invalid-email'
        }
        
        response = client.post('/api/v1/calendar/book', json=booking_data)
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    @patch('app.services.calendar_service.CalendarService.book_appointment')
    @patch('app.services.calendar_service.CalendarService.check_availability')
    def test_book_appointment_success(self, mock_availability, mock_book, client, auth_headers):
        """Test successful appointment booking."""
        mock_availability.return_value = {'is_available': True}
        mock_event = {
            'id': 'event123',
            'summary': 'Appointment with customer@example.com',
            'start': '2024-01-15T10:00:00Z',
            'end': '2024-01-15T11:00:00Z'
        }
        mock_book.return_value = mock_event
        
        booking_data = {
            'start_time': '2024-01-15T10:00:00',
            'end_time': '2024-01-15T11:00:00',
            'customer_email': 'customer@example.com',
            'customer_name': 'John Doe'
        }
        
        response = client.post('/api/v1/calendar/book', json=booking_data)
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['data']['event']['id'] == 'event123'
    
    @patch('app.services.calendar_service.CalendarService.check_availability')
    def test_book_appointment_slot_not_available(self, mock_availability, client, auth_headers):
        """Test booking appointment when slot is not available."""
        mock_availability.return_value = {'is_available': False}
        
        booking_data = {
            'start_time': '2024-01-15T10:00:00',
            'end_time': '2024-01-15T11:00:00',
            'customer_email': 'customer@example.com'
        }
        
        response = client.post('/api/v1/calendar/book', json=booking_data)
        
        assert response.status_code == 409
        data = json.loads(response.data)
        assert data['error']['code'] == 'SLOT_NOT_AVAILABLE'


class TestCalendarServiceUnit:
    """Unit tests for CalendarService."""
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_list_calendars(self, mock_service, app):
        """Test CalendarService.list_calendars method."""
        with app.app_context():
            # Mock Google Calendar service
            mock_calendar_service = Mock()
            mock_service.return_value = mock_calendar_service
            
            mock_calendar_service.calendarList().list().execute.return_value = {
                'items': [
                    {
                        'id': 'primary',
                        'summary': 'Primary Calendar',
                        'primary': True,
                        'accessRole': 'owner'
                    }
                ]
            }
            
            # Create service and test
            service = CalendarService()
            user = Mock()
            user.id = 1
            
            calendars = service.list_calendars(user)
            
            assert len(calendars) == 1
            assert calendars[0]['id'] == 'primary'
            assert calendars[0]['primary'] is True
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_list_events(self, mock_service, app):
        """Test CalendarService.list_events method."""
        with app.app_context():
            # Mock Google Calendar service
            mock_calendar_service = Mock()
            mock_service.return_value = mock_calendar_service
            
            mock_calendar_service.events().list().execute.return_value = {
                'items': [
                    {
                        'id': 'event1',
                        'summary': 'Test Event',
                        'start': {'dateTime': '2024-01-15T10:00:00Z'},
                        'end': {'dateTime': '2024-01-15T11:00:00Z'},
                        'status': 'confirmed'
                    }
                ]
            }
            
            # Create service and test
            service = CalendarService()
            user = Mock()
            user.id = 1
            
            events = service.list_events(user)
            
            assert len(events) == 1
            assert events[0]['id'] == 'event1'
            assert events[0]['summary'] == 'Test Event'
    
    @patch('app.services.calendar_service.CalendarService.list_events')
    def test_check_availability(self, mock_list_events, app):
        """Test CalendarService.check_availability method."""
        with app.app_context():
            # Mock existing events (busy periods)
            mock_list_events.return_value = [
                {
                    'id': 'event1',
                    'start': '2024-01-15T10:00:00Z',
                    'end': '2024-01-15T11:00:00Z',
                    'transparency': 'opaque'
                }
            ]
            
            # Create service and test
            service = CalendarService()
            user = Mock()
            user.id = 1
            
            start_time = datetime(2024, 1, 15, 9, 0, 0)
            end_time = datetime(2024, 1, 15, 17, 0, 0)
            
            availability = service.check_availability(
                user=user,
                time_min=start_time,
                time_max=end_time,
                duration=60
            )
            
            assert 'is_available' in availability
            assert 'available_slots' in availability
            assert 'busy_periods' in availability
            assert len(availability['busy_periods']) == 1
    
    @patch('app.services.google_oauth.GoogleOAuthService.get_calendar_service')
    def test_create_event(self, mock_service, app):
        """Test CalendarService.create_event method."""
        with app.app_context():
            # Mock Google Calendar service
            mock_calendar_service = Mock()
            mock_service.return_value = mock_calendar_service
            
            mock_calendar_service.events().insert().execute.return_value = {
                'id': 'event123',
                'summary': 'Test Event',
                'start': {'dateTime': '2024-01-15T10:00:00Z'},
                'end': {'dateTime': '2024-01-15T11:00:00Z'},
                'status': 'confirmed'
            }
            
            # Create service and test
            service = CalendarService()
            user = Mock()
            user.id = 1
            
            event_data = {
                'title': 'Test Event',
                'start_time': datetime(2024, 1, 15, 10, 0, 0),
                'end_time': datetime(2024, 1, 15, 11, 0, 0),
                'description': 'Test description'
            }
            
            event = service.create_event(user, event_data)
            
            assert event['id'] == 'event123'
            assert event['summary'] == 'Test Event'