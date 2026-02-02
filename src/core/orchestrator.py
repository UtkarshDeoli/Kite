"""
Orchestrator Module

The main agent orchestrator that coordinates all components.
Handles intent classification, task planning, and workflow management.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from ..llm.base import BaseLLMProvider, Message, MessageRole
from ..memory.database import Database
from ..memory.workflow_manager import WorkflowManager, Workflow
from ..prompts import get_system_prompt, DynamicPromptManager


logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a task"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a task to be executed"""
    id: str
    user_id: int
    intent_type: str
    category: str
    original_prompt: str
    parameters: Dict[str, Any]
    status: TaskStatus
    steps: List[Dict[str, Any]]
    current_step: int
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class Orchestrator:
    """
    Main orchestrator for the agent system.
    
    Responsibilities:
    - Classify user intent
    - Plan and execute tasks
    - Manage conversation state
    - Store and retrieve workflows
    - Coordinate with tools
    """
    
    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        db: Database,
        workflow_manager: WorkflowManager,
        prompt_manager: DynamicPromptManager = None,
        enable_learning: bool = True
    ):
        """
        Initialize the orchestrator.
        
        Args:
            llm_provider: LLM provider for AI operations
            db: Database instance
            workflow_manager: Workflow manager for learning
            prompt_manager: Dynamic prompt manager
            enable_learning: Whether to learn from successful tasks
        """
        self.llm = llm_provider
        self.db = db
        self.workflow_manager = workflow_manager
        self.prompt_manager = prompt_manager
        self.enable_learning = enable_learning
        
        self.tasks: Dict[str, Task] = {}
        self.active_tasks: Dict[str, Task] = {}
        
        logger.info("Orchestrator initialized")
    
    async def process_message(
        self,
        user_id: int,
        chat_id: int,
        username: Optional[str],
        message: str,
        send_progress: callable = None
    ) -> str:
        """
        Process an incoming user message.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            username: Username
            message: Message text
            send_progress: Callback for progress updates
            
        Returns:
            Response text
        """
        task_id = str(uuid.uuid4())[:8]
        
        logger.info(f"Processing message for user {user_id}: {message[:100]}")
        
        try:
            intent_type, category = await self._classify_intent(message)
            
            similar_workflows = await self.workflow_manager.find_similar_workflows(
                user_id=user_id,
                prompt=message,
                category=category,
                limit=3
            )
            
            task = await self._create_task(
                task_id=task_id,
                user_id=user_id,
                intent_type=intent_type,
                category=category,
                original_prompt=message,
                similar_workflows=similar_workflows
            )
            
            self.tasks[task_id] = task
            
            execution_result = await self._execute_task(
                task=task,
                send_progress=send_progress
            )
            
            if self.enable_learning and execution_result["success"]:
                await self._learn_from_execution(
                    task=task,
                    result=execution_result
                )
            
            return execution_result["response"]
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return f"I encountered an error: {str(e)}"
    
    async def _classify_intent(
        self,
        message: str
    ) -> tuple[str, str]:
        """
        Classify the intent of a message.
        
        Args:
            message: Message text
            
        Returns:
            Tuple of (intent_type, category)
        """
        message_lower = message.lower()
        
        if "linkedin" in message_lower:
            category = "linkedin"
            
            if "connection" in message_lower or "connect" in message_lower:
                intent_type = "connection_request"
            elif "message" in message_lower or "send" in message_lower:
                intent_type = "send_message"
            elif "profile" in message_lower:
                intent_type = "visit_profile"
            elif "search" in message_lower or "find" in message_lower:
                intent_type = "search_people"
            else:
                intent_type = "general"
        elif "youtube" in message_lower or "video" in message_lower:
            category = "youtube"
            
            if "transcript" in message_lower or "summary" in message_lower:
                intent_type = "video_research"
            else:
                intent_type = "video_download"
        else:
            category = "general"
            
            if "search" in message_lower or "research" in message_lower:
                intent_type = "web_search"
            elif "visit" in message_lower or "open" in message_lower:
                intent_type = "web_browse"
            else:
                intent_type = "general"
        
        return intent_type, category
    
    async def _create_task(
        self,
        task_id: str,
        user_id: int,
        intent_type: str,
        category: str,
        original_prompt: str,
        similar_workflows: List[Workflow]
    ) -> Task:
        """
        Create a new task.
        
        Args:
            task_id: Unique task ID
            user_id: User ID
            intent_type: Classified intent
            category: Task category
            original_prompt: Original user prompt
            similar_workflows: Similar successful workflows
            
        Returns:
            Task object
        """
        workflow_context = ""
        if similar_workflows:
            workflow_context = "\n\nSimilar successful workflows:\n"
            for wf in similar_workflows:
                workflow_context += f"- {wf.summary} (success rate: {wf.success_rate:.0%})\n"
        
        parameters = {
            "workflow_context": workflow_context,
            "similar_workflows": [wf.to_dict() for wf in similar_workflows]
        }
        
        steps = await self._plan_steps(
            intent_type=intent_type,
            category=category,
            prompt=original_prompt,
            similar_workflows=similar_workflows
        )
        
        return Task(
            id=task_id,
            user_id=user_id,
            intent_type=intent_type,
            category=category,
            original_prompt=original_prompt,
            parameters=parameters,
            status=TaskStatus.PENDING,
            steps=steps,
            current_step=0,
            result=None,
            error=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None
        )
    
    async def _plan_steps(
        self,
        intent_type: str,
        category: str,
        prompt: str,
        similar_workflows: List[Workflow]
    ) -> List[Dict[str, Any]]:
        """
        Plan the steps for task execution.
        
        Args:
            intent_type: Type of intent
            category: Task category
            prompt: User prompt
            similar_workflows: Similar workflows to参考
            
        Returns:
            List of steps to execute
        """
        if similar_workflows and similar_workflows[0].steps:
            return similar_workflows[0].steps
        
        base_steps = {
            "connection_request": [
                {"action": "search_people", "params": {"query": "extract from prompt"}},
                {"action": "visit_profile", "params": {"profile_url": "from search"}},
                {"action": "send_connection", "params": {"note": "personalized"}}
            ],
            "send_message": [
                {"action": "find_profile", "params": {"query": "extract from prompt"}},
                {"action": "send_message", "params": {"content": "compose message"}}
            ],
            "visit_profile": [
                {"action": "navigate", "params": {"url": "extract from prompt"}},
                {"action": "extract_info", "params": {"fields": ["name", "title", "company"]}}
            ],
            "search_people": [
                {"action": "search_people", "params": {"query": "extract from prompt"}},
                {"action": "filter_results", "params": {"criteria": "extract from prompt"}}
            ],
            "video_research": [
                {"action": "download_transcript", "params": {"url": "extract from prompt"}},
                {"action": "summarize", "params": {"length": "medium"}}
            ],
            "web_search": [
                {"action": "navigate", "params": {"url": "search engine"}},
                {"action": "extract_info", "params": {"query": "extract from prompt"}}
            ],
            "general": [
                {"action": "analyze_request", "params": {}},
                {"action": "execute_browser_action", "params": {"action": "determine from prompt"}}
            ]
        }
        
        return base_steps.get(intent_type, base_steps["general"])
    
    async def _execute_task(
        self,
        task: Task,
        send_progress: callable = None
    ) -> Dict[str, Any]:
        """
        Execute a task.
        
        Args:
            task: Task to execute
            send_progress: Progress callback
            
        Returns:
            Execution result dictionary
        """
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()
        
        step_results = []
        all_successful = True
        
        total_steps = len(task.steps)
        
        for i, step in enumerate(task.steps):
            task.current_step = i
            
            if send_progress:
                progress = (i / total_steps) * 100
                await send_progress(
                    task_id=task.id,
                    progress=progress,
                    message=f"Executing step {i+1}/{total_steps}: {step.get('action', 'unknown')}"
                )
            
            try:
                step_result = await self._execute_step(task, step)
                step_results.append({
                    "step": i,
                    "action": step.get("action"),
                    "success": True,
                    "result": step_result
                })
                
            except Exception as e:
                logger.error(f"Step {i} failed: {e}")
                step_results.append({
                    "step": i,
                    "action": step.get("action"),
                    "success": False,
                    "error": str(e)
                })
                all_successful = False
                task.error = str(e)
                break
        
        task.status = TaskStatus.COMPLETED if all_successful else TaskStatus.FAILED
        task.completed_at = datetime.now()
        task.result = {"step_results": step_results}
        
        response = await self._generate_response(
            task=task,
            step_results=step_results
        )
        
        return {
            "success": all_successful,
            "response": response,
            "task": task
        }
    
    async def _execute_step(
        self,
        task: Task,
        step: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single step.
        
        Args:
            task: Parent task
            step: Step to execute
            
        Returns:
            Step result
        """
        action = step.get("action", "unknown")
        params = step.get("params", {})
        
        logger.info(f"Executing step: {action} with params: {params}")
        
        return {
            "action": action,
            "message": f"Executed {action}",
            "success": True
        }
    
    async def _generate_response(
        self,
        task: Task,
        step_results: List[Dict[str, Any]]
    ) -> str:
        """
        Generate the final response for a task.
        
        Args:
            task: Completed task
            step_results: Results of each step
            
        Returns:
            Response text
        """
        if task.status == TaskStatus.COMPLETED:
            successful_steps = [s for s in step_results if s.get("success")]
            
            response = f"✅ Task completed successfully!\n\n"
            response += f"Executed {len(successful_steps)} steps for: {task.original_prompt[:100]}\n\n"
            
            for step in successful_steps[:3]:
                response += f"• {step.get('message', 'Done')}\n"
            
            if len(successful_steps) > 3:
                response += f"... and {len(successful_steps) - 3} more steps\n"
            
            return response
        else:
            return f"❌ Task failed: {task.error}\n\nPlease try again or rephrase your request."
    
    async def _learn_from_execution(
        self,
        task: Task,
        result: Dict[str, Any]
    ):
        """
        Learn from a successful execution by storing the workflow.
        
        Args:
            task: Completed task
            result: Execution result
        """
        try:
            await self.workflow_manager.record_workflow(
                user_id=task.user_id,
                category=task.category,
                intent_type=task.intent_type,
                original_prompt=task.original_prompt,
                summary=result["response"][:200] if "response" in result else task.original_prompt[:200],
                steps=task.steps,
                parameters=task.parameters,
                rating=5
            )
            
            logger.info(f"Learned from successful execution: {task.id}")
            
        except Exception as e:
            logger.error(f"Failed to learn from execution: {e}")
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task status dictionary or None
        """
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return {
            "id": task.id,
            "status": task.status.value,
            "current_step": task.current_step + 1,
            "total_steps": len(task.steps),
            "progress": (task.current_step / len(task.steps)) * 100 if task.steps else 0
        }
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if cancelled
        """
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.IN_PROGRESS:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            return True
        return False
