"""Supervisor Agent for content filtering and policy enforcement."""

import re
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .base_agent import BaseAgent, AgentContext, AgentResponse


@dataclass
class FilterResult:
    """Result of content filtering."""
    is_safe: bool
    filtered_content: str
    violations: List[str]
    confidence: float
    metadata: Dict[str, Any]
    response_message: str = ""
    requires_human_review: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'is_safe': self.is_safe,
            'filtered_content': self.filtered_content,
            'violations': self.violations,
            'confidence': self.confidence,
            'metadata': self.metadata,
            'response_message': self.response_message,
            'requires_human_review': self.requires_human_review
        }


@dataclass
class PolicyViolation:
    """Represents a policy violation."""
    type: str
    severity: str  # low, medium, high, critical
    description: str
    original_text: str
    suggested_action: str


class SupervisorAgent(BaseAgent):
    """Agent responsible for content filtering, PII detection, and policy enforcement."""
    
    def __init__(self):
        super().__init__("SupervisorAgent")
        
        # Toxic language patterns
        self.toxic_patterns = [
            r'\b(fuck|fucking|shit|damn|bitch|asshole|bastard)\b',
            r'\b(idiot|stupid|moron|retard)\b',
            r'\b(hate|kill|die|murder)\b'
        ]
        
        # PII patterns
        self.pii_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
            'iban': r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b'
        }
        
        # Compliance keywords that require special handling
        self.compliance_keywords = [
            'gdpr', 'privacy', 'data protection', 'personal data',
            'consent', 'right to be forgotten', 'data subject',
            'legal', 'lawsuit', 'court', 'attorney', 'lawyer'
        ]
        
        # Inappropriate content categories
        self.inappropriate_categories = [
            'violence', 'harassment', 'hate_speech', 'sexual_content',
            'illegal_activity', 'spam', 'misinformation'
        ]
    
    async def process(self, message: str, context: AgentContext) -> AgentResponse:
        """Process message for content filtering and policy enforcement."""
        try:
            # Filter toxic content
            filter_result = await self.filter_content(message, context)
            
            # Validate against policies
            policy_violations = await self._check_policy_violations(message, context)
            
            # Create response
            response = AgentResponse(
                content=filter_result.filtered_content,
                confidence=filter_result.confidence,
                requires_handoff=len(policy_violations) > 0,
                metadata={
                    'is_safe': filter_result.is_safe,
                    'violations': filter_result.violations,
                    'policy_violations': [v.__dict__ for v in policy_violations],
                    'pii_detected': len([v for v in filter_result.violations if 'PII' in v]) > 0
                }
            )
            
            self._log_interaction(message, response, context)
            return response
            
        except Exception as e:
            self.logger.error(f"Supervisor agent processing failed: {str(e)}")
            # Fail safe - block content if filtering fails
            return AgentResponse(
                content="[Content blocked due to filtering error]",
                confidence=0.0,
                requires_handoff=True,
                metadata={'error': str(e), 'is_safe': False}
            )
    
    async def filter_content(self, content: str, context: AgentContext) -> FilterResult:
        """Filter content for toxic language and PII."""
        violations = []
        filtered_content = content
        is_safe = True
        
        # Check for toxic language
        toxic_violations = self._detect_toxic_content(content)
        if toxic_violations:
            violations.extend(toxic_violations)
            filtered_content = self._mask_toxic_content(filtered_content)
            is_safe = False
        
        # Check for PII
        pii_violations = self._detect_pii(content)
        if pii_violations:
            violations.extend(pii_violations)
            filtered_content = self._mask_pii(filtered_content)
        
        # Use OpenAI for advanced content analysis
        ai_analysis = await self._analyze_content_with_ai(content, context)
        if ai_analysis.get('violations'):
            violations.extend(ai_analysis['violations'])
            if ai_analysis.get('is_unsafe'):
                is_safe = False
                # Only use AI filtered content if we haven't already filtered it
                if filtered_content == content:
                    filtered_content = ai_analysis.get('filtered_content', filtered_content)
        
        confidence = self._calculate_confidence(violations, ai_analysis)
        
        response_message = ""
        requires_human_review = False
        
        if not is_safe:
            response_message = "I apologize, but I cannot process this message due to content policy violations."
            requires_human_review = True
        
        return FilterResult(
            is_safe=is_safe,
            filtered_content=filtered_content,
            violations=violations,
            confidence=confidence,
            metadata={
                'original_length': len(content),
                'filtered_length': len(filtered_content),
                'ai_analysis': ai_analysis
            },
            response_message=response_message,
            requires_human_review=requires_human_review
        )
    
    def _detect_toxic_content(self, content: str) -> List[str]:
        """Detect toxic language using pattern matching."""
        violations = []
        content_lower = content.lower()
        
        for pattern in self.toxic_patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            if matches:
                violations.append(f"Toxic language detected: {', '.join(matches)}")
        
        return violations
    
    def _detect_pii(self, content: str) -> List[str]:
        """Detect personally identifiable information."""
        violations = []
        
        for pii_type, pattern in self.pii_patterns.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                violations.append(f"PII detected ({pii_type}): {len(matches)} instances")
        
        return violations
    
    def _mask_toxic_content(self, content: str) -> str:
        """Mask toxic content with asterisks."""
        filtered_content = content
        
        for pattern in self.toxic_patterns:
            # Extract the words from the pattern (remove \b and parentheses)
            words = pattern.replace(r'\b', '').replace('(', '').replace(')', '').split('|')
            for word in words:
                # Replace each word individually with case-insensitive matching
                word_pattern = r'\b' + re.escape(word) + r'\b'
                filtered_content = re.sub(
                    word_pattern, 
                    '*' * len(word), 
                    filtered_content, 
                    flags=re.IGNORECASE
                )
        
        return filtered_content
    
    def _mask_pii(self, content: str) -> str:
        """Mask PII with appropriate placeholders."""
        filtered_content = content
        
        # Mask emails
        filtered_content = re.sub(
            self.pii_patterns['email'], 
            '[EMAIL_REDACTED]', 
            filtered_content
        )
        
        # Mask phone numbers
        filtered_content = re.sub(
            self.pii_patterns['phone'], 
            '[PHONE_REDACTED]', 
            filtered_content
        )
        
        # Mask SSN
        filtered_content = re.sub(
            self.pii_patterns['ssn'], 
            '[SSN_REDACTED]', 
            filtered_content
        )
        
        # Mask credit cards
        filtered_content = re.sub(
            self.pii_patterns['credit_card'], 
            '[CARD_REDACTED]', 
            filtered_content
        )
        
        # Mask IBAN
        filtered_content = re.sub(
            self.pii_patterns['iban'], 
            '[IBAN_REDACTED]', 
            filtered_content
        )
        
        return filtered_content
    
    async def _analyze_content_with_ai(self, content: str, context: AgentContext) -> Dict[str, Any]:
        """Use OpenAI to analyze content for safety and appropriateness."""
        system_prompt = self._create_content_analysis_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ]
        
        try:
            response = await self._call_openai(messages, context)
            analysis = json.loads(response)
            return analysis
        except (json.JSONDecodeError, Exception) as e:
            self.logger.warning(f"AI content analysis failed: {str(e)}")
            return {
                'is_unsafe': False,
                'violations': [],
                'confidence': 0.5,
                'categories': [],
                'filtered_content': content
            }
    
    def _create_content_analysis_prompt(self) -> str:
        """Create system prompt for content analysis."""
        return f"""You are a content safety analyzer for a business communication platform.

Analyze the user message and return a JSON response with the following structure:
{{
    "is_unsafe": true/false,
    "violations": ["list", "of", "violations"],
    "confidence": 0.0-1.0,
    "categories": ["category1", "category2"],
    "filtered_content": "content with inappropriate parts masked",
    "severity": "low|medium|high|critical",
    "requires_human_review": true/false
}}

Check for:
- Harassment, bullying, or threatening language
- Hate speech or discriminatory content
- Sexual or inappropriate content
- Violence or illegal activities
- Spam or promotional content
- Misinformation or false claims

Categories: {', '.join(self.inappropriate_categories)}

Guidelines:
- Be conservative in flagging content
- Preserve business-appropriate communication
- Mask inappropriate content with [FILTERED] tags
- Consider context and intent
- Flag for human review if uncertain"""
    
    async def _check_policy_violations(self, content: str, context: AgentContext) -> List[PolicyViolation]:
        """Check for policy violations that require special handling."""
        violations = []
        content_lower = content.lower()
        
        # Check for compliance-related content
        for keyword in self.compliance_keywords:
            if keyword in content_lower:
                violations.append(PolicyViolation(
                    type="compliance",
                    severity="high",
                    description=f"Compliance-related keyword detected: {keyword}",
                    original_text=content,
                    suggested_action="Route to legal/compliance team"
                ))
        
        # Check for potential legal issues
        legal_patterns = [
            r'\b(sue|lawsuit|legal action|court|attorney|lawyer)\b',
            r'\b(discrimination|harassment|violation)\b',
            r'\b(breach|contract|agreement|terms)\b'
        ]
        
        for pattern in legal_patterns:
            if re.search(pattern, content_lower):
                violations.append(PolicyViolation(
                    type="legal",
                    severity="critical",
                    description="Potential legal issue detected",
                    original_text=content,
                    suggested_action="Escalate to legal team immediately"
                ))
        
        return violations
    
    def _calculate_confidence(self, violations: List[str], ai_analysis: Dict[str, Any]) -> float:
        """Calculate confidence score for filtering decision."""
        base_confidence = 0.8
        
        # Reduce confidence for each violation
        confidence_penalty = len(violations) * 0.1
        
        # Factor in AI analysis confidence
        ai_confidence = ai_analysis.get('confidence', 0.5)
        
        # Weighted average
        final_confidence = max(0.1, min(1.0, 
            (base_confidence - confidence_penalty) * 0.6 + ai_confidence * 0.4
        ))
        
        return final_confidence
    
    async def validate_response(self, response: str, context: AgentContext) -> AgentResponse:
        """Validate an AI-generated response before sending to customer."""
        filter_result = await self.filter_content(response, context)
        
        # Additional checks for responses
        response_violations = []
        
        # Check if response is too generic
        if len(response.strip()) < 10:
            response_violations.append("Response too short or generic")
        
        # Check if response contains placeholder text
        placeholder_patterns = [
            r'\[.*?\]', r'\{.*?\}', r'TODO', r'FIXME', r'XXX'
        ]
        
        for pattern in placeholder_patterns:
            if re.search(pattern, response):
                response_violations.append("Response contains placeholder text")
        
        return AgentResponse(
            content=filter_result.filtered_content,
            confidence=filter_result.confidence,
            requires_handoff=not filter_result.is_safe or len(response_violations) > 0,
            metadata={
                'is_safe': filter_result.is_safe,
                'violations': filter_result.violations + response_violations,
                'response_validation': True
            }
        )
    
    def get_safety_report(self, content: str, filter_result: FilterResult) -> Dict[str, Any]:
        """Generate a safety report for audit purposes."""
        return {
            'timestamp': self._get_timestamp(),
            'content_length': len(content),
            'is_safe': filter_result.is_safe,
            'violations_count': len(filter_result.violations),
            'violations': filter_result.violations,
            'confidence': filter_result.confidence,
            'pii_detected': len([v for v in filter_result.violations if 'PII' in v]) > 0,
            'toxic_content_detected': len([v for v in filter_result.violations if 'Toxic' in v]) > 0,
            'filtered_content_length': len(filter_result.filtered_content),
            'metadata': filter_result.metadata
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for logging."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    async def filter_input(self, message: str, context: AgentContext) -> FilterResult:
        """Filter input message for safety and policy compliance."""
        return await self.filter_content(message, context)
    
    async def health_check(self):
        """Perform health check on supervisor agent."""
        # Simple health check - could be expanded
        pass