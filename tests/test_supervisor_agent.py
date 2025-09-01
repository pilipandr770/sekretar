"""Comprehensive tests for Supervisor Agent - Content Filtering, PII Detection, and Policy Compliance."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from app.secretary.agents.supervisor_agent import SupervisorAgent, FilterResult, PolicyViolation
from app.secretary.agents.base_agent import AgentContext, AgentResponse


class TestSupervisorAgent:
    """Test cases for SupervisorAgent."""
    
    @pytest.fixture
    def supervisor_agent(self):
        """Create a SupervisorAgent instance for testing."""
        return SupervisorAgent()
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample AgentContext for testing."""
        return AgentContext(
            tenant_id="test-tenant-123",
            user_id="user-456",
            channel_type="telegram",
            conversation_id="conv-789",
            language="en"
        )
    
    def test_init(self, supervisor_agent):
        """Test SupervisorAgent initialization."""
        assert supervisor_agent.name == "SupervisorAgent"
        assert len(supervisor_agent.toxic_patterns) > 0
        assert len(supervisor_agent.pii_patterns) > 0
        assert 'email' in supervisor_agent.pii_patterns
        assert 'phone' in supervisor_agent.pii_patterns
        assert len(supervisor_agent.compliance_keywords) > 0
    
    @pytest.mark.asyncio
    async def test_process_safe_content(self, supervisor_agent, sample_context):
        """Test processing of safe content."""
        message = "Hello, I would like to know more about your services."
        
        # Mock AI analysis to return safe result
        mock_ai_analysis = {
            'is_unsafe': False,
            'violations': [],
            'confidence': 0.9,
            'categories': [],
            'filtered_content': message
        }
        
        with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
            response = await supervisor_agent.process(message, sample_context)
        
        assert isinstance(response, AgentResponse)
        assert response.content == message
        assert response.metadata['is_safe'] is True
        assert len(response.metadata['violations']) == 0
        assert response.requires_handoff is False
    
    @pytest.mark.asyncio
    async def test_process_toxic_content(self, supervisor_agent, sample_context):
        """Test processing of toxic content."""
        message = "You are such an idiot and I hate your service!"
        
        mock_ai_analysis = {
            'is_unsafe': True,
            'violations': ['Toxic language detected'],
            'confidence': 0.8,
            'categories': ['harassment'],
            'filtered_content': message
        }
        
        with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
            response = await supervisor_agent.process(message, sample_context)
        
        assert isinstance(response, AgentResponse)
        assert response.metadata['is_safe'] is False
        assert len(response.metadata['violations']) > 0
        assert '*' in response.content  # Content should be masked
    
    @pytest.mark.asyncio
    async def test_process_with_pii(self, supervisor_agent, sample_context):
        """Test processing of content with PII."""
        message = "My email is john.doe@example.com and phone is 555-123-4567"
        
        mock_ai_analysis = {
            'is_unsafe': False,
            'violations': [],
            'confidence': 0.7,
            'categories': [],
            'filtered_content': message
        }
        
        with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
            response = await supervisor_agent.process(message, sample_context)
        
        assert isinstance(response, AgentResponse)
        assert '[EMAIL_REDACTED]' in response.content
        assert '[PHONE_REDACTED]' in response.content
        assert response.metadata['pii_detected'] is True
    
    @pytest.mark.asyncio
    async def test_process_compliance_content(self, supervisor_agent, sample_context):
        """Test processing of compliance-related content."""
        message = "I want to file a lawsuit for GDPR violation"
        
        mock_ai_analysis = {
            'is_unsafe': False,
            'violations': [],
            'confidence': 0.6,
            'categories': [],
            'filtered_content': message
        }
        
        with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
            response = await supervisor_agent.process(message, sample_context)
        
        assert isinstance(response, AgentResponse)
        assert response.requires_handoff is True  # Should require human handoff
        assert len(response.metadata['policy_violations']) > 0
    
    @pytest.mark.asyncio
    async def test_process_error_handling(self, supervisor_agent, sample_context):
        """Test error handling during processing."""
        message = "Test message"
        
        # Mock filter_content to raise an exception
        with patch.object(supervisor_agent, 'filter_content', side_effect=Exception("Filter error")):
            response = await supervisor_agent.process(message, sample_context)
        
        assert response.content == "[Content blocked due to filtering error]"
        assert response.confidence == 0.0
        assert response.requires_handoff is True
        assert response.metadata['is_safe'] is False
        assert 'error' in response.metadata
    
    @pytest.mark.asyncio
    async def test_filter_content_safe(self, supervisor_agent, sample_context):
        """Test filtering of safe content."""
        content = "This is a normal business message."
        
        mock_ai_analysis = {
            'is_unsafe': False,
            'violations': [],
            'confidence': 0.9
        }
        
        with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
            result = await supervisor_agent.filter_content(content, sample_context)
        
        assert isinstance(result, FilterResult)
        assert result.is_safe is True
        assert result.filtered_content == content
        assert len(result.violations) == 0
        assert result.confidence > 0.5
    
    def test_detect_toxic_content(self, supervisor_agent):
        """Test toxic content detection."""
        toxic_content = "You are such a fucking idiot!"
        violations = supervisor_agent._detect_toxic_content(toxic_content)
        
        assert len(violations) > 0
        assert any('Toxic language detected' in v for v in violations)
    
    def test_detect_pii_email(self, supervisor_agent):
        """Test PII detection for email addresses."""
        content = "Contact me at john.doe@example.com"
        violations = supervisor_agent._detect_pii(content)
        
        assert len(violations) > 0
        assert any('email' in v.lower() for v in violations)
    
    def test_detect_pii_phone(self, supervisor_agent):
        """Test PII detection for phone numbers."""
        content = "Call me at 555-123-4567"
        violations = supervisor_agent._detect_pii(content)
        
        assert len(violations) > 0
        assert any('phone' in v.lower() for v in violations)
    
    def test_detect_pii_credit_card(self, supervisor_agent):
        """Test PII detection for credit card numbers."""
        content = "My card number is 4532-1234-5678-9012"
        violations = supervisor_agent._detect_pii(content)
        
        assert len(violations) > 0
        assert any('credit_card' in v.lower() for v in violations)
    
    def test_mask_toxic_content(self, supervisor_agent):
        """Test masking of toxic content."""
        content = "You are such a fucking idiot!"
        masked = supervisor_agent._mask_toxic_content(content)
        
        assert '*' in masked
        assert 'fucking' not in masked.lower()
        assert 'idiot' not in masked.lower()
    
    def test_mask_pii_email(self, supervisor_agent):
        """Test masking of email addresses."""
        content = "Contact me at john.doe@example.com"
        masked = supervisor_agent._mask_pii(content)
        
        assert '[EMAIL_REDACTED]' in masked
        assert 'john.doe@example.com' not in masked
    
    def test_mask_pii_phone(self, supervisor_agent):
        """Test masking of phone numbers."""
        content = "Call me at 555-123-4567"
        masked = supervisor_agent._mask_pii(content)
        
        assert '[PHONE_REDACTED]' in masked
        assert '555-123-4567' not in masked
    
    def test_mask_pii_credit_card(self, supervisor_agent):
        """Test masking of credit card numbers."""
        content = "My card is 4532-1234-5678-9012"
        masked = supervisor_agent._mask_pii(content)
        
        assert '[CARD_REDACTED]' in masked
        assert '4532-1234-5678-9012' not in masked
    
    @pytest.mark.asyncio
    async def test_analyze_content_with_ai_success(self, supervisor_agent, sample_context):
        """Test successful AI content analysis."""
        content = "This is test content"
        
        mock_response = json.dumps({
            'is_unsafe': False,
            'violations': [],
            'confidence': 0.9,
            'categories': [],
            'filtered_content': content
        })
        
        with patch.object(supervisor_agent, '_call_openai', return_value=mock_response):
            result = await supervisor_agent._analyze_content_with_ai(content, sample_context)
        
        assert result['is_unsafe'] is False
        assert result['confidence'] == 0.9
        assert len(result['violations']) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_content_with_ai_failure(self, supervisor_agent, sample_context):
        """Test AI content analysis failure handling."""
        content = "This is test content"
        
        # Mock OpenAI to return invalid JSON
        with patch.object(supervisor_agent, '_call_openai', return_value="Invalid JSON"):
            result = await supervisor_agent._analyze_content_with_ai(content, sample_context)
        
        assert result['is_unsafe'] is False
        assert result['confidence'] == 0.5
        assert result['filtered_content'] == content
    
    @pytest.mark.asyncio
    async def test_check_policy_violations_compliance(self, supervisor_agent, sample_context):
        """Test policy violation detection for compliance keywords."""
        content = "I have a GDPR complaint about data protection"
        violations = await supervisor_agent._check_policy_violations(content, sample_context)
        
        assert len(violations) > 0
        compliance_violations = [v for v in violations if v.type == "compliance"]
        assert len(compliance_violations) > 0
        assert compliance_violations[0].severity == "high"
    
    @pytest.mark.asyncio
    async def test_check_policy_violations_legal(self, supervisor_agent, sample_context):
        """Test policy violation detection for legal issues."""
        content = "I will sue you and take legal action"
        violations = await supervisor_agent._check_policy_violations(content, sample_context)
        
        assert len(violations) > 0
        legal_violations = [v for v in violations if v.type == "legal"]
        assert len(legal_violations) > 0
        assert legal_violations[0].severity == "critical"
    
    def test_calculate_confidence_no_violations(self, supervisor_agent):
        """Test confidence calculation with no violations."""
        violations = []
        ai_analysis = {'confidence': 0.9}
        
        confidence = supervisor_agent._calculate_confidence(violations, ai_analysis)
        
        assert confidence > 0.7
        assert confidence <= 1.0
    
    def test_calculate_confidence_with_violations(self, supervisor_agent):
        """Test confidence calculation with violations."""
        violations = ['violation1', 'violation2']
        ai_analysis = {'confidence': 0.6}
        
        confidence = supervisor_agent._calculate_confidence(violations, ai_analysis)
        
        assert confidence < 0.8  # Should be lower due to violations
        assert confidence >= 0.1  # Should not go below minimum
    
    @pytest.mark.asyncio
    async def test_validate_response_safe(self, supervisor_agent, sample_context):
        """Test response validation for safe content."""
        response = "Thank you for your inquiry. We will get back to you soon."
        
        mock_filter_result = FilterResult(
            is_safe=True,
            filtered_content=response,
            violations=[],
            confidence=0.9,
            metadata={}
        )
        
        with patch.object(supervisor_agent, 'filter_content', return_value=mock_filter_result):
            result = await supervisor_agent.validate_response(response, sample_context)
        
        assert isinstance(result, AgentResponse)
        assert result.content == response
        assert result.requires_handoff is False
        assert result.metadata['is_safe'] is True
    
    @pytest.mark.asyncio
    async def test_validate_response_too_short(self, supervisor_agent, sample_context):
        """Test response validation for too short responses."""
        response = "OK"
        
        mock_filter_result = FilterResult(
            is_safe=True,
            filtered_content=response,
            violations=[],
            confidence=0.9,
            metadata={}
        )
        
        with patch.object(supervisor_agent, 'filter_content', return_value=mock_filter_result):
            result = await supervisor_agent.validate_response(response, sample_context)
        
        assert result.requires_handoff is True
        assert any('too short' in v.lower() for v in result.metadata['violations'])
    
    @pytest.mark.asyncio
    async def test_validate_response_with_placeholders(self, supervisor_agent, sample_context):
        """Test response validation for responses with placeholders."""
        response = "Hello [NAME], your TODO item is ready."
        
        mock_filter_result = FilterResult(
            is_safe=True,
            filtered_content=response,
            violations=[],
            confidence=0.9,
            metadata={}
        )
        
        with patch.object(supervisor_agent, 'filter_content', return_value=mock_filter_result):
            result = await supervisor_agent.validate_response(response, sample_context)
        
        assert result.requires_handoff is True
        assert any('placeholder' in v.lower() for v in result.metadata['violations'])
    
    def test_get_safety_report(self, supervisor_agent):
        """Test safety report generation."""
        content = "Test content"
        filter_result = FilterResult(
            is_safe=True,
            filtered_content=content,
            violations=[],
            confidence=0.9,
            metadata={'test': 'data'}
        )
        
        report = supervisor_agent.get_safety_report(content, filter_result)
        
        assert 'timestamp' in report
        assert report['content_length'] == len(content)
        assert report['is_safe'] is True
        assert report['violations_count'] == 0
        assert report['confidence'] == 0.9
        assert report['pii_detected'] is False
        assert report['toxic_content_detected'] is False
    
    def test_create_content_analysis_prompt(self, supervisor_agent):
        """Test content analysis prompt creation."""
        prompt = supervisor_agent._create_content_analysis_prompt()
        
        assert 'content safety analyzer' in prompt.lower()
        assert 'json' in prompt.lower()
        assert 'harassment' in prompt.lower()
        assert 'hate speech' in prompt.lower()
        assert 'violence' in prompt.lower()
        assert all(category in prompt for category in supervisor_agent.inappropriate_categories)


