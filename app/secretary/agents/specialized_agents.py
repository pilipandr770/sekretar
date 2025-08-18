"""Specialized AI agents for different business functions."""

import json
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent, AgentContext, AgentResponse
from app.services.knowledge_service import KnowledgeService
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.pipeline import Pipeline


class SalesAgent(BaseAgent):
    """Agent specialized in handling sales inquiries and lead qualification."""
    
    def __init__(self):
        super().__init__("SalesAgent")
        self.sales_keywords = [
            'price', 'pricing', 'cost', 'quote', 'demo', 'trial', 'buy', 'purchase',
            'plan', 'subscription', 'features', 'comparison', 'discount', 'offer'
        ]
        self.qualification_questions = [
            "What specific features are you most interested in?",
            "What's your current solution for this?",
            "What's your timeline for making a decision?",
            "What's your budget range for this solution?",
            "Who else is involved in the decision-making process?"
        ]
    
    async def process(self, message: str, context: AgentContext) -> AgentResponse:
        """Process sales-related messages with lead qualification and knowledge integration."""
        try:
            # Search knowledge base for relevant sales information
            knowledge_results = await self._search_knowledge(message, context)
            
            # Analyze sales intent and qualification level
            sales_analysis = await self._analyze_sales_intent(message, context)
            
            # Generate contextual response
            response_content = await self._generate_sales_response(
                message, context, knowledge_results, sales_analysis
            )
            
            # Determine if lead creation is needed
            should_create_lead = self._should_create_lead(sales_analysis, context)
            
            response = AgentResponse(
                content=response_content,
                confidence=sales_analysis.get('confidence', 0.8),
                intent='sales',
                requires_handoff=sales_analysis.get('requires_human', False),
                suggested_actions=self._get_suggested_actions(sales_analysis, should_create_lead),
                metadata={
                    'sales_analysis': sales_analysis,
                    'knowledge_sources': [r.get('citations') for r in knowledge_results],
                    'should_create_lead': should_create_lead,
                    'qualification_level': sales_analysis.get('qualification_level', 'low')
                }
            )
            
            self._log_interaction(message, response, context)
            return response
            
        except Exception as e:
            self.logger.error(f"Sales agent processing failed: {str(e)}")
            return AgentResponse(
                content="I'd be happy to help with your sales inquiry. Let me connect you with our sales team for detailed information.",
                confidence=0.5,
                intent='sales',
                requires_handoff=True,
                metadata={'error': str(e)}
            )
    
    async def _search_knowledge(self, message: str, context: AgentContext) -> List[Dict[str, Any]]:
        """Search knowledge base for sales-related information."""
        try:
            # Extract key terms for knowledge search
            search_query = self._extract_search_terms(message)
            
            # Search knowledge base
            results = KnowledgeService.search_knowledge(
                tenant_id=int(context.tenant_id),
                query=search_query,
                limit=5,
                min_similarity=0.6
            )
            
            return results
        except Exception as e:
            self.logger.warning(f"Knowledge search failed: {str(e)}")
            return []
    
    async def _analyze_sales_intent(self, message: str, context: AgentContext) -> Dict[str, Any]:
        """Analyze sales intent and qualification level."""
        system_prompt = self._create_sales_analysis_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        try:
            response = await self._call_openai(messages, context)
            analysis = json.loads(response)
            return analysis
        except (json.JSONDecodeError, Exception) as e:
            self.logger.warning(f"Sales analysis failed: {str(e)}")
            return self._fallback_sales_analysis(message)
    
    def _create_sales_analysis_prompt(self) -> str:
        """Create system prompt for sales intent analysis."""
        return f"""You are a sales qualification expert analyzing customer inquiries.

Analyze the message and return a JSON response with this structure:
{{
    "intent_type": "pricing|demo|trial|purchase|comparison|general_inquiry",
    "qualification_level": "low|medium|high",
    "urgency": "low|medium|high",
    "budget_indicators": ["explicit_budget", "price_sensitive", "cost_conscious", "premium_focused"],
    "decision_stage": "awareness|consideration|decision|purchase",
    "pain_points": ["list", "of", "identified", "pain", "points"],
    "buying_signals": ["list", "of", "buying", "signals"],
    "qualification_questions": ["suggested", "questions", "to", "ask"],
    "confidence": 0.0-1.0,
    "requires_human": true/false,
    "suggested_next_steps": ["action1", "action2"]
}}

Qualification levels:
- low: General inquiry, early research phase
- medium: Specific questions, comparing options
- high: Ready to buy, discussing implementation

Look for buying signals like:
- Specific timeline mentions
- Budget discussions
- Implementation questions
- Decision maker involvement
- Urgency indicators

Keywords indicating sales intent: {', '.join(self.sales_keywords)}"""
    
    def _fallback_sales_analysis(self, message: str) -> Dict[str, Any]:
        """Fallback sales analysis using keyword matching."""
        message_lower = message.lower()
        
        # Detect intent type
        intent_scores = {
            'pricing': sum(1 for kw in ['price', 'cost', 'pricing', 'quote'] if kw in message_lower),
            'demo': sum(1 for kw in ['demo', 'demonstration', 'show'] if kw in message_lower),
            'trial': sum(1 for kw in ['trial', 'test', 'try'] if kw in message_lower),
            'purchase': sum(1 for kw in ['buy', 'purchase', 'order'] if kw in message_lower),
            'comparison': sum(1 for kw in ['compare', 'vs', 'versus', 'alternative'] if kw in message_lower)
        }
        
        intent_type = max(intent_scores, key=intent_scores.get) if any(intent_scores.values()) else 'general_inquiry'
        
        # Simple qualification scoring
        qualification_indicators = ['budget', 'timeline', 'decision', 'implement', 'urgent', 'need']
        qualification_score = sum(1 for indicator in qualification_indicators if indicator in message_lower)
        
        if qualification_score >= 3:
            qualification_level = 'high'
        elif qualification_score >= 1:
            qualification_level = 'medium'
        else:
            qualification_level = 'low'
        
        return {
            'intent_type': intent_type,
            'qualification_level': qualification_level,
            'urgency': 'high' if any(word in message_lower for word in ['urgent', 'asap', 'immediately']) else 'medium',
            'confidence': 0.6,
            'requires_human': qualification_level == 'high',
            'suggested_next_steps': ['qualify_further', 'provide_information']
        }
    
    async def _generate_sales_response(self, message: str, context: AgentContext, 
                                     knowledge_results: List[Dict], sales_analysis: Dict) -> str:
        """Generate contextual sales response."""
        # Prepare knowledge context
        knowledge_context = ""
        if knowledge_results:
            knowledge_context = "\n\nRelevant information from our knowledge base:\n"
            for result in knowledge_results[:3]:  # Use top 3 results
                knowledge_context += f"- {result.get('content_preview', '')}\n"
                if result.get('citations'):
                    knowledge_context += f"  Source: {result['citations'].get('title', 'Unknown')}\n"
        
        system_prompt = f"""You are a professional sales representative for our AI Secretary SaaS platform.

Customer message analysis:
- Intent: {sales_analysis.get('intent_type', 'general_inquiry')}
- Qualification level: {sales_analysis.get('qualification_level', 'low')}
- Urgency: {sales_analysis.get('urgency', 'medium')}

{knowledge_context}

Guidelines:
- Be helpful and professional
- Address their specific questions
- Use information from knowledge base when relevant
- Include citations when using knowledge base information
- Ask qualifying questions if appropriate
- Suggest next steps based on their intent
- Keep response concise but informative
- If high qualification level, offer to connect with sales team

Generate a helpful response to their inquiry."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        try:
            return await self._call_openai(messages, context)
        except Exception as e:
            self.logger.error(f"Sales response generation failed: {str(e)}")
            return "Thank you for your interest in our AI Secretary platform. I'd be happy to help you with information about our features and pricing. Could you tell me more about what you're looking for?"
    
    def _extract_search_terms(self, message: str) -> str:
        """Extract key terms for knowledge base search."""
        # Simple extraction - in production, you might use NLP libraries
        words = message.lower().split()
        
        # Filter out common words and focus on business terms
        business_terms = []
        for word in words:
            if len(word) > 3 and word not in ['this', 'that', 'with', 'have', 'will', 'from', 'they', 'been']:
                business_terms.append(word)
        
        return ' '.join(business_terms[:10])  # Limit to 10 terms
    
    def _should_create_lead(self, sales_analysis: Dict, context: AgentContext) -> bool:
        """Determine if a lead should be created."""
        qualification_level = sales_analysis.get('qualification_level', 'low')
        intent_type = sales_analysis.get('intent_type', 'general_inquiry')
        
        # Create lead for medium/high qualification or specific intents
        return (qualification_level in ['medium', 'high'] or 
                intent_type in ['pricing', 'demo', 'trial', 'purchase'])
    
    def _get_suggested_actions(self, sales_analysis: Dict, should_create_lead: bool) -> List[str]:
        """Get suggested actions based on analysis."""
        actions = []
        
        if should_create_lead:
            actions.append('create_lead')
        
        intent_type = sales_analysis.get('intent_type', 'general_inquiry')
        qualification_level = sales_analysis.get('qualification_level', 'low')
        
        if intent_type == 'demo':
            actions.append('schedule_demo')
        elif intent_type == 'pricing':
            actions.append('send_pricing')
        elif intent_type == 'trial':
            actions.append('setup_trial')
        elif qualification_level == 'high':
            actions.append('connect_sales_rep')
        
        if sales_analysis.get('urgency') == 'high':
            actions.append('priority_follow_up')
        
        return actions


class SupportAgent(BaseAgent):
    """Agent specialized in handling technical support and troubleshooting."""
    
    def __init__(self):
        super().__init__("SupportAgent")
        self.support_keywords = [
            'help', 'issue', 'problem', 'bug', 'error', 'broken', 'not working',
            'troubleshoot', 'fix', 'support', 'technical', 'how to', 'tutorial'
        ]
        self.severity_keywords = {
            'critical': ['down', 'outage', 'critical', 'urgent', 'emergency', 'broken'],
            'high': ['important', 'blocking', 'cannot', 'unable', 'stuck'],
            'medium': ['issue', 'problem', 'difficulty', 'trouble'],
            'low': ['question', 'how to', 'help', 'clarification']
        }
    
    async def process(self, message: str, context: AgentContext) -> AgentResponse:
        """Process support requests with knowledge base integration."""
        try:
            # Search knowledge base for solutions
            knowledge_results = await self._search_support_knowledge(message, context)
            
            # Analyze support request
            support_analysis = await self._analyze_support_request(message, context)
            
            # Generate support response
            response_content = await self._generate_support_response(
                message, context, knowledge_results, support_analysis
            )
            
            response = AgentResponse(
                content=response_content,
                confidence=support_analysis.get('confidence', 0.8),
                intent='support',
                requires_handoff=support_analysis.get('requires_human', False),
                suggested_actions=self._get_support_actions(support_analysis),
                metadata={
                    'support_analysis': support_analysis,
                    'knowledge_sources': [r.get('citations') for r in knowledge_results],
                    'severity': support_analysis.get('severity', 'medium'),
                    'category': support_analysis.get('category', 'general')
                }
            )
            
            self._log_interaction(message, response, context)
            return response
            
        except Exception as e:
            self.logger.error(f"Support agent processing failed: {str(e)}")
            return AgentResponse(
                content="I understand you need technical support. Let me connect you with our support team who can help resolve your issue quickly.",
                confidence=0.5,
                intent='support',
                requires_handoff=True,
                metadata={'error': str(e)}
            )
    
    async def _search_support_knowledge(self, message: str, context: AgentContext) -> List[Dict[str, Any]]:
        """Search knowledge base for support solutions."""
        try:
            # Focus search on technical terms and error messages
            search_query = self._extract_technical_terms(message)
            
            results = KnowledgeService.search_knowledge(
                tenant_id=int(context.tenant_id),
                query=search_query,
                limit=5,
                min_similarity=0.7
            )
            
            return results
        except Exception as e:
            self.logger.warning(f"Support knowledge search failed: {str(e)}")
            return []
    
    async def _analyze_support_request(self, message: str, context: AgentContext) -> Dict[str, Any]:
        """Analyze support request for severity and category."""
        system_prompt = self._create_support_analysis_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        try:
            response = await self._call_openai(messages, context)
            analysis = json.loads(response)
            return analysis
        except (json.JSONDecodeError, Exception) as e:
            self.logger.warning(f"Support analysis failed: {str(e)}")
            return self._fallback_support_analysis(message)
    
    def _create_support_analysis_prompt(self) -> str:
        """Create system prompt for support request analysis."""
        return f"""You are a technical support specialist analyzing customer issues.

