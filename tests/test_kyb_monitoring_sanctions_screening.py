"""
Comprehensive sanctions screening tests for KYB monitoring system.

This test suite validates sanctions screening integration using real company data.
Tests cover EU sanctions, OFAC SDN list, UK HMT sanctions, and comprehensive KYB workflows.
"""
import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from app import create_app, db
from app.models.kyb_monitoring import Counterparty, CounterpartySnapshot, CounterpartyDiff, KYBAlert, KYBMonitoringConfig
from app.services.kyb_adapters.sanctions_eu import EUSanctionsAdapter
from app.services.kyb_adapters.sanctions_ofac import OFACSanctionsAdapter
from app.services.kyb_adapters.sanctions_uk import UKSanctionsAdapter
from app.services.kyb_adapters.base import ValidationError, DataSourceUnavailable, RateLimitExceeded
from tests.conftest import TestConfig


class TestSanctionsScreeningKYB:
    """Base test class for sanctions screening integration."""
    
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
                    "country_code": "DE",
                    "address": "Dietmar-Hopp-Allee 16, 69190 Walldorf",
                    "industry": "Technology"
                },
                "microsoft_ireland": {
                    "name": "Microsoft Ireland Operations Limited",
                    "country_code": "IE",
                    "address": "One Microsoft Place, South County Business Park, Leopardstown, Dublin 18"
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
            
            # Create KYB monitoring config with all sanctions enabled
            config = KYBMonitoringConfig(
                tenant_id=tenant.id,
                sanctions_eu_enabled=True,
                sanctions_ofac_enabled=True,
                sanctions_uk_enabled=True,
                alert_on_sanctions_match=True,
                default_check_frequency='daily'
            )
            db.session.add(config)
            db.session.commit()
            
            yield tenant
            
            # Cleanup
            db.session.delete(config)
            db.session.delete(user)
            db.session.delete(tenant)
            db.session.commit()
    
    @pytest.fixture
    def known_sanctioned_entities(self):
        """Known sanctioned entities for testing (historical/public examples)."""
        return {
            # These are examples of historically sanctioned entities for testing purposes
            "test_entities": [
                {
                    "name": "Sberbank",
                    "type": "entity",
                    "expected_matches": ["EU", "OFAC", "UK"],
                    "aliases": ["Sberbank of Russia", "PJSC Sberbank"]
                },
                {
                    "name": "Gazprom",
                    "type": "entity", 
                    "expected_matches": ["EU", "UK"],
                    "aliases": ["Gazprom PJSC", "PAO Gazprom"]
                },
                {
                    "name": "Bank Rossiya",
                    "type": "entity",
                    "expected_matches": ["EU", "OFAC", "UK"],
                    "aliases": ["Bank Rossiya JSC"]
                }
            ],
            # Test entities that should NOT match (legitimate companies)
            "clean_entities": [
                "Microsoft Corporation",
                "Apple Inc",
                "Google LLC",
                "Amazon.com Inc",
                "SAP SE"
            ]
        }


class TestEUSanctionsScreening(TestSanctionsScreeningKYB):
    """Test EU sanctions screening functionality."""
    
    @pytest.fixture
    def eu_sanctions_adapter(self, mock_redis):
        """Create EU sanctions adapter with mocked Redis."""
        return EUSanctionsAdapter(redis_client=mock_redis)
    
    def test_eu_sanctions_entity_name_validation(self, eu_sanctions_adapter):
        """Test entity name validation for EU sanctions screening."""
        # Valid entity names
        valid_names = [
            "SAP SE",
            "Microsoft Ireland Operations Limited",
            "Deutsche Bank AG",
            "Société Générale",
            "Banco Santander S.A."
        ]
        
        for name in valid_names:
            clean_name = eu_sanctions_adapter._validate_entity_name(name)
            assert clean_name is not None
            assert len(clean_name.strip()) > 0
    
    def test_eu_sanctions_invalid_entity_names(self, eu_sanctions_adapter):
        """Test handling of invalid entity names."""
        invalid_names = [
            "",  # Empty
            "   ",  # Whitespace only
            "A",  # Too short
            "X" * 300  # Too long
        ]
        
        for invalid_name in invalid_names:
            with pytest.raises(ValidationError):
                eu_sanctions_adapter._validate_entity_name(invalid_name)
    
    @patch('requests.Session.get')
    def test_eu_sanctions_clean_entity_check(self, mock_get, eu_sanctions_adapter, real_company_data):
        """Test EU sanctions check for clean entities (should not match)."""
        # Mock EU sanctions API response with no matches
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [],
            "total": 0,
            "page": 1,
            "per_page": 50
        }
        mock_get.return_value = mock_response
        
        # Test with real company names (should be clean)
        for company in real_company_data.values():
            company_name = company['name']
            
            result = eu_sanctions_adapter.check_single(company_name)
            
            # Verify result structure
            assert 'status' in result
            assert 'match_found' in result
            assert 'identifier' in result
            assert 'source' in result
            assert result['source'] == 'EUSANCTIONS'
            assert 'checked_at' in result
            assert 'response_time_ms' in result
            
            # Should not find matches for legitimate companies
            assert result['match_found'] is False
            assert result['status'] == 'clean'
            assert result['matches'] == []
    
    @patch('requests.Session.get')
    def test_eu_sanctions_match_detection(self, mock_get, eu_sanctions_adapter, known_sanctioned_entities):
        """Test EU sanctions match detection for known sanctioned entities."""
        # Mock EU sanctions API response with matches
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "12345",
                    "name": "Test Sanctioned Entity",
                    "type": "Entity",
                    "programs": ["UKRAINE", "RUSSIA"],
                    "aliases": ["Test Entity Alias"],
                    "addresses": [
                        {
                            "country": "RU",
                            "city": "Moscow"
                        }
                    ],
                    "match_score": 0.95,
                    "last_updated": "2024-01-01T00:00:00Z"
                }
            ],
            "total": 1,
            "page": 1,
            "per_page": 50
        }
        mock_get.return_value = mock_response
        
        # Test with known sanctioned entity
        test_entity = known_sanctioned_entities['test_entities'][0]
        entity_name = test_entity['name']
        
        result = eu_sanctions_adapter.check_single(entity_name)
        
        # Should find matches for sanctioned entities
        assert result['match_found'] is True
        assert result['status'] == 'match'
        assert len(result['matches']) > 0
        
        # Verify match details
        match = result['matches'][0]
        assert 'name' in match
        assert 'match_score' in match
        assert 'programs' in match
        assert match['match_score'] >= 0.8  # High confidence match
    
    @patch('requests.Session.get')
    def test_eu_sanctions_api_error_handling(self, mock_get, eu_sanctions_adapter):
        """Test EU sanctions API error handling."""
        # Test different error scenarios
        error_scenarios = [
            {
                'exception': requests.exceptions.Timeout("Request timeout"),
                'expected_status': 'timeout'
            },
            {
                'exception': requests.exceptions.ConnectionError("Connection failed"),
                'expected_status': 'unavailable'
            },
            {
                'exception': Exception("General error"),
                'expected_status': 'error'
            }
        ]
        
        for scenario in error_scenarios:
            mock_get.side_effect = scenario['exception']
            
            result = eu_sanctions_adapter.check_single("Test Company")
            
            assert result['status'] == scenario['expected_status']
            assert result['match_found'] is False
            assert 'error' in result
    
    def test_eu_sanctions_batch_processing(self, eu_sanctions_adapter, real_company_data):
        """Test EU sanctions batch processing."""
        company_names = [company['name'] for company in real_company_data.values()][:3]
        
        # Mock clean responses for all companies
        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "results": [],
                "total": 0,
                "page": 1,
                "per_page": 50
            }
            mock_get.return_value = mock_response
            
            results = eu_sanctions_adapter.check_batch(company_names, batch_delay=0.01)
        
        # Verify batch results
        assert len(results) == len(company_names)
        for i, result in enumerate(results):
            assert result['identifier'] == company_names[i]
            assert result['source'] == 'EUSANCTIONS'
            assert result['match_found'] is False


