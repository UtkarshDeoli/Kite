"""
Base Tool Module

Abstract base classes for all tools.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Result from tool execution"""
    success: bool
    data: Any = None
    error: str = None
    metadata: Dict[str, Any] = None


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    
    All tools must implement the execute method.
    """
    
    name: str = "base_tool"
    description: str = "Base tool"
    category: str = "general"
    
    @abstractmethod
    async def execute(
        self,
        **kwargs
    ) -> ToolResult:
        """
        Execute the tool.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult with success status and data
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the tool schema for LLM function calling.
        
        Returns:
            Tool schema dictionary
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }


class ToolRegistry:
    """
    Registry for managing available tools.
    
    Provides easy tool registration and retrieval.
    """
    
    def __init__(self):
        """Initialize the tool registry"""
        self.tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool):
        """
        Register a new tool.
        
        Args:
            tool: Tool instance
        """
        self.tools[tool.name] = tool
        print(f"Registered tool: {tool.name}")
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a tool.
        
        Args:
            name: Tool name
            
        Returns:
            True if unregistered
        """
        if name in self.tools:
            del self.tools[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None
        """
        return self.tools.get(name)
    
    def get_all(self) -> Dict[str, BaseTool]:
        """
        Get all registered tools.
        
        Returns:
            Dictionary of all tools
        """
        return self.tools
    
    def get_by_category(self, category: str) -> Dict[str, BaseTool]:
        """
        Get all tools in a category.
        
        Args:
            category: Tool category
            
        Returns:
            Dictionary of tools in category
        """
        return {
            name: tool for name, tool in self.tools.items()
            if tool.category == category
        }
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all tools with their schemas.
        
        Returns:
            List of tool schemas
        """
        return [tool.get_schema() for tool in self.tools.values()]
