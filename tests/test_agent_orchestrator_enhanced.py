"""Unit tests for enhanced agent orchestration system."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.secretary.agents.orchestrator import (
    AgentOrchestrator, ConversationContext, AgentPerformanceMetrics, HandoffDecision
)
from app.secretary.agents.base_agent import AgentContext, AgentResponse


class TestEnhancedAgentOrchestrator:
    """Test cases for enhanced AgentOrchestrator functionality."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing."""
        return AgentOrchestrator()
    
    @pytest.fixture
    def agent_context(self):
        """Create agent context for testing."""
        return AgentContext(
            tenant_id="test_tenant_123",
            user_id="user_456",
            channel_type="telegram",
            conversation_id="conv_789",
            customer_id="customer_101",
            language="en",
            metadata={"test": "data"}
        )
    
    @pytest.fixture
    def conversation_context(self):
        """Create conversation context for testing."""
        return ConversationContext(
            thread_id="conv_789",
            conversation_history=[
                {"role": "customer", "content": "Hello", "timestamp": "2024-01-01T10:00:00"},
                {"role": "agent", "content": "Hi there!", "timestamp": "2024-01-01T10:01:00"}
            ],
            customer_profile={
                "customer_id": "customer_101",
                "customer_name": "John Doe",
                "customer_email": "john@example.com"
            },
            current_intent="sales",
            escalation_level=0
        )
    
    @pytest.fixture
    def handoff_decision(self):
        """Create handoff decision for testing."""
        return HandoffDecision(
            should_handoff=True,
            target_agent="support",
            reason="technical_question",
            urgency="medium",
            requires_human=False
        )
    
    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initialization with enhanced features."""
        assert orchestrator is not None
        assert len(orchestrator.agents) == 4  # sales, support, billing, operations
        assert orchestrator.router is not None
        assert orchestrator.supervisor is not None
        assert isinstance(orchestrator.conversation_contexts, dict)
        assert isinstance(orchestrator.performance_metrics, dict)
        assert isinstance(orchestrator.circuit_breakers, dict)
        assert orchestrator.context_retention_hours == 24
    
    def test_performance_metrics_initialization(self, orchestrator):
        """Test performance metrics are properly initialized."""
        expected_agents = ['router', 'supervisor', 'sales', 'support', 'billing', 'operations']
        
        for agent_name in expected_agents:
            assert agent_name in orchestrator.performance_metrics
            metrics = orchestrator.performance_metrics[agent_name]
            assert isinstance(metrics, AgentPerformanceMetrics)
            assert metrics.agent_name == agent_name
            assert metrics.total_requests == 0
            assert metrics.successful_responses == 0
            assert metrics.failed_responses == 0
    
    def test_circuit_breaker_initialization(self, orchestrator):
        """Test circuit breakers are properly initialized."""
        expected_agents = ['sales', 'support', 'billing', 'operations']
        
        for agent_name in expected_agents:
            assert agent_name in orchestrator.circuit_breakers
            breaker = orchestrator.circuit_breakers[agent_name]
            assert breaker['failure_count'] == 0
            assert breaker['failure_threshold'] == 5
            assert breaker['recovery_timeout'] == 300
            assert breaker['state'] == 'closed'
    
    @pytest.mark.asyncio
    async def test_conversation_context_management(self, orchestrator, agent_context):
        """Test conversation context creation and management."""
        # Mock database operations
        with patch('app.models.thread.Thread') as mock_thread_model:
            mock_thread = Mock()
            mock_thread.id = agent_context.conversation_id
            mock_thread.customer_id = agent_context.customer_id
            mock_thread.customer_name = "John Doe"
            mock_thread.customer_email = "john@example.com"
            mock_thread.status = "open"
            mock_thread.ai_context = {}
            mock_thread_model.query.filter_by.return_value.first.return_value = mock_thread
            
            with patch('app.models.inbox_message.InboxMessage') as mock_message_model:
                mock_message_model.get_thread_messages.return_value = []
                
                # Get conversation context
                context = await orchestrator._get_conversation_context(agent_context)
                
                assert context is not None
                assert context.thread_id == agent_context.conversation_id
                assert isinstance(context.conversation_history, list)
                assert isinstance(context.customer_profile, dict)
                assert context.escalation_level == 0
    
    @pytest.mark.asyncio
    async def test_handoff_evaluation(self, orchestrator, agent_context, conversation_context):
        """Test handoff decision evaluation logic."""
        # Mock routing result with low confidence
        routing_result = AgentResponse(
            content="Routed to sales",
            confidence=0.2,  # Low confidence should trigger handoff
            intent="sales",
            metadata={}
        )
        
        handoff_decision = await orchestrator._evaluate_handoff(
            routing_result, conversation_context, agent_context
        )
        
        assert handoff_decision.should_handoff is True
        assert handoff_decision.reason == 'low_confidence'
        assert handoff_decision.requires_human is True
        assert handoff_decision.urgency == 'high'
    
    @pytest.mark.asyncio
    async def test_handoff_escalation_limit(self, orchestrator, agent_context, conversation_context):
        """Test handoff when escalation limit is reached."""
        # Set high escalation level
        conversation_context.escalation_level = 3
        
        routing_result = AgentResponse(
            content="Routed to sales",
            confidence=0.8,
            intent="sales",
            metadata={}
        )
        
        handoff_decision = await orchestrator._evaluate_handoff(
            routing_result, conversation_context, agent_context
        )
        
        assert handoff_decision.should_handoff is True
        assert handoff_decision.reason == 'escalation_limit_reached'
        assert handoff_decision.requires_human is True
    
    def test_circuit_breaker_state_management(self, orchestrator):
        """Test circuit breaker state transitions."""
        agent_name = "sales"
        
        # Initially closed
        assert not orchestrator._is_circuit_breaker_open(agent_name)
        
        # Simulate failures to open circuit breaker
        for _ in range(5):
            orchestrator._update_circuit_breaker(agent_name, success=False)
        
        # Should be open now
        assert orchestrator._is_circuit_breaker_open(agent_name)
        assert orchestrator.circuit_breakers[agent_name]['state'] == 'open'
        
        # Simulate recovery timeout
        orchestrator.circuit_breakers[agent_name]['last_failure'] = (
            datetime.now() - timedelta(seconds=400)
        ).isoformat()
        
        # Should move to half-open
        assert not orchestrator._is_circuit_breaker_open(agent_name)
        assert orchestrator.circuit_breakers[agent_name]['state'] == 'half_open'
        
        # Successful operation should close it
        orchestrator._update_circuit_breaker(agent_name, success=True)
        assert orchestrator.circuit_breakers[agent_name]['state'] == 'closed'
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_fallback(self, orchestrator, agent_context):
        """Test circuit breaker fallback mechanism."""
        # Open circuit breaker for sales agent
        orchestrator.circuit_breakers['sales']['state'] = 'open'
        
        # Mock operations agent to work
        with patch.object(orchestrator.agents['operations'], 'process') as mock_process:
            mock_process.return_value = AgentResponse(
                content="Fallback response",
                confidence=0.7,
                intent="operations"
            )
            
            response = await orchestrator._handle_circuit_breaker_fallback(
                "test message", agent_context, "sales"
            )
            
            assert response.content == "Fallback response"
            assert response.metadata['circuit_breaker_fallback'] is True
            assert response.metadata['original_agent'] == "sales"
            assert response.metadata['fallback_agent'] == "operations"
    
    @pytest.mark.asyncio
    async def test_performance_metrics_update(self, orchestrator):
        """Test performance metrics updating."""
        agent_name = "sales"
        initial_metrics = orchestrator.performance_metrics[agent_name]
        
        # Simulate successful processing
        await orchestrator._update_performance_metrics(
            agent_name, processing_time=1.5, confidence=0.8, requires_handoff=False
        )
        
        metrics = orchestrator.performance_metrics[agent_name]
        assert metrics.total_requests == 1
        assert metrics.successful_responses == 1
        assert metrics.failed_responses == 0
        assert metrics.average_response_time == 1.5
        assert len(metrics.confidence_scores) == 1
        assert metrics.confidence_scores[0] == 0.8
        assert metrics.handoff_rate == 0.0
    
    @pytest.mark.asyncio
    async def test_performance_metrics_with_handoff(self, orchestrator):
        """Test performance metrics with handoff."""
        agent_name = "support"
        
        # Simulate processing with handoff
        await orchestrator._update_performance_metrics(
            agent_name, processing_time=2.0, confidence=0.6, requires_handoff=True
        )
        
        metrics = orchestrator.performance_metrics[agent_name]
        assert metrics.total_requests == 1
        assert metrics.handoff_rate == 1.0
        assert hasattr(metrics, 'handoff_count')
        assert getattr(metrics, 'handoff_count') == 1
    
    @pytest.mark.asyncio
    async def test_force_agent_handoff(self, orchestrator, conversation_context):
        """Test forcing agent handoff."""
        conversation_id = "conv_789"
        orchestrator.conversation_contexts[conversation_id] = conversation_context
        
        # Force handoff to support
        result = await orchestrator.force_agent_handoff(
            conversation_id, "support", "manual_override"
        )
        
        assert result is True
        updated_context = orchestrator.conversation_contexts[conversation_id]
        assert updated_context.current_intent == "support"
        assert updated_context.previous_agent == "sales"
        assert updated_context.handoff_reason == "manual_override"
        assert updated_context.escalation_level == 1
    
    @pytest.mark.asyncio
    async def test_reset_conversation_context(self, orchestrator, conversation_context):
        """Test resetting conversation context."""
        conversation_id = "conv_789"
        orchestrator.conversation_contexts[conversation_id] = conversation_context
        
        # Reset context
        result = await orchestrator.reset_conversation_context(conversation_id)
        
        assert result is True
        assert conversation_id not in orchestrator.conversation_contexts
    
    def test_get_conversation_context(self, orchestrator, conversation_context):
        """Test getting conversation context."""
        conversation_id = "conv_789"
        orchestrator.conversation_contexts[conversation_id] = conversation_context
        
        context_dict = orchestrator.get_conversation_context(conversation_id)
        
        assert context_dict is not None
        assert context_dict['thread_id'] == conversation_id
        assert context_dict['current_intent'] == "sales"
        assert context_dict['escalation_level'] == 0
    
    def test_get_agent_health_status(self, orchestrator):
        """Test getting agent health status."""
        # Set up some test conditions
        orchestrator.circuit_breakers['sales']['state'] = 'open'
        orchestrator.circuit_breakers['support']['state'] = 'half_open'
        
        # Add some performance data
        orchestrator.performance_metrics['billing'].total_requests = 10
        orchestrator.performance_metrics['billing'].successful_responses = 7  # 70% success rate
        
        health_status = orchestrator.get_agent_health_status()
        
        assert health_status['sales']['health'] == 'unhealthy'
        assert health_status['support']['health'] == 'recovering'
        assert health_status['billing']['health'] == 'degraded'  # < 80% success rate
        assert health_status['operations']['health'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_get_conversation_analytics(self, orchestrator, conversation_context):
        """Test getting conversation analytics."""
        conversation_id = "conv_789"
        
        # Add some AI intent data to conversation history
        conversation_context.conversation_history = [
            {"role": "customer", "content": "Hello", "ai_intent": "sales"},
            {"role": "agent", "content": "Hi!", "ai_intent": "sales"},
            {"role": "customer", "content": "I need help", "ai_intent": "support"},
            {"role": "agent", "content": "Sure!", "ai_intent": "support"}
        ]
        conversation_context.escalation_level = 1
        
        orchestrator.conversation_contexts[conversation_id] = conversation_context
        
        analytics = await orchestrator.get_conversation_analytics(conversation_id)
        
        assert analytics is not None
        assert analytics['conversation_id'] == conversation_id
        assert analytics['message_count'] == 4
        assert analytics['agent_switches'] == 1  # sales -> support
        assert set(analytics['agents_used']) == {'sales', 'support'}
        assert analytics['escalation_level'] == 1
    
    def test_get_orchestrator_metrics(self, orchestrator, conversation_context):
        """Test getting orchestrator-level metrics."""
        # Add some test data
        orchestrator.conversation_contexts["conv1"] = conversation_context
        orchestrator.conversation_contexts["conv2"] = conversation_context
        orchestrator.circuit_breakers['sales']['state'] = 'open'
        
        metrics = orchestrator.get_orchestrator_metrics()
        
        assert metrics['total_conversation_contexts'] == 2
        assert metrics['active_contexts'] <= 2
        assert metrics['circuit_breaker_stats']['open'] == 1
        assert metrics['circuit_breaker_stats']['closed'] == 3  # support, billing, operations
        assert metrics['agents_count'] == 4
        assert metrics['context_retention_hours'] == 24
    
    @pytest.mark.asyncio
    async def test_bulk_reset_contexts(self, orchestrator):
        """Test bulk resetting conversation contexts."""
        # Add test contexts
        context1 = ConversationContext(thread_id="conv1")
        context1.customer_profile = {"tenant_id": "tenant1"}
        
        context2 = ConversationContext(thread_id="conv2")
        context2.customer_profile = {"tenant_id": "tenant2"}
        
        orchestrator.conversation_contexts["conv1"] = context1
        orchestrator.conversation_contexts["conv2"] = context2
        
        # Reset all contexts for tenant1
        reset_count = await orchestrator.bulk_reset_contexts("tenant1")
        
        assert reset_count == 1
        assert "conv1" not in orchestrator.conversation_contexts
        assert "conv2" in orchestrator.conversation_contexts
    
    @pytest.mark.asyncio
    async def test_context_expiration(self, orchestrator):
        """Test conversation context expiration."""
        # Create expired context
        expired_context = ConversationContext(
            thread_id="expired_conv",
            last_updated=(datetime.now() - timedelta(hours=25)).isoformat()
        )
        
        # Create fresh context
        fresh_context = ConversationContext(
            thread_id="fresh_conv",
            last_updated=datetime.now().isoformat()
        )
        
        orchestrator.conversation_contexts["expired_conv"] = expired_context
        orchestrator.conversation_contexts["fresh_conv"] = fresh_context
        
        # Clean up expired contexts
        cleaned_count = await orchestrator.cleanup_expired_contexts()
        
        assert cleaned_count == 1
        assert "expired_conv" not in orchestrator.conversation_contexts
        assert "fresh_conv" in orchestrator.conversation_contexts
    
    @pytest.mark.asyncio
    async def test_enhanced_routing_with_context(self, orchestrator, agent_context, conversation_context):
        """Test enhanced routing that includes conversation context."""
        with patch.object(orchestrator.router, 'process') as mock_router:
            mock_router.return_value = AgentResponse(
                content="Routed to sales",
                confidence=0.8,
                intent="sales",
                metadata={"routing": "success"}
            )
            
            result = await orchestrator._enhanced_routing(
                "test message", agent_context, conversation_context
            )
            
            # Verify router was called with enhanced context
            mock_router.assert_called_once()
            call_args = mock_router.call_args
            enhanced_context = call_args[0][1]  # Second argument is context
            
            assert 'conversation_history' in enhanced_context.metadata
            assert 'customer_profile' in enhanced_context.metadata
            assert 'previous_agent' in enhanced_context.metadata
            assert enhanced_context.metadata['previous_agent'] == "sales"
    
    @pytest.mark.asyncio
    async def test_complete_orchestration_flow(self, orchestrator, agent_context):
        """Test complete orchestration flow with all components."""
        message = "I need help with pricing"
        
        # Mock all the components
        with patch.object(orchestrator.supervisor, 'filter_content') as mock_filter:
            mock_filter.return_value = Mock(
                is_safe=True,
                filtered_content=message,
                violations=[],
                confidence=0.9
            )
            
            with patch.object(orchestrator.router, 'process') as mock_router:
                mock_router.return_value = AgentResponse(
                    content="Routed to sales",
                    confidence=0.8,
                    intent="sales",
                    metadata={"routing": "success"}
                )
                
                with patch.object(orchestrator.agents['sales'], 'process') as mock_sales:
                    mock_sales.return_value = AgentResponse(
                        content="Here's our pricing information...",
                        confidence=0.9,
                        intent="sales",
                        metadata={"agent": "sales"}
                    )
                    
                    with patch.object(orchestrator.supervisor, 'validate_response') as mock_validate:
                        mock_validate.return_value = AgentResponse(
                            content="Here's our pricing information...",
                            confidence=0.9,
                            intent="sales",
                            metadata={"validated": True}
                        )
                        
                        # Process the message
                        response = await orchestrator.process_message(message, agent_context)
                        
                        # Verify the complete flow
                        assert response.content == "Here's our pricing information..."
                        assert response.intent == "sales"
                        assert response.confidence > 0.7
                        assert 'orchestrator_version' in response.metadata
                        
                        # Verify all components were called
                        mock_filter.assert_called_once()
                        mock_router.assert_called_once()
                        mock_sales.assert_called_once()
                        mock_validate.assert_called_once()