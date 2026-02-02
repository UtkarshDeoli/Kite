"""
LinkedIn Prompt Templates Module

Templates and prompts specific to LinkedIn operations.
"""

from typing import Dict, Any


class LinkedInPromptTemplates:
    """
    Prompt templates for LinkedIn-specific operations.
    """
    
    CONNECTION_REQUEST = """Send a connection request to {name} at {company}.

Profile Information:
- Name: {name}
- Title: {title}
- Company: {company}
- Location: {location}

Your connection note should:
1. Be personalized based on their profile
2. Mention a specific detail about their work
3. Explain why you want to connect
4. Be under 200 characters

Compose your connection note:"""
    
    MESSAGE_TEMPLATE = """Send a message to {name}.

Context: {context}
Message purpose: {purpose}

Guidelines:
- Be professional but friendly
- Get straight to the point
- Provide value
- Include a clear call-to-action

Compose your message:"""
    
    PROFILE_SUMMARY = """Extract and summarize the following LinkedIn profile information:

{profile_content}

Please provide:
1. Current role and company
2. Key skills and expertise
3. Recent experience or projects
4. Notable achievements
5. Potential connection angles"""
    
    SEARCH_QUERY = """Create a LinkedIn search query for:

Target: {target}
Criteria: {criteria}

Provide:
1. Optimized search keywords
2. Suggested filters
3. Expected results profile"""

    @staticmethod
    def format_template(template: str, **kwargs) -> str:
        """
        Format a template with provided values.
        
        Args:
            template: Template string
            **kwargs: Values to substitute
            
        Returns:
            Formatted template
        """
        return template.format(**kwargs)
