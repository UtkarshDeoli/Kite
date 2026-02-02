"""
State Manager Module

Manages conversation state and user context.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """Stores conversation context for a user"""
    user_id: int
    chat_id: int
    messages: list = field(default_factory=list)
    current_task: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class StateManager:
    """
    Manages conversation state and user context.
    
    Provides:
    - Conversation context storage
    - State persistence
    - Context retrieval and updates
    """
    
    def __init__(self, max_history: int = 50):
        """
        Initialize the state manager.
        
        Args:
            max_history: Maximum number of messages to keep in history
        """
        self.contexts: Dict[int, ConversationContext] = {}
        self.max_history = max_history
        
        logger.info("StateManager initialized")
    
    def get_context(
        self,
        user_id: int,
        chat_id: int
    ) -> ConversationContext:
        """
        Get or create a conversation context.
        
        Args:
            user_id: User ID
            chat_id: Chat ID
            
        Returns:
            Conversation context
        """
        if user_id not in self.contexts:
            self.contexts[user_id] = ConversationContext(
                user_id=user_id,
                chat_id=chat_id
            )
        
        self.contexts[user_id].last_activity = datetime.now()
        return self.contexts[user_id]
    
    def add_message(
        self,
        user_id: int,
        chat_id: int,
        role: str,
        content: str
    ):
        """
        Add a message to the conversation history.
        
        Args:
            user_id: User ID
            chat_id: Chat ID
            role: Message role (user, assistant, system)
            content: Message content
        """
        context = self.get_context(user_id, chat_id)
        
        context.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        if len(context.messages) > self.max_history:
            context.messages = context.messages[-self.max_history:]
    
    def set_task(
        self,
        user_id: int,
        task_id: Optional[str]
    ):
        """
        Set the current task for a user.
        
        Args:
            user_id: User ID
            task_id: Task ID or None
        """
        context = self.get_context(user_id, 0)
        context.current_task = task_id
    
    def get_history(
        self,
        user_id: int,
        chat_id: int,
        limit: int = 10
    ) -> list:
        """
        Get recent conversation history.
        
        Args:
            user_id: User ID
            chat_id: Chat ID
            limit: Maximum number of messages
            
        Returns:
            List of recent messages
        """
        context = self.get_context(user_id, chat_id)
        return context.messages[-limit:]
    
    def update_preferences(
        self,
        user_id: int,
        chat_id: int,
        preferences: Dict[str, Any]
    ):
        """
        Update user preferences.
        
        Args:
            user_id: User ID
            chat_id: Chat ID
            preferences: New preferences
        """
        context = self.get_context(user_id, chat_id)
        context.preferences.update(preferences)
    
    def clear_context(self, user_id: int):
        """
        Clear conversation context for a user.
        
        Args:
            user_id: User ID
        """
        if user_id in self.contexts:
            del self.contexts[user_id]
        logger.debug(f"Cleared context for user {user_id}")
    
    def cleanup_inactive(self, max_age_hours: int = 24):
        """
        Remove contexts that haven't been active.
        
        Args:
            max_age_hours: Maximum age in hours
        """
        import time
        
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        removed = 0
        
        for user_id, context in list(self.contexts.items()):
            if context.last_activity.timestamp() < cutoff:
                del self.contexts[user_id]
                removed += 1
        
        if removed:
            logger.info(f"Cleaned up {removed} inactive contexts")
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get state manager statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_contexts": len(self.contexts),
            "active_tasks": sum(
                1 for c in self.contexts.values() if c.current_task
            )
        }
