"""Tests for Supervisor Agent."""

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