Analyze the message and return a JSON response:
{{
    "category": "technical|account|billing|feature_request|how_to|bug_report",
    "severity": "low|medium|high|critical",
    "urgency": "low|medium|high",
    "issue_type": "specific_issue_description",
    "affected_features": ["feature1", "feature2"],
    "error_indicators": ["error_messages", "symptoms"],
    "troubleshooting_steps": ["step1", "step2"],
    "requires_human": true/false,
    "confidence": 0.0-1.0,
    "estimated_resolution_time": "immediate|hours|days"
}}

Severity levels:
- critical: System down, data loss, security breach
- high: Major feature broken, blocking work
- medium: Feature issue, workaround available
- low: Minor issue, cosmetic, how-to question

Categories:
- technical: System errors, performance issues
- account: Login, permissions, user management
- billing: Payment, subscription issues
- feature_request: New feature suggestions
- how_to: Usage questions, tutorials
- bug_report: Software defects

Support keywords: {', '.join(self.support_keywords)}"""
    
    def _fallback_support_analysis(self, message: str) -> Dict[str, Any]:
        """Fallback support analysis using keyword matching."""
        message_lower = message.lower()
        
        # Determine severity
        severity = 'low'
        for sev_level, keywords in self.severity_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                severity = sev_level
                break
        
        # Determine category
        if any(word in message_lower for word in ['login', 'password', 'account', 'access']):
            category = 'account'
        elif any(word in message_lower for word in ['payment', 'billing', 'subscription', 'invoice']):
            category = 'billing'
        elif any(word in message_lower for word in ['how to', 'tutorial', 'guide', 'help']):
            category = 'how_to'
        elif any(word in message_lower for word in ['bug', 'error', 'broken', 'not working']):
            category = 'bug_report'
        else:
            category = 'technical'
        
        return {
            'category': category,
            'severity': severity,
            'urgency': 'high' if severity in ['critical', 'high'] else 'medium',
            'confidence': 0.6,
            'requires_human': severity in ['critical', 'high'],
            'estimated_resolution_time': 'immediate' if severity == 'critical' else 'hours'
        }
    
    async def _generate_support_response(self, message: str, context: AgentContext,
                                       knowledge_results: List[Dict], support_analysis: Dict) -> str:
        """Generate contextual support response."""
        # Prepare knowledge context
        knowledge_context = ""
        if knowledge_results:
            knowledge_context = "\n\nRelevant solutions from our knowledge base:\n"
            for result in knowledge_results[:3]:
                knowledge_context += f"- {result.get('content_preview', '')}\n"
                if result.get('citations'):
                    knowledge_context += f"  Source: {result['citations'].get('title', 'Unknown')}\n"
        
        system_prompt = f"""You are a technical support specialist for our AI Secretary SaaS platform.

