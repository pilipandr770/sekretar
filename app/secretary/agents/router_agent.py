"""Router Agent for intent detection and message routing."""

import json
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from .base_agent import BaseAgent, AgentContext, AgentResponse


@dataclass
class IntentResult:
    """Result of intent detection."""
    category: str
    confidence: float
    language: str
    customer_context: Dict[str, Any]
    routing_metadata: Dict[str, Any]


class RouterAgent(BaseAgent):
    """Agent responsible for detecting intent and routing messages to specialized agents."""
    
    def __init__(self):
        super().__init__("RouterAgent")
        self.intent_categories = {
            'sales': ['quote', 'pricing', 'product', 'demo', 'purchase', 'buy'],
            'support': ['help', 'issue', 'problem', 'bug', 'error', 'technical'],
            'billing': ['invoice', 'payment', 'subscription', 'billing', 'charge', 'refund'],
            'operations': ['general', 'information', 'hours', 'contact', 'location']
        }
        self.supported_languages = ['en', 'de', 'uk', 'es', 'fr']
    
    async def process(self, message: str, context: AgentContext) -> AgentResponse:
        """Process message for intent detection and routing."""
        try:
            # Detect intent and language
            intent_result = await self.detect_intent(message, context)
            
            # Analyze customer context
            customer_context = await self._analyze_customer_context(message, context)
            
            # Create routing response
            response = AgentResponse(
                content=f"Message routed to {intent_result.category} agent",
                confidence=intent_result.confidence,
                intent=intent_result.category,
                metadata={
                    'language': intent_result.language,
                    'customer_context': customer_context,
                    'routing_metadata': intent_result.routing_metadata
                }
            )
            
            self._log_interaction(message, response, context)
            return response
            
        except Exception as e:
            self.logger.error(f"Router agent processing failed: {str(e)}")
            # Fallback to operations agent
            return AgentResponse(
                content="Message routed to operations agent (fallback)",
                confidence=0.5,
                intent='operations',
                metadata={'error': str(e)}
            )
    
    async def detect_intent(self, message: str, context: AgentContext) -> IntentResult:
        """Detect the intent of the message using OpenAI."""
        system_prompt = self._create_intent_detection_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        try:
            response = await self._call_openai(messages, context)
            intent_data = json.loads(response)
            
            return IntentResult(
                category=intent_data.get('category', 'operations'),
                confidence=intent_data.get('confidence', 0.5),
                language=intent_data.get('language', 'en'),
                customer_context=intent_data.get('customer_context', {}),
                routing_metadata=intent_data.get('routing_metadata', {})
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning(f"Failed to parse intent detection response: {str(e)}")
            # Fallback to keyword-based detection
            return self._fallback_intent_detection(message)
    
    def _create_intent_detection_prompt(self) -> str:
        """Create system prompt for intent detection."""
        categories_desc = {
            'sales': 'Sales inquiries, product information, pricing, quotes, demos, purchases',
            'support': 'Technical support, troubleshooting, bug reports, help requests',
            'billing': 'Billing questions, payment issues, invoices, subscriptions, refunds',
            'operations': 'General inquiries, business hours, contact information, other topics'
        }
        
        return f"""You are an intent detection system for a business communication platform.

Analyze the user message and return a JSON response with the following structure:
{{
    "category": "sales|support|billing|operations",
    "confidence": 0.0-1.0,
    "language": "en|de|uk|es|fr|auto",
    "customer_context": {{
        "urgency": "low|medium|high",
        "sentiment": "positive|neutral|negative",
        "complexity": "simple|medium|complex"
    }},
    "routing_metadata": {{
        "keywords": ["list", "of", "relevant", "keywords"],
        "entities": ["extracted", "entities"],
        "priority": "low|medium|high"
    }}
}}

Categories:
{chr(10).join([f"- {cat}: {desc}" for cat, desc in categories_desc.items()])}

Supported languages: {', '.join(self.supported_languages)}

Guidelines:
- Analyze the message content, tone, and context
- Detect the primary language (default to 'en' if uncertain)
- Assess urgency based on language used (urgent words, caps, etc.)
- Extract relevant keywords and entities
- Provide confidence score based on clarity of intent
- Default to 'operations' category if intent is unclear"""
    
    def _fallback_intent_detection(self, message: str) -> IntentResult:
        """Fallback keyword-based intent detection."""
        message_lower = message.lower()
        
        # Calculate scores for each category
        category_scores = {}
        for category, keywords in self.intent_categories.items():
            score = sum(1 for keyword in keywords if keyword in message_lower)
            if score > 0:
                category_scores[category] = score / len(keywords)
        
        # Determine best category
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            confidence = min(category_scores[best_category], 0.8)  # Cap at 0.8 for fallback
        else:
            best_category = 'operations'
            confidence = 0.3
        
        # Simple language detection
        language = self._detect_language_simple(message)
        
        return IntentResult(
            category=best_category,
            confidence=confidence,
            language=language,
            customer_context={
                'urgency': 'medium',
                'sentiment': 'neutral',
                'complexity': 'medium'
            },
            routing_metadata={
                'keywords': [kw for kw in self.intent_categories.get(best_category, []) if kw in message_lower],
                'entities': [],
                'priority': 'medium',
                'fallback_used': True
            }
        )
    
    def _detect_language_simple(self, message: str) -> str:
        """Simple language detection based on common words."""
        language_patterns = {
            'de': ['der', 'die', 'das', 'und', 'ist', 'ich', 'sie', 'haben', 'werden', 'können', 'mit', 'ein', 'eine', 'habe'],
            'uk': ['і', 'в', 'на', 'з', 'що', 'як', 'до', 'від', 'для', 'або', 'я', 'маю', 'про', 'ваш'],
            'es': ['el', 'la', 'que', 'y', 'es', 'en', 'un', 'ser', 'se', 'con'],
            'fr': ['le', 'et', 'à', 'un', 'il', 'être', 'en', 'avoir', 'avec']
        }
        
        message_lower = message.lower()
        language_scores = {}
        
        for lang, patterns in language_patterns.items():
            score = sum(1 for pattern in patterns if f' {pattern} ' in f' {message_lower} ')
            if score > 0:
                language_scores[lang] = score
        
        if language_scores:
            return max(language_scores, key=language_scores.get)
        return 'en'  # Default to English
    
    async def _analyze_customer_context(self, message: str, context: AgentContext) -> Dict[str, Any]:
        """Analyze customer context from message and conversation history."""
        # Basic context analysis
        customer_context = {
            'message_length': len(message),
            'has_questions': '?' in message,
            'has_urgency_indicators': any(word in message.lower() for word in ['urgent', 'asap', 'immediately', 'emergency']),
            'is_greeting': any(word in message.lower() for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']),
            'is_complaint': any(word in message.lower() for word in ['complaint', 'problem', 'issue', 'wrong', 'error'])
        }
        
        # Add context from conversation history if available
        if context.conversation_id:
            # TODO: Implement conversation history lookup
            customer_context['has_conversation_history'] = True
        
        return customer_context
    
    def get_routing_decision(self, intent_result: IntentResult) -> Dict[str, Any]:
        """Get routing decision based on intent result."""
        routing_decision = {
            'target_agent': intent_result.category,
            'confidence': intent_result.confidence,
            'priority': intent_result.routing_metadata.get('priority', 'medium'),
            'language': intent_result.language,
            'requires_human': intent_result.confidence < 0.3,  # Low confidence requires human
            'estimated_complexity': intent_result.customer_context.get('complexity', 'medium')
        }
        
        # Special routing rules
        if intent_result.customer_context.get('urgency') == 'high':
            routing_decision['priority'] = 'high'
            routing_decision['requires_human'] = True
        
        if intent_result.customer_context.get('sentiment') == 'negative':
            routing_decision['priority'] = 'high'
        
        return routing_decision
    
