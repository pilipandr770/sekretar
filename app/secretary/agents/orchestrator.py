"""Agent orchestrator for managing multi-agent AI system."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from app.secretary.agents.base_agent import AgentContext, AgentResponse
from app.secretary.agents.router_agent import RouterAgent
from app.secretary.agents.supervisor_agent import SupervisorAgent
from app.secretary.agents.specialized_agents import (
    SalesAgent, SupportAgent, BillingAgent, OperationsAgent
)


@dataclass
class ConversationContext:
    """Context for ongoing conversations."""
    conversation_id: str
    tenant_id: str
    customer_id: str
    channel_type: str
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    current_agent: Optional[str] = None
    intent_history: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentPerformanceMetrics:
    """Performance metrics for agents."""
    agent_name: str
    total_requests: int = 0
    successful_responses: int = 0
    failed_responses: int = 0
    average_response_time: float = 0.0
    confidence_scores: List[float] = field(default_factory=list)
    handoff_requests: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class HandoffDecision:
    """Decision about agent handoff."""
    should_handoff: bool
    target_agent: Optional[str] = None
    reason: str = ""
    confidence: float = 0.0
    requires_human: bool = False
    urgency: str = "normal"  # low, normal, high, urgent


class AgentOrchestrator:
    """Orchestrates multiple AI agents for handling customer interactions."""
    
    def __init__(self):
        self.logger = logging.getLogger("agent.orchestrator")
        
        # Initialize agents
        self.router = RouterAgent()
        self.supervisor = SupervisorAgent()
        self.agents = {
            'sales': SalesAgent(),
            'support': SupportAgent(),
            'billing': BillingAgent(),
            'operations': OperationsAgent()
        }
        
        # Conversation tracking
        self.conversation_contexts: Dict[str, ConversationContext] = {}
        self.performance_metrics: Dict[str, AgentPerformanceMetrics] = {}
        
        # Configuration
        self.max_conversation_age = timedelta(hours=24)
        self.max_handoff_attempts = 3
        
        # Initialize performance metrics
        for agent_name in self.agents.keys():
            self.performance_metrics[agent_name] = AgentPerformanceMetrics(agent_name=agent_name)
    
    async def process_message(self, message: str, context: AgentContext) -> AgentResponse:
        """Process a message through the agent system."""
        try:
            start_time = datetime.now()
            
            # Update conversation context
            conv_context = self._get_or_create_conversation_context(context)
            conv_context.last_activity = datetime.now()
            conv_context.message_count += 1
            
            # Step 1: Supervisor filtering (input)
            filter_result = await self.supervisor.filter_input(message, context)
            if not filter_result.is_safe:
                return AgentResponse(
                    content=filter_result.response_message,
                    confidence=1.0,
                    intent="safety_violation",
                    requires_handoff=filter_result.requires_human_review,
                    metadata={"filter_result": filter_result.to_dict()}
                )
            
            # Use filtered message
            filtered_message = filter_result.filtered_content
            
            # Step 2: Intent detection and routing
            routing_result = await self.router.detect_intent(filtered_message, context)
            
            # Update conversation context
            conv_context.intent_history.append(routing_result.intent)
            if len(conv_context.intent_history) > 10:  # Keep last 10 intents
                conv_context.intent_history = conv_context.intent_history[-10:]
            
            # Step 3: Determine if handoff is needed
            handoff_decision = await self._evaluate_handoff_need(
                routing_result, conv_context, context
            )
            
            if handoff_decision.requires_human:
                return AgentResponse(
                    content="I'd like to connect you with one of our human agents who can better assist you with this request.",
                    confidence=0.5,
                    intent=routing_result.intent,
                    requires_handoff=True,
                    metadata={
                        "handoff_reason": handoff_decision.reason,
                        "urgency": handoff_decision.urgency
                    }
                )
            
            # Step 4: Route to appropriate agent
            target_agent = handoff_decision.target_agent or routing_result.intent
            if target_agent not in self.agents:
                target_agent = 'operations'  # Default fallback
            
            agent = self.agents[target_agent]
            conv_context.current_agent = target_agent
            
            # Step 5: Generate response
            response = await agent.generate_response(filtered_message, context)
            
            # Step 6: Supervisor validation (output)
            validation_result = await self.supervisor.validate_response(response.content, context)
            if validation_result.metadata and not validation_result.metadata.get('is_safe', True):
                # Use supervisor's filtered response
                response.content = validation_result.content
                response.metadata = response.metadata or {}
                response.metadata["supervisor_intervention"] = True
            
            # Step 7: Update metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            self._update_performance_metrics(target_agent, response, processing_time)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            return AgentResponse(
                content="I apologize, but I'm experiencing technical difficulties. Please try again in a moment.",
                confidence=0.0,
                intent="error",
                requires_handoff=True,
                metadata={"error": str(e)}
            )
    
    def _get_or_create_conversation_context(self, context: AgentContext) -> ConversationContext:
        """Get or create conversation context."""
        conv_id = context.conversation_id
        
        if conv_id not in self.conversation_contexts:
            self.conversation_contexts[conv_id] = ConversationContext(
                conversation_id=conv_id,
                tenant_id=context.tenant_id,
                customer_id=context.customer_id,
                channel_type=context.channel_type
            )
        
        return self.conversation_contexts[conv_id]
    
    async def _evaluate_handoff_need(self, routing_result, conv_context: ConversationContext, 
                                   context: AgentContext) -> HandoffDecision:
        """Evaluate if agent handoff is needed."""
        
        # Check for explicit human requests
        human_keywords = ['human', 'person', 'agent', 'representative', 'manager', 'supervisor']
        if any(keyword in routing_result.message.lower() for keyword in human_keywords):
            return HandoffDecision(
                should_handoff=True,
                requires_human=True,
                reason="Customer explicitly requested human agent",
                confidence=0.9,
                urgency="normal"
            )
        
        # Check for complex issues that need human intervention
        complex_keywords = ['complaint', 'refund', 'cancel', 'legal', 'urgent', 'emergency']
        if any(keyword in routing_result.message.lower() for keyword in complex_keywords):
            return HandoffDecision(
                should_handoff=True,
                requires_human=True,
                reason="Complex issue detected",
                confidence=0.8,
                urgency="high"
            )
        
        # Check conversation length - long conversations might need human touch
        if conv_context.message_count > 10:
            return HandoffDecision(
                should_handoff=True,
                requires_human=True,
                reason="Long conversation detected",
                confidence=0.6,
                urgency="normal"
            )
        
        # Check for repeated failed intents
        if len(conv_context.intent_history) >= 3:
            recent_intents = conv_context.intent_history[-3:]
            if len(set(recent_intents)) == 1 and recent_intents[0] == 'unknown':
                return HandoffDecision(
                    should_handoff=True,
                    requires_human=True,
                    reason="Repeated unknown intents",
                    confidence=0.7,
                    urgency="normal"
                )
        
        # Default: continue with AI
        return HandoffDecision(
            should_handoff=False,
            target_agent=routing_result.intent,
            reason="AI can handle this request",
            confidence=routing_result.confidence
        )
    
    def _update_performance_metrics(self, agent_name: str, response: AgentResponse, 
                                  processing_time: float):
        """Update performance metrics for an agent."""
        if agent_name not in self.performance_metrics:
            self.performance_metrics[agent_name] = AgentPerformanceMetrics(agent_name=agent_name)
        
        metrics = self.performance_metrics[agent_name]
        metrics.total_requests += 1
        
        if response.confidence > 0.5:
            metrics.successful_responses += 1
        else:
            metrics.failed_responses += 1
        
        # Update average response time
        total_time = metrics.average_response_time * (metrics.total_requests - 1) + processing_time
        metrics.average_response_time = total_time / metrics.total_requests
        
        # Track confidence scores
        metrics.confidence_scores.append(response.confidence)
        if len(metrics.confidence_scores) > 100:  # Keep last 100 scores
            metrics.confidence_scores = metrics.confidence_scores[-100:]
        
        if response.requires_handoff:
            metrics.handoff_requests += 1
        
        metrics.last_updated = datetime.now()
    
    def get_performance_metrics(self, agent_name: Optional[str] = None) -> Dict[str, Any]:
        """Get performance metrics for agents."""
        if agent_name:
            if agent_name in self.performance_metrics:
                return self.performance_metrics[agent_name].__dict__
            return {}
        
        return {name: metrics.__dict__ for name, metrics in self.performance_metrics.items()}
    
    def get_conversation_context(self, conversation_id: str) -> Optional[ConversationContext]:
        """Get conversation context by ID."""
        return self.conversation_contexts.get(conversation_id)
    
    def cleanup_expired_contexts(self):
        """Clean up expired conversation contexts."""
        current_time = datetime.now()
        expired_contexts = []
        
        for conv_id, context in self.conversation_contexts.items():
            if current_time - context.last_activity > self.max_conversation_age:
                expired_contexts.append(conv_id)
        
        for conv_id in expired_contexts:
            del self.conversation_contexts[conv_id]
        
        if expired_contexts:
            self.logger.info(f"Cleaned up {len(expired_contexts)} expired conversation contexts")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all agents."""
        health_status = {
            "orchestrator": "healthy",
            "agents": {},
            "conversation_contexts": len(self.conversation_contexts),
            "performance_metrics": {}
        }
        
        # Check router agent
        try:
            await self.router.health_check()
            health_status["agents"]["router"] = "healthy"
        except Exception as e:
            health_status["agents"]["router"] = f"unhealthy: {str(e)}"
        
        # Check supervisor agent
        try:
            await self.supervisor.health_check()
            health_status["agents"]["supervisor"] = "healthy"
        except Exception as e:
            health_status["agents"]["supervisor"] = f"unhealthy: {str(e)}"
        
        # Check specialized agents
        for name, agent in self.agents.items():
            try:
                await agent.health_check()
                health_status["agents"][name] = "healthy"
            except Exception as e:
                health_status["agents"][name] = f"unhealthy: {str(e)}"
        
        # Add performance summary
        for name, metrics in self.performance_metrics.items():
            success_rate = 0
            if metrics.total_requests > 0:
                success_rate = metrics.successful_responses / metrics.total_requests
            
            health_status["performance_metrics"][name] = {
                "total_requests": metrics.total_requests,
                "success_rate": success_rate,
                "average_response_time": metrics.average_response_time,
                "handoff_rate": metrics.handoff_requests / max(metrics.total_requests, 1)
            }
        
        return health_status
    
    def get_agent_capabilities(self) -> Dict[str, Any]:
        """Get capabilities of all agents."""
        return {
            'sales': {
                'description': 'Handles sales inquiries, pricing, and lead qualification',
                'keywords': ['price', 'pricing', 'cost', 'quote', 'demo', 'trial', 'buy', 'purchase'],
                'can_create_leads': True,
                'requires_account_access': False,
                'escalation_triggers': ['high_qualification', 'enterprise_inquiry']
            },
            'support': {
                'description': 'Provides technical support and troubleshooting',
                'keywords': ['help', 'issue', 'problem', 'bug', 'error', 'broken', 'not working'],
                'can_create_leads': False,
                'requires_account_access': False,
                'escalation_triggers': ['critical_severity', 'system_outage']
            },
            'billing': {
                'description': 'Handles billing, payments, and subscription inquiries',
                'keywords': ['billing', 'payment', 'invoice', 'subscription', 'plan', 'upgrade'],
                'can_create_leads': False,
                'requires_account_access': True,
                'escalation_triggers': ['payment_dispute', 'refund_request']
            },
            'operations': {
                'description': 'Provides general business information and operations support',
                'keywords': ['general', 'information', 'hours', 'contact', 'location'],
                'can_create_leads': False,
                'requires_account_access': False,
                'escalation_triggers': ['complex_inquiry']
            }
        }
    
    async def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        return {
            'orchestrator': {
                'status': 'active',
                'agents_count': len(self.agents),
                'conversation_contexts': len(self.conversation_contexts)
            },
            'router': {
                'status': 'active'
            },
            'supervisor': {
                'status': 'active'
            },
            'specialized_agents': {
                'sales': 'active',
                'support': 'active',
                'billing': 'active',
                'operations': 'active'
            }
        }
    
    def get_available_intents(self) -> List[str]:
        """Get list of available intents."""
        return list(self.agents.keys())
    
    async def process_with_specific_agent(self, message: str, context: AgentContext, agent_name: str) -> AgentResponse:
        """Process message with a specific agent, bypassing routing."""
        try:
            # Step 1: Supervisor filtering (input)
            filter_result = await self.supervisor.filter_input(message, context)
            if not filter_result.is_safe:
                return AgentResponse(
                    content=filter_result.response_message or "Content blocked",
                    confidence=1.0,
                    intent="safety_violation",
                    requires_handoff=True,
                    metadata={"filter_result": filter_result.__dict__, "direct_routing": True}
                )
            
            # Use filtered message
            filtered_message = filter_result.filtered_content
            
            # Route to specific agent
            if agent_name not in self.agents:
                agent_name = 'operations'  # Default fallback
            
            agent = self.agents[agent_name]
            
            # Generate response
            response = await agent.generate_response(filtered_message, context)
            
            # Supervisor validation
            validation_result = await self.supervisor.validate_response(response.content, context)
            if validation_result.metadata and not validation_result.metadata.get('is_safe', True):
                response.content = validation_result.content
                response.metadata = response.metadata or {}
                response.metadata["supervisor_intervention"] = True
            
            response.metadata = response.metadata or {}
            response.metadata["direct_routing"] = True
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in direct agent routing: {str(e)}")
            return AgentResponse(
                content="I apologize, but I'm experiencing technical difficulties.",
                confidence=0.0,
                intent="error",
                requires_handoff=True,
                metadata={"error": str(e), "direct_routing": True}
            )