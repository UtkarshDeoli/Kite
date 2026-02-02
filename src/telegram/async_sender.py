"""
Async Message Sender Module

This module provides async message sending capabilities to Telegram,
allowing the bot to send progress updates while performing long-running tasks.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Callable, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from telegram import Bot
from telegram.error import TelegramError


logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages that can be sent"""
    PROGRESS = "progress"
    RESULT = "result"
    ERROR = "error"
    NOTIFICATION = "notification"
    STATUS_UPDATE = "status_update"


@dataclass
class ProgressUpdate:
    """Represents a progress update"""
    task_id: str
    progress: float
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AsyncSender:
    """
    Async message sender for Telegram with progress update support.
    
    This class provides:
    - Non-blocking message sending
    - Progress update tracking
    - Rate limiting protection
    - Message queuing for reliability
    """
    
    def __init__(
        self,
        token: str = None,
        max_concurrent: int = 5,
        rate_limit_delay: float = 0.1
    ):
        """
        Initialize the async sender.
        
        Args:
            token: Telegram bot token
            max_concurrent: Maximum concurrent message operations
            rate_limit_delay: Delay between messages (seconds)
        """
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("Telegram bot token is required")
        
        self.bot = Bot(token=self.token)
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay
        
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._last_message_time: Dict[int, datetime] = {}
        
        self._progress_callbacks: Dict[str, Callable] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        
        logger.info("AsyncSender initialized")
    
    async def start(self):
        """Start the message processing worker"""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._message_worker())
            logger.info("AsyncSender worker started")
    
    async def stop(self):
        """Stop the message processing worker"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("AsyncSender worker stopped")
    
    async def _message_worker(self):
        """Background worker to process queued messages"""
        while self._running:
            try:
                coro, chat_id, kwargs = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                
                async with self._semaphore:
                    try:
                        await coro
                    except Exception as e:
                        logger.error(f"Error sending queued message: {e}")
                    
                    self._message_queue.task_done()
                    
                    await asyncio.sleep(self.rate_limit_delay)
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Message worker error: {e}")
    
    async def _rate_limit(self, chat_id: int):
        """
        Apply rate limiting for a chat.
        
        Args:
            chat_id: Telegram chat ID
        """
        last_time = self._last_message_time.get(chat_id)
        
        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - elapsed)
        
        self._last_message_time[chat_id] = datetime.now()
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = None,
        reply_markup: Any = None,
        disable_web_page_preview: bool = False,
        queue: bool = False
    ) -> bool:
        """
        Send a text message to a Telegram chat.
        
        Args:
            chat_id: Telegram chat ID
            text: Message text
            parse_mode: Parse mode (Markdown, HTML, etc.)
            reply_markup: Inline keyboard markup
            disable_web_page_preview: Disable link preview
            queue: Queue the message for async delivery
            
        Returns:
            True if successful
        """
        async def _send():
            await self._rate_limit(chat_id)
            
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview
                )
                return True
                
            except TelegramError as e:
                logger.error(f"Failed to send message to {chat_id}: {e}")
                return False
        
        if queue:
            self._message_queue.put_nowait((_send(), chat_id, {}))
            return True
        
        return await _send()
    
    async def send_progress_update(
        self,
        chat_id: int,
        task_id: str,
        progress: float,
        message: str,
        details: Dict[str, Any] = None,
        update_callback: bool = True
    ):
        """
        Send a progress update for a running task.
        
        Args:
            chat_id: Telegram chat ID
            task_id: ID of the task
            progress: Progress percentage (0-100)
            message: Progress message
            details: Additional details dictionary
            update_callback: Whether to trigger callback
        """
        progress_update = ProgressUpdate(
            task_id=task_id,
            progress=progress,
            message=message,
            details=details
        )
        
        progress_bar = self._create_progress_bar(progress)
        
        text = f"{progress_bar}\n\n📊 *Progress:* {progress:.1f}%\n\n{message}"
        
        await self._rate_limit(chat_id)
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown"
            )
        except TelegramError as e:
            logger.error(f"Failed to send progress update: {e}")
        
        if update_callback and task_id in self._progress_callbacks:
            try:
                self._progress_callbacks[task_id](progress_update)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    async def send_result(
        self,
        chat_id: int,
        task_id: str,
        result_text: str,
        success: bool = True
    ):
        """
        Send the result of a completed task.
        
        Args:
            chat_id: Telegram chat ID
            task_id: ID of the task
            result_text: Result message
            success: Whether the task was successful
        """
        emoji = "✅" if success else "❌"
        status = "Task Completed" if success else "Task Failed"
        
        text = f"{emoji} *{status}*\n\n{result_text}"
        
        await self.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown"
        )
        
        if task_id in self._progress_callbacks:
            del self._progress_callbacks[task_id]
    
    async def send_error(
        self,
        chat_id: int,
        error_message: str,
        task_id: str = None,
        recovery_suggestion: str = None
    ):
        """
        Send an error message.
        
        Args:
            chat_id: Telegram chat ID
            error_message: Error description
            task_id: Optional task ID that failed
            recovery_suggestion: Optional suggestion for recovery
        """
        text = f"❌ *Error Encountered*\n\n{error_message}"
        
        if recovery_suggestion:
            text += f"\n\n💡 *Suggestion:* {recovery_suggestion}"
        
        if task_id:
            text += f"\n\nTask ID: `{task_id}`"
        
        await self.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown"
        )
    
    async def send_typing_action(self, chat_id: int):
        """
        Send typing action to indicate the bot is working.
        
        Args:
            chat_id: Telegram chat ID
        """
        try:
            await self.bot.send_chat_action(
                chat_id=chat_id,
                action="typing"
            )
        except TelegramError as e:
            logger.debug(f"Failed to send typing action: {e}")
    
    async def send_chat_action(
        self,
        chat_id: int,
        action: str
    ):
        """
        Send a custom chat action.
        
        Args:
            chat_id: Telegram chat ID
            action: Action type (typing, upload_photo, etc.)
        """
        try:
            await self.bot.send_chat_action(
                chat_id=chat_id,
                action=action
            )
        except TelegramError as e:
            logger.debug(f"Failed to send chat action: {e}")
    
    def register_progress_callback(
        self,
        task_id: str,
        callback: Callable[[ProgressUpdate], None]
    ):
        """
        Register a callback for progress updates.
        
        Args:
            task_id: ID of the task
            callback: Callback function
        """
        self._progress_callbacks[task_id] = callback
    
    def unregister_progress_callback(self, task_id: str):
        """
        Unregister a progress callback.
        
        Args:
            task_id: ID of the task
        """
        if task_id in self._progress_callbacks:
            del self._progress_callbacks[task_id]
    
    def _create_progress_bar(self, progress: float, length: int = 20) -> str:
        """
        Create a text-based progress bar.
        
        Args:
            progress: Progress percentage (0-100)
            length: Length of the bar
            
        Returns:
            Progress bar string
        """
        filled = int(length * progress / 100)
        empty = length - filled
        
        filled_char = "█"
        empty_char = "░"
        
        return f"[{filled_char * filled}{empty_char * empty}]"
    
    async def get_chat(self, chat_id: int) -> Dict[str, Any]:
        """
        Get information about a chat.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Chat information dictionary
        """
        try:
            chat = await self.bot.get_chat(chat_id)
            return {
                "id": chat.id,
                "type": str(chat.type),
                "title": chat.title,
                "username": chat.username,
                "first_name": chat.first_name,
                "last_name": chat.last_name
            }
        except TelegramError as e:
            logger.error(f"Failed to get chat {chat_id}: {e}")
            return {}
    
    async def count_messages_sent(self) -> int:
        """
        Get count of messages in the queue.
        
        Returns:
            Number of queued messages
        """
        return self._message_queue.qsize()
