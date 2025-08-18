"""Unit tests for invoice management endpoints."""
import pytest
import json
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from flask import url_for
from app.models.billing import Invoice, Subscription, Plan
from app.models.tenant import Tenant
from app.models.user import User
from app.services.stripe_service import StripeService
from app.utils.exceptions import StripeError, ValidationError


@pytest.fixture
def mock_stripe_service():
    """Mock Stripe service for testing."""
    with patch('app.billing.invoices.StripeService') as mock:
        service_instance = Mock()
        mock.return_value = service_instance
        yield service_instance


@pytest.fixture
def sample_invoice_data():
    """Sample invoice data for testing."""
    return {
        'customer_id': 'cus_test123',
        'amount': 100.00,
        'currency': 'USD',
        'description': 'Test invoice',
        'metadata': {'test': 'data'}
    }


@pytest.fixture
def sample_invoice(app):
    """Create a sample invoice for testing."""
    with app.app_context():
        tenant = Tenant.create(name="Test Tenant", slug="test-tenant")
        
        invoice = Invoice.create(
            tenant_id=tenant.id,
            stripe_invoice_id='in_test123',
            invoice_number='INV-001',
            amount_total=Decimal('100.00'),
            amount_paid=Decimal('0.00'),
            currency='USD',
            status='draft'
        )
        
        return invoice


