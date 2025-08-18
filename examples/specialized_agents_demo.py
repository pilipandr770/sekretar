#!/usr/bin/env python3
"""
Demo script showing how the specialized agents work with knowledge base integration.

This script demonstrates:
1. Sales agent handling pricing inquiries with knowledge base integration
2. Support agent providing technical help with knowledge search
3. Billing agent handling account-related questions securely
4. Operations agent providing general business information
5. Agent orchestrator coordinating the complete flow

Run this script to see the agents in action.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.secretary.agents.base_agent import AgentContext
from app.secretary.agents.orchestrator import AgentOrchestrator
from app.secretary.agents.specialized_agents import (
    SalesAgent, SupportAgent, BillingAgent, OperationsAgent
)


async def demo_sales_agent():
    """Demonstrate sales agent capabilities."""
    print("\n" + "="*60)
    print("SALES AGENT DEMO")
    print("="*60)
    
    sales_agent = SalesAgent()
    context = AgentContext(
        tenant_id="demo_tenant",
        user_id="demo_user",
        channel_type="web",
        conversation_id="demo_conv_1",
        language="en"
    )
    
    # Test messages
    messages = [
        "What are your pricing plans?",
        "I'd like to schedule a demo of your AI secretary",
        "How much does the enterprise plan cost?",
        "Can you tell me about your features and pricing?"
    ]
    
    for i, message in enumerate(messages, 1):
        print(f"\n{i}. Customer: {message}")
        try:
            # Mock the OpenAI calls for demo
            import unittest.mock
            with unittest.mock.patch.object(sales_agent, '_call_openai') as mock_openai:
                mock_openai.side_effect = [
                    '{"intent_type": "pricing", "qualification_level": "medium", "confidence": 0.8, "requires_human": false}',
                    f"Thank you for your interest! Based on your inquiry about {message.lower()}, I'd be happy to help you find the right solution for your business needs."
                ]
                
                with unittest.mock.patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                    mock_search.return_value = [
                        {
                            'content_preview': 'Our pricing starts at $29/month for the Starter plan...',
                            'citations': {'title': 'Pricing Guide', 'url': 'https://example.com/pricing'}
                        }
                    ]
                    
                    response = await sales_agent.process(message, context)
                    print(f"   Sales Agent: {response.content}")
                    print(f"   Confidence: {response.confidence:.2f}")
                    print(f"   Actions: {response.suggested_actions}")
                    
        except Exception as e:
            print(f"   Error: {str(e)}")


async def demo_support_agent():
    """Demonstrate support agent capabilities."""
    print("\n" + "="*60)
    print("SUPPORT AGENT DEMO")
    print("="*60)
    
    support_agent = SupportAgent()
    context = AgentContext(
        tenant_id="demo_tenant",
        user_id="demo_user",
        channel_type="web",
        conversation_id="demo_conv_2",
        language="en"
    )
    
    messages = [
        "I'm having trouble logging in",
        "The system is completely down and not working!",
        "How do I reset my password?",
        "Getting error 500 when trying to access my dashboard"
    ]
    
    for i, message in enumerate(messages, 1):
        print(f"\n{i}. Customer: {message}")
        try:
            import unittest.mock
            with unittest.mock.patch.object(support_agent, '_call_openai') as mock_openai:
                severity = "critical" if "down" in message.lower() else "medium"
                mock_openai.side_effect = [
                    f'{{"category": "technical", "severity": "{severity}", "confidence": 0.8, "requires_human": {str(severity == "critical").lower()}}}',
                    f"I understand you're experiencing {message.lower()}. Let me help you resolve this issue with some troubleshooting steps."
                ]
                
                with unittest.mock.patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                    mock_search.return_value = [
                        {
                            'content_preview': 'For login issues, try clearing your browser cache...',
                            'citations': {'title': 'Troubleshooting Guide', 'url': 'https://example.com/help'}
                        }
                    ]
                    
                    response = await support_agent.process(message, context)
                    print(f"   Support Agent: {response.content}")
                    print(f"   Severity: {response.metadata.get('severity', 'unknown')}")
                    print(f"   Requires Handoff: {response.requires_handoff}")
                    
        except Exception as e:
            print(f"   Error: {str(e)}")


async def demo_billing_agent():
    """Demonstrate billing agent capabilities."""
    print("\n" + "="*60)
    print("BILLING AGENT DEMO")
    print("="*60)
    
    billing_agent = BillingAgent()
    context = AgentContext(
        tenant_id="demo_tenant",
        user_id="demo_user",
        channel_type="web",
        conversation_id="demo_conv_3",
        language="en"
    )
    
    messages = [
        "Can I get a copy of my latest invoice?",
        "My credit card was charged twice",
        "What are your billing cycles?",
        "I want to cancel my subscription"
    ]
    
    for i, message in enumerate(messages, 1):
        print(f"\n{i}. Customer: {message}")
        try:
            import unittest.mock
            with unittest.mock.patch.object(billing_agent, '_call_openai') as mock_openai:
                sensitive = "card" in message.lower() or "charged" in message.lower()
                mock_openai.side_effect = [
                    f'{{"category": "billing", "contains_sensitive_data": {str(sensitive).lower()}, "confidence": 0.8, "requires_human": {str(sensitive).lower()}}}',
                    f"I understand your billing concern. For account security and to access your specific billing information, let me connect you with our billing team."
                ]
                
                with unittest.mock.patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                    mock_search.return_value = []
                    
                    response = await billing_agent.process(message, context)
                    print(f"   Billing Agent: {response.content}")
                    print(f"   Sensitive Data: {response.metadata.get('sensitive_data', False)}")
                    print(f"   Requires Handoff: {response.requires_handoff}")
                    
        except Exception as e:
            print(f"   Error: {str(e)}")


async def demo_operations_agent():
    """Demonstrate operations agent capabilities."""
    print("\n" + "="*60)
    print("OPERATIONS AGENT DEMO")
    print("="*60)
    
    operations_agent = OperationsAgent()
    context = AgentContext(
        tenant_id="demo_tenant",
        user_id="demo_user",
        channel_type="web",
        conversation_id="demo_conv_4",
        language="en"
    )
    
    messages = [
        "What are your business hours?",
        "Tell me about your company",
        "How can I contact you?",
        "What services do you provide?"
    ]
    
    for i, message in enumerate(messages, 1):
        print(f"\n{i}. Customer: {message}")
        try:
            import unittest.mock
            with unittest.mock.patch.object(operations_agent, '_call_openai') as mock_openai:
                mock_openai.side_effect = [
                    '{"inquiry_type": "business_hours", "can_self_serve": true, "confidence": 0.9, "requires_human": false}',
                    f"Thank you for your question about {message.lower()}. I'm happy to provide you with that information."
                ]
                
                with unittest.mock.patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                    mock_search.return_value = [
                        {
                            'content_preview': 'Our business hours are Monday-Friday 9AM-6PM EST...',
                            'citations': {'title': 'Contact Information', 'url': 'https://example.com/contact'}
                        }
                    ]
                    
                    response = await operations_agent.process(message, context)
                    print(f"   Operations Agent: {response.content}")
                    print(f"   Inquiry Type: {response.metadata.get('inquiry_type', 'unknown')}")
                    print(f"   Self-Service: {response.metadata.get('operations_analysis', {}).get('can_self_serve', 'unknown')}")
                    
        except Exception as e:
            print(f"   Error: {str(e)}")


async def demo_orchestrator():
    """Demonstrate the complete orchestrator flow."""
    print("\n" + "="*60)
    print("AGENT ORCHESTRATOR DEMO")
    print("="*60)
    
    orchestrator = AgentOrchestrator()
    context = AgentContext(
        tenant_id="demo_tenant",
        user_id="demo_user",
        channel_type="web",
        conversation_id="demo_conv_5",
        language="en"
    )
    
    messages = [
        "I'm interested in your pricing plans",
        "I need help with a technical issue",
        "Can you send me my latest invoice?",
        "What are your business hours?"
    ]
    
    print("\nDemonstrating complete message processing flow:")
    print("1. Supervisor filtering (input)")
    print("2. Router intent detection")
    print("3. Specialized agent processing")
    print("4. Supervisor validation (output)")
    
    for i, message in enumerate(messages, 1):
        print(f"\n{i}. Customer: {message}")
        try:
            import unittest.mock
            
            # Mock all the components
            with unittest.mock.patch.object(orchestrator.supervisor, 'filter_content') as mock_filter:
                mock_filter.return_value = unittest.mock.Mock(
                    is_safe=True,
                    filtered_content=message,
                    violations=[],
                    confidence=0.9
                )
                
                with unittest.mock.patch.object(orchestrator.router, 'process') as mock_router:
                    intent = ['sales', 'support', 'billing', 'operations'][i-1]
                    mock_router.return_value = unittest.mock.Mock(
                        content=f"Routed to {intent}",
                        confidence=0.8,
                        intent=intent,
                        metadata={'language': 'en'}
                    )
                    
                    # Mock the specific agent
                    agent = orchestrator.agents[intent]
                    with unittest.mock.patch.object(agent, 'process') as mock_agent:
                        mock_agent.return_value = unittest.mock.Mock(
                            content=f"Response from {intent} agent for: {message}",
                            confidence=0.9,
                            intent=intent,
                            requires_handoff=False,
                            suggested_actions=[f'{intent}_action'],
                            metadata={'agent_type': intent}
                        )
                        
                        with unittest.mock.patch.object(orchestrator.supervisor, 'validate_response') as mock_validate:
                            mock_validate.return_value = unittest.mock.Mock(
                                content=f"Validated response from {intent} agent",
                                confidence=0.9,
                                requires_handoff=False,
                                metadata={'validated': True}
                            )
                            
                            response = await orchestrator.process_message(message, context)
                            print(f"   → Routed to: {response.intent} agent")
                            print(f"   → Response: {response.content}")
                            print(f"   → Confidence: {response.confidence:.2f}")
                            print(f"   → Handoff needed: {response.requires_handoff}")
                            
        except Exception as e:
            print(f"   Error: {str(e)}")


async def demo_agent_capabilities():
    """Show agent capabilities and status."""
    print("\n" + "="*60)
    print("AGENT CAPABILITIES & STATUS")
    print("="*60)
    
    orchestrator = AgentOrchestrator()
    
    print("\nAgent Capabilities:")
    capabilities = orchestrator.get_agent_capabilities()
    for agent_name, caps in capabilities.items():
        print(f"\n{agent_name.upper()} AGENT:")
        print(f"  Description: {caps['description']}")
        print(f"  Keywords: {caps['keywords'][:5]}...")  # Show first 5 keywords
        print(f"  Can create leads: {caps['can_create_leads']}")
        print(f"  Requires account access: {caps['requires_account_access']}")
        print(f"  Escalation triggers: {caps['escalation_triggers']}")
    
    print(f"\nAvailable Intents: {orchestrator.get_available_intents()}")
    
    status = await orchestrator.get_agent_status()
    print(f"\nOrchestrator Status: {status['orchestrator']['status']}")
    print(f"Total Agents: {status['orchestrator']['agents_count']}")


async def main():
    """Run all demos."""
    print("AI SECRETARY SPECIALIZED AGENTS DEMO")
    print("="*60)
    print("This demo shows how the specialized agents work with:")
    print("- Context-aware response generation using OpenAI")
    print("- Knowledge base integration for accurate responses")
    print("- Agent orchestration and coordination")
    print("- Content filtering and validation")
    
    # Set up mock environment
    os.environ['OPENAI_API_KEY'] = 'demo-key-for-testing'
    
    try:
        await demo_sales_agent()
        await demo_support_agent()
        await demo_billing_agent()
        await demo_operations_agent()
        await demo_orchestrator()
        await demo_agent_capabilities()
        
        print("\n" + "="*60)
        print("DEMO COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nKey Features Demonstrated:")
        print("✓ Sales agent with lead qualification")
        print("✓ Support agent with severity assessment")
        print("✓ Billing agent with security awareness")
        print("✓ Operations agent with self-service capabilities")
        print("✓ Agent orchestrator with complete flow")
        print("✓ Knowledge base integration")
        print("✓ Content filtering and validation")
        print("✓ Error handling and fallbacks")
        
    except Exception as e:
        print(f"\nDemo failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())