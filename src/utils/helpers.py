"""
Helper Functions Module

Utility functions for the application.
"""

import re
from typing import Any, Dict, List


def setup_environment():
    """
    Set up the application environment.
    Creates necessary directories and validates setup.
    """
    import os
    from pathlib import Path
    
    directories = [
        "./data",
        "./data/logs",
        "./data/youtube"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


def clean_text(text: str) -> str:
    """
    Clean and normalize text.
    
    Args:
        text: Input text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    
    return text


def extract_numbers(text: str) -> List[str]:
    """
    Extract all numbers from text.
    
    Args:
        text: Input text
        
    Returns:
        List of number strings
    """
    return re.findall(r'\d+', text)


def parse_quantity(text: str) -> int:
    """
    Parse a quantity from text.
    
    Args:
        text: Input text
        
    Returns:
        Quantity as integer, defaults to 1
    """
    numbers = extract_numbers(text)
    if numbers:
        return int(numbers[0])
    return 1


def extract_url(text: str) -> str:
    """
    Extract a URL from text.
    
    Args:
        text: Input text
        
    Returns:
        Extracted URL or empty string
    """
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    match = re.search(url_pattern, text)
    return match.group(0) if match else ""


def format_duration(seconds: int) -> str:
    """
    Format seconds into a human-readable duration.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


class RateLimiter:
    """
    Simple rate limiter for API calls.
    """
    
    def __init__(self, max_calls: int, period: float):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum calls in period
            period: Time period in seconds
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = []
    
    def allow(self) -> bool:
        """
        Check if a call is allowed.
        
        Returns:
            True if allowed, False if rate limited
        """
        import time
        
        now = time.time()
        
        self.calls = [t for t in self.calls if now - t < self.period]
        
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        
        return False
    
    def wait(self):
        """Wait until a call is allowed"""
        import time
        
        while not self.allow():
            time.sleep(0.1)
