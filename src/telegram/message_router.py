"""
Message Router Module

This module routes incoming messages to appropriate handlers based on intent.
"""

import logging
from typing import Callable, Dict, Any, Optional

from .async_sender import AsyncSender


logger = logging.getLogger(__name__)


class MessageRouter:
    """
    Routes messages to appropriate handlers based on intent.
    
    This class:
    - Classifies incoming messages
    - Routes to appropriate handlers
    - Manages conversation context
    """
    
    def __init__(self):
        """
        Initialize the message router.
        """
        self.handlers: Dict[str, Callable] = {}
        self.default_handler: Optional[Callable] = None
        
        logger.info("MessageRouter initialized")
    
    def register_handler(
        self,
        intent: str,
        handler: Callable
    ):
        """
        Register a handler for a specific intent.
        
        Args:
            intent: Intent identifier
            handler: Handler function
        """
        self.handlers[intent] = handler
        logger.debug(f"Registered handler for intent: {intent}")
    
    def set_default_handler(self, handler: Callable):
        """
        Set the default handler for unrecognized intents.
        
        Args:
            handler: Default handler function
        """
        self.default_handler = handler
    
    async def route_message(
        self,
        user_id: int,
        chat_id: int,
        username: Optional[str],
        message: str,
        send_progress: Callable = None
    ) -> str:
        """
        Route a message to the appropriate handler.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            username: Username
            message: Message text
            send_progress: Progress callback function
            
        Returns:
            Response text
        """
        intent = self._classify_intent(message)
        
        logger.info(f"Routing message with intent: {intent}")
        
        handler = self.handlers.get(intent, self.default_handler)
        
        if handler:
            try:
                response = await handler(
                    user_id=user_id,
                    chat_id=chat_id,
                    username=username,
                    message=message,
                    send_progress=send_progress
                )
                return response
            except Exception as e:
                logger.error(f"Handler error for intent {intent}: {e}")
                return f"I encountered an error while processing your request: {str(e)}"
        
        return self._generate_default_response(message)
    
    def _classify_intent(self, message: str) -> str:
        """
        Classify the intent of a message.
        
        Args:
            message: Message text
            
        Returns:
            Intent identifier
        """
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["linkedin", "connection", "profile", "message"]):
            if "connection" in message_lower or "connect" in message_lower:
                return "linkedin_connection"
            elif "message" in message_lower or "send" in message_lower:
                return "linkedin_message"
            elif "profile" in message_lower:
                return "linkedin_profile"
            elif "search" in message_lower or "find" in message_lower:
                return "linkedin_search"
            return "linkedin_general"
        
        if any(word in message_lower for word in ["youtube", "video", "transcript"]):
            if "transcript" in message_lower or "summary" in message_lower:
                return "youtube_research"
            return "youtube_general"
        
        if any(word in message_lower for word in ["search", "research", "find", "look up"]):
            return "web_search"
        
        if any(word in message_lower for word in ["visit", "open", "go to", "navigate"]):
            return "web_browse"
        
        if any(word in message_lower for word in ["help", "what can", "how to"]):
            return "help"
        
        return "general"
    
    def _generate_default_response(self, message: str) -> str:
        """
        Generate a default response for unrecognized messages.
        
        Args:
            message: Original message
            
        Returns:
            Default response text
        """
        return (
            f"I received your message: \"{message[:100]}{'...' if len(message) > 100 else ''}\"\n\n"
            "I'm not sure how to help with that specifically. "
            "I can assist with:\n"
            "• LinkedIn tasks (connections, messages, profiles)\n"
            "• Web browsing and research\n"
            "• YouTube video analysis\n\n"
            "Try rephrasing your request or ask for help!"
        )