Issue analysis:
- Category: {support_analysis.get('category', 'technical')}
- Severity: {support_analysis.get('severity', 'medium')}
- Urgency: {support_analysis.get('urgency', 'medium')}

{knowledge_context}

Guidelines:
- Provide clear, step-by-step solutions when possible
- Use information from knowledge base when relevant
- Include citations for knowledge base references
- If critical/high severity, escalate to human support
- Ask clarifying questions if needed
- Provide workarounds when available
- Be empathetic and professional
- Offer additional resources or documentation

Generate a helpful support response."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        try:
            return await self._call_openai(messages, context)
        except Exception as e:
            self.logger.error(f"Support response generation failed: {str(e)}")
            return "I understand you're experiencing an issue. Let me connect you with our technical support team who can provide immediate assistance."
    
    def _extract_technical_terms(self, message: str) -> str:
        """Extract technical terms for knowledge search."""
        # Focus on error messages, feature names, and technical terms
        words = message.split()
        technical_terms = []
        
        for word in words:
            # Keep error codes, feature names, and technical terms
            if (len(word) > 3 and 
                (word.isupper() or  # Error codes
                 any(char.isdigit() for char in word) or  # Version numbers, codes
                 word.lower() in self.support_keywords)):
                technical_terms.append(word)
        
        return ' '.join(technical_terms[:8])
    
    def _get_support_actions(self, support_analysis: Dict) -> List[str]:
        """Get suggested actions for support request."""
        actions = []
        
        severity = support_analysis.get('severity', 'medium')
        category = support_analysis.get('category', 'technical')
        
        if severity in ['critical', 'high']:
            actions.append('escalate_to_human')
            actions.append('priority_response')
        
        if category == 'bug_report':
            actions.append('create_bug_ticket')
        elif category == 'feature_request':
            actions.append('forward_to_product')
        elif category == 'account':
            actions.append('verify_account_status')
        
        actions.append('follow_up_24h')
        return actions


