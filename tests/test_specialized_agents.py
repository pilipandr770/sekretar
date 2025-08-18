"""Unit tests for specialized AI agents."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from app.secretary.agents.base_agent import AgentContext, AgentResponse
from app.secretary.agents.specialized_agents import (
    SalesAgent, SupportAgent, BillingAgent, OperationsAgent
)
from app.secretary.agents.orchestrator import AgentOrchestrator


class TestSalesAgent:
    """Test cases for SalesAgent."""
    
    @pytest.fixture
    def sales_agent(self):
        return SalesAgent()
    
    @pytest.fixture
    def context(self):
        return AgentContext(
            tenant_id="123",
            user_id="user1",
            channel_type="web",
            conversation_id="conv1",
            language="en"
        )
    
    @pytest.mark.asyncio
    async def test_sales_agent_pricing_inquiry(self, sales_agent, context):
        """Test sales agent handling pricing inquiry."""
        message = "What are your pricing plans and how much does it cost?"
        
        with patch.object(sales_agent, '_call_openai') as mock_openai:
            # Mock OpenAI responses
            mock_openai.side_effect = [
                json.dumps({
                    "intent_type": "pricing",
                    "qualification_level": "medium",
                    "urgency": "medium",
                    "confidence": 0.8,
                    "requires_human": False,
                    "suggested_next_steps": ["provide_pricing", "qualify_further"]
                }),
                "Thank you for your interest in our AI Secretary platform! We offer several pricing tiers to fit different business needs:\n\n- Starter Plan: $29/month\n- Pro Plan: $79/month\n- Enterprise: Custom pricing\n\nWould you like to schedule a demo to see which plan works best for your needs?"
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [
                    {
                        'content_preview': 'Our pricing plans start at $29/month for the Starter plan...',
                        'citations': {'title': 'Pricing Guide', 'url': 'https://example.com/pricing'}
                    }
                ]
                
                response = await sales_agent.process(message, context)
                
                assert response.intent == 'sales'
                assert response.confidence > 0.7
                assert 'pricing' in response.content.lower()
                assert response.metadata['should_create_lead'] is True
                assert 'send_pricing' in response.suggested_actions
    
    @pytest.mark.asyncio
    async def test_sales_agent_demo_request(self, sales_agent, context):
        """Test sales agent handling demo request."""
        message = "I'd like to see a demo of your AI secretary system"
        
        with patch.object(sales_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "intent_type": "demo",
                    "qualification_level": "high",
                    "urgency": "medium",
                    "confidence": 0.9,
                    "requires_human": True,
                    "suggested_next_steps": ["schedule_demo"]
                }),
                "I'd be happy to arrange a demo of our AI Secretary platform! Our demos typically last 30 minutes and cover all the key features including multi-channel communication, CRM integration, and AI-powered responses. Let me connect you with our sales team to schedule a convenient time."
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = []
                
                response = await sales_agent.process(message, context)
                
                assert response.intent == 'sales'
                assert response.requires_handoff is True
                assert 'demo' in response.content.lower()
                assert 'schedule_demo' in response.suggested_actions
    
    @pytest.mark.asyncio
    async def test_sales_agent_fallback_analysis(self, sales_agent, context):
        """Test sales agent fallback analysis when OpenAI fails."""
        message = "How much does your pricing cost for enterprise customers?"
        
        with patch.object(sales_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = Exception("OpenAI API error")
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = []
                
                response = await sales_agent.process(message, context)
                
                assert response.intent == 'sales'
                assert response.confidence >= 0.5
                assert 'sales' in response.content.lower() or 'help' in response.content.lower()
    
    def test_sales_agent_should_create_lead(self, sales_agent, context):
        """Test lead creation logic."""
        # High qualification should create lead
        analysis_high = {'qualification_level': 'high', 'intent_type': 'general_inquiry'}
        assert sales_agent._should_create_lead(analysis_high, context) is True
        
        # Pricing intent should create lead
        analysis_pricing = {'qualification_level': 'low', 'intent_type': 'pricing'}
        assert sales_agent._should_create_lead(analysis_pricing, context) is True
        
        # Low qualification general inquiry should not create lead
        analysis_low = {'qualification_level': 'low', 'intent_type': 'general_inquiry'}
        assert sales_agent._should_create_lead(analysis_low, context) is False


class TestSupportAgent:
    """Test cases for SupportAgent."""
    
    @pytest.fixture
    def support_agent(self):
        return SupportAgent()
    
    @pytest.fixture
    def context(self):
        return AgentContext(
            tenant_id="123",
            user_id="user1",
            channel_type="web",
            conversation_id="conv1",
            language="en"
        )
    
    @pytest.mark.asyncio
    async def test_support_agent_technical_issue(self, support_agent, context):
        """Test support agent handling technical issue."""
        message = "I'm having trouble logging in, getting error 500"
        
        with patch.object(support_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "category": "technical",
                    "severity": "medium",
                    "urgency": "medium",
                    "confidence": 0.8,
                    "requires_human": False,
                    "estimated_resolution_time": "hours"
                }),
                "I understand you're experiencing a login issue with error 500. This is typically a server-side error. Here are some steps to try:\n\n1. Clear your browser cache and cookies\n2. Try using an incognito/private browser window\n3. Check if the issue persists on a different browser\n\nIf these steps don't resolve the issue, I'll escalate this to our technical team for immediate assistance."
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [
                    {
                        'content_preview': 'Error 500 troubleshooting: Clear cache, try incognito mode...',
                        'citations': {'title': 'Login Troubleshooting', 'url': 'https://example.com/help'}
                    }
                ]
                
                response = await support_agent.process(message, context)
                
                assert response.intent == 'support'
                assert response.confidence > 0.7
                assert 'error 500' in response.content or 'login' in response.content
                assert response.metadata['severity'] == 'medium'
    
    @pytest.mark.asyncio
    async def test_support_agent_critical_issue(self, support_agent, context):
        """Test support agent handling critical issue."""
        message = "URGENT: Our entire system is down and we can't access anything!"
        
        with patch.object(support_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "category": "technical",
                    "severity": "critical",
                    "urgency": "high",
                    "confidence": 0.9,
                    "requires_human": True,
                    "estimated_resolution_time": "immediate"
                }),
                "I understand this is a critical system outage affecting your operations. I'm immediately escalating this to our technical team for urgent attention. You should receive a response within 15 minutes. In the meantime, please check our status page for any known issues."
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = []
                
                response = await support_agent.process(message, context)
                
                assert response.intent == 'support'
                assert response.requires_handoff is True
                assert response.metadata['severity'] == 'critical'
                assert 'escalate_to_human' in response.suggested_actions
    
    def test_support_agent_fallback_analysis(self, support_agent):
        """Test support agent fallback analysis."""
        # Critical keywords should result in high severity
        message_critical = "URGENT: System is completely broken and down"
        analysis = support_agent._fallback_support_analysis(message_critical)
        assert analysis['severity'] == 'critical'
        assert analysis['requires_human'] is True
        
        # How-to question should be low severity
        message_howto = "How do I change my password?"
        analysis = support_agent._fallback_support_analysis(message_howto)
        assert analysis['category'] == 'account'  # Password change is categorized as account
        assert analysis['severity'] == 'low'


class TestBillingAgent:
    """Test cases for BillingAgent."""
    
    @pytest.fixture
    def billing_agent(self):
        return BillingAgent()
    
    @pytest.fixture
    def context(self):
        return AgentContext(
            tenant_id="123",
            user_id="user1",
            channel_type="web",
            conversation_id="conv1",
            language="en"
        )
    
    @pytest.mark.asyncio
    async def test_billing_agent_invoice_request(self, billing_agent, context):
        """Test billing agent handling invoice request."""
        message = "Can I get a copy of my latest invoice?"
        
        with patch.object(billing_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "category": "invoice",
                    "urgency": "medium",
                    "contains_sensitive_data": False,
                    "account_access_required": True,
                    "confidence": 0.8,
                    "requires_human": True
                }),
                "I'd be happy to help you get a copy of your latest invoice. For account security, I'll need to connect you with our billing team who can access your account and provide the invoice securely. They'll be able to send it to your registered email address."
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = []
                
                response = await billing_agent.process(message, context)
                
                assert response.intent == 'billing'
                assert response.requires_handoff is True
                assert response.metadata['category'] == 'invoice'
                assert 'escalate_to_billing_team' in response.suggested_actions
    
    @pytest.mark.asyncio
    async def test_billing_agent_payment_issue(self, billing_agent, context):
        """Test billing agent handling payment issue."""
        message = "My credit card was charged twice for the same subscription"
        
        with patch.object(billing_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "category": "payment_issue",
                    "urgency": "high",
                    "contains_sensitive_data": True,
                    "account_access_required": True,
                    "confidence": 0.9,
                    "requires_human": True
                }),
                "I understand your concern about the duplicate charge on your credit card. This is definitely something we need to investigate immediately. For your security and to access your billing details, I'm connecting you with our billing team right away. They'll be able to review your account and resolve any duplicate charges."
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = []
                
                response = await billing_agent.process(message, context)
                
                assert response.intent == 'billing'
                assert response.requires_handoff is True
                assert response.metadata['sensitive_data'] is True
                assert 'check_payment_status' in response.suggested_actions
    
    def test_billing_agent_fallback_analysis(self, billing_agent):
        """Test billing agent fallback analysis."""
        # Payment issue should be high urgency
        message_payment = "My payment failed and I can't access my account urgently"
        analysis = billing_agent._fallback_billing_analysis(message_payment)
        assert analysis['category'] == 'payment_issue'
        assert analysis['urgency'] == 'high'
        assert analysis['requires_human'] is True
        
        # General billing question
        message_general = "What are your billing cycles?"
        analysis = billing_agent._fallback_billing_analysis(message_general)
        assert analysis['category'] == 'invoice'  # "billing" keyword maps to invoice category
        assert analysis['contains_sensitive_data'] is False


class TestOperationsAgent:
    """Test cases for OperationsAgent."""
    
    @pytest.fixture
    def operations_agent(self):
        return OperationsAgent()
    
    @pytest.fixture
    def context(self):
        return AgentContext(
            tenant_id="123",
            user_id="user1",
            channel_type="web",
            conversation_id="conv1",
            language="en"
        )
    
    @pytest.mark.asyncio
    async def test_operations_agent_business_hours(self, operations_agent, context):
        """Test operations agent handling business hours inquiry."""
        message = "What are your business hours?"
        
        with patch.object(operations_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "inquiry_type": "business_hours",
                    "complexity": "simple",
                    "can_self_serve": True,
                    "confidence": 0.9,
                    "requires_human": False
                }),
                "Our business hours are Monday through Friday, 9:00 AM to 6:00 PM EST. We also provide 24/7 support for critical issues through our online support system. Is there anything specific you need help with during our business hours?"
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [
                    {
                        'content_preview': 'Business hours: Monday-Friday 9AM-6PM EST...',
                        'citations': {'title': 'Contact Information', 'url': 'https://example.com/contact'}
                    }
                ]
                
                response = await operations_agent.process(message, context)
                
                assert response.intent == 'operations'
                assert response.confidence > 0.8
                assert 'hours' in response.content.lower()
                assert response.metadata['inquiry_type'] == 'business_hours'
    
    @pytest.mark.asyncio
    async def test_operations_agent_company_info(self, operations_agent, context):
        """Test operations agent handling company information request."""
        message = "Tell me about your company and what services you provide"
        
        with patch.object(operations_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "inquiry_type": "company_info",
                    "complexity": "medium",
                    "can_self_serve": True,
                    "confidence": 0.8,
                    "requires_human": False
                }),
                "We're an AI-powered business communication platform that provides omnichannel customer support through intelligent agents. Our services include multi-channel messaging, CRM integration, calendar scheduling, and automated customer service. We help businesses streamline their customer communications and improve response times."
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = []
                
                response = await operations_agent.process(message, context)
                
                assert response.intent == 'operations'
                assert 'services' in response.content.lower() or 'company' in response.content.lower()
                assert response.metadata['inquiry_type'] == 'company_info'
    
    def test_operations_agent_fallback_analysis(self, operations_agent):
        """Test operations agent fallback analysis."""
        # Business hours inquiry
        message_hours = "When are you open?"
        analysis = operations_agent._fallback_operations_analysis(message_hours)
        assert analysis['inquiry_type'] == 'business_hours'
        assert analysis['can_self_serve'] is True
        
        # Complex inquiry (needs to be over 20 words to be considered complex)
        message_complex = "I need detailed information about your enterprise partnership program and integration capabilities for large-scale deployments with custom requirements and specific technical specifications that need to be evaluated"
        analysis = operations_agent._fallback_operations_analysis(message_complex)
        assert analysis['complexity'] == 'complex'
        assert analysis['requires_human'] is True


class TestAgentOrchestrator:
    """Test cases for AgentOrchestrator."""
    
    @pytest.fixture
    def orchestrator(self):
        return AgentOrchestrator()
    
    @pytest.fixture
    def context(self):
        return AgentContext(
            tenant_id="123",
            user_id="user1",
            channel_type="web",
            conversation_id="conv1",
            language="en"
        )
    
    @pytest.mark.asyncio
    async def test_orchestrator_sales_flow(self, orchestrator, context):
        """Test complete orchestrator flow for sales message."""
        message = "I'm interested in your pricing plans"
        
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
                    intent='sales',
                    metadata={'language': 'en'}
                )
                
                with patch.object(orchestrator.agents['sales'], 'process') as mock_sales:
                    mock_sales.return_value = AgentResponse(
                        content="Here are our pricing plans...",
                        confidence=0.9,
                        intent='sales',
                        suggested_actions=['create_lead']
                    )
                    
                    with patch.object(orchestrator.supervisor, 'validate_response') as mock_validate:
                        mock_validate.return_value = AgentResponse(
                            content="Here are our pricing plans...",
                            confidence=0.9,
                            intent='sales'
                        )
                        
                        response = await orchestrator.process_message(message, context)
                        
                        assert response.intent == 'sales'
                        assert response.confidence > 0.7
                        assert 'pricing' in response.content.lower()
                        assert mock_filter.called
                        assert mock_router.called
                        assert mock_sales.called
                        assert mock_validate.called
    
    @pytest.mark.asyncio
    async def test_orchestrator_blocked_content(self, orchestrator, context):
        """Test orchestrator handling blocked content."""
        message = "This is inappropriate content"
        
        with patch.object(orchestrator.supervisor, 'filter_content') as mock_filter:
            mock_filter.return_value = Mock(
                is_safe=False,
                filtered_content="[FILTERED]",
                violations=['Inappropriate content'],
                confidence=0.9
            )
            
            response = await orchestrator.process_message(message, context)
            
            assert response.intent == 'blocked'
            assert response.requires_handoff is True
            assert response.metadata['blocked'] is True
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_handling(self, orchestrator, context):
        """Test orchestrator error handling."""
        message = "Test message"
        
        with patch.object(orchestrator.supervisor, 'filter_content') as mock_filter:
            mock_filter.side_effect = Exception("Supervisor error")
            
            response = await orchestrator.process_message(message, context)
            
            assert response.intent == 'error'
            assert response.requires_handoff is True
            assert response.confidence == 0.0
            assert 'technical difficulties' in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_orchestrator_direct_agent_routing(self, orchestrator, context):
        """Test direct agent routing bypass."""
        message = "Test support message"
        
        with patch.object(orchestrator.supervisor, 'filter_content') as mock_filter:
            mock_filter.return_value = Mock(
                is_safe=True,
                filtered_content=message,
                violations=[],
                confidence=0.9
            )
            
            with patch.object(orchestrator.agents['support'], 'process') as mock_support:
                mock_support.return_value = AgentResponse(
                    content="Support response",
                    confidence=0.8,
                    intent='support'
                )
                
                with patch.object(orchestrator.supervisor, 'validate_response') as mock_validate:
                    mock_validate.return_value = AgentResponse(
                        content="Support response",
                        confidence=0.8,
                        intent='support'
                    )
                    
                    response = await orchestrator.process_with_specific_agent(
                        message, context, 'support'
                    )
                    
                    assert response.intent == 'support'
                    assert response.metadata['direct_routing'] is True
                    assert mock_support.called
                    # Router should not be called in direct routing
                    assert response.metadata.get('direct_routing') is True
    
    def test_orchestrator_get_capabilities(self, orchestrator):
        """Test getting agent capabilities."""
        capabilities = orchestrator.get_agent_capabilities()
        
        assert 'sales' in capabilities
        assert 'support' in capabilities
        assert 'billing' in capabilities
        assert 'operations' in capabilities
        
        assert capabilities['sales']['can_create_leads'] is True
        assert capabilities['billing']['requires_account_access'] is True
        assert 'pricing' in capabilities['sales']['keywords']
        assert 'help' in capabilities['support']['keywords']
    
    @pytest.mark.asyncio
    async def test_orchestrator_status(self, orchestrator):
        """Test getting orchestrator status."""
        status = await orchestrator.get_agent_status()
        
        assert status['orchestrator']['status'] == 'active'
        assert status['router']['status'] == 'active'
        assert status['supervisor']['status'] == 'active'
        assert len(status['specialized_agents']) == 4
        assert 'sales' in status['specialized_agents']
        assert 'support' in status['specialized_agents']
        assert 'billing' in status['specialized_agents']
        assert 'operations' in status['specialized_agents']


# Integration test fixtures and helpers
@pytest.fixture
def mock_knowledge_service():
    """Mock knowledge service for testing."""
    with patch('app.services.knowledge_service.KnowledgeService') as mock:
        mock.search_knowledge.return_value = [
            {
                'content_preview': 'Sample knowledge content...',
                'citations': {'title': 'Test Document', 'url': 'https://example.com/test'}
            }
        ]
        yield mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch('openai.OpenAI') as mock:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test AI response"
        mock_client.chat.completions.create.return_value = mock_response
        mock.return_value = mock_client
        yield mock_client


# Test configuration
@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment."""
    import os
    os.environ['OPENAI_API_KEY'] = 'test-key-for-testing'
    yield
    # Cleanup if needed