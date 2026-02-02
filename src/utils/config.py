"""
Configuration Module

Manages application configuration from environment variables.
"""

import os
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class Config:
    """
    Application configuration loaded from environment variables.
    """
    
    telegram_token: str = field(default="")
    openrouter_api_key: str = field(default="")
    openrouter_model: str = field(default="openai/gpt-4o")
    anthropic_api_key: str = field(default="")
    anthropic_model: str = field(default="claude-3-5-sonnet-20241022")
    
    database_path: str = field(default="/app/data/agent.db")
    
    browser_headless: bool = field(default=True)
    browser_type: str = field(default="chromium")
    
    linkedin_email: str = field(default="")
    linkedin_password: str = field(default="")
    
    youtube_download_path: str = field(default="/app/data/youtube")
    
    log_level: str = field(default="INFO")
    log_file: str = field(default="/app/data/logs/agent.log")
    
    app_host: str = field(default="0.0.0.0")
    app_port: int = field(default=8000)
    webhook_url: str = field(default="")
    
    max_concurrent_tasks: int = field(default=5)
    task_timeout_seconds: int = field(default=300)
    
    enable_learning: bool = field(default=True)
    enable_browser_tools: bool = field(default=True)
    enable_youtube_tools: bool = field(default=False)
    
    def __post_init__(self):
        """Load configuration from environment variables"""
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", self.telegram_token)
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", self.openrouter_api_key)
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", self.openrouter_model)
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", self.anthropic_api_key)
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", self.anthropic_model)
        
        self.database_path = os.getenv("DATABASE_PATH", self.database_path)
        
        self.browser_headless = os.getenv("HEADLESS_MODE", str(self.browser_headless)).lower() == "true"
        self.browser_type = os.getenv("BROWSER_TYPE", self.browser_type)
        
        self.linkedin_email = os.getenv("LINKEDIN_EMAIL", self.linkedin_email)
        self.linkedin_password = os.getenv("LINKEDIN_PASSWORD", self.linkedin_password)
        
        self.youtube_download_path = os.getenv("YOUTUBE_DOWNLOAD_PATH", self.youtube_download_path)
        
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        self.log_file = os.getenv("LOG_FILE", self.log_file)
        
        self.app_host = os.getenv("APP_HOST", self.app_host)
        self.app_port = int(os.getenv("APP_PORT", str(self.app_port)))
        self.webhook_url = os.getenv("WEBHOOK_URL", self.webhook_url)
        
        self.max_concurrent_tasks = int(os.getenv("MAX_CONCURRENT_TASKS", str(self.max_concurrent_tasks)))
        self.task_timeout_seconds = int(os.getenv("TASK_TIMEOUT_SECONDS", str(self.task_timeout_seconds)))
        
        self.enable_learning = os.getenv("ENABLE_LEARNING", str(self.enable_learning)).lower() == "true"
        self.enable_browser_tools = os.getenv("ENABLE_BROWSER_TOOLS", str(self.enable_browser_tools)).lower() == "true"
        self.enable_youtube_tools = os.getenv("ENABLE_YOUTUBE_TOOLS", str(self.enable_youtube_tools)).lower() == "true"
    
    def validate(self) -> tuple[bool, list]:
        """
        Validate the configuration.
        
        Returns:
            Tuple of (is_valid, list of missing fields)
        """
        missing = []
        
        if not self.telegram_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        
        if not self.openrouter_api_key:
            missing.append("OPENROUTER_API_KEY")
        
        return len(missing) == 0, missing


_config: Optional[Config] = None


def load_config() -> Config:
    """
    Load application configuration.
    
    Returns:
        Config instance
    """
    global _config
    
    if _config is None:
        _config = Config()
    
    return _config


def get_config() -> Config:
    """
    Get the current configuration.
    
    Returns:
        Config instance
    """
    if _config is None:
        return load_config()
    return _config
