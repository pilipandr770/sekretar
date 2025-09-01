"""Comprehensive tests for Specialized AI Agents with real business scenarios."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from app.secretary.agents.base_agent import AgentContext, AgentResponse
from app.secretary.agents.specialized_agents import SalesAgent, SupportAgent, BillingAgent


class TestSalesAgentComprehensive:
    """Comprehensive test cases for SalesAgent with real lead qualification scenarios."""
    
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

    # Lead Qualification Tests
    @pytest.mark.asyncio
    async def test_sales_agent_high_qualification_enterprise_inquiry(self, sales_agent, context):
        """Test sales agent handling high qualification enterprise inquiry."""
        message = "We're a 500-employee company looking to implement your AI Secretary solution across our organization. We need pricing for enterprise features, integration with Salesforce, and a demo next week. Our budget is around $50k annually."
        
        with patch.object(sales_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "intent_type": "pricing",
                    "qualification_level": "high",
                    "urgency": "medium",
                    "budget_indicators": ["explicit_budget"],
                    "decision_stage": "consideration",
                    "pain_points": ["organization-wide implementation", "integration needs"],
                    "buying_signals": ["specific timeline", "budget mentioned", "demo request"],
                    "qualification_questions": ["What's your current solution?", "Who else is involved in the decision?"],
                    "confidence": 0.95,
                    "requires_human": True,
                    "suggested_next_steps": ["schedule_demo", "connect_sales_rep", "prepare_enterprise_proposal"]
                }),
                "Thank you for your interest in our AI Secretary platform! Based on your requirements for a 500-employee organization with Salesforce integration, I can see this is a significant enterprise implementation. Given your timeline and budget considerations, I'd like to connect you immediately with our Enterprise Sales team who can provide detailed pricing, arrange a comprehensive demo, and discuss integration specifics. They'll be able to address your $50k budget and ensure we meet your next week demo timeline."
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [
                    {
                        'content_preview': 'Enterprise pricing starts at $45k annually for 500+ employees with Salesforce integration...',
                        'citations': {'title': 'Enterprise Pricing Guide', 'url': 'https://example.com/enterprise-pricing'}
                    }
                ]
                
                response = await sales_agent.process(message, context)
                
                assert response.intent == 'sales'
                assert response.confidence >= 0.9
                assert response.requires_handoff is True  # High qualification requires human
                assert response.metadata['should_create_lead'] is True
                assert response.metadata['qualification_level'] == 'high'
                assert 'connect_sales_rep' in response.suggested_actions
                assert 'schedule_demo' in response.suggested_actions
                assert 'enterprise' in response.content.lower()

    @pytest.mark.asyncio
    async def test_sales_agent_medium_qualification_pricing_inquiry(self, sales_agent, context):
        """Test sales agent handling medium qualification pricing inquiry."""
        message = "Hi, I'm evaluating different AI assistant solutions for our small business. Can you tell me about your pricing plans and what features are included? We're comparing a few options."
        
        with patch.object(sales_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "intent_type": "comparison",
                    "qualification_level": "medium",
                    "urgency": "low",
                    "budget_indicators": ["cost_conscious"],
                    "decision_stage": "consideration",
                    "pain_points": ["solution evaluation", "feature comparison"],
                    "buying_signals": ["comparing options", "evaluating solutions"],
                    "qualification_questions": ["What's your current solution?", "What's your timeline?", "What features are most important?"],
                    "confidence": 0.8,
                    "requires_human": False,
                    "suggested_next_steps": ["provide_pricing", "qualify_further", "send_comparison_guide"]
                }),
                "I'd be happy to help you evaluate our AI Secretary solution! For small businesses, we offer several pricing tiers:\n\n- Starter Plan: $29/month (up to 5 users)\n- Professional Plan: $79/month (up to 25 users)\n- Business Plan: $149/month (up to 100 users)\n\nKey features include multi-channel communication, CRM integration, and AI-powered responses. Since you're comparing options, I can send you a detailed comparison guide. What specific features are most important for your business needs?"
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [
                    {
                        'content_preview': 'Small business pricing: Starter $29/month, Professional $79/month...',
                        'citations': {'title': 'Small Business Pricing', 'url': 'https://example.com/pricing'}
                    }
                ]
                
                response = await sales_agent.process(message, context)
                
                assert response.intent == 'sales'
                assert response.confidence >= 0.7
                assert response.requires_handoff is False  # Medium qualification can be handled by AI
                assert response.metadata['should_create_lead'] is True
                assert response.metadata['qualification_level'] == 'medium'
                assert 'send_pricing' in response.suggested_actions
                assert 'qualify_further' in response.suggested_actions
                assert '$29' in response.content or 'pricing' in response.content.lower()

    def test_sales_agent_should_create_lead_logic(self, sales_agent, context):
        """Test lead creation decision logic."""
        # High qualification should create lead
        analysis_high = {'qualification_level': 'high', 'intent_type': 'general_inquiry'}
        assert sales_agent._should_create_lead(analysis_high, context) is True
        
        # Medium qualification should create lead
        analysis_medium = {'qualification_level': 'medium', 'intent_type': 'general_inquiry'}
        assert sales_agent._should_create_lead(analysis_medium, context) is True
        
        # Pricing intent should create lead regardless of qualification
        analysis_pricing = {'qualification_level': 'low', 'intent_type': 'pricing'}
        assert sales_agent._should_create_lead(analysis_pricing, context) is True
        
        # Demo intent should create lead
        analysis_demo = {'qualification_level': 'low', 'intent_type': 'demo'}
        assert sales_agent._should_create_lead(analysis_demo, context) is True
        
        # Trial intent should create lead
        analysis_trial = {'qualification_level': 'low', 'intent_type': 'trial'}
        assert sales_agent._should_create_lead(analysis_trial, context) is True
        
        # Purchase intent should create lead
        analysis_purchase = {'qualification_level': 'low', 'intent_type': 'purchase'}
        assert sales_agent._should_create_lead(analysis_purchase, context) is True
        
        # Low qualification general inquiry should not create lead
        analysis_low = {'qualification_level': 'low', 'intent_type': 'general_inquiry'}
        assert sales_agent._should_create_lead(analysis_low, context) is False
c
lass TestSupportAgentComprehensive:
    """Comprehensive test cases for SupportAgent with real issue resolution scenarios."""
    
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

    # Issue Resolution Tests
    @pytest.mark.asyncio
    async def test_support_agent_critical_system_outage(self, support_agent, context):
        """Test support agent handling critical system outage."""
        message = "CRITICAL: Our entire AI Secretary system is down! None of our team can access the platform, customers can't reach us, and we're losing business. This started 2 hours ago and we need immediate help!"
        
        with patch.object(support_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "category": "technical",
                    "severity": "critical",
                    "urgency": "high",
                    "issue_type": "system_outage",
                    "affected_features": ["platform_access", "customer_communication", "team_access"],
                    "error_indicators": ["system down", "no access", "platform unavailable"],
                    "troubleshooting_steps": ["check_status_page", "verify_internet_connection", "clear_browser_cache"],
                    "requires_human": True,
                    "confidence": 0.95,
                    "estimated_resolution_time": "immediate"
                }),
                "I understand this is a critical system outage affecting your entire operation. This requires immediate escalation to our technical team. I'm creating a Priority 1 incident ticket and our on-call engineers will be notified immediately.\n\nImmediate steps:\n1. I've escalated this as a critical incident\n2. Our technical team will contact you within 15 minutes\n3. Please check our status page at status.example.com for real-time updates\n4. We'll provide updates every 30 minutes until resolved\n\nIncident ID: INC-2024-001234. You'll receive a call from our senior engineer shortly."
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [
                    {
                        'content_preview': 'Critical incident response: Immediate escalation, 15-minute response time...',
                        'citations': {'title': 'Critical Incident Procedures', 'url': 'https://example.com/critical-incidents'}
                    }
                ]
                
                response = await support_agent.process(message, context)
                
                assert response.intent == 'support'
                assert response.confidence >= 0.9
                assert response.requires_handoff is True
                assert response.metadata['severity'] == 'critical'
                assert response.metadata['category'] == 'technical'
                assert 'escalate_to_human' in response.suggested_actions
                assert 'priority_response' in response.suggested_actions
                assert 'critical' in response.content.lower() or 'immediate' in response.content.lower()

    @pytest.mark.asyncio
    async def test_support_agent_login_authentication_issue(self, support_agent, context):
        """Test support agent handling login/authentication issues."""
        message = "I can't log into my account. I keep getting 'Invalid credentials' error even though I'm using the correct password. I tried resetting my password twice but still can't get in. This is blocking my work."
        
        with patch.object(support_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "category": "account",
                    "severity": "high",
                    "urgency": "high",
                    "issue_type": "authentication_failure",
                    "affected_features": ["login", "account_access"],
                    "error_indicators": ["invalid credentials", "password reset failed"],
                    "troubleshooting_steps": ["clear_browser_cache", "try_incognito_mode", "check_caps_lock", "verify_email_address"],
                    "requires_human": False,
                    "confidence": 0.88,
                    "estimated_resolution_time": "hours"
                }),
                "I understand how frustrating login issues can be, especially when they're blocking your work. Let's troubleshoot this step by step:\n\n1. **Clear your browser cache and cookies** - Old cached data can cause authentication issues\n2. **Try logging in using an incognito/private browser window** - This eliminates browser-related issues\n3. **Verify you're using the correct email address** - Sometimes similar email addresses get confused\n4. **Check if Caps Lock is on** - Passwords are case-sensitive\n5. **Try a different browser** - Sometimes browser-specific issues occur\n\nIf these steps don't resolve the issue, I'll escalate this to our account team who can check your account status directly. Please try these steps and let me know the results."
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [
                    {
                        'content_preview': 'Login troubleshooting: Clear cache, try incognito mode, verify credentials...',
                        'citations': {'title': 'Login Troubleshooting Guide', 'url': 'https://example.com/login-help'}
                    }
                ]
                
                response = await support_agent.process(message, context)
                
                assert response.intent == 'support'
                assert response.confidence >= 0.8
                assert response.metadata['severity'] == 'high'
                assert response.metadata['category'] == 'account'
                assert 'verify_account_status' in response.suggested_actions
                assert 'cache' in response.content.lower() or 'incognito' in response.content.lower()

    def test_support_agent_fallback_analysis_severity_detection(self, support_agent):
        """Test support agent fallback analysis for severity detection."""
        # Critical severity keywords
        message_critical = "URGENT EMERGENCY: System is completely down and broken, we have a critical outage"
        analysis = support_agent._fallback_support_analysis(message_critical)
        assert analysis['severity'] == 'critical'
        assert analysis['requires_human'] is True
        assert analysis['estimated_resolution_time'] == 'immediate'
        
        # High severity keywords
        message_high = "This is important and blocking our work, we cannot continue"
        analysis = support_agent._fallback_support_analysis(message_high)
        assert analysis['severity'] == 'high'
        assert analysis['requires_human'] is True
        
        # Medium severity keywords
        message_medium = "We have an issue with the system that's causing problems"
        analysis = support_agent._fallback_support_analysis(message_medium)
        assert analysis['severity'] == 'medium'
        
        # Low severity keywords
        message_low = "I have a question about how to use this feature"
        analysis = support_agent._fallback_support_analysis(message_low)
        assert analysis['severity'] == 'low'
        assert analysis['category'] == 'how_to'


class TestBillingAgentComprehensive:
    """Comprehensive test cases for BillingAgent with real payment query scenarios."""
    
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

    # Payment Query Tests
    @pytest.mark.asyncio
    async def test_billing_agent_payment_failure_dispute(self, billing_agent, context):
        """Test billing agent handling payment failure and dispute."""
        message = "My credit card was charged $299 yesterday but my account shows the payment failed. Now I'm being charged a late fee and my service is suspended. I need this resolved immediately as this is affecting our business operations."
        
        with patch.object(billing_agent, '_call_openai') as mock_openai:
            mock_openai.side_effect = [
                json.dumps({
                    "category": "payment_issue",
                    "urgency": "high",
                    "contains_sensitive_data": True,
                    "account_access_required": True,
                    "issue_type": "payment_failure_dispute",
                    "potential_solutions": ["verify_payment_status", "reverse_late_fee", "restore_service"],
                    "requires_human": True,
                    "confidence": 0.92,
                    "escalation_reason": "payment dispute with service suspension"
                }),
                "I understand how concerning this payment issue must be, especially with your service suspended. Payment discrepancies combined with service interruptions require immediate attention from our billing specialists.\n\n**Immediate Actions:**\n1. I'm escalating this as a priority billing issue\n2. Our billing team will investigate the payment status discrepancy\n3. We'll review the late fee application\n4. Service restoration will be prioritized once payment status is verified\n\nFor security reasons, I cannot access your specific payment details, but our billing team will contact you within 30 minutes to resolve this. Please have your account information and payment confirmation ready.\n\nTicket ID: BILL-PAY-2024-9876"
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [
                    {
                        'content_preview': 'Payment dispute resolution: Verify payment status, investigate discrepancies...',
                        'citations': {'title': 'Payment Dispute Procedures', 'url': 'https://example.com/payment-disputes'}
                    }
                ]
                
                response = await billing_agent.process(message, context)
                
                assert response.intent == 'billing'
                assert response.confidence >= 0.9
                assert response.requires_handoff is True
                assert response.metadata['category'] == 'payment_issue'
                assert response.metadata['sensitive_data'] is True
                assert 'escalate_to_billing_team' in response.suggested_actions
                assert 'check_payment_status' in response.suggested_actions
                assert 'payment' in response.content.lower() or 'billing' in response.content.lower()

    def test_billing_agent_fallback_analysis_category_detection(self, billing_agent):
        """Test billing agent fallback analysis for category detection."""
        # Payment issue
        message_payment = "My payment failed and I was charged twice urgently need help"
        analysis = billing_agent._fallback_billing_analysis(message_payment)
        assert analysis['category'] == 'payment_issue'
        assert analysis['urgency'] == 'high'
        assert analysis['requires_human'] is True
        
        # Subscription inquiry
        message_subscription = "I want to upgrade my plan and change my subscription"
        analysis = billing_agent._fallback_billing_analysis(message_subscription)
        assert analysis['category'] == 'subscription'
        assert analysis['account_access_required'] is True
        
        # Invoice request
        message_invoice = "Can I get my billing statement and invoice for last month"
        analysis = billing_agent._fallback_billing_analysis(message_invoice)
        assert analysis['category'] == 'invoice'
        assert analysis['account_access_required'] is True
        
        # Refund request
        message_refund = "I want to cancel and get my money back with a refund"
        analysis = billing_agent._fallback_billing_analysis(message_refund)
        assert analysis['category'] == 'refund'
        assert analysis['requires_human'] is True


# Test configuration and fixtures
@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment for specialized agent tests."""
    import os
    os.environ['OPENAI_API_KEY'] = 'test-key-for-specialized-agents'
    yield