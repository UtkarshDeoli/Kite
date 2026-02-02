"""
Logging Setup Module

Configures application logging.
"""

import os
import logging
from datetime import datetime
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "/app/data/logs/agent.log"
) -> logging.Logger:
    """
    Set up application logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
        
    Returns:
        Configured root logger
    """
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level_int,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at level: {log_level}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