class TestOFACSanctionsScreening(TestSanctionsScreeningKYB):
    """Test OFAC sanctions screening functionality."""
    
    @pytest.fixture
    def ofac_sanctions_adapter(self, mock_redis):
        """Create OFAC sanctions adapter with mocked Redis."""
        return OFACSanctionsAdapter(redis_client=mock_redis)
    
    @patch('requests.Session.get')
    def test_ofac_sanctions_clean_entity_check(self, mock_get, ofac_sanctions_adapter, real_company_data):
        """Test OFAC sanctions check for clean entities."""
        # Mock OFAC API response with no matches
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
        <sdnList>
            <publshInformation>
                <Publish_Date>01/01/2024</Publish_Date>
                <Record_Count>0</Record_Count>
            </publshInformation>
        </sdnList>'''
        mock_get.return_value = mock_response
        
        # Test with real company names
        for company in real_company_data.values():
            company_name = company['name']
            
            result = ofac_sanctions_adapter.check_single(company_name)
            
            # Verify result structure
            assert 'status' in result
            assert 'match_found' in result
            assert 'source' in result
            assert result['source'] == 'OFACSANCTIONS'
            
            # Should not find matches for legitimate companies
            assert result['match_found'] is False
            assert result['status'] == 'clean'
    
    @patch('requests.Session.get')
    def test_ofac_sanctions_match_detection(self, mock_get, ofac_sanctions_adapter, known_sanctioned_entities):
        """Test OFAC sanctions match detection."""
        # Mock OFAC XML response with matches
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
        <sdnList>
            <publshInformation>
                <Publish_Date>01/01/2024</Publish_Date>
                <Record_Count>1</Record_Count>
            </publshInformation>
            <sdnEntry>
                <uid>12345</uid>
                <firstName>Test</firstName>
                <lastName>Sanctioned Entity</lastName>
                <sdnType>Entity</sdnType>
                <programList>
                    <program>UKRAINE-EO13662</program>
                </programList>
                <akaList>
                    <aka>
                        <uid>12346</uid>
                        <type>a.k.a.</type>
                        <category>strong</category>
                        <lastName>Test Entity Alias</lastName>
                    </aka>
                </akaList>
                <addressList>
                    <address>
                        <uid>12347</uid>
                        <country>Russia</country>
                        <city>Moscow</city>
                    </address>
                </addressList>
            </sdnEntry>
        </sdnList>'''
        mock_get.return_value = mock_response
        
        # Test with known sanctioned entity
        test_entity = known_sanctioned_entities['test_entities'][0]
        entity_name = test_entity['name']
        
        result = ofac_sanctions_adapter.check_single(entity_name)
        
        # Should find matches for sanctioned entities
        assert result['match_found'] is True
        assert result['status'] == 'match'
        assert len(result['matches']) > 0
        
        # Verify match details
        match = result['matches'][0]
        assert 'name' in match
        assert 'programs' in match
        assert 'match_score' in match
    
    def test_ofac_sanctions_program_filtering(self, ofac_sanctions_adapter):
        """Test OFAC sanctions filtering by specific programs."""
        # Mock OFAC response with multiple programs
        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
            <sdnList>
                <publshInformation>
                    <Publish_Date>01/01/2024</Publish_Date>
                    <Record_Count>2</Record_Count>
                </publshInformation>
                <sdnEntry>
                    <uid>12345</uid>
                    <lastName>Ukraine Sanctioned Entity</lastName>
                    <sdnType>Entity</sdnType>
                    <programList>
                        <program>UKRAINE-EO13662</program>
                    </programList>
                </sdnEntry>
                <sdnEntry>
                    <uid>12346</uid>
                    <lastName>Iran Sanctioned Entity</lastName>
                    <sdnType>Entity</sdnType>
                    <programList>
                        <program>IRAN</program>
                    </programList>
                </sdnEntry>
            </sdnList>'''
            mock_get.return_value = mock_response
            
            # Test filtering by specific program
            result = ofac_sanctions_adapter.check_single(
                "Test Entity", 
                programs=["UKRAINE-EO13662"]
            )
            
            # Should only return matches for specified program
            if result['match_found']:
                for match in result['matches']:
                    assert any('UKRAINE' in program for program in match.get('programs', []))


class TestUKSanctionsScreening(TestSanctionsScreeningKYB):
    """Test UK HMT sanctions screening functionality."""
    
    @pytest.fixture
    def uk_sanctions_adapter(self, mock_redis):
        """Create UK sanctions adapter with mocked Redis."""
        return UKSanctionsAdapter(redis_client=mock_redis)
    
    @patch('requests.Session.get')
    def test_uk_sanctions_clean_entity_check(self, mock_get, uk_sanctions_adapter, real_company_data):
        """Test UK sanctions check for clean entities."""
        # Mock UK sanctions API response with no matches
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "FinancialSanctionsList": {
                "LastUpdated": "2024-01-01T00:00:00Z",
                "Individuals": [],
                "Entities": []
            }
        }
        mock_get.return_value = mock_response
        
        # Test with real company names
        for company in real_company_data.values():
            company_name = company['name']
            
            result = uk_sanctions_adapter.check_single(company_name)
            
            # Verify result structure
            assert 'status' in result
            assert 'match_found' in result
            assert 'source' in result
            assert result['source'] == 'UKSANCTIONS'
            
            # Should not find matches for legitimate companies
            assert result['match_found'] is False
            assert result['status'] == 'clean'
    
    @patch('requests.Session.get')
    def test_uk_sanctions_match_detection(self, mock_get, uk_sanctions_adapter, known_sanctioned_entities):
        """Test UK sanctions match detection."""
        # Mock UK sanctions JSON response with matches
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "FinancialSanctionsList": {
                "LastUpdated": "2024-01-01T00:00:00Z",
                "Individuals": [],
                "Entities": [
                    {
                        "Names": [
                            {
                                "Name6": "Test Sanctioned Entity",
                                "NameType": "Primary Name"
                            },
                            {
                                "Name6": "Test Entity Alias",
                                "NameType": "Alias"
                            }
                        ],
                        "Addresses": [
                            {
                                "Country": "Russia",
                                "City": "Moscow"
                            }
                        ],
                        "SanctionsRegimes": [
                            {
                                "RegimeName": "Russia"
                            }
                        ],
                        "UniqueID": "UK12345"
                    }
                ]
            }
        }
        mock_get.return_value = mock_response
        
        # Test with known sanctioned entity
        test_entity = known_sanctioned_entities['test_entities'][0]
        entity_name = test_entity['name']
        
        result = uk_sanctions_adapter.check_single(entity_name)
        
        # Should find matches for sanctioned entities
        assert result['match_found'] is True
        assert result['status'] == 'match'
        assert len(result['matches']) > 0
        
        # Verify match details
        match = result['matches'][0]
        assert 'name' in match
        assert 'regimes' in match
        assert 'match_score' in match
    
    def test_uk_sanctions_regime_filtering(self, uk_sanctions_adapter):
        """Test UK sanctions filtering by specific regimes."""
        # Mock UK response with multiple regimes
        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "FinancialSanctionsList": {
                    "LastUpdated": "2024-01-01T00:00:00Z",
                    "Individuals": [],
                    "Entities": [
                        {
                            "Names": [{"Name6": "Russia Entity", "NameType": "Primary Name"}],
                            "SanctionsRegimes": [{"RegimeName": "Russia"}],
                            "UniqueID": "UK12345"
                        },
                        {
                            "Names": [{"Name6": "Iran Entity", "NameType": "Primary Name"}],
                            "SanctionsRegimes": [{"RegimeName": "Iran"}],
                            "UniqueID": "UK12346"
                        }
                    ]
                }
            }
            mock_get.return_value = mock_response
            
            # Test filtering by specific regime
            result = uk_sanctions_adapter.check_single(
                "Test Entity", 
                regimes=["Russia"]
            )
            
            # Should only return matches for specified regime
            if result['match_found']:
                for match in result['matches']:
                    assert any('Russia' in regime for regime in match.get('regimes', []))


class TestComprehensiveSanctionsScreening(TestSanctionsScreeningKYB):
    """Test comprehensive sanctions screening across all sources."""
    
    @pytest.fixture
    def all_sanctions_adapters(self, mock_redis):
        """Create all sanctions adapters."""
        return {
            'eu': EUSanctionsAdapter(redis_client=mock_redis),
            'ofac': OFACSanctionsAdapter(redis_client=mock_redis),
            'uk': UKSanctionsAdapter(redis_client=mock_redis)
        }
    
    def test_multi_source_clean_entity_screening(self, all_sanctions_adapters, real_company_data):
        """Test screening clean entities across all sanctions sources."""
        # Mock clean responses for all adapters
        with patch('requests.Session.get') as mock_get:
            # Mock different response formats for each adapter
            def mock_get_side_effect(url, **kwargs):
                mock_response = Mock()
                mock_response.status_code = 200
                
                if 'ec.europa.eu' in url:
                    # EU sanctions format
                    mock_response.json.return_value = {
                        "results": [],
                        "total": 0
                    }
                elif 'treasury.gov' in url:
                    # OFAC format
                    mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
                    <sdnList>
                        <publshInformation>
                            <Record_Count>0</Record_Count>
                        </publshInformation>
                    </sdnList>'''
                elif 'blob.core.windows.net' in url or 'assets.publishing.service.gov.uk' in url:
                    # UK sanctions format
                    mock_response.json.return_value = {
                        "FinancialSanctionsList": {
                            "Individuals": [],
                            "Entities": []
                        }
                    }
                
                return mock_response
            
            mock_get.side_effect = mock_get_side_effect
            
            # Test first company across all sources
            first_company = next(iter(real_company_data.values()))
            company_name = first_company['name']
            
            results = {}
            for source_name, adapter in all_sanctions_adapters.items():
                results[source_name] = adapter.check_single(company_name)
            
            # All sources should return clean results
            for source_name, result in results.items():
                assert result['match_found'] is False, f"{source_name} should not match clean entity"
                assert result['status'] == 'clean'
                assert result['source'] in ['EUSANCTIONS', 'OFACSANCTIONS', 'UKSANCTIONS']
    
    def test_multi_source_sanctioned_entity_screening(self, all_sanctions_adapters, known_sanctioned_entities):
        """Test screening known sanctioned entities across all sources."""
        # Mock match responses for all adapters
        with patch('requests.Session.get') as mock_get:
            def mock_get_side_effect(url, **kwargs):
                mock_response = Mock()
                mock_response.status_code = 200
                
                if 'ec.europa.eu' in url:
                    # EU sanctions match
                    mock_response.json.return_value = {
                        "results": [
                            {
                                "id": "EU12345",
                                "name": "Test Sanctioned Entity",
                                "type": "Entity",
                                "programs": ["RUSSIA"],
                                "match_score": 0.95
                            }
                        ],
                        "total": 1
                    }
                elif 'treasury.gov' in url:
                    # OFAC match
                    mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
                    <sdnList>
                        <publshInformation>
                            <Record_Count>1</Record_Count>
                        </publshInformation>
                        <sdnEntry>
                            <uid>OFAC12345</uid>
                            <lastName>Test Sanctioned Entity</lastName>
                            <sdnType>Entity</sdnType>
                            <programList>
                                <program>UKRAINE-EO13662</program>
                            </programList>
                        </sdnEntry>
                    </sdnList>'''
                elif 'blob.core.windows.net' in url or 'assets.publishing.service.gov.uk' in url:
                    # UK sanctions match
                    mock_response.json.return_value = {
                        "FinancialSanctionsList": {
                            "Individuals": [],
                            "Entities": [
                                {
                                    "Names": [{"Name6": "Test Sanctioned Entity", "NameType": "Primary Name"}],
                                    "SanctionsRegimes": [{"RegimeName": "Russia"}],
                                    "UniqueID": "UK12345"
                                }
                            ]
                        }
                    }
                
                return mock_response
            
            mock_get.side_effect = mock_get_side_effect
            
            # Test known sanctioned entity across all sources
            test_entity = known_sanctioned_entities['test_entities'][0]
            entity_name = test_entity['name']
            
            results = {}
            for source_name, adapter in all_sanctions_adapters.items():
                results[source_name] = adapter.check_single(entity_name)
            
            # At least some sources should find matches
            match_found_count = sum(1 for result in results.values() if result['match_found'])
            assert match_found_count > 0, "At least one source should find matches for sanctioned entity"
            
            # Verify match details for sources that found matches
            for source_name, result in results.items():
                if result['match_found']:
                    assert result['status'] == 'match'
                    assert len(result['matches']) > 0
                    assert all('match_score' in match for match in result['matches'])


class TestSanctionsKYBIntegration(TestSanctionsScreeningKYB):
    """Test sanctions screening integration with KYB monitoring workflow."""
    
    def test_counterparty_sanctions_screening_workflow(self, app, test_tenant, real_company_data):
        """Test complete workflow from counterparty creation to sanctions screening."""
        with app.app_context():
            # Create counterparty with real company data
            first_company = next(iter(real_company_data.values()))
            
            counterparty = Counterparty(
                tenant_id=test_tenant.id,
                name=first_company['name'],
                country_code=first_company['country_code'],
                address=first_company.get('address', ''),
                status='active',
                monitoring_enabled=True
            )
            db.session.add(counterparty)
            db.session.commit()
            
            # Mock clean sanctions screening results
            with patch('requests.Session.get') as mock_get:
                def mock_get_side_effect(url, **kwargs):
                    mock_response = Mock()
                    mock_response.status_code = 200
                    
                    if 'ec.europa.eu' in url:
                        mock_response.json.return_value = {"results": [], "total": 0}
                    elif 'treasury.gov' in url:
                        mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
                        <sdnList><publshInformation><Record_Count>0</Record_Count></publshInformation></sdnList>'''
                    else:
                        mock_response.json.return_value = {
                            "FinancialSanctionsList": {"Individuals": [], "Entities": []}
                        }
                    
                    return mock_response
                
                mock_get.side_effect = mock_get_side_effect
                
                # Perform sanctions screening for each source
                adapters = {
                    'EU': EUSanctionsAdapter(),
                    'OFAC': OFACSanctionsAdapter(),
                    'UK': UKSanctionsAdapter()
                }
                
                for source_name, adapter in adapters.items():
                    result = adapter.check_single(counterparty.name)
                    
                    # Create snapshot
                    snapshot = CounterpartySnapshot(
                        tenant_id=test_tenant.id,
                        counterparty_id=counterparty.id,
                        source=f'{source_name}_SANCTIONS',
                        check_type='sanctions',
                        data_hash=f'test_hash_{source_name}',
                        raw_data=result,
                        status=result['status'],
                        response_time_ms=result.get('response_time_ms', 0)
                    )
                    db.session.add(snapshot)
                
                db.session.commit()
            
            # Verify snapshots were created
            snapshots = CounterpartySnapshot.query.filter_by(counterparty_id=counterparty.id).all()
            assert len(snapshots) == 3  # One for each sanctions source
            
            for snapshot in snapshots:
                assert snapshot.check_type == 'sanctions'
                assert snapshot.source.endswith('_SANCTIONS')
                assert snapshot.status == 'clean'  # Should be clean for legitimate company
    
    def test_sanctions_match_alert_generation(self, app, test_tenant):
        """Test alert generation for sanctions matches."""
        with app.app_context():
            # Create counterparty with potentially sanctioned name
            counterparty = Counterparty(
                tenant_id=test_tenant.id,
                name="Test Sanctioned Entity",
                country_code="RU",
                status='active',
                monitoring_enabled=True
            )
            db.session.add(counterparty)
            db.session.commit()
            
            # Mock sanctions match response
            with patch('requests.Session.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "results": [
                        {
                            "id": "12345",
                            "name": "Test Sanctioned Entity",
                            "type": "Entity",
                            "programs": ["RUSSIA"],
                            "match_score": 0.95
                        }
                    ],
                    "total": 1
                }
                mock_get.return_value = mock_response
                
                # Perform sanctions screening
                adapter = EUSanctionsAdapter()
                result = adapter.check_single(counterparty.name)
                
                # Create snapshot
                snapshot = CounterpartySnapshot(
                    tenant_id=test_tenant.id,
                    counterparty_id=counterparty.id,
                    source='EU_SANCTIONS',
                    check_type='sanctions',
                    data_hash='test_hash',
                    raw_data=result,
                    status=result['status']
                )
                db.session.add(snapshot)
                
                # Create alert for sanctions match
                if result.get('match_found', False):
                    alert = KYBAlert(
                        tenant_id=test_tenant.id,
                        counterparty_id=counterparty.id,
                        alert_type='sanctions_match',
                        severity='critical',
                        title='Sanctions Match Detected',
                        message=f'Counterparty {counterparty.name} matches EU sanctions list',
                        source='EU_SANCTIONS',
                        status='open',
                        alert_data={
                            'matches': result.get('matches', []),
                            'match_count': len(result.get('matches', [])),
                            'highest_score': max([m.get('match_score', 0) for m in result.get('matches', [])], default=0)
                        }
                    )
                    db.session.add(alert)
                
                db.session.commit()
            
            # Verify alert was created
            alerts = KYBAlert.query.filter_by(counterparty_id=counterparty.id).all()
            assert len(alerts) > 0
            alert = alerts[0]
            assert alert.alert_type == 'sanctions_match'
            assert alert.severity == 'critical'
            assert 'sanctions' in alert.message.lower()
            assert 'matches' in alert.alert_data
    
    def test_batch_sanctions_screening_monitoring(self, app, test_tenant, real_company_data):
        """Test batch sanctions screening for multiple counterparties."""
        with app.app_context():
            # Create multiple counterparties from real data
            counterparties = []
            for i, (key, company) in enumerate(list(real_company_data.items())[:3]):
                counterparty = Counterparty(
                    tenant_id=test_tenant.id,
                    name=company['name'],
                    country_code=company['country_code'],
                    address=company.get('address', ''),
                    status='active',
                    monitoring_enabled=True
                )
                db.session.add(counterparty)
                counterparties.append(counterparty)
            
            db.session.commit()
            
            # Collect company names for batch processing
            company_names = [cp.name for cp in counterparties]
            
            # Mock batch sanctions screening
            with patch('requests.Session.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "results": [],
                    "total": 0
                }
                mock_get.return_value = mock_response
                
                # Perform batch screening
                adapter = EUSanctionsAdapter()
                results = adapter.check_batch(company_names, batch_delay=0.01)
                
                # Create snapshots for all results
                for i, result in enumerate(results):
                    snapshot = CounterpartySnapshot(
                        tenant_id=test_tenant.id,
                        counterparty_id=counterparties[i].id,
                        source='EU_SANCTIONS',
                        check_type='sanctions',
                        data_hash=f'test_hash_{i}',
                        raw_data=result,
                        status=result['status']
                    )
                    db.session.add(snapshot)
                
                db.session.commit()
            
            # Verify all snapshots were created
            snapshots = CounterpartySnapshot.query.filter_by(tenant_id=test_tenant.id).all()
            assert len(snapshots) == len(counterparties)
            
            for snapshot in snapshots:
                assert snapshot.source == 'EU_SANCTIONS'
                assert snapshot.check_type == 'sanctions'
                assert snapshot.status == 'clean'  # Should be clean for legitimate companies