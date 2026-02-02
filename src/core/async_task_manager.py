"""
Async Task Manager Module

Manages asynchronous task execution with progress tracking.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Callable, Optional, Awaitable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of an async task"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AsyncTask:
    """Represents an asynchronous task"""
    id: str
    name: str
    status: TaskStatus
    progress: float
    message: str
    result: Any = None
    error: str = None
    progress_callback: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AsyncTaskManager:
    """
    Manages asynchronous task execution.
    
    Features:
    - Background task execution
    - Progress tracking and reporting
    - Task cancellation
    - Concurrency control
    """
    
    def __init__(
        self,
        max_concurrent: int = 5,
        max_queue_size: int = 100
    ):
        """
        Initialize the async task manager.
        
        Args:
            max_concurrent: Maximum concurrent tasks
            max_queue_size: Maximum queued tasks
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        self.tasks: Dict[str, AsyncTask] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("AsyncTaskManager initialized")
    
    async def start(self):
        """Start the task processing worker"""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._process_queue())
            logger.info("AsyncTaskManager worker started")
    
    async def stop(self):
        """Stop the task processing worker"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("AsyncTaskManager worker stopped")
    
    async def _process_queue(self):
        """Process tasks from the queue"""
        while self._running:
            try:
                coro, task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )
                
                async with self.semaphore:
                    try:
                        await coro
                    except Exception as e:
                        logger.error(f"Task execution error: {e}")
                    
                    self.task_queue.task_done()
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
    
    async def create_task(
        self,
        name: str,
        coro: Awaitable,
        progress_callback: Callable = None
    ) -> str:
        """
        Create a new task and queue it for execution.
        
        Args:
            name: Task name
            coro: Coroutine to execute
            progress_callback: Callback for progress updates
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())[:8]
        
        task = AsyncTask(
            id=task_id,
            name=name,
            status=TaskStatus.PENDING,
            progress=0.0,
            message="Task queued",
            progress_callback=progress_callback
        )
        
        self.tasks[task_id] = task
        
        await self.task_queue.put((coro, task))
        
        logger.info(f"Created task: {task_id} - {name}")
        return task_id
    
    async def run_task(
        self,
        name: str,
        coro: Awaitable,
        progress_callback: Callable = None
    ) -> AsyncTask:
        """
        Run a task immediately (bypasses queue).
        
        Args:
            name: Task name
            coro: Coroutine to execute
            progress_callback: Callback for progress updates
            
        Returns:
            Completed AsyncTask
        """
        task_id = str(uuid.uuid4())[:8]
        
        task = AsyncTask(
            id=task_id,
            name=name,
            status=TaskStatus.RUNNING,
            progress=0.0,
            message="Starting task",
            progress_callback=progress_callback,
            started_at=datetime.now()
        )
        
        self.tasks[task_id] = task
        
        try:
            async with self.semaphore:
                result = await coro
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.progress = 100.0
                task.message = "Task completed"
                
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.message = f"Task failed: {str(e)}"
            
            logger.error(f"Task {task_id} failed: {e}")
        
        task.completed_at = datetime.now()
        
        logger.info(f"Task {task_id} completed with status: {task.status.value}")
        return task
    
    def update_progress(
        self,
        task_id: str,
        progress: float,
        message: str
    ):
        """
        Update task progress.
        
        Args:
            task_id: Task ID
            progress: Progress percentage
            message: Progress message
        """
        task = self.tasks.get(task_id)
        if not task:
            return
        
        task.progress = progress
        task.message = message
        
        if task.progress_callback:
            try:
                task.progress_callback(task_id, progress, message)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if cancelled
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        task.message = "Task cancelled"
        
        logger.info(f"Task {task_id} cancelled")
        return True
    
    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        """
        Get task information.
        
        Args:
            task_id: Task ID
            
        Returns:
            AsyncTask or None
        """
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, AsyncTask]:
        """
        Get all tasks.
        
        Returns:
            Dictionary of all tasks
        """
        return self.tasks
    
    def get_running_tasks(self) -> list:
        """
        Get all currently running tasks.
        
        Returns:
            List of running tasks
        """
        return [
            task for task in self.tasks.values()
            if task.status == TaskStatus.RUNNING
        ]
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get task manager statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total": len(self.tasks),
            "pending": sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING),
            "running": sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING),
            "completed": sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED),
            "queue_size": self.task_queue.qsize()
        }
    
    async def cleanup_completed(self, max_age_hours: int = 24):
        """
        Remove completed tasks older than max_age.
        
        Args:
            max_age_hours: Maximum age in hours
        """
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        removed = 0
        
        for task_id, task in list(self.tasks.items()):
            if task.completed_at and task.completed_at.timestamp() < cutoff:
                del self.tasks[task_id]
                removed += 1
        
        if removed:
            logger.info(f"Cleaned up {removed} completed tasks")
