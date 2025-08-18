"""Unit tests for agent orchestration system."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.secretary.agents.orchestrator import (
    AgentOrchestrator, ConversationContext, AgentPerformanceMetrics, HandoffDecision
)
from app.secretary.agents.base_agent import AgentContext, AgentResponse


class TestAgentOrchestrator:
    """Test cases for AgentOrchestrator."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing."""
        return AgentOrchestrator()
    
    @pytest.fixture
    def agent_context(self):
        """Create agent context for testing."""
        return AgentContext(
            tenant_id="test-tenant-123",
            user_id="user-456",
            channel_type="web",
            conversation_id="conv-789",
            customer_id="customer-123",
            language="en"
        )    

    @pytest.mark.asyncio
    async def test_process_message_success(self, orchestrator, agent_context):
        """Test successful message processing through orchestrator."""
        message = "I need help with pricing"
        
        # Mock supervisor filter
        mock_filter_result = Mock()
        mock_filter_result.is_safe = True
        mock_filter_result.filtered_content = message
        mock_filter_result.violations = []
        mock_filter_result.confidence = 0.9
        
        # Mock router response
        mock_router_response = AgentResponse(
            content="Routed to sales",
            confidence=0.8,
            intent="sales",
            metadata={"language": "en"}
        )
        
        # Mock agent response
        mock_agent_response = AgentResponse(
            content="Here's our pricing information...",
            confidence=0.9,
            intent="sales",
            suggested_actions=["create_lead"]
        )
        
        # Mock validation response
        mock_validation_response = AgentResponse(
            content="Here's our pricing information...",
            confidence=0.9,
            intent="sales"
        )
        
        with patch.object(orchestrator.supervisor, 'filter_input', return_value=mock_filter_result):
            with patch.object(orchestrator.router, 'detect_intent', return_value=mock_router_response):
                with patch.object(orchestrator, '_evaluate_handoff_need') as mock_handoff:
                    mock_handoff.return_value = HandoffDecision(
                        should_handoff=False,
                        target_agent="sales",
                        reason="AI can handle",
                        confidence=0.8
                    )
                    
                    with patch.object(orchestrator.agents['sales'], 'generate_response', return_value=mock_agent_response):
                        with patch.object(orchestrator.supervisor, 'validate_response', return_value=mock_validation_response):
                            response = await orchestrator.process_message(message, agent_context)
        
        assert response.intent == "sales"
        assert response.confidence > 0.8
        assert "pricing" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_process_message_unsafe_content(self, orchestrator, agent_context):
        """Test processing of unsafe content."""
        message = "This is inappropriate content"
        
        # Mock supervisor to block content
        mock_filter_result = Mock()
        mock_filter_result.is_safe = False
        mock_filter_result.response_message = "Content blocked due to policy violation"
        mock_filter_result.requires_human_review = True
        mock_filter_result.to_dict.return_value = {"blocked": True}
        
        with patch.object(orchestrator.supervisor, 'filter_input', return_value=mock_filter_result):
            response = await orchestrator.process_message(message, agent_context)
        
        assert response.intent == "safety_violation"
        assert response.requires_handoff is True
        assert "blocked" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_evaluate_handoff_human_request(self, orchestrator, agent_context):
        """Test handoff evaluation for human agent request."""
        conv_context = ConversationContext(
            conversation_id="conv-789",
            tenant_id="test-tenant-123",
            customer_id="customer-123",
            channel_type="web"
        )
        
        # Mock routing result with human request
        routing_result = Mock()
        routing_result.message = "I want to speak to a human agent"
        routing_result.intent = "support"
        routing_result.confidence = 0.8
        
        decision = await orchestrator._evaluate_handoff_need(routing_result, conv_context, agent_context)
        
        assert decision.should_handoff is True
        assert decision.requires_human is True
        assert "human agent" in decision.reason.lower()
    
    @pytest.mark.asyncio
    async def test_evaluate_handoff_complex_issue(self, orchestrator, agent_context):
        """Test handoff evaluation for complex issues."""
        conv_context = ConversationContext(
            conversation_id="conv-789",
            tenant_id="test-tenant-123",
            customer_id="customer-123",
            channel_type="web"
        )
        
        # Mock routing result with complaint
        routing_result = Mock()
        routing_result.message = "I have a complaint about your service"
        routing_result.intent = "support"
        routing_result.confidence = 0.8
        
        decision = await orchestrator._evaluate_handoff_need(routing_result, conv_context, agent_context)
        
        assert decision.should_handoff is True
        assert decision.requires_human is True
        assert decision.urgency == "high"
    
    @pytest.mark.asyncio
    async def test_evaluate_handoff_long_conversation(self, orchestrator, agent_context):
        """Test handoff evaluation for long conversations."""
        conv_context = ConversationContext(
            conversation_id="conv-789",
            tenant_id="test-tenant-123",
            customer_id="customer-123",
            channel_type="web",
            message_count=15  # Long conversation
        )
        
        # Mock routing result
        routing_result = Mock()
        routing_result.message = "I still need help"
        routing_result.intent = "support"
        routing_result.confidence = 0.8
        
        decision = await orchestrator._evaluate_handoff_need(routing_result, conv_context, agent_context)
        
        assert decision.should_handoff is True
        assert decision.requires_human is True
        assert "long conversation" in decision.reason.lower()
    
    def test_get_or_create_conversation_context(self, orchestrator, agent_context):
        """Test conversation context creation and retrieval."""
        # First call should create new context
        context1 = orchestrator._get_or_create_conversation_context(agent_context)
        assert context1.conversation_id == agent_context.conversation_id
        assert context1.tenant_id == agent_context.tenant_id
        
        # Second call should return same context
        context2 = orchestrator._get_or_create_conversation_context(agent_context)
        assert context1 is context2
    
    def test_update_performance_metrics(self, orchestrator):
        """Test performance metrics updating."""
        response = AgentResponse(
            content="Test response",
            confidence=0.8,
            intent="sales",
            requires_handoff=False
        )
        
        orchestrator._update_performance_metrics("sales", response, 1.5)
        
        metrics = orchestrator.performance_metrics["sales"]
        assert metrics.total_requests == 1
        assert metrics.successful_responses == 1
        assert metrics.failed_responses == 0
        assert metrics.average_response_time == 1.5
        assert len(metrics.confidence_scores) == 1
        assert metrics.confidence_scores[0] == 0.8
    
    def test_update_performance_metrics_failed_response(self, orchestrator):
        """Test performance metrics for failed responses."""
        response = AgentResponse(
            content="Error response",
            confidence=0.3,  # Low confidence = failed
            intent="support",
            requires_handoff=True
        )
        
        orchestrator._update_performance_metrics("support", response, 2.0)
        
        metrics = orchestrator.performance_metrics["support"]
        assert metrics.total_requests == 1
        assert metrics.successful_responses == 0
        assert metrics.failed_responses == 1
        assert metrics.handoff_requests == 1
    
    def test_get_performance_metrics_single_agent(self, orchestrator):
        """Test getting performance metrics for single agent."""
        # Add some test data
        response = AgentResponse(content="Test", confidence=0.8, intent="sales")
        orchestrator._update_performance_metrics("sales", response, 1.0)
        
        metrics = orchestrator.get_performance_metrics("sales")
        assert metrics["agent_name"] == "sales"
        assert metrics["total_requests"] == 1
    
    def test_get_performance_metrics_all_agents(self, orchestrator):
        """Test getting performance metrics for all agents."""
        # Add test data for multiple agents
        response1 = AgentResponse(content="Test1", confidence=0.8, intent="sales")
        response2 = AgentResponse(content="Test2", confidence=0.7, intent="support")
        
        orchestrator._update_performance_metrics("sales", response1, 1.0)
        orchestrator._update_performance_metrics("support", response2, 1.5)
        
        all_metrics = orchestrator.get_performance_metrics()
        assert "sales" in all_metrics
        assert "support" in all_metrics
        assert all_metrics["sales"]["total_requests"] == 1
        assert all_metrics["support"]["total_requests"] == 1
    
    def test_get_conversation_context(self, orchestrator, agent_context):
        """Test getting conversation context by ID."""
        # Create context first
        created_context = orchestrator._get_or_create_conversation_context(agent_context)
        
        # Retrieve it
        retrieved_context = orchestrator.get_conversation_context(agent_context.conversation_id)
        assert retrieved_context is created_context
        
        # Non-existent context should return None
        non_existent = orchestrator.get_conversation_context("non-existent-id")
        assert non_existent is None
    
    def test_cleanup_expired_contexts(self, orchestrator, agent_context):
        """Test cleanup of expired conversation contexts."""
        # Create context
        context = orchestrator._get_or_create_conversation_context(agent_context)
        
        # Make it expired
        context.last_activity = datetime.now() - timedelta(hours=25)
        
        # Cleanup should remove it
        orchestrator.cleanup_expired_contexts()
        
        # Should no longer exist
        retrieved = orchestrator.get_conversation_context(agent_context.conversation_id)
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_health_check(self, orchestrator):
        """Test orchestrator health check."""
        # Mock agent health checks
        with patch.object(orchestrator.router, 'health_check', return_value=None):
            with patch.object(orchestrator.supervisor, 'health_check', return_value=None):
                with patch.object(orchestrator.agents['sales'], 'health_check', return_value=None):
                    with patch.object(orchestrator.agents['support'], 'health_check', return_value=None):
                        with patch.object(orchestrator.agents['billing'], 'health_check', return_value=None):
                            with patch.object(orchestrator.agents['operations'], 'health_check', return_value=None):
                                health = await orchestrator.health_check()
        
        assert health["orchestrator"] == "healthy"
        assert health["agents"]["router"] == "healthy"
        assert health["agents"]["supervisor"] == "healthy"
        assert health["agents"]["sales"] == "healthy"
        assert health["agents"]["support"] == "healthy"
        assert health["agents"]["billing"] == "healthy"
        assert health["agents"]["operations"] == "healthy"
        assert "conversation_contexts" in health
        assert "performance_metrics" in health


