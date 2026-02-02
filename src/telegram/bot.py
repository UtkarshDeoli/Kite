"""
Telegram Bot Module

This module provides the main Telegram bot interface for receiving messages
and delegating them to the orchestrator for processing.
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

from .async_sender import AsyncSender
from .message_router import MessageRouter


logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Main Telegram Bot class.
    
    This class handles:
    - Receiving messages from users
    - Routing messages to appropriate handlers
    - Sending async progress updates
    - Managing conversation context
    """
    
    def __init__(
        self,
        token: str = None,
        webhook_url: str = None,
        async_sender: AsyncSender = None,
        message_router: MessageRouter = None,
        port: int = 8000
    ):
        """
        Initialize the Telegram bot.
        
        Args:
            token: Telegram bot token
            webhook_url: Webhook URL for production
            async_sender: Async message sender
            message_router: Message router for processing
            port: Port for webhook (if using webhook mode)
        """
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("Telegram bot token is required")
        
        self.webhook_url = webhook_url or os.getenv("WEBHOOK_URL")
        self.port = port
        self.async_sender = async_sender or AsyncSender()
        self.message_router = message_router or MessageRouter()
        
        self.application: Optional[Application] = None
        self._running = False
        
        logger.info("TelegramBot initialized")
    
    async def initialize(self):
        """
        Initialize the bot and set up handlers.
        """
        self.application = Application.builder().token(self.token).build()
        
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        self.application.add_handler(CommandHandler("status", self._handle_status))
        self.application.add_handler(CommandHandler("cancel", self._handle_cancel))
        
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        
        self.application.add_handler(
            CallbackQueryHandler(self._handle_callback)
        )
        
        await self.application.initialize()
        logger.info("TelegramBot handlers initialized")
    
    async def start_polling(self):
        """
        Start the bot in polling mode (for development).
        """
        if not self.application:
            await self.initialize()
        
        await self.application.start()
        await self.application.updater.start_polling()
        self._running = True
        
        logger.info("TelegramBot started in polling mode")
        
        await self.application.updater.start_polling()
        await self.application.updater.stop()
    
    async def start_webhook(self):
        """
        Start the bot in webhook mode (for production).
        """
        if not self.application:
            await self.initialize()
        
        if not self.webhook_url:
            raise ValueError("Webhook URL is required for webhook mode")
        
        await self.application.bot.set_webhook(
            url=f"{self.webhook_url}/webhook",
            allowed_updates=["message", "callback_query"]
        )
        
        await self.application.start()
        self._running = True
        
        logger.info(f"TelegramBot started in webhook mode: {self.webhook_url}/webhook")
    
    async def stop(self):
        """
        Stop the bot gracefully.
        """
        if self.application:
            await self.application.stop()
            self._running = False
            logger.info("TelegramBot stopped")
    
    async def _handle_start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle /start command.
        """
        user = update.message.from_user
        chat_id = update.message.chat_id
        
        welcome_message = (
            f"Hi {user.first_name}! 👋\n\n"
            "I'm your AI browser automation assistant. I can help you with:\n\n"
            "• LinkedIn tasks (send connections, messages, search profiles)\n"
            "• Web research and browsing\n"
            "• YouTube video research (with transcripts)\n"
            "• Any browser-based automation tasks\n\n"
            "Just chat with me naturally, and I'll help you get things done!\n\n"
            "Type /help for more information."
        )
        
        keyboard = [
            [
                InlineKeyboardButton("LinkedIn Tasks", callback_data="category_linkedin"),
                InlineKeyboardButton("Web Research", callback_data="category_general")
            ],
            [
                InlineKeyboardButton("Help", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.async_sender.send_message(
            chat_id=chat_id,
            text=welcome_message,
            reply_markup=reply_markup
        )
        
        logger.info(f"User {user.id} started conversation")
    
    async def _handle_help(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle /help command.
        """
        chat_id = update.message.chat_id
        
        help_text = """
🔧 *Available Commands*

/start - Start the bot
/help - Show this help message
/status - Check bot status
/cancel - Cancel current task

💬 *How to Use*

Just chat with me naturally! Examples:

• "Send connection requests to 5 product managers at Google"
• "Visit my LinkedIn profile and summarize it"
• "Research AI trends on YouTube"
• "Search for software engineers at startups"

🔒 *Privacy Notes*

• I only access websites you request
• Your data is stored locally
• I learn from successful tasks to help you better

⚡ *Async Features*

I can perform tasks in the background while continuing our conversation. 
You'll receive progress updates as I work!
        """
        
        await self.async_sender.send_message(
            chat_id=chat_id,
            text=help_text,
            parse_mode="Markdown"
        )
    
    async def _handle_status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle /status command.
        """
        chat_id = update.message.chat_id
        
        status_text = """
✅ *System Status*

• Bot: Online
• Database: Connected
• LLM: Ready
• Browser Tools: Available

📊 *Quick Stats*

• Completed tasks today: [count]
• Active workflows: [count]

Need help with anything specific?
        """
        
        await self.async_sender.send_message(
            chat_id=chat_id,
            text=status_text,
            parse_mode="Markdown"
        )
    
    async def _handle_cancel(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle /cancel command to cancel running tasks.
        """
        chat_id = update.message.chat_id
        
        await self.async_sender.send_message(
            chat_id=chat_id,
            text="🛑 Cancelling any running tasks...\n\nIf you have any active tasks, they will be stopped."
        )
        
        logger.info(f"User {chat_id} cancelled tasks")
    
    async def _handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle incoming text messages.
        
        This is the main entry point for user interactions.
        Messages are routed to the orchestrator for processing.
        """
        if not update.message:
            return
        
        user = update.message.from_user
        chat_id = update.message.chat_id
        message_text = update.message.text
        
        logger.info(f"Received message from user {user.id}: {message_text[:100]}")
        
        await self.async_sender.send_chat_action(chat_id, "typing")
        
        try:
            response = await self.message_router.route_message(
                user_id=user.id,
                chat_id=chat_id,
                username=user.username,
                message=message_text,
                send_progress=self.async_sender.send_progress_update
            )
            
            await self.async_sender.send_message(
                chat_id=chat_id,
                text=response
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            
            await self.async_sender.send_message(
                chat_id=chat_id,
                text=f"❌ I encountered an error: {str(e)}\n\nPlease try again or rephrase your request."
            )
    
    async def _handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle inline button callbacks.
        """
        query = update.callback_query
        if not query:
            return
        
        await query.answer()
        
        chat_id = query.message.chat_id
        callback_data = query.data
        
        if callback_data.startswith("category_"):
            category = callback_data.replace("category_", "")
            
            await query.edit_message_text(
                text=f"Selected category: {category}\n\nWhat would you like me to help you with?"
            )
        
        elif callback_data == "help":
            await self._handle_help(update, context)
        
        logger.info(f"Callback received: {callback_data}")
    
    async def send_to_user(
        self,
        chat_id: int,
        text: str,
        **kwargs
    ):
        """
        Send a message to a specific user.
        
        Args:
            chat_id: Telegram chat ID
            text: Message text
            **kwargs: Additional arguments for send_message
        """
        await self.async_sender.send_message(chat_id=chat_id, text=text, **kwargs)
    
    async def send_progress(
        self,
        chat_id: int,
        task_id: str,
        progress: float,
        message: str
    ):
        """
        Send a progress update to a user.
        
        Args:
            chat_id: Telegram chat ID
            task_id: ID of the task
            progress: Progress percentage (0-100)
            message: Progress message
        """
        await self.async_sender.send_progress_update(
            chat_id=chat_id,
            task_id=task_id,
            progress=progress,
            message=message
        )