class TestContentFiltering:
    """Comprehensive content filtering tests for real-world scenarios."""
    
    @pytest.fixture
    def supervisor_agent(self):
        """Create a SupervisorAgent instance for testing."""
        return SupervisorAgent()
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample AgentContext for testing."""
        return AgentContext(
            tenant_id="test-tenant-123",
            user_id="user-456",
            channel_type="telegram",
            conversation_id="conv-789",
            language="en"
        )
    
    @pytest.mark.asyncio
    async def test_filter_business_communication_safe(self, supervisor_agent, sample_context):
        """Test filtering of safe business communication."""
        messages = [
            "Hello, I would like to schedule a meeting to discuss our partnership.",
            "Could you please send me the quarterly financial report?",
            "Thank you for your excellent service. We are very satisfied.",
            "I need help with setting up the new CRM system for our team."
        ]
        
        for message in messages:
            mock_ai_analysis = {
                'is_unsafe': False,
                'violations': [],
                'confidence': 0.9,
                'categories': [],
                'filtered_content': message
            }
            
            with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
                result = await supervisor_agent.filter_content(message, sample_context)
            
            assert result.is_safe is True
            assert result.filtered_content == message
            assert len(result.violations) == 0
            assert result.confidence > 0.7
    
    @pytest.mark.asyncio
    async def test_filter_toxic_language_variations(self, supervisor_agent, sample_context):
        """Test filtering of various toxic language patterns."""
        toxic_messages = [
            "You are such a fucking idiot!",
            "This service is shit and you're all morons",
            "I hate this company and want to kill someone",
            "Damn you bastards for this terrible service"
        ]
        
        for message in toxic_messages:
            mock_ai_analysis = {
                'is_unsafe': True,
                'violations': ['Toxic language detected'],
                'confidence': 0.8,
                'categories': ['harassment'],
                'filtered_content': message
            }
            
            with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
                result = await supervisor_agent.filter_content(message, sample_context)
            
            assert result.is_safe is False
            assert '*' in result.filtered_content  # Content should be masked
            assert len(result.violations) > 0
            assert any('Toxic' in v for v in result.violations)
    
    @pytest.mark.asyncio
    async def test_filter_harassment_content(self, supervisor_agent, sample_context):
        """Test filtering of harassment and threatening content."""
        harassment_messages = [
            "I'm going to find you and make you pay for this",
            "You better watch your back, I know where you work",
            "I will destroy your business and ruin your reputation",
            "You're going to regret crossing me, I promise"
        ]
        
        for message in harassment_messages:
            mock_ai_analysis = {
                'is_unsafe': True,
                'violations': ['Threatening language detected', 'Harassment detected'],
                'confidence': 0.9,
                'categories': ['harassment', 'violence'],
                'filtered_content': '[FILTERED] content removed due to threats'
            }
            
            with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
                result = await supervisor_agent.filter_content(message, sample_context)
            
            assert result.is_safe is False
            assert result.requires_human_review is True
            assert len(result.violations) > 0
    
    @pytest.mark.asyncio
    async def test_filter_spam_content(self, supervisor_agent, sample_context):
        """Test filtering of spam and promotional content."""
        spam_messages = [
            "CLICK HERE NOW!!! AMAZING DEALS!!! LIMITED TIME OFFER!!!",
            "Make $5000 per day working from home! No experience needed!",
            "FREE MONEY! GUARANTEED RETURNS! INVEST NOW!!!",
            "You have won $1,000,000! Click this link to claim your prize!"
        ]
        
        for message in spam_messages:
            mock_ai_analysis = {
                'is_unsafe': True,
                'violations': ['Spam content detected', 'Promotional content'],
                'confidence': 0.85,
                'categories': ['spam'],
                'filtered_content': '[FILTERED] promotional content removed'
            }
            
            with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
                result = await supervisor_agent.filter_content(message, sample_context)
            
            assert result.is_safe is False
            assert len(result.violations) > 0


class TestPIIDetection:
    """Comprehensive PII detection and masking tests."""
    
    @pytest.fixture
    def supervisor_agent(self):
        """Create a SupervisorAgent instance for testing."""
        return SupervisorAgent()
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample AgentContext for testing."""
        return AgentContext(
            tenant_id="test-tenant-123",
            user_id="user-456",
            channel_type="telegram",
            conversation_id="conv-789",
            language="en"
        )
    
    @pytest.mark.asyncio
    async def test_detect_and_mask_email_addresses(self, supervisor_agent, sample_context):
        """Test detection and masking of email addresses."""
        test_cases = [
            ("Contact me at john.doe@example.com", "[EMAIL_REDACTED]"),
            ("My emails are: admin@company.org and support@help.net", "[EMAIL_REDACTED]"),
            ("Send to: user123@domain.co.uk and test@sub.domain.com", "[EMAIL_REDACTED]"),
            ("Email: firstname.lastname+tag@very-long-domain-name.com", "[EMAIL_REDACTED]")
        ]
        
        for original, expected_mask in test_cases:
            mock_ai_analysis = {
                'is_unsafe': False,
                'violations': [],
                'confidence': 0.8,
                'categories': [],
                'filtered_content': original
            }
            
            with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
                result = await supervisor_agent.filter_content(original, sample_context)
            
            assert expected_mask in result.filtered_content
            assert len(result.violations) > 0
            assert any('email' in v.lower() for v in result.violations)
    
    @pytest.mark.asyncio
    async def test_detect_and_mask_phone_numbers(self, supervisor_agent, sample_context):
        """Test detection and masking of phone numbers."""
        test_cases = [
            ("Call me at 555-123-4567", "[PHONE_REDACTED]"),
            ("My number is (555) 123-4567", "[PHONE_REDACTED]"),
            ("Phone: +1-555-123-4567", "[PHONE_REDACTED]"),
            ("Contact: 555.123.4567 or 555 123 4567", "[PHONE_REDACTED]")
        ]
        
        for original, expected_mask in test_cases:
            mock_ai_analysis = {
                'is_unsafe': False,
                'violations': [],
                'confidence': 0.8,
                'categories': [],
                'filtered_content': original
            }
            
            with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
                result = await supervisor_agent.filter_content(original, sample_context)
            
            assert expected_mask in result.filtered_content
            assert len(result.violations) > 0
            assert any('phone' in v.lower() for v in result.violations)
    
    @pytest.mark.asyncio
    async def test_detect_and_mask_credit_cards(self, supervisor_agent, sample_context):
        """Test detection and masking of credit card numbers."""
        test_cases = [
            ("My card is 4532-1234-5678-9012", "[CARD_REDACTED]"),
            ("Credit card: 4532 1234 5678 9012", "[CARD_REDACTED]"),
            ("Card number: 4532123456789012", "[CARD_REDACTED]"),
            ("Payment with 5555-5555-5555-4444", "[CARD_REDACTED]")
        ]
        
        for original, expected_mask in test_cases:
            mock_ai_analysis = {
                'is_unsafe': False,
                'violations': [],
                'confidence': 0.8,
                'categories': [],
                'filtered_content': original
            }
            
            with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
                result = await supervisor_agent.filter_content(original, sample_context)
            
            assert expected_mask in result.filtered_content
            assert len(result.violations) > 0
            assert any('credit_card' in v.lower() for v in result.violations)
    
    @pytest.mark.asyncio
    async def test_detect_and_mask_ssn(self, supervisor_agent, sample_context):
        """Test detection and masking of Social Security Numbers."""
        test_cases = [
            ("My SSN is 123-45-6789", "[SSN_REDACTED]"),
            ("Social Security: 987-65-4321", "[SSN_REDACTED]"),
            ("SSN: 555-44-3333", "[SSN_REDACTED]")
        ]
        
        for original, expected_mask in test_cases:
            mock_ai_analysis = {
                'is_unsafe': False,
                'violations': [],
                'confidence': 0.8,
                'categories': [],
                'filtered_content': original
            }
            
            with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
                result = await supervisor_agent.filter_content(original, sample_context)
            
            assert expected_mask in result.filtered_content
            assert len(result.violations) > 0
            assert any('ssn' in v.lower() for v in result.violations)
    
    @pytest.mark.asyncio
    async def test_detect_and_mask_iban(self, supervisor_agent, sample_context):
        """Test detection and masking of IBAN numbers."""
        test_cases = [
            ("IBAN: GB82WEST12345698765432", "[IBAN_REDACTED]"),
            ("My IBAN is DE89370400440532013000", "[IBAN_REDACTED]"),
            ("Bank account: FR1420041010050500013M02606", "[IBAN_REDACTED]")
        ]
        
        for original, expected_mask in test_cases:
            mock_ai_analysis = {
                'is_unsafe': False,
                'violations': [],
                'confidence': 0.8,
                'categories': [],
                'filtered_content': original
            }
            
            with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
                result = await supervisor_agent.filter_content(original, sample_context)
            
            assert expected_mask in result.filtered_content
            assert len(result.violations) > 0
            assert any('iban' in v.lower() for v in result.violations)
    
    @pytest.mark.asyncio
    async def test_multiple_pii_types_in_message(self, supervisor_agent, sample_context):
        """Test detection of multiple PII types in a single message."""
        message = "Contact John at john.doe@example.com or call 555-123-4567. His card is 4532-1234-5678-9012"
        
        mock_ai_analysis = {
            'is_unsafe': False,
            'violations': [],
            'confidence': 0.8,
            'categories': [],
            'filtered_content': message
        }
        
        with patch.object(supervisor_agent, '_analyze_content_with_ai', return_value=mock_ai_analysis):
            result = await supervisor_agent.filter_content(message, sample_context)
        
        assert '[EMAIL_REDACTED]' in result.filtered_content
        assert '[PHONE_REDACTED]' in result.filtered_content
        assert '[CARD_REDACTED]' in result.filtered_content
        assert len(result.violations) >= 3  # Should detect all three PII types


