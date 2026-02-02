"""
Dynamic Prompt Manager Module

Manages dynamic prompts retrieved from the database.
"""

import logging
from typing import Dict, Any, List, Optional

from .system_prompts import get_system_prompt, get_linkedin_prompt


logger = logging.getLogger(__name__)


class DynamicPromptManager:
    """
    Manages dynamic prompts based on context.
    
    Retrieves context-specific prompts from database and
    augments static prompts with dynamic content.
    """
    
    def __init__(self):
        """Initialize the dynamic prompt manager"""
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._workflow_context: Dict[str, Any] = {}
        
        logger.info("DynamicPromptManager initialized")
    
    async def get_prompt(
        self,
        category: str = "general",
        intent_type: str = None,
        user_context: Dict[str, Any] = None
    ) -> str:
        """
        Get the appropriate prompt for the context.
        
        Args:
            category: Prompt category (linkedin, youtube, general)
            intent_type: Specific intent type
            user_context: User-specific context
            
        Returns:
            Complete prompt string
        """
        base_prompt = self._get_base_prompt(category)
        
        dynamic_content = await self._get_dynamic_content(
            category=category,
            intent_type=intent_type,
            user_context=user_context
        )
        
        if dynamic_content:
            base_prompt += "\n\n## Dynamic Instructions\n\n"
            base_prompt += dynamic_content
        
        return base_prompt
    
    def _get_base_prompt(self, category: str) -> str:
        """
        Get the base prompt for a category.
        
        Args:
            category: Prompt category
            
        Returns:
            Base prompt string
        """
        prompts = {
            "general": get_system_prompt(),
            "linkedin": get_linkedin_prompt(),
            "youtube": get_system_prompt("You are a YouTube research expert"),
            "research": get_system_prompt("You are a research assistant")
        }
        
        return prompts.get(category, prompts["general"])
    
    async def _get_dynamic_content(
        self,
        category: str,
        intent_type: str = None,
        user_context: Dict[str, Any] = None
    ) -> str:
        """
        Get dynamic content from database or context.
        
        Args:
            category: Prompt category
            intent_type: Specific intent
            user_context: User context
            
        Returns:
            Dynamic content string
        """
        dynamic_parts = []
        
        if intent_type:
            intent_prompts = self._get_intent_prompts()
            if intent_type in intent_prompts:
                dynamic_parts.append(intent_prompts[intent_type])
        
        if user_context:
            context_str = self._format_user_context(user_context)
            if context_str:
                dynamic_parts.append(context_str)
        
        workflow_info = self._get_workflow_context()
        if workflow_info:
            dynamic_parts.append(workflow_info)
        
        return "\n\n".join(dynamic_parts)
    
    def _get_intent_prompts(self) -> Dict[str, str]:
        """
        Get prompts for specific intents.
        
        Returns:
            Dictionary of intent prompts
        """
        return {
            "connection_request": """When sending connection requests:
- Always include a personalized note
- Mention something specific from their profile
- Explain why you want to connect
- Keep it concise (under 200 characters)
- Avoid generic templates""",
            
            "send_message": """When sending messages:
- Personalize based on recent activity or profile
- Provide value upfront
- Be clear about your purpose
- End with a clear call-to-action or question""",
            
            "search_people": """When searching for people:
- Use specific keywords for titles and companies
- Consider location for local searches
- Sort by relevance for best results
- Verify profile quality before engaging""",
            
            "visit_profile": """When visiting profiles:
- Extract key information: name, title, company, location
- Note any shared connections or interests
- Look for recent activity or posts
- Prepare relevant talking points"""
        }
    
    def _format_user_context(self, context: Dict[str, Any]) -> str:
        """
        Format user context into a string.
        
        Args:
            context: User context dictionary
            
        Returns:
            Formatted context string
        """
        if not context:
            return ""
        
        parts = []
        
        if "preferences" in context:
            prefs = context["preferences"]
            if "tone" in prefs:
                parts.append(f"User prefers a {prefs['tone']} tone")
            if "industries" in prefs:
                parts.append(f"Focus on industries: {', '.join(prefs['industries'])}")
        
        if "last_tasks" in context:
            tasks = context["last_tasks"][-3:]
            if tasks:
                parts.append(f"Recent tasks: {', '.join(tasks)}")
        
        return "User Context: " + " | ".join(parts) if parts else ""
    
    def _get_workflow_context(self) -> str:
        """
        Get context from successful workflows.
        
        Returns:
            Workflow context string
        """
        if not self._workflow_context:
            return ""
        
        parts = ["Learned Patterns:"]
        
        for intent, info in self._workflow_context.items():
            parts.append(f"- {intent}: {info.get('summary', 'Successful pattern')}")
        
        return "\n".join(parts)
    
    def add_workflow_context(
        self,
        intent_type: str,
        workflow_info: Dict[str, Any]
    ):
        """
        Add workflow information to context.
        
        Args:
            intent_type: Type of intent
            workflow_info: Workflow details
        """
        self._workflow_context[intent_type] = workflow_info
        logger.debug(f"Added workflow context for: {intent_type}")
    
    def clear_context(self):
        """Clear all dynamic context"""
        self._workflow_context.clear()
        self._cache.clear()
        logger.info("Dynamic prompt context cleared")