class BillingAgent(BaseAgent):
    """Agent specialized in handling billing and subscription inquiries."""
    
    def __init__(self):
        super().__init__("BillingAgent")
        self.billing_keywords = [
            'billing', 'payment', 'invoice', 'subscription', 'plan', 'upgrade',
            'downgrade', 'cancel', 'refund', 'charge', 'credit', 'trial'
        ]
        self.billing_categories = {
            'payment_issue': ['payment', 'charge', 'declined', 'failed', 'error'],
            'subscription': ['plan', 'upgrade', 'downgrade', 'change', 'subscription'],
            'invoice': ['invoice', 'receipt', 'billing', 'statement'],
            'refund': ['refund', 'cancel', 'cancellation', 'money back'],
            'trial': ['trial', 'free', 'test', 'evaluation']
        }
    
    async def process(self, message: str, context: AgentContext) -> AgentResponse:
        """Process billing inquiries with account integration."""
        try:
            # Search knowledge base for billing information
            knowledge_results = await self._search_billing_knowledge(message, context)
            
            # Analyze billing request
            billing_analysis = await self._analyze_billing_request(message, context)
            
            # Generate billing response
            response_content = await self._generate_billing_response(
                message, context, knowledge_results, billing_analysis
            )
            
            response = AgentResponse(
                content=response_content,
                confidence=billing_analysis.get('confidence', 0.8),
                intent='billing',
                requires_handoff=billing_analysis.get('requires_human', False),
                suggested_actions=self._get_billing_actions(billing_analysis),
                metadata={
                    'billing_analysis': billing_analysis,
                    'knowledge_sources': [r.get('citations') for r in knowledge_results],
                    'category': billing_analysis.get('category', 'general'),
                    'sensitive_data': billing_analysis.get('contains_sensitive_data', False)
                }
            )
            
            self._log_interaction(message, response, context)
            return response
            
        except Exception as e:
            self.logger.error(f"Billing agent processing failed: {str(e)}")
            return AgentResponse(
                content="I'd be happy to help with your billing inquiry. For account security, let me connect you with our billing team who can access your account details.",
                confidence=0.5,
                intent='billing',
                requires_handoff=True,
                metadata={'error': str(e)}
            )
    
    async def _search_billing_knowledge(self, message: str, context: AgentContext) -> List[Dict[str, Any]]:
        """Search knowledge base for billing information."""
        try:
            search_query = self._extract_billing_terms(message)
            
            results = KnowledgeService.search_knowledge(
                tenant_id=int(context.tenant_id),
                query=search_query,
                limit=5,
                min_similarity=0.7
            )
            
            return results
        except Exception as e:
            self.logger.warning(f"Billing knowledge search failed: {str(e)}")
            return []
    
    async def _analyze_billing_request(self, message: str, context: AgentContext) -> Dict[str, Any]:
        """Analyze billing request for category and sensitivity."""
        system_prompt = self._create_billing_analysis_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        try:
            response = await self._call_openai(messages, context)
            analysis = json.loads(response)
            return analysis
        except (json.JSONDecodeError, Exception) as e:
            self.logger.warning(f"Billing analysis failed: {str(e)}")
            return self._fallback_billing_analysis(message)
    
    def _create_billing_analysis_prompt(self) -> str:
        """Create system prompt for billing request analysis."""
        return f"""You are a billing specialist analyzing customer billing inquiries.

Analyze the message and return a JSON response:
{{
    "category": "payment_issue|subscription|invoice|refund|trial|pricing|general",
    "urgency": "low|medium|high",
    "contains_sensitive_data": true/false,
    "account_access_required": true/false,
    "issue_type": "specific_issue_description",
    "potential_solutions": ["solution1", "solution2"],
    "requires_human": true/false,
    "confidence": 0.0-1.0,
    "escalation_reason": "reason_if_escalation_needed"
}}

Categories:
- payment_issue: Failed payments, declined cards, payment errors
- subscription: Plan changes, upgrades, downgrades
- invoice: Invoice requests, billing statements, receipts
- refund: Cancellations, refund requests, disputes
- trial: Trial extensions, trial to paid conversion
- pricing: Plan pricing, feature costs, billing cycles
- general: Other billing questions

Sensitive data indicators:
- Credit card numbers, payment details
- Account balances, specific amounts
- Personal financial information

Always escalate if:
- Sensitive financial data is mentioned
- Account access is required
- Refund/cancellation requests
- Payment disputes

Billing keywords: {', '.join(self.billing_keywords)}"""
    
    def _fallback_billing_analysis(self, message: str) -> Dict[str, Any]:
        """Fallback billing analysis using keyword matching."""
        message_lower = message.lower()
        
        # Determine category
        category = 'general'
        for cat, keywords in self.billing_categories.items():
            if any(keyword in message_lower for keyword in keywords):
                category = cat
                break
        
        # Check for sensitive data indicators
        sensitive_indicators = ['card', 'payment', 'amount', '$', 'refund', 'cancel']
        contains_sensitive = any(indicator in message_lower for indicator in sensitive_indicators)
        
        # Determine urgency
        urgency = 'high' if any(word in message_lower for word in ['urgent', 'asap', 'immediately', 'problem']) else 'medium'
        
        return {
            'category': category,
            'urgency': urgency,
            'contains_sensitive_data': contains_sensitive,
            'account_access_required': category in ['payment_issue', 'subscription', 'refund'],
            'confidence': 0.6,
            'requires_human': contains_sensitive or category in ['refund', 'payment_issue']
        }
    
    async def _generate_billing_response(self, message: str, context: AgentContext,
                                       knowledge_results: List[Dict], billing_analysis: Dict) -> str:
        """Generate contextual billing response."""
        # Prepare knowledge context
        knowledge_context = ""
        if knowledge_results:
            knowledge_context = "\n\nRelevant billing information:\n"
            for result in knowledge_results[:3]:
                knowledge_context += f"- {result.get('content_preview', '')}\n"
                if result.get('citations'):
                    knowledge_context += f"  Source: {result['citations'].get('title', 'Unknown')}\n"
        
        system_prompt = f"""You are a billing specialist for our AI Secretary SaaS platform.

Billing inquiry analysis:
- Category: {billing_analysis.get('category', 'general')}
- Urgency: {billing_analysis.get('urgency', 'medium')}
- Sensitive data: {billing_analysis.get('contains_sensitive_data', False)}
- Account access needed: {billing_analysis.get('account_access_required', False)}

{knowledge_context}

Guidelines:
- Be professional and empathetic with billing concerns
- Use knowledge base information when relevant
- NEVER ask for or process sensitive financial information
- If account access is needed, escalate to human billing team
- Provide general billing information and policies
- Include citations for knowledge base references
- Offer to connect with billing team for account-specific issues
- Be clear about what you can and cannot help with

Generate a helpful billing response while maintaining security."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        try:
            return await self._call_openai(messages, context)
        except Exception as e:
            self.logger.error(f"Billing response generation failed: {str(e)}")
            return "I understand you have a billing question. For account security and to access your specific billing information, let me connect you with our billing team."
    
    def _extract_billing_terms(self, message: str) -> str:
        """Extract billing-related terms for knowledge search."""
        words = message.lower().split()
        billing_terms = []
        
        for word in words:
            if (word in self.billing_keywords or 
                any(word in keywords for keywords in self.billing_categories.values()) or
                word.startswith('$') or word.endswith('%')):
                billing_terms.append(word)
        
        return ' '.join(billing_terms[:8])
    
    def _get_billing_actions(self, billing_analysis: Dict) -> List[str]:
        """Get suggested actions for billing request."""
        actions = []
        
        category = billing_analysis.get('category', 'general')
        urgency = billing_analysis.get('urgency', 'medium')
        
        if billing_analysis.get('contains_sensitive_data') or billing_analysis.get('account_access_required'):
            actions.append('escalate_to_billing_team')
        
        if category == 'payment_issue':
            actions.append('check_payment_status')
        elif category == 'refund':
            actions.append('process_refund_request')
        elif category == 'subscription':
            actions.append('review_subscription_options')
        
        if urgency == 'high':
            actions.append('priority_billing_support')
        
        return actions


class OperationsAgent(BaseAgent):
    """Agent specialized in handling general business operations and inquiries."""
    
    def __init__(self):
        super().__init__("OperationsAgent")
        self.operations_keywords = [
            'hours', 'contact', 'location', 'address', 'phone', 'email',
            'about', 'company', 'services', 'general', 'information'
        ]
        self.common_inquiries = {
            'business_hours': ['hours', 'open', 'closed', 'schedule', 'time'],
            'contact_info': ['contact', 'phone', 'email', 'address', 'reach'],
            'company_info': ['about', 'company', 'business', 'who', 'what'],
            'services': ['services', 'offer', 'do', 'provide', 'features'],
            'general': ['help', 'information', 'question', 'inquiry']
        }
    
    async def process(self, message: str, context: AgentContext) -> AgentResponse:
        """Process general operations inquiries."""
        try:
            # Search knowledge base for general information
            knowledge_results = await self._search_operations_knowledge(message, context)
            
            # Analyze operations request
            ops_analysis = await self._analyze_operations_request(message, context)
            
            # Generate operations response
            response_content = await self._generate_operations_response(
                message, context, knowledge_results, ops_analysis
            )
            
            response = AgentResponse(
                content=response_content,
                confidence=ops_analysis.get('confidence', 0.8),
                intent='operations',
                requires_handoff=ops_analysis.get('requires_human', False),
                suggested_actions=self._get_operations_actions(ops_analysis),
                metadata={
                    'operations_analysis': ops_analysis,
                    'knowledge_sources': [r.get('citations') for r in knowledge_results],
                    'inquiry_type': ops_analysis.get('inquiry_type', 'general')
                }
            )
            
            self._log_interaction(message, response, context)
            return response
            
        except Exception as e:
            self.logger.error(f"Operations agent processing failed: {str(e)}")
            return AgentResponse(
                content="Thank you for your inquiry. I'm here to help with general questions about our business. How can I assist you today?",
                confidence=0.5,
                intent='operations',
                requires_handoff=False,
                metadata={'error': str(e)}
            )
    
    async def _search_operations_knowledge(self, message: str, context: AgentContext) -> List[Dict[str, Any]]:
        """Search knowledge base for operations information."""
        try:
            search_query = self._extract_operations_terms(message)
            
            results = KnowledgeService.search_knowledge(
                tenant_id=int(context.tenant_id),
                query=search_query,
                limit=5,
                min_similarity=0.6
            )
            
            return results
        except Exception as e:
            self.logger.warning(f"Operations knowledge search failed: {str(e)}")
            return []
    
    async def _analyze_operations_request(self, message: str, context: AgentContext) -> Dict[str, Any]:
        """Analyze operations request for type and routing."""
        system_prompt = self._create_operations_analysis_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        try:
            response = await self._call_openai(messages, context)
            analysis = json.loads(response)
            return analysis
        except (json.JSONDecodeError, Exception) as e:
            self.logger.warning(f"Operations analysis failed: {str(e)}")
            return self._fallback_operations_analysis(message)
    
    def _create_operations_analysis_prompt(self) -> str:
        """Create system prompt for operations request analysis."""
        return f"""You are an operations specialist analyzing general business inquiries.