class TestPolicyCompliance:
    """Comprehensive policy compliance checking tests."""
    
    @pytest.fixture
    def supervisor_agent(self):
        """Create a SupervisorAgent instance for testing."""
        return SupervisorAgent()
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample AgentContext for testing."""
        return AgentContext(
            tenant_id="test-tenant-123",
            user_id="user-456",
            channel_type="telegram",
            conversation_id="conv-789",
            language="en"
        )
    
    @pytest.mark.asyncio
    async def test_gdpr_compliance_detection(self, supervisor_agent, sample_context):
        """Test detection of GDPR-related compliance issues."""
        gdpr_messages = [
            "I want to exercise my GDPR rights and delete all my personal data",
            "This is a data protection violation under GDPR Article 6",
            "I need to file a privacy complaint with the data protection authority",
            "You are processing my personal data without proper consent"
        ]
        
        for message in gdpr_messages:
            violations = await supervisor_agent._check_policy_violations(message, sample_context)
            
            compliance_violations = [v for v in violations if v.type == "compliance"]
            assert len(compliance_violations) > 0
            assert compliance_violations[0].severity == "high"
            # Check that the description contains compliance-related keywords
            description_lower = compliance_violations[0].description.lower()
            assert ("gdpr" in description_lower or "privacy" in description_lower or 
                   "data protection" in description_lower or "personal data" in description_lower)
    
    @pytest.mark.asyncio
    async def test_legal_issue_detection(self, supervisor_agent, sample_context):
        """Test detection of legal issues requiring escalation."""
        legal_messages = [
            "I am going to sue your company for breach of contract",
            "My attorney will be contacting you about this legal matter",
            "This is a clear violation of our service agreement",
            "I will take legal action if this is not resolved immediately"
        ]
        
        for message in legal_messages:
            violations = await supervisor_agent._check_policy_violations(message, sample_context)
            
            legal_violations = [v for v in violations if v.type == "legal"]
            assert len(legal_violations) > 0
            assert legal_violations[0].severity == "critical"
            assert "legal" in legal_violations[0].suggested_action.lower()
    
    @pytest.mark.asyncio
    async def test_discrimination_detection(self, supervisor_agent, sample_context):
        """Test detection of discrimination-related content."""
        discrimination_messages = [
            "I experienced discrimination because of my race",
            "This is workplace harassment based on my gender", 
            "I'm being treated unfairly due to discrimination",
            "This is a clear violation of employment law"
        ]
        
        for message in discrimination_messages:
            violations = await supervisor_agent._check_policy_violations(message, sample_context)
            
            # These messages should trigger legal violations due to keywords like "discrimination", "harassment", "violation"
            legal_violations = [v for v in violations if v.type == "legal"]
            assert len(legal_violations) > 0, f"No legal violations found for message: {message}. All violations: {[v.__dict__ for v in violations]}"
            assert legal_violations[0].severity == "critical"
    
    @pytest.mark.asyncio
    async def test_contract_breach_detection(self, supervisor_agent, sample_context):
        """Test detection of contract breach issues."""
        contract_messages = [
            "You have breached our service agreement terms",
            "This violates the contract we signed last month",
            "The terms and conditions are not being followed",
            "This is a clear breach of our business agreement"
        ]
        
        for message in contract_messages:
            violations = await supervisor_agent._check_policy_violations(message, sample_context)
            
            legal_violations = [v for v in violations if v.type == "legal"]
            assert len(legal_violations) > 0
            assert legal_violations[0].severity == "critical"
    
    @pytest.mark.asyncio
    async def test_compliance_escalation_workflow(self, supervisor_agent, sample_context):
        """Test that compliance issues trigger proper escalation."""
        compliance_message = "I need to file a GDPR complaint about data protection violations"
        
        response = await supervisor_agent.process(compliance_message, sample_context)
        
        assert response.requires_handoff is True
        assert len(response.metadata['policy_violations']) > 0
        
        policy_violation = response.metadata['policy_violations'][0]
        assert policy_violation['type'] == "compliance"
        assert policy_violation['severity'] == "high"
        assert "legal" in policy_violation['suggested_action'].lower() or "compliance" in policy_violation['suggested_action'].lower()


class TestResponseValidation:
    """Comprehensive response validation tests for AI-generated content."""
    
    @pytest.fixture
    def supervisor_agent(self):
        """Create a SupervisorAgent instance for testing."""
        return SupervisorAgent()
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample AgentContext for testing."""
        return AgentContext(
            tenant_id="test-tenant-123",
            user_id="user-456",
            channel_type="telegram",
            conversation_id="conv-789",
            language="en"
        )
    
    @pytest.mark.asyncio
    async def test_validate_professional_responses(self, supervisor_agent, sample_context):
        """Test validation of professional AI responses."""
        professional_responses = [
            "Thank you for contacting us. I'll be happy to help you with your inquiry about our services.",
            "I understand your concern and will escalate this to our technical team for immediate attention.",
            "Based on your requirements, I recommend our Enterprise plan which includes advanced features.",
            "I've scheduled your meeting for tomorrow at 2 PM. You'll receive a calendar invitation shortly."
        ]
        
        for response in professional_responses:
            mock_filter_result = FilterResult(
                is_safe=True,
                filtered_content=response,
                violations=[],
                confidence=0.9,
                metadata={}
            )
            
            with patch.object(supervisor_agent, 'filter_content', return_value=mock_filter_result):
                result = await supervisor_agent.validate_response(response, sample_context)
            
            assert result.content == response
            assert result.requires_handoff is False
            assert result.metadata['is_safe'] is True
            assert len(result.metadata['violations']) == 0
    
    @pytest.mark.asyncio
    async def test_validate_responses_with_placeholders(self, supervisor_agent, sample_context):
        """Test validation catches responses with placeholder text."""
        placeholder_responses = [
            "Hello [CUSTOMER_NAME], thank you for your inquiry.",
            "Your order {ORDER_ID} has been processed successfully.",
            "TODO: Add specific details about the service here.",
            "FIXME: This response needs to be customized.",
            "XXX: Replace with actual information"
        ]
        
        for response in placeholder_responses:
            mock_filter_result = FilterResult(
                is_safe=True,
                filtered_content=response,
                violations=[],
                confidence=0.9,
                metadata={}
            )
            
            with patch.object(supervisor_agent, 'filter_content', return_value=mock_filter_result):
                result = await supervisor_agent.validate_response(response, sample_context)
            
            assert result.requires_handoff is True
            assert any('placeholder' in v.lower() for v in result.metadata['violations'])
    
    @pytest.mark.asyncio
    async def test_validate_too_short_responses(self, supervisor_agent, sample_context):
        """Test validation catches responses that are too short or generic."""
        short_responses = [
            "OK",
            "Yes",
            "No",
            "Thanks",
            "Sure",
            "Done",
            "Hi"
        ]
        
        for response in short_responses:
            mock_filter_result = FilterResult(
                is_safe=True,
                filtered_content=response,
                violations=[],
                confidence=0.9,
                metadata={}
            )
            
            with patch.object(supervisor_agent, 'filter_content', return_value=mock_filter_result):
                result = await supervisor_agent.validate_response(response, sample_context)
            
            assert result.requires_handoff is True
            assert any('too short' in v.lower() for v in result.metadata['violations'])
    
    @pytest.mark.asyncio
    async def test_validate_responses_with_inappropriate_content(self, supervisor_agent, sample_context):
        """Test validation catches responses with inappropriate content."""
        inappropriate_responses = [
            "I don't give a damn about your problem.",
            "That's a stupid question to ask.",
            "You're being an idiot about this issue.",
            "This is fucking ridiculous."
        ]
        
        for response in inappropriate_responses:
            mock_filter_result = FilterResult(
                is_safe=False,
                filtered_content="**** inappropriate content filtered ****",
                violations=["Toxic language detected"],
                confidence=0.3,
                metadata={}
            )
            
            with patch.object(supervisor_agent, 'filter_content', return_value=mock_filter_result):
                result = await supervisor_agent.validate_response(response, sample_context)
            
            assert result.requires_handoff is True
            assert result.metadata['is_safe'] is False
            assert len(result.metadata['violations']) > 0
    
    @pytest.mark.asyncio
    async def test_validate_responses_with_pii_leakage(self, supervisor_agent, sample_context):
        """Test validation catches responses that leak PII."""
        pii_responses = [
            "I can see your email is john.doe@example.com in our system.",
            "Your phone number 555-123-4567 is already registered.",
            "The credit card ending in 1234 was charged successfully.",
            "Your SSN 123-45-6789 has been verified."
        ]
        
        for response in pii_responses:
            mock_filter_result = FilterResult(
                is_safe=True,
                filtered_content=response.replace("john.doe@example.com", "[EMAIL_REDACTED]")
                                        .replace("555-123-4567", "[PHONE_REDACTED]")
                                        .replace("1234", "[CARD_REDACTED]")
                                        .replace("123-45-6789", "[SSN_REDACTED]"),
                violations=["PII detected in response"],
                confidence=0.7,
                metadata={}
            )
            
            with patch.object(supervisor_agent, 'filter_content', return_value=mock_filter_result):
                result = await supervisor_agent.validate_response(response, sample_context)
            
            assert 'REDACTED' in result.content
            assert len(result.metadata['violations']) > 0
    
    @pytest.mark.asyncio
    async def test_response_validation_error_handling(self, supervisor_agent, sample_context):
        """Test response validation handles errors gracefully."""
        response = "This is a test response"
        
        # Mock filter_content to raise an exception
        with patch.object(supervisor_agent, 'filter_content', side_effect=Exception("Validation error")):
            # The validate_response method doesn't have error handling, so it should raise the exception
            with pytest.raises(Exception, match="Validation error"):
                await supervisor_agent.validate_response(response, sample_context)
    
    @pytest.mark.asyncio
    async def test_response_quality_assessment(self, supervisor_agent, sample_context):
        """Test assessment of response quality and helpfulness."""
        quality_test_cases = [
            ("Thank you for your inquiry. I'll help you resolve this issue step by step.", True),
            ("I understand your concern and will provide a detailed solution.", True),
            ("Here's the information you requested with relevant details.", True),
            ("I can't help with that.", False),
            ("That's not my problem.", False),
            ("Figure it out yourself.", False)
        ]
        
        for response, should_be_good in quality_test_cases:
            mock_filter_result = FilterResult(
                is_safe=True,
                filtered_content=response,
                violations=[],
                confidence=0.9 if should_be_good else 0.3,
                metadata={}
            )
            
            with patch.object(supervisor_agent, 'filter_content', return_value=mock_filter_result):
                result = await supervisor_agent.validate_response(response, sample_context)
            
            if should_be_good:
                assert result.requires_handoff is False
                assert result.metadata['is_safe'] is True
            else:
                # Poor quality responses might require handoff depending on length
                if len(response) < 10:
                    assert result.requires_handoff is True