"""
Anthropic LLM Provider Implementation

This module provides the Anthropic implementation of the BaseLLMProvider.
Anthropic provides Claude models with excellent reasoning capabilities.
"""

import os
import logging
from typing import List, Dict, Any, Optional, AsyncIterator

from anthropic import Anthropic, AsyncAnthropic

from .base import (
    BaseLLMProvider, Message, MessageRole, ChatCompletion, EmbeddingResult
)


logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic LLM Provider implementation.
    
    Anthropic provides Claude models with excellent reasoning and instruction
    following capabilities. This implementation uses the official Anthropic SDK.
    
    Supported models include:
    - claude-3-5-sonnet-20241022 (latest)
    - claude-3-opus-20240229
    - claude-3-sonnet-20240229
    - claude-3-haiku-20240307
    """
    
    def __init__(
        self,
        model_name: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the Anthropic provider.
        
        Args:
            model_name: Model to use (default: claude-3-5-sonnet)
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            temperature: Default temperature for completions
            max_tokens: Maximum tokens per response
            **kwargs: Additional parameters
        """
        super().__init__(model_name, temperature, max_tokens, **kwargs)
        
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable.")
        
        self.client = Anthropic(api_key=self.api_key, **kwargs)
        self.async_client = AsyncAnthropic(api_key=self.api_key, **kwargs)
        
        logger.info(f"Initialized Anthropic provider with model: {model_name}")
    
    def _format_messages_for_anthropic(self, messages: List[Message]) -> str:
        """
        Format messages into Anthropic's expected format (single string with roles).
        
        Args:
            messages: List of Message objects
            
        Returns:
            Formatted message string
        """
        formatted_parts = []
        
        for msg in messages:
            role = msg.role.value
            if msg.role == MessageRole.TOOL:
                role = "user"  # Anthropic uses user role for tool results
            
            formatted_parts.append(f"\n\n{role}: {msg.content}")
        
        return "".join(formatted_parts).strip()
    
    async def chat_completion(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> ChatCompletion:
        """
        Send a chat completion request to Anthropic.
        
        Args:
            messages: List of messages in the conversation
            temperature: Override default temperature
            max_tokens: Override default max tokens
            tools: Optional list of tool definitions
            **kwargs: Additional parameters
            
        Returns:
            ChatCompletion with the model's response
        """
        try:
            formatted_messages = self._format_messages_for_anthropic(messages)
            
            request_params = {
                "model": self.model_name,
                "messages": [formatted_messages],
                "temperature": temperature or self.temperature,
            }
            
            if max_tokens or self.max_tokens:
                request_params["max_tokens"] = max_tokens or self.max_tokens
            
            if tools:
                request_params["tools"] = tools
            
            request_params.update(kwargs)
            
            response = await self.async_client.messages.create(**request_params)
            
            tool_calls = None
            content_parts = []
            
            for content in response.content:
                if content.type == "text":
                    content_parts.append(content.text)
                elif content.type == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append({
                        "id": content.id,
                        "type": "function",
                        "function": {
                            "name": content.name,
                            "arguments": content.input
                        }
                    })
            
            return ChatCompletion(
                content="".join(content_parts),
                tool_calls=tool_calls,
                finish_reason=response.stop_reason or "stop",
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                } if response.usage else None
            )
            
        except Exception as e:
            logger.error(f"Anthropic chat completion error: {e}")
            raise
    
    async def get_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        **kwargs
    ) -> List[EmbeddingResult]:
        """
        Get embeddings using Anthropic's embedding models.
        
        Note: Anthropic doesn't have native embedding support in the SDK.
        This falls back to using OpenAI embeddings or another provider.
        
        Args:
            texts: List of texts to embed
            model: Ignored (Anthropic doesn't have embedding models)
            **kwargs: Additional parameters
            
        Returns:
            List of EmbeddingResult objects (may be empty or use fallback)
        """
        logger.warning("Anthropic doesn't support native embeddings. "
                      "Consider using OpenRouter for embeddings.")
        
        return []
    
    async def stream_chat_completion(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream chat completion response token by token.
        
        Args:
            messages: List of messages in the conversation
            temperature: Override default temperature
            max_tokens: Override default max tokens
            **kwargs: Additional parameters
            
        Yields:
            Tokens from the streaming response
        """
        try:
            formatted_messages = self._format_messages_for_anthropic(messages)
            
            request_params = {
                "model": self.model_name,
                "messages": [formatted_messages],
                "temperature": temperature or self.temperature,
                "stream": True,
            }
            
            if max_tokens or self.max_tokens:
                request_params["max_tokens"] = max_tokens or self.max_tokens
            
            request_params.update(kwargs)
            
            stream = await self.async_client.messages.create(**request_params)
            
            async for chunk in stream:
                if chunk.type == "content_block_delta":
                    if chunk.delta.type == "text_delta":
                        yield chunk.delta.text
                    
        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise
    
    def validate_api_key(self) -> bool:
        """
        Validate the Anthropic API key.
        
        Returns:
            True if the API key is valid, False otherwise
        """
        try:
            self.client.messages.create(
                model=self.model_name,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception as e:
            logger.warning(f"Anthropic API key validation failed: {e}")
            return False
    
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.
        
        Returns:
            String name of the provider
        """
        return "anthropic"
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models from Anthropic.
        
        Returns:
            List of model information dictionaries
        """
        return [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
            {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
        ]
    
    def close(self):
        """Close the HTTP client"""
        self.client.close()