Analyze the message and return a JSON response:
{{
    "inquiry_type": "business_hours|contact_info|company_info|services|location|general",
    "complexity": "simple|medium|complex",
    "can_self_serve": true/false,
    "information_needed": ["info1", "info2"],
    "suggested_response_type": "direct_answer|knowledge_base|human_handoff",
    "requires_human": true/false,
    "confidence": 0.0-1.0,
    "routing_suggestion": "operations|sales|support|billing"
}}

Inquiry types:
- business_hours: Operating hours, schedule questions
- contact_info: Phone, email, address requests
- company_info: About us, company background
- services: What we offer, capabilities
- location: Office locations, addresses
- general: Other general questions

Self-service criteria:
- Simple factual information
- Available in knowledge base
- No account-specific details needed

Human handoff criteria:
- Complex business questions
- Partnership inquiries
- Media/press requests
- Complaints or escalations

Operations keywords: {', '.join(self.operations_keywords)}"""
    
    def _fallback_operations_analysis(self, message: str) -> Dict[str, Any]:
        """Fallback operations analysis using keyword matching."""
        message_lower = message.lower()
        
        # Determine inquiry type
        inquiry_type = 'general'
        for inq_type, keywords in self.common_inquiries.items():
            if any(keyword in message_lower for keyword in keywords):
                inquiry_type = inq_type
                break
        
        # Simple complexity assessment
        complexity = 'complex' if len(message.split()) > 20 else 'simple'
        
        # Can self-serve for basic inquiries
        can_self_serve = inquiry_type in ['business_hours', 'contact_info', 'services']
        
        return {
            'inquiry_type': inquiry_type,
            'complexity': complexity,
            'can_self_serve': can_self_serve,
            'confidence': 0.6,
            'requires_human': not can_self_serve and complexity == 'complex',
            'routing_suggestion': 'operations'
        }
    
    async def _generate_operations_response(self, message: str, context: AgentContext,
                                          knowledge_results: List[Dict], ops_analysis: Dict) -> str:
        """Generate contextual operations response."""
        # Prepare knowledge context
        knowledge_context = ""
        if knowledge_results:
            knowledge_context = "\n\nRelevant information:\n"
            for result in knowledge_results[:3]:
                knowledge_context += f"- {result.get('content_preview', '')}\n"
                if result.get('citations'):
                    knowledge_context += f"  Source: {result['citations'].get('title', 'Unknown')}\n"
        
        system_prompt = f"""You are a helpful operations representative for our AI Secretary SaaS platform.

