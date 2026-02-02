"""
LLM Abstraction Layer - Base Classes

This module defines the abstract base classes for LLM providers.
Implementing these interfaces allows for easy swapping between different LLM providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass
from enum import Enum


class MessageRole(Enum):
    """Enum for message roles in conversations"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """Represents a single message in a conversation"""
    role: MessageRole
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # For tool role


@dataclass
class ChatCompletion:
    """Represents a chat completion response"""
    content: str
    finish_reason: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, int]] = None


@dataclass
class EmbeddingResult:
    """Represents an embedding response"""
    embedding: List[float]
    model: str
    usage: Optional[Dict[str, int]] = None


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    This class defines the interface that all LLM providers must implement.
    This allows for easy swapping between providers without changing the rest
    of the application code.
    
    Attributes:
        model_name: The name of the model being used
        temperature: Default temperature for completions
        max_tokens: Maximum tokens to generate
    """
    
    def __init__(
        self,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the LLM provider.
        
        Args:
            model_name: The name of the model to use
            temperature: Default temperature for completions (0.0 - 2.0)
            max_tokens: Maximum tokens to generate per response
            **kwargs: Additional provider-specific parameters
        """
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> ChatCompletion:
        """
        Send a chat completion request.
        
        Args:
            messages: List of messages in the conversation
            temperature: Override default temperature
            max_tokens: Override default max tokens
            tools: Optional list of tool definitions for function calling
            **kwargs: Additional provider-specific parameters
            
        Returns:
            ChatCompletion object with the model's response
        """
        pass
    
    @abstractmethod
    async def get_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        **kwargs
    ) -> List[EmbeddingResult]:
        """
        Get embeddings for a list of texts.
        
        Args:
            texts: List of texts to embed
            model: Optional override for embedding model
            **kwargs: Additional provider-specific parameters
            
        Returns:
            List of EmbeddingResult objects
        """
        pass
    
    @abstractmethod
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
            **kwargs: Additional provider-specific parameters
            
        Yields:
            Tokens from the streaming response
        """
        pass
    
    @abstractmethod
    def validate_api_key(self) -> bool:
        """
        Validate that the API key is set and valid.
        
        Returns:
            True if API key is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.
        
        Returns:
            String name of the provider
        """
        pass
    
    def format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Format messages for the API request.
        
        Args:
            messages: List of Message objects
            
        Returns:
            List of dictionaries formatted for the API
        """
        formatted = []
        for msg in messages:
            message_dict = {"role": msg.role.value, "content": msg.content}
            if msg.tool_calls:
                message_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id
            if msg.name:
                message_dict["name"] = msg.name
            formatted.append(message_dict)
        return formatted


class BaseEmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    
    This allows using different embedding models from different providers.
    """
    
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """
        Get embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings
        """
        pass
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings from this provider.
        
        Returns:
            Integer dimension of embeddings
        """
        pass