class TestConversationContext:
    """Test cases for ConversationContext."""
    
    def test_conversation_context_creation(self):
        """Test conversation context creation."""
        context = ConversationContext(
            conversation_id="conv-123",
            tenant_id="tenant-456",
            customer_id="customer-789",
            channel_type="telegram"
        )
        
        assert context.conversation_id == "conv-123"
        assert context.tenant_id == "tenant-456"
        assert context.customer_id == "customer-789"
        assert context.channel_type == "telegram"
        assert context.message_count == 0
        assert context.current_agent is None
        assert len(context.intent_history) == 0
        assert isinstance(context.created_at, datetime)
        assert isinstance(context.last_activity, datetime)


class TestAgentPerformanceMetrics:
    """Test cases for AgentPerformanceMetrics."""
    
    def test_performance_metrics_creation(self):
        """Test performance metrics creation."""
        metrics = AgentPerformanceMetrics(agent_name="test_agent")
        
        assert metrics.agent_name == "test_agent"
        assert metrics.total_requests == 0
        assert metrics.successful_responses == 0
        assert metrics.failed_responses == 0
        assert metrics.average_response_time == 0.0
        assert len(metrics.confidence_scores) == 0
        assert metrics.handoff_requests == 0
        assert isinstance(metrics.last_updated, datetime)


class TestHandoffDecision:
    """Test cases for HandoffDecision."""
    
    def test_handoff_decision_creation(self):
        """Test handoff decision creation."""
        decision = HandoffDecision(
            should_handoff=True,
            target_agent="sales",
            reason="High qualification level",
            confidence=0.9,
            requires_human=False,
            urgency="high"
        )
        
        assert decision.should_handoff is True
        assert decision.target_agent == "sales"
        assert decision.reason == "High qualification level"
        assert decision.confidence == 0.9
        assert decision.requires_human is False
        assert decision.urgency == "high"
    
    def test_handoff_decision_defaults(self):
        """Test handoff decision with default values."""
        decision = HandoffDecision(should_handoff=False)
        
        assert decision.should_handoff is False
        assert decision.target_agent is None
        assert decision.reason == ""
        assert decision.confidence == 0.0
        assert decision.requires_human is False
        assert decision.urgency == "normal"