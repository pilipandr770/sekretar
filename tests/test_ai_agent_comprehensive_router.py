"""Comprehensive tests for Router Agent with real business scenarios."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from app.secretary.agents.router_agent import RouterAgent, IntentResult
from app.secretary.agents.base_agent import AgentContext, AgentResponse


class TestRouterAgentComprehensive:
    """Comprehensive test cases for RouterAgent with real business scenarios."""
    
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

    # Language Detection Tests
    @pytest.mark.asyncio
    async def test_language_detection_english_business_inquiry(self, router_agent, sample_context):
        """Test language detection for English business inquiry."""
        message = "Hello, I would like to know more about your pricing plans and available features for enterprise customers."
        
        mock_intent = IntentResult(
            category="sales",
            confidence=0.9,
            language="en",
            customer_context={"urgency": "medium", "sentiment": "positive"},
            routing_metadata={"keywords": ["pricing", "enterprise"], "priority": "medium"}
        )
        
        with patch.object(router_agent, 'detect_intent', return_value=mock_intent):
            with patch.object(router_agent, '_analyze_customer_context', return_value={"has_questions": True}):
                response = await router_agent.process(message, sample_context)
        
        assert response.metadata["language"] == "en"
        assert response.intent == "sales"
        assert response.confidence == 0.9

    @pytest.mark.asyncio
    async def test_language_detection_german_support_request(self, router_agent, sample_context):
        """Test language detection for German support request."""
        message = "Hallo, ich habe ein Problem mit der Anmeldung und kann nicht auf mein Konto zugreifen."
        
        mock_intent = IntentResult(
            category="support",
            confidence=0.85,
            language="de",
            customer_context={"urgency": "high", "sentiment": "negative"},
            routing_metadata={"keywords": ["Problem", "Anmeldung"], "priority": "high"}
        )
        
        with patch.object(router_agent, 'detect_intent', return_value=mock_intent):
            with patch.object(router_agent, '_analyze_customer_context', return_value={"is_complaint": True}):
                response = await router_agent.process(message, sample_context)
        
        assert response.metadata["language"] == "de"
        assert response.intent == "support"
        assert response.confidence == 0.85

    @pytest.mark.asyncio
    async def test_language_detection_ukrainian_billing_inquiry(self, router_agent, sample_context):
        """Test language detection for Ukrainian billing inquiry."""
        message = "Привіт, я маю питання про мій рахунок і платежі за підписку."
        
        mock_intent = IntentResult(
            category="billing",
            confidence=0.8,
            language="uk",
            customer_context={"urgency": "medium", "sentiment": "neutral"},
            routing_metadata={"keywords": ["рахунок", "платежі"], "priority": "medium"}
        )
        
        with patch.object(router_agent, 'detect_intent', return_value=mock_intent):
            with patch.object(router_agent, '_analyze_customer_context', return_value={"has_questions": True}):
                response = await router_agent.process(message, sample_context)
        
        assert response.metadata["language"] == "uk"
        assert response.intent == "billing"

    def test_simple_language_detection_german(self, router_agent):
        """Test simple German language detection with common words."""
        message = "Ich habe ein Problem mit der Rechnung und brauche Hilfe"
        language = router_agent._detect_language_simple(message)
        assert language == "de"

    def test_simple_language_detection_ukrainian(self, router_agent):
        """Test simple Ukrainian language detection with common words."""
        message = "Я маю проблему з рахунком і потребую допомоги"
        language = router_agent._detect_language_simple(message)
        assert language == "uk"

    def test_simple_language_detection_mixed_content(self, router_agent):
        """Test language detection with mixed content defaulting to English."""
        message = "Hello world 123 xyz random text without clear language indicators"
        language = router_agent._detect_language_simple(message)
        assert language == "en"

    # Intent Classification Tests with Real Business Scenarios
    @pytest.mark.asyncio
    async def test_intent_classification_sales_pricing_inquiry(self, router_agent, sample_context):
        """Test intent classification for sales pricing inquiry."""
        message = "I'm interested in your enterprise plan. Can you provide pricing details and a demo?"
        
        mock_response = json.dumps({
            "category": "sales",
            "confidence": 0.95,
            "language": "en",
            "customer_context": {
                "urgency": "medium",
                "sentiment": "positive",
                "complexity": "medium"
            },
            "routing_metadata": {
                "keywords": ["enterprise", "pricing", "demo"],
                "entities": ["enterprise plan"],
                "priority": "high"
            }
        })
        
        with patch.object(router_agent, '_call_openai', return_value=mock_response):
            result = await router_agent.detect_intent(message, sample_context)
        
        assert result.category == "sales"
        assert result.confidence == 0.95
        assert "enterprise" in result.routing_metadata["keywords"]
        assert result.customer_context["sentiment"] == "positive"

    @pytest.mark.asyncio
    async def test_intent_classification_support_technical_issue(self, router_agent, sample_context):
        """Test intent classification for technical support issue."""
        message = "I'm experiencing a critical bug where the system crashes when I try to upload files. This is blocking our operations."
        
        mock_response = json.dumps({
            "category": "support",
            "confidence": 0.92,
            "language": "en",
            "customer_context": {
                "urgency": "high",
                "sentiment": "negative",
                "complexity": "complex"
            },
            "routing_metadata": {
                "keywords": ["critical", "bug", "crashes", "upload"],
                "entities": ["file upload", "system crash"],
                "priority": "critical"
            }
        })
        
        with patch.object(router_agent, '_call_openai', return_value=mock_response):
            result = await router_agent.detect_intent(message, sample_context)
        
        assert result.category == "support"
        assert result.confidence == 0.92
        assert result.customer_context["urgency"] == "high"
        assert result.routing_metadata["priority"] == "critical"

    @pytest.mark.asyncio
    async def test_intent_classification_billing_payment_dispute(self, router_agent, sample_context):
        """Test intent classification for billing payment dispute."""
        message = "I was charged twice for my subscription this month. I need a refund for the duplicate charge immediately."
        
        mock_response = json.dumps({
            "category": "billing",
            "confidence": 0.88,
            "language": "en",
            "customer_context": {
                "urgency": "high",
                "sentiment": "negative",
                "complexity": "medium"
            },
            "routing_metadata": {
                "keywords": ["charged", "twice", "refund", "duplicate"],
                "entities": ["subscription", "duplicate charge"],
                "priority": "high"
            }
        })
        
        with patch.object(router_agent, '_call_openai', return_value=mock_response):
            result = await router_agent.detect_intent(message, sample_context)
        
        assert result.category == "billing"
        assert result.confidence == 0.88
        assert "refund" in result.routing_metadata["keywords"]
        assert result.customer_context["urgency"] == "high"

    @pytest.mark.asyncio
    async def test_intent_classification_operations_business_hours(self, router_agent, sample_context):
        """Test intent classification for operations inquiry about business hours."""
        message = "What are your business hours and how can I contact your support team outside of normal hours?"
        
        mock_response = json.dumps({
            "category": "operations",
            "confidence": 0.85,
            "language": "en",
            "customer_context": {
                "urgency": "low",
                "sentiment": "neutral",
                "complexity": "simple"
            },
            "routing_metadata": {
                "keywords": ["business hours", "contact", "support team"],
                "entities": ["business hours", "support team"],
                "priority": "low"
            }
        })
        
        with patch.object(router_agent, '_call_openai', return_value=mock_response):
            result = await router_agent.detect_intent(message, sample_context)
        
        assert result.category == "operations"
        assert result.confidence == 0.85
        assert result.customer_context["complexity"] == "simple"

    @pytest.mark.asyncio
    async def test_intent_classification_mixed_sales_support(self, router_agent, sample_context):
        """Test intent classification for mixed sales and support inquiry."""
        message = "I'm interested in upgrading to your premium plan, but I'm having issues with my current account settings."
        
        mock_response = json.dumps({
            "category": "sales",
            "confidence": 0.75,
            "language": "en",
            "customer_context": {
                "urgency": "medium",
                "sentiment": "neutral",
                "complexity": "medium"
            },
            "routing_metadata": {
                "keywords": ["upgrading", "premium plan", "issues", "account"],
                "entities": ["premium plan", "account settings"],
                "priority": "medium"
            }
        })
        
        with patch.object(router_agent, '_call_openai', return_value=mock_response):
            result = await router_agent.detect_intent(message, sample_context)
        
        assert result.category == "sales"
        assert result.confidence == 0.75
        assert "upgrading" in result.routing_metadata["keywords"]

    # Agent Routing Decision Validation Tests
    def test_routing_decision_high_confidence_sales(self, router_agent):
        """Test routing decision for high confidence sales intent."""
        intent_result = IntentResult(
            category="sales",
            confidence=0.95,
            language="en",
            customer_context={"urgency": "medium", "sentiment": "positive", "complexity": "medium"},
            routing_metadata={"keywords": ["pricing", "demo"], "priority": "high"}
        )
        
        decision = router_agent.get_routing_decision(intent_result)
        
        assert decision["target_agent"] == "sales"
        assert decision["confidence"] == 0.95
        assert decision["priority"] == "high"
        assert decision["requires_human"] is False
        assert decision["language"] == "en"

    def test_routing_decision_critical_support_issue(self, router_agent):
        """Test routing decision for critical support issue."""
        intent_result = IntentResult(
            category="support",
            confidence=0.9,
            language="en",
            customer_context={"urgency": "high", "sentiment": "negative", "complexity": "complex"},
            routing_metadata={"keywords": ["critical", "bug", "system down"], "priority": "critical"}
        )
        
        decision = router_agent.get_routing_decision(intent_result)
        
        assert decision["target_agent"] == "support"
        assert decision["priority"] == "high"  # Upgraded due to high urgency
        assert decision["requires_human"] is True  # High urgency requires human
        assert decision["estimated_complexity"] == "complex"

    def test_routing_decision_low_confidence_fallback(self, router_agent):
        """Test routing decision for low confidence requiring human intervention."""
        intent_result = IntentResult(
            category="operations",
            confidence=0.25,
            language="en",
            customer_context={"urgency": "low", "sentiment": "neutral", "complexity": "simple"},
            routing_metadata={"keywords": [], "priority": "low"}
        )
        
        decision = router_agent.get_routing_decision(intent_result)
        
        assert decision["target_agent"] == "operations"
        assert decision["confidence"] == 0.25
        assert decision["requires_human"] is True  # Low confidence requires human
        assert decision["priority"] == "low"

    def test_routing_decision_billing_sensitive_data(self, router_agent):
        """Test routing decision for billing with sensitive data indicators."""
        intent_result = IntentResult(
            category="billing",
            confidence=0.8,
            language="en",
            customer_context={"urgency": "high", "sentiment": "negative", "complexity": "medium"},
            routing_metadata={"keywords": ["payment", "card", "refund"], "priority": "medium"}
        )
        
        decision = router_agent.get_routing_decision(intent_result)
        
        assert decision["target_agent"] == "billing"
        assert decision["priority"] == "high"  # Upgraded due to negative sentiment
        assert decision["confidence"] == 0.8

    # Fallback Intent Detection Tests
    def test_fallback_intent_detection_sales_keywords(self, router_agent):
        """Test fallback intent detection with strong sales keywords."""
        message = "I want to buy your premium product and need a quote for enterprise pricing"
        result = router_agent._fallback_intent_detection(message)
        
        assert result.category == "sales"
        assert result.confidence > 0.5
        assert "buy" in result.routing_metadata["keywords"]
        assert "pricing" in result.routing_metadata["keywords"]
        assert result.routing_metadata["fallback_used"] is True

    def test_fallback_intent_detection_support_keywords(self, router_agent):
        """Test fallback intent detection with strong support keywords."""
        message = "I have a technical problem and need help troubleshooting this error"
        result = router_agent._fallback_intent_detection(message)
        
        assert result.category == "support"
        assert result.confidence > 0.5
        assert "help" in result.routing_metadata["keywords"]
        assert "problem" in result.routing_metadata["keywords"]

    def test_fallback_intent_detection_billing_keywords(self, router_agent):
        """Test fallback intent detection with billing keywords."""
        message = "I need my invoice and have questions about subscription billing"
        result = router_agent._fallback_intent_detection(message)
        
        assert result.category == "billing"
        assert result.confidence > 0.5
        assert "invoice" in result.routing_metadata["keywords"]
        assert "billing" in result.routing_metadata["keywords"]

    def test_fallback_intent_detection_no_clear_keywords(self, router_agent):
        """Test fallback intent detection with no clear category keywords."""
        message = "Hello there, just checking in to see how things are going"
        result = router_agent._fallback_intent_detection(message)
        
        assert result.category == "operations"
        assert result.confidence >= 0.3
        assert result.routing_metadata["fallback_used"] is True

    # Customer Context Analysis Tests
    @pytest.mark.asyncio
    async def test_customer_context_analysis_urgent_complaint(self, router_agent, sample_context):
        """Test customer context analysis for urgent complaint."""
        message = "URGENT: This is completely unacceptable! Your system has been down for hours and we're losing money!"
        context = await router_agent._analyze_customer_context(message, sample_context)
        
        assert context["has_urgency_indicators"] is True
        assert context["is_complaint"] is True
        assert context["has_questions"] is False
        assert context["message_length"] == len(message)

    @pytest.mark.asyncio
    async def test_customer_context_analysis_polite_inquiry(self, router_agent, sample_context):
        """Test customer context analysis for polite inquiry."""
        message = "Good morning! I hope you're doing well. Could you please help me understand your pricing structure?"
        context = await router_agent._analyze_customer_context(message, sample_context)
        
        assert context["is_greeting"] is True
        assert context["has_questions"] is True
        assert context["has_urgency_indicators"] is False
        assert context["is_complaint"] is False

    @pytest.mark.asyncio
    async def test_customer_context_analysis_with_conversation_history(self, router_agent):
        """Test customer context analysis with conversation history."""
        context_with_history = AgentContext(
            tenant_id="test-tenant-123",
            user_id="user-456",
            channel_type="telegram",
            conversation_id="existing-conv-123",
            language="en"
        )
        
        message = "Following up on my previous question about billing"
        context = await router_agent._analyze_customer_context(message, context_with_history)
        
        assert context["has_conversation_history"] is True
        assert context["message_length"] == len(message)

    # Error Handling and Edge Cases
    @pytest.mark.asyncio
    async def test_process_with_openai_api_failure(self, router_agent, sample_context):
        """Test processing when OpenAI API fails."""
        message = "I need help with my account"
        
        with patch.object(router_agent, 'detect_intent', side_effect=Exception("OpenAI API timeout")):
            response = await router_agent.process(message, sample_context)
        
        assert response.intent == "operations"  # Fallback
        assert response.confidence == 0.5
        assert "fallback" in response.content.lower()
        assert "error" in response.metadata

    @pytest.mark.asyncio
    async def test_detect_intent_with_invalid_json_response(self, router_agent, sample_context):
        """Test intent detection with invalid JSON from OpenAI."""
        message = "Help me with billing issues"
        
        with patch.object(router_agent, '_call_openai', return_value="This is not valid JSON"):
            result = await router_agent.detect_intent(message, sample_context)
        
        assert isinstance(result, IntentResult)
        assert result.routing_metadata.get("fallback_used") is True
        assert result.category in ["billing", "support"]  # Should detect from keywords

    @pytest.mark.asyncio
    async def test_detect_intent_with_partial_json_response(self, router_agent, sample_context):
        """Test intent detection with partial/malformed JSON from OpenAI."""
        message = "I want to upgrade my plan"
        
        malformed_json = '{"category": "sales", "confidence": 0.8'  # Missing closing brace
        
        with patch.object(router_agent, '_call_openai', return_value=malformed_json):
            result = await router_agent.detect_intent(message, sample_context)
        
        assert isinstance(result, IntentResult)
        assert result.routing_metadata.get("fallback_used") is True
        assert result.category == "sales"  # Should detect from keywords

    # Multi-language Business Scenarios
    @pytest.mark.asyncio
    async def test_german_business_inquiry_complete_flow(self, router_agent, sample_context):
        """Test complete flow for German business inquiry."""
        message = "Guten Tag, ich interessiere mich für Ihre Unternehmenslösung und möchte gerne ein Angebot erhalten."
        
        mock_intent = IntentResult(
            category="sales",
            confidence=0.87,
            language="de",
            customer_context={"urgency": "medium", "sentiment": "positive", "complexity": "medium"},
            routing_metadata={"keywords": ["Unternehmenslösung", "Angebot"], "priority": "medium"}
        )
        
        with patch.object(router_agent, 'detect_intent', return_value=mock_intent):
            with patch.object(router_agent, '_analyze_customer_context', return_value={"is_greeting": True}):
                response = await router_agent.process(message, sample_context)
        
        assert response.intent == "sales"
        assert response.metadata["language"] == "de"
        assert response.confidence == 0.87

    @pytest.mark.asyncio
    async def test_ukrainian_support_request_complete_flow(self, router_agent, sample_context):
        """Test complete flow for Ukrainian support request."""
        message = "Допоможіть, будь ласка! У мене проблема з входом в систему і я не можу отримати доступ до свого акаунту."
        
        mock_intent = IntentResult(
            category="support",
            confidence=0.83,
            language="uk",
            customer_context={"urgency": "high", "sentiment": "negative", "complexity": "medium"},
            routing_metadata={"keywords": ["проблема", "вхід", "акаунт"], "priority": "high"}
        )
        
        with patch.object(router_agent, 'detect_intent', return_value=mock_intent):
            with patch.object(router_agent, '_analyze_customer_context', return_value={"is_complaint": True}):
                response = await router_agent.process(message, sample_context)
        
        assert response.intent == "support"
        assert response.metadata["language"] == "uk"
        assert response.confidence == 0.83

    # Performance and Edge Case Tests
    def test_intent_categories_completeness(self, router_agent):
        """Test that all required intent categories are defined."""
        required_categories = ['sales', 'support', 'billing', 'operations']
        
        for category in required_categories:
            assert category in router_agent.intent_categories
            assert len(router_agent.intent_categories[category]) > 0

    def test_supported_languages_completeness(self, router_agent):
        """Test that all required languages are supported."""
        required_languages = ['en', 'de', 'uk']
        
        for language in required_languages:
            assert language in router_agent.supported_languages

    def test_create_intent_detection_prompt_completeness(self, router_agent):
        """Test that intent detection prompt includes all necessary elements."""
        prompt = router_agent._create_intent_detection_prompt()
        
        # Check for required sections
        assert "intent detection system" in prompt.lower()
        assert "json" in prompt.lower()
        assert "category" in prompt.lower()
        assert "confidence" in prompt.lower()
        assert "language" in prompt.lower()
        
        # Check for all categories
        for category in router_agent.intent_categories.keys():
            assert category in prompt.lower()
        
        # Check for all supported languages
        for language in router_agent.supported_languages:
            assert language in prompt