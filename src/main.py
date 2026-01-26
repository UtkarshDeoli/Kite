"""
Telegram Browser Agent - Main Application Entry Point

This is the main entry point for the Telegram Browser Agent.
"""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.utils.logging import setup_logging
from src.utils.helpers import setup_environment
from src.memory.database import Database
from src.memory.embedding_store import EmbeddingStore
from src.memory.workflow_manager import WorkflowManager
from src.llm.openrouter import OpenRouterProvider
from src.core.orchestrator import Orchestrator
from src.core.state_manager import StateManager
from src.core.async_task_manager import AsyncTaskManager
from src.telegram.bot import TelegramBot
from src.telegram.message_router import MessageRouter
from src.prompts.dynamic_prompts import DynamicPromptManager
from src.tools.base import ToolRegistry
from src.tools.browser_use import BrowserTool, LinkedInActions


logger = None
config = None
db = None


async def initialize_components():
    """
    Initialize all application components.
    """
    global logger, config, db
    
    logger = setup_logging(
        log_level=config.log_level,
        log_file=config.log_file
    )
    
    logger.info("Initializing Telegram Browser Agent...")
    
    setup_environment()
    
    db = Database(db_path=config.database_path)
    await db.initialize()
    logger.info("Database initialized")
    
    embedding_store = EmbeddingStore(db)
    workflow_manager = WorkflowManager(db, embedding_store)
    
    llm = OpenRouterProvider(
        model_name=config.openrouter_model,
        api_key=config.openrouter_api_key
    )
    
    prompt_manager = DynamicPromptManager()
    
    state_manager = StateManager()
    async_task_manager = AsyncTaskManager(
        max_concurrent=config.max_concurrent_tasks
    )
    await async_task_manager.start()
    
    orchestrator = Orchestrator(
        llm_provider=llm,
        db=db,
        workflow_manager=workflow_manager,
        prompt_manager=prompt_manager,
        enable_learning=config.enable_learning
    )
    
    tool_registry = ToolRegistry()
    
    if config.enable_browser_tools:
        browser_tool = BrowserTool(headless=config.browser_headless)
        linkedin_actions = LinkedInActions(browser_tool)
        tool_registry.register(browser_tool)
        tool_registry.register(linkedin_actions)
    
    message_router = MessageRouter()
    message_router.set_default_handler(
        lambda **kwargs: orchestrator.process_message(**kwargs)
    )
    
    async_sender = AsyncSender(token=config.telegram_token)
    await async_sender.start()
    
    bot = TelegramBot(
        token=config.telegram_token,
        webhook_url=config.webhook_url if config.webhook_url else None,
        async_sender=async_sender,
        message_router=message_router,
        port=config.app_port
    )
    await bot.initialize()
    
    logger.info("All components initialized successfully")
    
    return {
        "bot": bot,
        "db": db,
        "async_task_manager": async_task_manager,
        "async_sender": async_sender
    }


async def run_polling(components: dict):
    """
    Run the bot in polling mode.
    """
    logger.info("Starting bot in polling mode...")
    await components["bot"].start_polling()


async def run_webhook(components: dict):
    """
    Run the bot in webhook mode.
    """
    logger.info(f"Starting bot in webhook mode: {config.webhook_url}/webhook")
    await components["bot"].start_webhook()


async def shutdown(components: dict):
    """
    Gracefully shutdown the application.
    """
    logger.info("Shutting down...")
    
    if components.get("bot"):
        await components["bot"].stop()
    
    if components.get("async_task_manager"):
        await components["async_task_manager"].stop()
    
    if components.get("async_sender"):
        await components["async_sender"].stop()
    
    if db:
        await db.close()
    
    logger.info("Shutdown complete")


async def main():
    """
    Main application entry point.
    """
    global config
    
    config = load_config()
    
    valid, missing = config.validate()
    if not valid:
        print(f"Missing required configuration: {', '.join(missing)}")
        print("Please set the following environment variables:")
        for field in missing:
            print(f"  - {field}")
        sys.exit(1)
    
    try:
        components = await initialize_components()
        
        if config.webhook_url:
            await run_webhook(components)
        else:
            await run_polling(components)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        raise
    finally:
        await shutdown(components)


if __name__ == "__main__":
    asyncio.run(main())
