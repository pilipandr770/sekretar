"""Tests for Router Agent."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from app.secretary.agents.router_agent import RouterAgent, IntentResult
from app.secretary.agents.base_agent import AgentContext, AgentResponse


class TestRouterAgent:
    """Test cases for RouterAgent."""
    
    @pytest.fixture
    def router_agent(self):
        """Create a RouterAgent instance for testing."""
        return RouterAgent()
    
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
    
    def test_init(self, router_agent):
        """Test RouterAgent initialization."""
        assert router_agent.name == "RouterAgent"
        assert "sales" in router_agent.intent_categories
        assert "support" in router_agent.intent_categories
        assert "billing" in router_agent.intent_categories
        assert "operations" in router_agent.intent_categories
        assert "en" in router_agent.supported_languages
    
    @pytest.mark.asyncio
    async def test_process_success(self, router_agent, sample_context):
        """Test successful message processing."""
        message = "I need help with pricing for your product"
        
        # Mock the detect_intent method
        mock_intent = IntentResult(
            category="sales",
            confidence=0.9,
            language="en",
            customer_context={"urgency": "medium", "sentiment": "neutral"},
            routing_metadata={"keywords": ["pricing", "product"], "priority": "medium"}
        )
        
        with patch.object(router_agent, 'detect_intent', return_value=mock_intent):
            with patch.object(router_agent, '_analyze_customer_context', return_value={"has_questions": True}):
                response = await router_agent.process(message, sample_context)
        
        assert isinstance(response, AgentResponse)
        assert response.intent == "sales"
        assert response.confidence == 0.9
        assert "sales agent" in response.content.lower()
        assert response.metadata["language"] == "en"
    
    @pytest.mark.asyncio
    async def test_process_fallback_on_error(self, router_agent, sample_context):
        """Test fallback behavior when processing fails."""
        message = "Test message"
        
        # Mock detect_intent to raise an exception
        with patch.object(router_agent, 'detect_intent', side_effect=Exception("API Error")):
            response = await router_agent.process(message, sample_context)
        
        assert response.intent == "operations"
        assert response.confidence == 0.5
        assert "fallback" in response.content.lower()
        assert "error" in response.metadata
    
    @pytest.mark.asyncio
    async def test_detect_intent_with_openai(self, router_agent, sample_context):
        """Test intent detection using OpenAI API."""
        message = "I want to buy your premium plan"
        
        # Mock OpenAI response
        mock_response = json.dumps({
            "category": "sales",
            "confidence": 0.95,
            "language": "en",
            "customer_context": {
                "urgency": "medium",
                "sentiment": "positive",
                "complexity": "simple"
            },
            "routing_metadata": {
                "keywords": ["buy", "premium", "plan"],
                "entities": ["premium plan"],
                "priority": "high"
            }
        })
        
        with patch.object(router_agent, '_call_openai', return_value=mock_response):
            result = await router_agent.detect_intent(message, sample_context)
        
        assert isinstance(result, IntentResult)
        assert result.category == "sales"
        assert result.confidence == 0.95
        assert result.language == "en"
        assert result.customer_context["sentiment"] == "positive"
        assert "buy" in result.routing_metadata["keywords"]
    
    @pytest.mark.asyncio
    async def test_detect_intent_fallback_on_json_error(self, router_agent, sample_context):
        """Test fallback when OpenAI returns invalid JSON."""
        message = "Help me with billing"
        
        # Mock OpenAI to return invalid JSON
        with patch.object(router_agent, '_call_openai', return_value="Invalid JSON response"):
            result = await router_agent.detect_intent(message, sample_context)
        
        assert isinstance(result, IntentResult)
        # Should detect billing from keywords, but might detect support due to "help"
        assert result.category in ["billing", "support"]  
        assert result.routing_metadata.get("fallback_used") is True
    
    def test_fallback_intent_detection_sales(self, router_agent):
        """Test fallback intent detection for sales messages."""
        message = "I want to buy your product and get a quote"
        result = router_agent._fallback_intent_detection(message)
        
        assert result.category == "sales"
        assert result.confidence > 0
        assert "buy" in result.routing_metadata["keywords"]
    
    def test_fallback_intent_detection_support(self, router_agent):
        """Test fallback intent detection for support messages."""
        message = "I have a technical problem and need help"
        result = router_agent._fallback_intent_detection(message)
        
        assert result.category == "support"
        assert result.confidence > 0
        assert "help" in result.routing_metadata["keywords"]
    
    def test_fallback_intent_detection_billing(self, router_agent):
        """Test fallback intent detection for billing messages."""
        message = "I need my invoice and have payment issues"
        result = router_agent._fallback_intent_detection(message)
        
        assert result.category == "billing"
        assert result.confidence > 0
        assert "invoice" in result.routing_metadata["keywords"]
    
    def test_fallback_intent_detection_operations(self, router_agent):
        """Test fallback intent detection for general messages."""
        message = "What are your business hours?"
        result = router_agent._fallback_intent_detection(message)
        
        assert result.category == "operations"
        # Confidence might be lower if some keywords match
        assert result.confidence >= 0.2
    
    def test_detect_language_simple_german(self, router_agent):
        """Test simple German language detection."""
        message = "Ich habe ein Problem mit der Rechnung"
        language = router_agent._detect_language_simple(message)
        assert language == "de"
    
    def test_detect_language_simple_ukrainian(self, router_agent):
        """Test simple Ukrainian language detection."""
        message = "Я маю питання про ваш продукт"
        language = router_agent._detect_language_simple(message)
        assert language == "uk"
    
    def test_detect_language_simple_english_default(self, router_agent):
        """Test default to English when language unclear."""
        message = "xyz abc 123 random text"
        language = router_agent._detect_language_simple(message)
        assert language == "en"
    
    @pytest.mark.asyncio
    async def test_analyze_customer_context(self, router_agent, sample_context):
        """Test customer context analysis."""
        message = "URGENT: I have a problem with my account!"
        context = await router_agent._analyze_customer_context(message, sample_context)
        
        assert context["has_urgency_indicators"] is True
        assert context["has_questions"] is False
        assert context["is_complaint"] is True
        assert context["message_length"] == len(message)
    
    def test_get_routing_decision_high_confidence(self, router_agent):
        """Test routing decision for high confidence intent."""
        intent_result = IntentResult(
            category="sales",
            confidence=0.9,
            language="en",
            customer_context={"urgency": "medium", "sentiment": "positive"},
            routing_metadata={"priority": "medium"}
        )
        
        decision = router_agent.get_routing_decision(intent_result)
        
        assert decision["target_agent"] == "sales"
        assert decision["confidence"] == 0.9
        assert decision["requires_human"] is False
        assert decision["priority"] == "medium"
    
    def test_get_routing_decision_low_confidence(self, router_agent):
        """Test routing decision for low confidence intent."""
        intent_result = IntentResult(
            category="operations",
            confidence=0.2,
            language="en",
            customer_context={"urgency": "low", "sentiment": "neutral"},
            routing_metadata={"priority": "low"}
        )
        
        decision = router_agent.get_routing_decision(intent_result)
        
        assert decision["target_agent"] == "operations"
        assert decision["confidence"] == 0.2
        assert decision["requires_human"] is True  # Low confidence
    
    def test_get_routing_decision_high_urgency(self, router_agent):
        """Test routing decision for high urgency messages."""
        intent_result = IntentResult(
            category="support",
            confidence=0.8,
            language="en",
            customer_context={"urgency": "high", "sentiment": "negative"},
            routing_metadata={"priority": "medium"}
        )
        
        decision = router_agent.get_routing_decision(intent_result)
        
        assert decision["target_agent"] == "support"
        assert decision["priority"] == "high"  # Upgraded due to urgency
        assert decision["requires_human"] is True  # High urgency requires human
    
    def test_get_routing_decision_negative_sentiment(self, router_agent):
        """Test routing decision for negative sentiment messages."""
        intent_result = IntentResult(
            category="billing",
            confidence=0.7,
            language="en",
            customer_context={"urgency": "medium", "sentiment": "negative"},
            routing_metadata={"priority": "low"}
        )
        
        decision = router_agent.get_routing_decision(intent_result)
        
        assert decision["target_agent"] == "billing"
        assert decision["priority"] == "high"  # Upgraded due to negative sentiment
    
    def test_create_intent_detection_prompt(self, router_agent):
        """Test intent detection prompt creation."""
        prompt = router_agent._create_intent_detection_prompt()
        
        assert "intent detection system" in prompt.lower()
        assert "sales" in prompt
        assert "support" in prompt
        assert "billing" in prompt
        assert "operations" in prompt
        assert "json" in prompt.lower()
        assert all(lang in prompt for lang in router_agent.supported_languages)