Inquiry analysis:
- Type: {ops_analysis.get('inquiry_type', 'general')}
- Complexity: {ops_analysis.get('complexity', 'simple')}
- Can self-serve: {ops_analysis.get('can_self_serve', True)}

{knowledge_context}

Guidelines:
- Be friendly and professional
- Provide accurate information from knowledge base when available
- Include citations for knowledge base references
- If you don't have specific information, offer to connect with appropriate team
- Keep responses helpful and informative
- Ask clarifying questions if needed
- Suggest relevant resources or next steps

Generate a helpful operations response."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        try:
            return await self._call_openai(messages, context)
        except Exception as e:
            self.logger.error(f"Operations response generation failed: {str(e)}")
            return "Thank you for your question. I'm here to help with general information about our business. Could you please provide more details about what you'd like to know?"
    
    def _extract_operations_terms(self, message: str) -> str:
        """Extract operations-related terms for knowledge search."""
        words = message.lower().split()
        ops_terms = []
        
        for word in words:
            if (word in self.operations_keywords or 
                any(word in keywords for keywords in self.common_inquiries.values()) or
                len(word) > 4):  # Include longer words that might be relevant
                ops_terms.append(word)
        
        return ' '.join(ops_terms[:10])
    
    def _get_operations_actions(self, ops_analysis: Dict) -> List[str]:
        """Get suggested actions for operations request."""
        actions = []
        
        inquiry_type = ops_analysis.get('inquiry_type', 'general')
        
        if inquiry_type == 'contact_info':
            actions.append('provide_contact_details')
        elif inquiry_type == 'business_hours':
            actions.append('provide_hours')
        elif inquiry_type == 'company_info':
            actions.append('provide_company_info')
        elif inquiry_type == 'services':
            actions.append('describe_services')
        
        if not ops_analysis.get('can_self_serve', True):
            actions.append('escalate_to_operations')
        
        return actions
        