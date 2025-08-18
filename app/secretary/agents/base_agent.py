"""Base agent class for all AI agents."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import openai
from flask import current_app


@dataclass
class AgentContext:
    """Context information for agent processing."""
    tenant_id: str
    user_id: Optional[str] = None
    channel_type: Optional[str] = None
    conversation_id: Optional[str] = None
    customer_id: Optional[str] = None
    language: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AgentResponse:
    """Response from an agent."""
    content: str
    confidence: float
    intent: Optional[str] = None
    requires_handoff: bool = False
    suggested_actions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseAgent(ABC):
    """Base class for all AI agents."""
    
    def __init__(self, name: str, model: str = None):
        self.name = name
        self.model = model or 'gpt-4-turbo-preview'
        self.logger = logging.getLogger(f"agent.{name}")
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                api_key = current_app.config.get('OPENAI_API_KEY')
            except RuntimeError:
                # For testing without Flask context
                import os
                api_key = os.environ.get('OPENAI_API_KEY')
            
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            self._client = openai.OpenAI(api_key=api_key)
        return self._client
    
    @abstractmethod
    async def process(self, message: str, context: AgentContext) -> AgentResponse:
        """Process a message and return a response."""
        pass
    
    def _create_system_prompt(self, context: AgentContext) -> str:
        """Create system prompt for the agent."""
        base_prompt = f"""You are {self.name}, an AI assistant for a business communication platform.
        
Current context:
- Tenant ID: {context.tenant_id}
- Channel: {context.channel_type or 'unknown'}
- Language: {context.language or 'auto-detect'}
- Conversation ID: {context.conversation_id or 'new'}

Guidelines:
- Be professional and helpful
- Keep responses concise and relevant
- If you cannot help, suggest appropriate alternatives
- Always maintain customer privacy and data protection
"""
        return base_prompt
    
    async def _call_openai(self, messages: List[Dict[str, str]], context: AgentContext) -> str:
        """Make a call to OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI API call failed: {str(e)}")
            raise
    
    def _log_interaction(self, message: str, response: AgentResponse, context: AgentContext):
        """Log agent interaction for monitoring."""
        self.logger.info(
            "Agent interaction",
            extra={
                "agent": self.name,
                "tenant_id": context.tenant_id,
                "message_length": len(message),
                "response_length": len(response.content),
                "confidence": response.confidence,
                "intent": response.intent,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    async def generate_response(self, message: str, context: AgentContext) -> AgentResponse:
        """Generate response - delegates to process method."""
        return await self.process(message, context)
    
    async def health_check(self):
        """Perform health check on agent."""
        # Simple health check - could be expanded
        pass