"""
OpenRouter LLM Provider Implementation

This module provides the OpenRouter implementation of the BaseLLMProvider.
OpenRouter provides access to various models through a unified API.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, AsyncIterator

import httpx
from openai import OpenAI, AsyncOpenAI

from .base import (
    BaseLLMProvider, Message, MessageRole, ChatCompletion, EmbeddingResult
)


logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLMProvider):
    """
    OpenRouter LLM Provider implementation.
    
    OpenRouter provides access to models from OpenAI, Anthropic, and other providers
    through a unified API. This implementation uses the OpenAI-compatible API.
    
    Supported models include:
    - openai/gpt-4o, gpt-4o-mini
    - openai/gpt-4-turbo
    - anthropic/claude-3-sonnet, claude-3-opus
    - meta-llama/llama-3.1-405b
    - and many more
    """
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(
        self,
        model_name: str = "openai/gpt-4o",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the OpenRouter provider.
        
        Args:
            model_name: Model to use (default: openai/gpt-4o)
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            temperature: Default temperature for completions
            max_tokens: Maximum tokens per response
            base_url: Override base URL (for testing or proxies)
            **kwargs: Additional parameters passed to the OpenAI client
        """
        super().__init__(model_name, temperature, max_tokens, **kwargs)
        
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable.")
        
        self.base_url = base_url or self.BASE_URL
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            **kwargs
        )
        
        self.async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            **kwargs
        )
        
        logger.info(f"Initialized OpenRouter provider with model: {model_name}")
    
    async def chat_completion(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> ChatCompletion:
        """
        Send a chat completion request to OpenRouter.
        
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
            formatted_messages = self.format_messages(messages)
            
            request_params = {
                "model": self.model_name,
                "messages": formatted_messages,
                "temperature": temperature or self.temperature,
            }
            
            if max_tokens or self.max_tokens:
                request_params["max_tokens"] = max_tokens or self.max_tokens
            
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = "auto"
            
            request_params.update(kwargs)
            
            response = await self.async_client.chat.completions.create(**request_params)
            
            choice = response.choices[0]
            
            return ChatCompletion(
                content=choice.message.content or "",
                tool_calls=[tc.model_dump() for tc in choice.message.tool_calls] if choice.message.tool_calls else None,
                finish_reason=choice.finish_reason or "stop",
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else None
            )
            
        except Exception as e:
            logger.error(f"OpenRouter chat completion error: {e}")
            raise
    
    async def get_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        **kwargs
    ) -> List[EmbeddingResult]:
        """
        Get embeddings using OpenRouter's embedding models.
        
        Note: OpenRouter supports various embedding models. The default is
        a high-quality embedding model for semantic search.
        
        Args:
            texts: List of texts to embed
            model: Optional embedding model override
            **kwargs: Additional parameters
            
        Returns:
            List of EmbeddingResult objects
        """
        embedding_model = model or "openai/text-embedding-3-small"
        
        try:
            response = await self.async_client.embeddings.create(
                model=embedding_model,
                input=texts,
                **kwargs
            )
            
            results = []
            for data in response.data:
                results.append(EmbeddingResult(
                    embedding=data.embedding,
                    model=embedding_model,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "total_tokens": response.usage.total_tokens,
                    } if response.usage else None
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"OpenRouter embedding error: {e}")
            raise
    
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
            formatted_messages = self.format_messages(messages)
            
            request_params = {
                "model": self.model_name,
                "messages": formatted_messages,
                "temperature": temperature or self.temperature,
                "stream": True,
            }
            
            if max_tokens or self.max_tokens:
                request_params["max_tokens"] = max_tokens or self.max_tokens
            
            request_params.update(kwargs)
            
            stream = await self.async_client.chat.completions.create(**request_params)
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"OpenRouter streaming error: {e}")
            raise
    
    def validate_api_key(self) -> bool:
        """
        Validate the OpenRouter API key.
        
        Returns:
            True if the API key is valid, False otherwise
        """
        try:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            client.models.list()
            return True
        except Exception as e:
            logger.warning(f"OpenRouter API key validation failed: {e}")
            return False
    
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.
        
        Returns:
            String name of the provider
        """
        return "openrouter"
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models from OpenRouter.
        
        Returns:
            List of model information dictionaries
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url.replace('/api/v1', '')}/api/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
        except Exception as e:
            logger.error(f"Failed to get models from OpenRouter: {e}")
            return []
    
    def close(self):
        """Close the HTTP clients"""
        self.client.close()
        import asyncio
        asyncio.create_task(self.async_client.close())
