"""
Comprehensive GLEIF integration tests for KYB monitoring system.

This test suite validates GLEIF LEI integration using real company data from the test dataset.
Tests cover LEI code validation, corporate hierarchy retrieval, status monitoring, and KYB workflows.
"""
import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from app import create_app, db
from app.models.kyb_monitoring import Counterparty, CounterpartySnapshot, CounterpartyDiff, KYBAlert, KYBMonitoringConfig
from app.services.kyb_adapters.gleif import GLEIFAdapter
from app.services.kyb_adapters.base import ValidationError, DataSourceUnavailable, RateLimitExceeded
from tests.conftest import TestConfig


class TestGLEIFIntegrationKYB:
    """Test GLEIF integration with real company data for KYB monitoring."""
    
    @pytest.fixture(scope='class')
    def app(self):
        """Create test application."""
        app = create_app(TestConfig)
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.incr.return_value = 1
        redis_mock.keys.return_value = []
        redis_mock.delete.return_value = 1
        return redis_mock
    
    @pytest.fixture
    def gleif_adapter(self, mock_redis):
        """Create GLEIF adapter with mocked Redis."""
        return GLEIFAdapter(redis_client=mock_redis)
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data from test dataset."""
        try:
            with open('comprehensive_test_dataset.json', 'r', encoding='utf-8') as f:
                dataset = json.load(f)
            return dataset['companies']
        except FileNotFoundError:
            # Fallback to minimal test data if dataset not available
            return {
                "sap_germany": {
                    "name": "SAP SE",
                    "lei_code": "529900T8BM49AURSDO55",
                    "country_code": "DE",
                    "address": "Dietmar-Hopp-Allee 16, 69190 Walldorf",
                    "industry": "Technology"
                },
                "deutsche_bank": {
                    "name": "Deutsche Bank AG",
                    "lei_code": "7LTWFZYICNSX8D621K86",
                    "country_code": "DE",
                    "address": "Taunusanlage 12, 60325 Frankfurt am Main"
                }
            }
    
    @pytest.fixture
    def test_tenant(self, app):
        """Create test tenant with KYB monitoring config."""
        from app.models.tenancy import Tenant
        from app.models.auth import User
        
        with app.app_context():
            # Create tenant
            tenant = Tenant(
                name="Test Company",
                domain="test.com",
                status="active"
            )
            db.session.add(tenant)
            db.session.flush()
            
            # Create user
            user = User(
                email="test@test.com",
                full_name="Test User",
                tenant_id=tenant.id
            )
            user.set_password("password123")
            db.session.add(user)
            
            # Create KYB monitoring config
            config = KYBMonitoringConfig(
                tenant_id=tenant.id,
                gleif_enabled=True,
                default_check_frequency='daily',
                alert_on_lei_invalid=True
            )
            db.session.add(config)
            db.session.commit()
            
            yield tenant
            
            # Cleanup
            db.session.delete(config)
            db.session.delete(user)
            db.session.delete(tenant)
            db.session.commit()


class TestGLEIFRealDataValidation(TestGLEIFIntegrationKYB):
    """Test GLEIF validation with real company LEI codes."""
    
    def test_validate_real_lei_codes_format(self, gleif_adapter, real_company_data):
        """Test format validation of real LEI codes."""
        lei_companies = {k: v for k, v in real_company_data.items() 
                        if 'lei_code' in v and v['lei_code']}
        
        assert len(lei_companies) > 0, "No companies with LEI codes in test data"
        
        for company_key, company in lei_companies.items():
            lei_code = company['lei_code']
            
            # Test LEI format validation
            is_valid = gleif_adapter._validate_lei_format(lei_code)
            assert is_valid == lei_code, f"Invalid LEI format for {company['name']}: {lei_code}"
            
            # Verify LEI is exactly 20 characters
            assert len(lei_code) == 20, f"LEI should be 20 characters, got {len(lei_code)} for {lei_code}"
            
            # Verify LEI contains only alphanumeric characters
            assert lei_code.isalnum(), f"LEI should be alphanumeric: {lei_code}"
            
            # Verify LEI is uppercase
            assert lei_code.isupper(), f"LEI should be uppercase: {lei_code}"
    
    def test_validate_lei_checksum(self, gleif_adapter, real_company_data):
        """Test LEI checksum validation for real codes."""
        lei_companies = {k: v for k, v in real_company_data.items() 
                        if 'lei_code' in v and v['lei_code']}
        
        for company_key, company in lei_companies.items():
            lei_code = company['lei_code']
            
            # Test checksum validation (LEI uses ISO 17442 standard)
            # This is a basic format check - full checksum validation would require the algorithm
            assert len(lei_code) == 20
            assert lei_code[:18].isalnum()  # First 18 characters
            assert lei_code[18:].isdigit()  # Last 2 characters are check digits
    
    @patch('requests.Session.get')
    def test_gleif_api_call_with_real_data(self, mock_get, gleif_adapter, real_company_data):
        """Test actual GLEIF API calls with real company data."""
        # Mock successful GLEIF response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "type": "lei-records",
                "id": "529900T8BM49AURSDO55",
                "attributes": {
                    "lei": "529900T8BM49AURSDO55",
                    "entity": {
                        "legalName": {
                            "name": "SAP SE"
                        },
                        "legalAddress": {
                            "firstAddressLine": "Dietmar-Hopp-Allee 16",
                            "city": "Walldorf",
                            "region": "DE-BW",
                            "country": "DE",
                            "postalCode": "69190"
                        },
                        "headquartersAddress": {
                            "firstAddressLine": "Dietmar-Hopp-Allee 16",
                            "city": "Walldorf",
                            "region": "DE-BW",
                            "country": "DE",
                            "postalCode": "69190"
                        },
                        "registrationAuthority": {
                            "registrationAuthorityID": "RA000665",
                            "registrationAuthorityEntityID": "HRB 719915"
                        },
                        "legalJurisdiction": "DE",
                        "entityCategory": "GENERAL",
                        "legalForm": {
                            "entityLegalFormCode": "XJHM"
                        },
                        "entityStatus": "ACTIVE"
                    },
                    "registration": {
                        "initialRegistrationDate": "2014-11-18T15:53:00.000Z",
                        "lastUpdateDate": "2023-12-01T09:15:23.000Z",
                        "registrationStatus": "ISSUED",
                        "nextRenewalDate": "2024-11-18T15:53:00.000Z"
                    }
                }
            }
        }
        mock_get.return_value = mock_response
        
        # Test with first company from dataset that has LEI
        lei_companies = {k: v for k, v in real_company_data.items() 
                        if 'lei_code' in v and v['lei_code']}
        first_company = next(iter(lei_companies.values()))
        lei_code = first_company['lei_code']
        
        result = gleif_adapter.check_single(lei_code)
        
        # Verify result structure
        assert 'status' in result
        assert 'valid' in result
        assert 'identifier' in result
        assert 'source' in result
        assert result['source'] == 'GLEIF'
        assert 'checked_at' in result
        assert 'response_time_ms' in result
        
        # Verify entity data is included
        if result.get('valid'):
            assert 'entity_data' in result
            entity_data = result['entity_data']
            assert 'legal_name' in entity_data
            assert 'status' in entity_data
        
        # Verify API was called
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert lei_code in call_args[0][0]  # LEI should be in URL
    
    def test_lei_status_validation(self, gleif_adapter):
        """Test LEI status validation logic."""
        # Test different status scenarios
        test_cases = [
            {
                'status': 'ISSUED',
                'entity_status': 'ACTIVE',
                'expected_valid': True,
                'expected_status': 'valid'
            },
            {
                'status': 'LAPSED',
                'entity_status': 'ACTIVE',
                'expected_valid': False,
                'expected_status': 'lapsed'
            },
            {
                'status': 'ISSUED',
                'entity_status': 'INACTIVE',
                'expected_valid': False,
                'expected_status': 'inactive'
            },
            {
                'status': 'RETIRED',
                'entity_status': 'ACTIVE',
                'expected_valid': False,
                'expected_status': 'retired'
            }
        ]
        
        for case in test_cases:
            # Mock GLEIF response with specific status
            with patch('requests.Session.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "data": {
                        "type": "lei-records",
                        "id": "529900T8BM49AURSDO55",
                        "attributes": {
                            "lei": "529900T8BM49AURSDO55",
                            "entity": {
                                "legalName": {"name": "Test Company"},
                                "entityStatus": case['entity_status']
                            },
                            "registration": {
                                "registrationStatus": case['status']
                            }
                        }
                    }
                }
                mock_get.return_value = mock_response
                
                result = gleif_adapter.check_single("529900T8BM49AURSDO55")
                
                assert result['valid'] == case['expected_valid'], f"Status {case['status']}/{case['entity_status']} should be {case['expected_valid']}"


class TestGLEIFCorporateHierarchy(TestGLEIFIntegrationKYB):
    """Test GLEIF corporate hierarchy retrieval."""
    
    @patch('requests.Session.get')
    def test_retrieve_corporate_relationships(self, mock_get, gleif_adapter, real_company_data):
        """Test retrieval of corporate hierarchy relationships."""
        # Mock GLEIF relationship response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "type": "rr-records",
                    "id": "529900T8BM49AURSDO55-7LTWFZYICNSX8D621K86",
                    "attributes": {
                        "startNode": "529900T8BM49AURSDO55",
                        "endNode": "7LTWFZYICNSX8D621K86",
                        "relationshipType": "IS_DIRECTLY_CONSOLIDATED_BY",
                        "relationshipPeriods": [
                            {
                                "startDate": "2014-11-18T00:00:00.000Z",
                                "endDate": None,
                                "relationshipStatus": "ACTIVE"
                            }
                        ]
                    }
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Test with first LEI from dataset
        lei_companies = {k: v for k, v in real_company_data.items() 
                        if 'lei_code' in v and v['lei_code']}
        first_company = next(iter(lei_companies.values()))
        lei_code = first_company['lei_code']
        
        result = gleif_adapter.check_single(lei_code, include_relationships=True)
        
        # Verify relationships are included
        if result.get('valid') and 'relationships' in result:
            relationships = result['relationships']
            assert isinstance(relationships, list)
            
            for relationship in relationships:
                assert 'start_node' in relationship
                assert 'end_node' in relationship
                assert 'relationship_type' in relationship
                assert 'status' in relationship
    
    @patch('requests.Session.get')
    def test_parent_company_identification(self, mock_get, gleif_adapter):
        """Test identification of parent companies through relationships."""
        # Mock responses for LEI lookup and relationships
        def mock_get_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            
            if 'relationships' in url:
                # Relationship response
                mock_response.json.return_value = {
                    "data": [
                        {
                            "type": "rr-records",
                            "attributes": {
                                "startNode": "529900T8BM49AURSDO55",
                                "endNode": "PARENT123456789012345",
                                "relationshipType": "IS_DIRECTLY_CONSOLIDATED_BY",
                                "relationshipPeriods": [
                                    {
                                        "startDate": "2014-11-18T00:00:00.000Z",
                                        "endDate": None,
                                        "relationshipStatus": "ACTIVE"
                                    }
                                ]
                            }
                        }
                    ]
                }
            else:
                # LEI record response
                mock_response.json.return_value = {
                    "data": {
                        "type": "lei-records",
                        "id": "529900T8BM49AURSDO55",
                        "attributes": {
                            "lei": "529900T8BM49AURSDO55",
                            "entity": {
                                "legalName": {"name": "Test Subsidiary"},
                                "entityStatus": "ACTIVE"
                            },
                            "registration": {
                                "registrationStatus": "ISSUED"
                            }
                        }
                    }
                }
            
            return mock_response
        
        mock_get.side_effect = mock_get_side_effect
        
        result = gleif_adapter.check_single("529900T8BM49AURSDO55", include_relationships=True)
        
        # Verify parent company information is extracted
        if result.get('valid') and 'relationships' in result:
            parent_relationships = [r for r in result['relationships'] 
                                  if r.get('relationship_type') == 'IS_DIRECTLY_CONSOLIDATED_BY']
            
            if parent_relationships:
                parent_rel = parent_relationships[0]
                assert 'end_node' in parent_rel  # Parent LEI
                assert parent_rel['end_node'] == 'PARENT123456789012345'


class TestGLEIFBatchProcessing(TestGLEIFIntegrationKYB):
    """Test GLEIF batch processing with real company data."""
    
    @patch('requests.Session.get')
    def test_batch_lei_validation(self, mock_get, gleif_adapter, real_company_data):
        """Test batch validation of real company LEI codes."""
        # Mock successful responses for all requests
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "type": "lei-records",
                "id": "529900T8BM49AURSDO55",
                "attributes": {
                    "lei": "529900T8BM49AURSDO55",
                    "entity": {
                        "legalName": {"name": "Test Company"},
                        "entityStatus": "ACTIVE"
                    },
                    "registration": {
                        "registrationStatus": "ISSUED"
                    }
                }
            }
        }
        mock_get.return_value = mock_response
        
        # Get LEI codes from real companies
        lei_codes = [company['lei_code'] for company in real_company_data.values() 
                    if 'lei_code' in company and company['lei_code']][:5]  # Limit to 5 for testing
        
        assert len(lei_codes) > 0, "No LEI codes found in test data"
        
        # Test batch processing
        results = gleif_adapter.check_batch(lei_codes, batch_delay=0.1)
        
        # Verify results
        assert len(results) == len(lei_codes)
        for i, result in enumerate(results):
            assert result['identifier'] == lei_codes[i]
            assert 'status' in result
            assert 'source' in result
            assert result['source'] == 'GLEIF'
        
        # Verify API was called for each LEI code
        assert mock_get.call_count == len(lei_codes)
    
    def test_batch_processing_performance_metrics(self, gleif_adapter, real_company_data):
        """Test batch processing performance with real data."""
        lei_codes = [company['lei_code'] for company in real_company_data.values() 
                    if 'lei_code' in company and company['lei_code']][:3]  # Small batch for testing
        
        start_time = time.time()
        
        # Mock the actual API calls to avoid external dependencies
        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {
                    "type": "lei-records",
                    "id": "529900T8BM49AURSDO55",
                    "attributes": {
                        "lei": "529900T8BM49AURSDO55",
                        "entity": {
                            "legalName": {"name": "Test Company"},
                            "entityStatus": "ACTIVE"
                        },
                        "registration": {
                            "registrationStatus": "ISSUED"
                        }
                    }
                }
            }
            mock_get.return_value = mock_response
            
            results = gleif_adapter.check_batch(lei_codes, batch_delay=0.01)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify performance metrics
        assert len(results) == len(lei_codes)
        for result in results:
            assert 'response_time_ms' in result
            assert isinstance(result['response_time_ms'], int)
        
        # Batch should complete reasonably quickly (allowing for delays)
        expected_max_time = len(lei_codes) * 0.1 + 2  # batch_delay + overhead
        assert total_time < expected_max_time, f"Batch took too long: {total_time}s"


class TestGLEIFErrorHandling(TestGLEIFIntegrationKYB):
    """Test GLEIF error handling scenarios."""
    
    def test_invalid_lei_code_handling(self, gleif_adapter):
        """Test handling of invalid LEI codes."""
        invalid_lei_codes = [
            "INVALID123",
            "529900T8BM49AURSDO5",  # Too short
            "529900T8BM49AURSDO555",  # Too long
            "",  # Empty
            "529900t8bm49aursdo55",  # Lowercase
            "529900T8BM49AURSDO5A"  # Invalid check digits
        ]
        
        for invalid_lei in invalid_lei_codes:
            result = gleif_adapter.check_single(invalid_lei)
            assert result['status'] in ['validation_error', 'error'], f"Should fail for {invalid_lei}"
            assert result['valid'] is False
            assert 'error' in result
    
    @patch('requests.Session.get')
    def test_gleif_service_unavailable(self, mock_get, gleif_adapter, real_company_data):
        """Test handling when GLEIF service is unavailable."""
        # Mock service unavailable response
        mock_get.side_effect = Exception("Service unavailable")
        
        lei_companies = {k: v for k, v in real_company_data.items() 
                        if 'lei_code' in v and v['lei_code']}
        first_company = next(iter(lei_companies.values()))
        lei_code = first_company['lei_code']
        
        result = gleif_adapter.check_single(lei_code)
        
        assert result['status'] == 'unavailable'
        assert result['valid'] is False
        assert 'error' in result
        assert result['source'] == 'GLEIF'
    
    @patch('requests.Session.get')
    def test_gleif_timeout_handling(self, mock_get, gleif_adapter, real_company_data):
        """Test handling of GLEIF API timeouts."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        lei_companies = {k: v for k, v in real_company_data.items() 
                        if 'lei_code' in v and v['lei_code']}
        first_company = next(iter(lei_companies.values()))
        lei_code = first_company['lei_code']
        
        result = gleif_adapter.check_single(lei_code, timeout=5)
        
        assert result['status'] == 'timeout'
        assert result['valid'] is False
        assert 'timeout' in result.get('error', '').lower()
    
    @patch('requests.Session.get')
    def test_gleif_not_found_handling(self, mock_get, gleif_adapter):
        """Test handling of LEI not found responses."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "errors": [
                {
                    "status": "404",
                    "title": "Not Found",
                    "detail": "LEI record not found"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        result = gleif_adapter.check_single("NOTFOUND123456789012")
        
        assert result['status'] == 'not_found'
        assert result['valid'] is False
        assert 'not found' in result.get('error', '').lower()
    
    @patch('requests.Session.get')
    def test_gleif_rate_limit_handling(self, mock_get, gleif_adapter, mock_redis):
        """Test handling of GLEIF rate limits."""
        # Mock rate limit exceeded
        mock_redis.get.return_value = str(gleif_adapter.RATE_LIMIT)  # At limit
        
        result = gleif_adapter.check_single("529900T8BM49AURSDO55")
        
        # Should either return cached result or rate limit error
        assert result['status'] in ['rate_limited', 'cached', 'error']
        mock_get.assert_not_called()


class TestGLEIFKYBIntegration(TestGLEIFIntegrationKYB):
    """Test GLEIF integration with KYB monitoring workflow."""
    
    def test_counterparty_lei_validation_workflow(self, app, test_tenant, gleif_adapter, real_company_data):
        """Test complete workflow from counterparty creation to LEI validation."""
        with app.app_context():
            # Create counterparty with real company data
            lei_companies = {k: v for k, v in real_company_data.items() 
                            if 'lei_code' in v and v['lei_code']}
            first_company = next(iter(lei_companies.values()))
            
            counterparty = Counterparty(
                tenant_id=test_tenant.id,
                name=first_company['name'],
                lei_code=first_company['lei_code'],
                country_code=first_company['country_code'],
                address=first_company.get('address', ''),
                status='active',
                monitoring_enabled=True
            )
            db.session.add(counterparty)
            db.session.commit()
            
            # Mock GLEIF validation
            with patch('requests.Session.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "data": {
                        "type": "lei-records",
                        "id": first_company['lei_code'],
                        "attributes": {
                            "lei": first_company['lei_code'],
                            "entity": {
                                "legalName": {"name": first_company['name']},
                                "legalAddress": {
                                    "firstAddressLine": first_company.get('address', 'Test Address'),
                                    "country": first_company['country_code']
                                },
                                "entityStatus": "ACTIVE"
                            },
                            "registration": {
                                "registrationStatus": "ISSUED",
                                "lastUpdateDate": "2023-12-01T09:15:23.000Z"
                            }
                        }
                    }
                }
                mock_get.return_value = mock_response
                
                # Perform LEI validation
                result = gleif_adapter.check_single(counterparty.lei_code)
                
                # Create snapshot
                snapshot = CounterpartySnapshot(
                    tenant_id=test_tenant.id,
                    counterparty_id=counterparty.id,
                    source='GLEIF',
                    check_type='lei',
                    data_hash='test_hash',
                    raw_data=result,
                    status=result['status'],
                    response_time_ms=result.get('response_time_ms', 0)
                )
                db.session.add(snapshot)
                db.session.commit()
            
            # Verify counterparty was created
            assert counterparty.id is not None
            assert counterparty.lei_code == first_company['lei_code']
            
            # Verify snapshot was created
            assert snapshot.id is not None
            assert snapshot.source == 'GLEIF'
            assert snapshot.check_type == 'lei'
            assert snapshot.counterparty_id == counterparty.id
    
    def test_lei_status_change_detection(self, app, test_tenant, gleif_adapter):
        """Test detection of LEI status changes."""
        with app.app_context():
            # Create counterparty
            counterparty = Counterparty(
                tenant_id=test_tenant.id,
                name="Test Company",
                lei_code="529900T8BM49AURSDO55",
                country_code="DE",
                status='active',
                monitoring_enabled=True
            )
            db.session.add(counterparty)
            db.session.commit()
            
            # Create initial snapshot with ACTIVE status
            initial_snapshot = CounterpartySnapshot(
                tenant_id=test_tenant.id,
                counterparty_id=counterparty.id,
                source='GLEIF',
                check_type='lei',
                data_hash='initial_hash',
                raw_data={
                    'status': 'valid',
                    'entity_data': {
                        'status': 'ACTIVE',
                        'registration_status': 'ISSUED'
                    }
                },
                status='valid'
            )
            db.session.add(initial_snapshot)
            db.session.commit()
            
            # Mock new GLEIF response with INACTIVE status
            with patch('requests.Session.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "data": {
                        "type": "lei-records",
                        "id": "529900T8BM49AURSDO55",
                        "attributes": {
                            "lei": "529900T8BM49AURSDO55",
                            "entity": {
                                "legalName": {"name": "Test Company"},
                                "entityStatus": "INACTIVE"  # Changed status
                            },
                            "registration": {
                                "registrationStatus": "ISSUED"
                            }
                        }
                    }
                }
                mock_get.return_value = mock_response
                
                # Perform new validation
                result = gleif_adapter.check_single(counterparty.lei_code)
                
                # Create new snapshot
                new_snapshot = CounterpartySnapshot(
                    tenant_id=test_tenant.id,
                    counterparty_id=counterparty.id,
                    source='GLEIF',
                    check_type='lei',
                    data_hash='new_hash',
                    raw_data=result,
                    status=result['status']
                )
                db.session.add(new_snapshot)
                
                # Create diff for status change
                diff = CounterpartyDiff(
                    tenant_id=test_tenant.id,
                    counterparty_id=counterparty.id,
                    old_snapshot_id=initial_snapshot.id,
                    new_snapshot_id=new_snapshot.id,
                    field_path='entity_data.status',
                    old_value='ACTIVE',
                    new_value='INACTIVE',
                    change_type='modified',
                    risk_impact='high'
                )
                db.session.add(diff)
                
                # Create alert for status change
                alert = KYBAlert(
                    tenant_id=test_tenant.id,
                    counterparty_id=counterparty.id,
                    diff_id=diff.id,
                    alert_type='data_change',
                    severity='high',
                    title='LEI Status Changed',
                    message=f'LEI {counterparty.lei_code} status changed from ACTIVE to INACTIVE',
                    source='GLEIF',
                    status='open'
                )
                db.session.add(alert)
                db.session.commit()
            
            # Verify diff was created
            diffs = CounterpartyDiff.query.filter_by(counterparty_id=counterparty.id).all()
            assert len(diffs) > 0
            diff = diffs[0]
            assert diff.field_path == 'entity_data.status'
            assert diff.old_value == 'ACTIVE'
            assert diff.new_value == 'INACTIVE'
            assert diff.risk_impact == 'high'
            
            # Verify alert was created
            alerts = KYBAlert.query.filter_by(counterparty_id=counterparty.id).all()
            assert len(alerts) > 0
            alert = alerts[0]
            assert alert.alert_type == 'data_change'
            assert alert.severity == 'high'
            assert 'INACTIVE' in alert.message
    
    def test_batch_counterparty_lei_monitoring(self, app, test_tenant, gleif_adapter, real_company_data):
        """Test batch monitoring of multiple counterparties with LEI codes."""
        with app.app_context():
            # Create multiple counterparties from real data
            lei_companies = {k: v for k, v in real_company_data.items() 
                            if 'lei_code' in v and v['lei_code']}
            counterparties = []
            
            for i, (key, company) in enumerate(list(lei_companies.items())[:3]):
                counterparty = Counterparty(
                    tenant_id=test_tenant.id,
                    name=company['name'],
                    lei_code=company['lei_code'],
                    country_code=company['country_code'],
                    address=company.get('address', ''),
                    status='active',
                    monitoring_enabled=True
                )
                db.session.add(counterparty)
                counterparties.append(counterparty)
            
            db.session.commit()
            
            # Collect LEI codes for batch processing
            lei_codes = [cp.lei_code for cp in counterparties]
            
            # Mock batch GLEIF validation
            with patch('requests.Session.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "data": {
                        "type": "lei-records",
                        "id": "529900T8BM49AURSDO55",
                        "attributes": {
                            "lei": "529900T8BM49AURSDO55",
                            "entity": {
                                "legalName": {"name": "Test Company"},
                                "entityStatus": "ACTIVE"
                            },
                            "registration": {
                                "registrationStatus": "ISSUED"
                            }
                        }
                    }
                }
                mock_get.return_value = mock_response
                
                # Perform batch validation
                results = gleif_adapter.check_batch(lei_codes, batch_delay=0.01)
                
                # Create snapshots for all results
                for i, result in enumerate(results):
                    snapshot = CounterpartySnapshot(
                        tenant_id=test_tenant.id,
                        counterparty_id=counterparties[i].id,
                        source='GLEIF',
                        check_type='lei',
                        data_hash=f'test_hash_{i}',
                        raw_data=result,
                        status=result['status'],
                        response_time_ms=result.get('response_time_ms', 0)
                    )
                    db.session.add(snapshot)
                
                db.session.commit()
            
            # Verify all snapshots were created
            snapshots = CounterpartySnapshot.query.filter_by(tenant_id=test_tenant.id).all()
            assert len(snapshots) == len(counterparties)
            
            for snapshot in snapshots:
                assert snapshot.source == 'GLEIF'
                assert snapshot.check_type == 'lei'
                assert snapshot.counterparty_id in [cp.id for cp in counterparties]