class TestInvoiceListEndpoint:
    """Test invoice listing endpoint."""
    
    def test_list_invoices_success(self, client, auth_headers, sample_invoice):
        """Test successful invoice listing."""
        response = client.get('/api/v1/billing/invoices', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'items' in data['data']
        assert 'pagination' in data['data']
    
    def test_list_invoices_with_filters(self, client, auth_headers):
        """Test invoice listing with filters."""
        response = client.get(
            '/api/v1/billing/invoices?status=paid&start_date=2024-01-01T00:00:00Z',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_list_invoices_pagination(self, client, auth_headers):
        """Test invoice listing pagination."""
        response = client.get(
            '/api/v1/billing/invoices?page=1&per_page=10',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['pagination']['page'] == 1
        assert data['data']['pagination']['per_page'] == 10
    
    def test_list_invoices_invalid_date_filter(self, client, auth_headers):
        """Test invoice listing with invalid date filter."""
        response = client.get(
            '/api/v1/billing/invoices?start_date=invalid-date',
            headers=auth_headers
        )
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'validation_errors' in data['error']['details']
    
    def test_list_invoices_unauthorized(self, client):
        """Test invoice listing without authentication."""
        response = client.get('/api/v1/billing/invoices')
        
        assert response.status_code == 401


class TestInvoiceGetEndpoint:
    """Test invoice retrieval endpoint."""
    
    def test_get_invoice_success(self, client, auth_headers, sample_invoice):
        """Test successful invoice retrieval."""
        response = client.get(
            f'/api/v1/billing/invoices/{sample_invoice.id}',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['id'] == sample_invoice.id
        assert data['data']['amount_total'] == '100.00'
    
    def test_get_invoice_not_found(self, client, auth_headers):
        """Test invoice retrieval with non-existent ID."""
        response = client.get('/api/v1/billing/invoices/99999', headers=auth_headers)
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'not found' in data['error']['message'].lower()
    
    def test_get_invoice_unauthorized(self, client, sample_invoice):
        """Test invoice retrieval without authentication."""
        response = client.get(f'/api/v1/billing/invoices/{sample_invoice.id}')
        
        assert response.status_code == 401


class TestInvoiceCreateEndpoint:
    """Test invoice creation endpoint."""
    
    def test_create_invoice_success(self, client, auth_headers, sample_invoice_data, mock_stripe_service):
        """Test successful invoice creation."""
        # Mock Stripe service response
        mock_invoice = Mock()
        mock_invoice.to_dict.return_value = {
            'id': 1,
            'stripe_invoice_id': 'in_test123',
            'amount_total': '100.00',
            'status': 'draft'
        }
        mock_stripe_service.create_invoice.return_value = mock_invoice
        
        response = client.post(
            '/api/v1/billing/invoices',
            headers=auth_headers,
            json=sample_invoice_data
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        mock_stripe_service.create_invoice.assert_called_once()
    
    def test_create_invoice_missing_customer_id(self, client, auth_headers):
        """Test invoice creation without customer ID."""
        response = client.post(
            '/api/v1/billing/invoices',
            headers=auth_headers,
            json={'amount': 100.00}
        )
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'validation_errors' in data['error']['details']
    
    def test_create_invoice_invalid_amount(self, client, auth_headers):
        """Test invoice creation with invalid amount."""
        response = client.post(
            '/api/v1/billing/invoices',
            headers=auth_headers,
            json={
                'customer_id': 'cus_test123',
                'amount': -50.00
            }
        )
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_create_invoice_stripe_error(self, client, auth_headers, sample_invoice_data, mock_stripe_service):
        """Test invoice creation with Stripe error."""
        mock_stripe_service.create_invoice.side_effect = StripeError("Stripe API error")
        
        response = client.post(
            '/api/v1/billing/invoices',
            headers=auth_headers,
            json=sample_invoice_data
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error']['code'] == 'STRIPE_ERROR'
    
    def test_create_invoice_unauthorized(self, client, sample_invoice_data):
        """Test invoice creation without authentication."""
        response = client.post('/api/v1/billing/invoices', json=sample_invoice_data)
        
        assert response.status_code == 401


class TestInvoiceFinalizeEndpoint:
    """Test invoice finalization endpoint."""
    
    def test_finalize_invoice_success(self, client, auth_headers, sample_invoice, mock_stripe_service):
        """Test successful invoice finalization."""
        # Mock Stripe service response
        mock_invoice = Mock()
        mock_invoice.to_dict.return_value = {
            'id': sample_invoice.id,
            'status': 'open'
        }
        mock_stripe_service.finalize_invoice.return_value = mock_invoice
        
        response = client.post(
            f'/api/v1/billing/invoices/{sample_invoice.id}/finalize',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        mock_stripe_service.finalize_invoice.assert_called_once_with(sample_invoice.id)
    
    def test_finalize_invoice_not_draft(self, client, auth_headers, sample_invoice):
        """Test finalizing non-draft invoice."""
        sample_invoice.status = 'paid'
        sample_invoice.save()
        
        response = client.post(
            f'/api/v1/billing/invoices/{sample_invoice.id}/finalize',
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'draft' in data['error']['message'].lower()
    
    def test_finalize_invoice_not_found(self, client, auth_headers):
        """Test finalizing non-existent invoice."""
        response = client.post('/api/v1/billing/invoices/99999/finalize', headers=auth_headers)
        
        assert response.status_code == 404


class TestInvoiceSendEndpoint:
    """Test invoice sending endpoint."""
    
    def test_send_invoice_success(self, client, auth_headers, sample_invoice, mock_stripe_service):
        """Test successful invoice sending."""
        sample_invoice.status = 'open'
        sample_invoice.save()
        
        # Mock Stripe service response
        mock_invoice = Mock()
        mock_invoice.to_dict.return_value = {
            'id': sample_invoice.id,
            'status': 'open'
        }
        mock_stripe_service.send_invoice.return_value = mock_invoice
        
        response = client.post(
            f'/api/v1/billing/invoices/{sample_invoice.id}/send',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        mock_stripe_service.send_invoice.assert_called_once_with(sample_invoice.id)
    
    def test_send_invoice_invalid_status(self, client, auth_headers, sample_invoice):
        """Test sending invoice with invalid status."""
        sample_invoice.status = 'paid'
        sample_invoice.save()
        
        response = client.post(
            f'/api/v1/billing/invoices/{sample_invoice.id}/send',
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False


class TestInvoiceVoidEndpoint:
    """Test invoice voiding endpoint."""
    
    def test_void_invoice_success(self, client, auth_headers, sample_invoice, mock_stripe_service):
        """Test successful invoice voiding."""
        sample_invoice.status = 'open'
        sample_invoice.save()
        
        # Mock Stripe service response
        mock_invoice = Mock()
        mock_invoice.to_dict.return_value = {
            'id': sample_invoice.id,
            'status': 'void'
        }
        mock_stripe_service.void_invoice.return_value = mock_invoice
        
        response = client.post(
            f'/api/v1/billing/invoices/{sample_invoice.id}/void',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        mock_stripe_service.void_invoice.assert_called_once_with(sample_invoice.id)
    
    def test_void_paid_invoice(self, client, auth_headers, sample_invoice):
        """Test voiding paid invoice."""
        sample_invoice.status = 'paid'
        sample_invoice.save()
        
        response = client.post(
            f'/api/v1/billing/invoices/{sample_invoice.id}/void',
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'paid' in data['error']['message'].lower()


class TestInvoiceStatusEndpoint:
    """Test invoice status endpoint."""
    
    def test_get_invoice_status_success(self, client, auth_headers, sample_invoice, mock_stripe_service):
        """Test successful invoice status retrieval."""
        # Mock Stripe service response
        status_data = {
            'id': sample_invoice.id,
            'status': 'open',
            'amount_total': 100.00,
            'amount_paid': 0.00
        }
        mock_stripe_service.get_invoice_status.return_value = status_data
        
        response = client.get(
            f'/api/v1/billing/invoices/{sample_invoice.id}/status',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['status'] == 'open'
        mock_stripe_service.get_invoice_status.assert_called_once_with(sample_invoice.id)


class TestInvoicePaymentLinkEndpoint:
    """Test invoice payment link endpoint."""
    
    def test_create_payment_link_success(self, client, auth_headers, sample_invoice, mock_stripe_service):
        """Test successful payment link creation."""
        sample_invoice.status = 'open'
        sample_invoice.save()
        
        # Mock Stripe service response
        payment_url = 'https://checkout.stripe.com/pay/test123'
        mock_stripe_service.create_payment_link.return_value = payment_url
        
        response = client.post(
            f'/api/v1/billing/invoices/{sample_invoice.id}/payment-link',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['payment_url'] == payment_url
        mock_stripe_service.create_payment_link.assert_called_once_with(sample_invoice.id)
    
    def test_create_payment_link_paid_invoice(self, client, auth_headers, sample_invoice):
        """Test creating payment link for paid invoice."""
        sample_invoice.status = 'paid'
        sample_invoice.save()
        
        response = client.post(
            f'/api/v1/billing/invoices/{sample_invoice.id}/payment-link',
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False


class TestInvoiceSummaryEndpoint:
    """Test invoice summary endpoint."""
    
    def test_get_invoice_summary_success(self, client, auth_headers, sample_invoice):
        """Test successful invoice summary retrieval."""
        response = client.get('/api/v1/billing/invoices/reports/summary', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'totals' in data['data']
        assert 'status_breakdown' in data['data']
        assert 'overdue' in data['data']
    
    def test_get_invoice_summary_with_date_range(self, client, auth_headers):
        """Test invoice summary with date range."""
        start_date = '2024-01-01T00:00:00Z'
        end_date = '2024-12-31T23:59:59Z'
        
        response = client.get(
            f'/api/v1/billing/invoices/reports/summary?start_date={start_date}&end_date={end_date}',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['period']['start_date'] == start_date
        assert data['data']['period']['end_date'] == end_date


class TestInvoiceWebhookEndpoint:
    """Test invoice webhook endpoint."""
    
    def test_webhook_success(self, client, mock_stripe_service):
        """Test successful webhook processing."""
        webhook_data = {
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'id': 'in_test123',
                    'status': 'paid',
                    'amount_paid': 10000
                }
            }
        }
        
        mock_stripe_service.handle_webhook_event.return_value = True
        
        response = client.post(
            '/api/v1/billing/invoices/webhook',
            json=webhook_data
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        mock_stripe_service.handle_webhook_event.assert_called_once()
    
    def test_webhook_invalid_json(self, client):
        """Test webhook with invalid JSON."""
        response = client.post(
            '/api/v1/billing/invoices/webhook',
            data='invalid json',
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False


class TestStripeServiceIntegration:
    """Test Stripe service integration."""
    
    def test_stripe_service_initialization(self):
        """Test Stripe service can be initialized."""
        service = StripeService()
        assert service is not None
    
    @patch('stripe.Invoice.create')
    def test_create_invoice_stripe_integration(self, mock_stripe_create, app):
        """Test invoice creation with Stripe integration."""
        with app.app_context():
            # Mock Stripe response
            mock_stripe_invoice = Mock()
            mock_stripe_invoice.id = 'in_test123'
            mock_stripe_invoice.number = 'INV-001'
            mock_stripe_invoice.total = 10000  # $100.00 in cents
            mock_stripe_invoice.amount_paid = 0
            mock_stripe_invoice.currency = 'usd'
            mock_stripe_invoice.status = 'draft'
            mock_stripe_invoice.created = 1640995200  # 2022-01-01
            mock_stripe_invoice.due_date = None
            mock_stripe_invoice.hosted_invoice_url = None
            mock_stripe_invoice.invoice_pdf = None
            mock_stripe_invoice.payment_intent = None
            mock_stripe_invoice.lines.data = []
            
            mock_stripe_create.return_value = mock_stripe_invoice
            
            # Create tenant for testing
            tenant = Tenant.create(name="Test Tenant", slug="test-tenant")
            
            service = StripeService()
            invoice = service.create_invoice(
                tenant_id=tenant.id,
                customer_id='cus_test123',
                amount=Decimal('100.00'),
                currency='USD'
            )
            
            assert invoice is not None
            assert invoice.stripe_invoice_id == 'in_test123'
            assert invoice.amount_total == Decimal('100.00')
            mock_stripe_create.assert_called_once()


class TestInvoiceModelMethods:
    """Test invoice model methods and properties."""
    
    def test_invoice_is_paid_property(self, app):
        """Test invoice is_paid property."""
        with app.app_context():
            tenant = Tenant.create(name="Test Tenant", slug="test-tenant")
            
            invoice = Invoice.create(
                tenant_id=tenant.id,
                amount_total=Decimal('100.00'),
                amount_paid=Decimal('100.00'),
                status='paid'
            )
            
            assert invoice.is_paid is True
    
    def test_invoice_amount_due_property(self, app):
        """Test invoice amount_due property."""
        with app.app_context():
            tenant = Tenant.create(name="Test Tenant", slug="test-tenant")
            
            invoice = Invoice.create(
                tenant_id=tenant.id,
                amount_total=Decimal('100.00'),
                amount_paid=Decimal('30.00'),
                status='open'
            )
            
            assert invoice.amount_due == 70.00
    
    def test_invoice_overdue_property(self, app):
        """Test invoice is_overdue property."""
        with app.app_context():
            tenant = Tenant.create(name="Test Tenant", slug="test-tenant")
            
            # Create overdue invoice
            past_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
            invoice = Invoice.create(
                tenant_id=tenant.id,
                amount_total=Decimal('100.00'),
                amount_paid=Decimal('0.00'),
                status='open',
                due_date=past_date
            )
            
            assert invoice.is_overdue is True
    
    def test_invoice_to_dict_method(self, app):
        """Test invoice to_dict method."""
        with app.app_context():
            tenant = Tenant.create(name="Test Tenant", slug="test-tenant")
            
            invoice = Invoice.create(
                tenant_id=tenant.id,
                stripe_invoice_id='in_test123',
                amount_total=Decimal('100.00'),
                amount_paid=Decimal('0.00'),
                status='draft'
            )
            
            data = invoice.to_dict()
            
            assert isinstance(data, dict)
            assert data['id'] == invoice.id
            assert data['stripe_invoice_id'] == 'in_test123'
            assert data['amount_total'] == '100.00'
            assert data['is_paid'] is False
            assert data['amount_due'] == 100.00
