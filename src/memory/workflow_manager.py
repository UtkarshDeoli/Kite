"""
Workflow Manager Module

This module manages the storage and retrieval of successful workflows.
It handles workflow recording, retrieval, success tracking, and learning.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from .database import Database, json_dumps, json_loads
from .embedding_store import EmbeddingStore, KeywordExtractor


logger = logging.getLogger(__name__)


@dataclass
class Workflow:
    """Represents a stored workflow"""
    id: Optional[int]
    user_id: int
    category: str
    intent_type: str
    keywords: str
    original_prompt: str
    summary: str
    steps: List[Dict[str, Any]]
    parameters: Dict[str, Any]
    success_rate: float
    success_count: int
    total_count: int
    rating: int
    is_template: bool
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "category": self.category,
            "intent_type": self.intent_type,
            "keywords": self.keywords,
            "original_prompt": self.original_prompt,
            "summary": self.summary,
            "steps": self.steps,
            "parameters": self.parameters,
            "success_rate": self.success_rate,
            "success_count": self.success_count,
            "total_count": self.total_count,
            "rating": self.rating,
            "is_template": self.is_template,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class WorkflowManager:
    """
    Manages workflow storage, retrieval, and learning.
    
    This class provides:
    - Recording successful workflow executions
    - Retrieving similar workflows based on prompts
    - Tracking success rates and ratings
    - Managing workflow templates
    - Learning from user feedback
    """
    
    def __init__(self, db: Database, embedding_store: EmbeddingStore = None):
        """
        Initialize the workflow manager.
        
        Args:
            db: Database instance
            embedding_store: Optional embedding store for semantic search
        """
        self.db = db
        self.embedding_store = embedding_store
        self.keyword_extractor = KeywordExtractor(max_keywords=15)
    
    async def record_workflow(
        self,
        user_id: int,
        category: str,
        intent_type: str,
        original_prompt: str,
        summary: str,
        steps: List[Dict[str, Any]],
        parameters: Dict[str, Any] = None,
        is_template: bool = False,
        rating: int = 5
    ) -> int:
        """
        Record a new successful workflow.
        
        Args:
            user_id: ID of the user who executed the workflow
            category: Category (e.g., 'linkedin', 'youtube')
            intent_type: Type of intent (e.g., 'connection_request')
            original_prompt: The original user prompt
            summary: Brief summary of what was done
            steps: List of steps executed
            parameters: Parameters used
            is_template: Whether this can be used as a template
            rating: User rating (1-5)
            
        Returns:
            ID of the recorded workflow
        """
        keywords = self.keyword_extractor.extract_as_string(original_prompt)
        
        workflow_id = await self.db.insert(
            """
            INSERT INTO workflows (
                user_id, category, intent_type, keywords, original_prompt,
                summary, steps, parameters, success_rate, success_count,
                total_count, rating, is_template
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1.0, 1, 1, ?, ?)
            """,
            (
                user_id, category, intent_type, keywords, original_prompt,
                summary, json_dumps(steps), json_dumps(parameters or {}),
                rating, 1 if is_template else 0
            )
        )
        
        if self.embedding_store:
            await self.embedding_store.store_embedding(
                content_id=workflow_id,
                table_name="workflows",
                content=f"{original_prompt} {summary}",
                metadata={
                    "category": category,
                    "intent_type": intent_type,
                    "keywords": keywords
                }
            )
        
        logger.info(f"Recorded workflow {workflow_id}: {summary}")
        return workflow_id
    
    async def update_workflow_success(
        self,
        workflow_id: int,
        was_successful: bool,
        new_steps: List[Dict[str, Any]] = None
    ):
        """
        Update workflow success information.
        
        Args:
            workflow_id: ID of the workflow
            was_successful: Whether the execution was successful
            new_steps: Updated steps if different
        """
        workflow = await self.db.fetchone(
            "SELECT * FROM workflows WHERE id = ?",
            (workflow_id,)
        )
        
        if not workflow:
            logger.warning(f"Workflow {workflow_id} not found for update")
            return
        
        success_count = workflow["success_count"] + (1 if was_successful else 0)
        total_count = workflow["total_count"] + 1
        success_rate = success_count / total_count
        
        update_query = """
            UPDATE workflows 
            SET success_count = ?, total_count = ?, success_rate = ?,
                updated_at = CURRENT_TIMESTAMP
        """
        params = [success_count, total_count, success_rate]
        
        if new_steps:
            update_query += ", steps = ?"
            params.append(json_dumps(new_steps))
        
        update_query += " WHERE id = ?"
        params.append(workflow_id)
        
        await self.db.execute(update_query, tuple(params))
        logger.debug(f"Updated workflow {workflow_id}: success_rate={success_rate:.2f}")
    
    async def get_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """
        Get a specific workflow by ID.
        
        Args:
            workflow_id: ID of the workflow
            
        Returns:
            Workflow object or None
        """
        row = await self.db.fetchone(
            "SELECT * FROM workflows WHERE id = ?",
            (workflow_id,)
        )
        
        if row:
            return self._row_to_workflow(row)
        return None
    
    async def find_similar_workflows(
        self,
        user_id: int,
        prompt: str,
        category: str = None,
        limit: int = 5
    ) -> List[Workflow]:
        """
        Find workflows similar to the given prompt.
        
        Uses hybrid search combining semantic similarity with keyword matching.
        
        Args:
            user_id: ID of the user (to find personal workflows first)
            prompt: User's prompt to match against
            category: Optional category filter
            limit: Maximum number of results
            
        Returns:
            List of matching workflows sorted by relevance
        """
        query = """
            SELECT * FROM workflows 
            WHERE user_id = ? 
        """
        params = [user_id]
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY success_rate DESC, success_count DESC, rating DESC LIMIT ?"
        params.append(limit * 2)
        
        rows = await self.db.fetchall(query, tuple(params))
        
        keywords = self.keyword_extractor.extract(prompt)
        
        workflows = []
        for row in rows:
            workflow_keywords = set(row["keywords"].split(","))
            keyword_matches = len(keywords & workflow_keywords)
            
            if keyword_matches > 0:
                workflows.append(self._row_to_workflow(row))
        
        if self.embedding_store and len(workflows) < limit:
            semantic_results = await self.embedding_store.search_similar(
                query=prompt,
                table_name="workflows",
                limit=limit
            )
            
            for result in semantic_results:
                workflow = await self.get_workflow(result["content_id"])
                if workflow and workflow.id not in [w.id for w in workflows]:
                    workflows.append(workflow)
                    if len(workflows) >= limit:
                        break
        
        return workflows[:limit]
    
    async def get_best_workflow(
        self,
        user_id: int,
        intent_type: str,
        category: str = None
    ) -> Optional[Workflow]:
        """
        Get the best performing workflow for a specific intent.
        
        Args:
            user_id: ID of the user
            intent_type: Type of intent
            category: Optional category filter
            
        Returns:
            Best workflow or None
        """
        query = """
            SELECT * FROM workflows 
            WHERE user_id = ? AND intent_type = ?
        """
        params = [user_id, intent_type]
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY success_rate DESC, success_count DESC LIMIT 1"
        
        row = await self.db.fetchone(query, tuple(params))
        
        if row:
            return self._row_to_workflow(row)
        return None
    
    async def get_workflow_templates(
        self,
        category: str = None,
        intent_type: str = None,
        limit: int = 10
    ) -> List[Workflow]:
        """
        Get workflow templates for sharing/reuse.
        
        Args:
            category: Optional category filter
            intent_type: Optional intent type filter
            limit: Maximum number of results
            
        Returns:
            List of template workflows
        """
        query = """
            SELECT * FROM workflows 
            WHERE is_template = 1
        """
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if intent_type:
            query += " AND intent_type = ?"
            params.append(intent_type)
        
        query += " ORDER BY success_rate DESC, rating DESC LIMIT ?"
        params.append(limit)
        
        rows = await self.db.fetchall(query, tuple(params))
        
        return [self._row_to_workflow(row) for row in rows]
    
    async def convert_to_template(
        self,
        workflow_id: int,
        user_id: int
    ) -> bool:
        """
        Convert a personal workflow to a template.
        
        Args:
            workflow_id: ID of the workflow
            user_id: ID of the user (for verification)
            
        Returns:
            True if successful
        """
        result = await self.db.execute(
            """
            UPDATE workflows 
            SET is_template = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (workflow_id, user_id)
        )
        
        return result.rowcount > 0
    
    async def record_execution(
        self,
        workflow_id: int,
        user_id: int,
        status: str,
        step_results: List[Dict[str, Any]] = None,
        error_message: str = None
    ) -> int:
        """
        Record a workflow execution.
        
        Args:
            workflow_id: ID of the workflow
            user_id: ID of the user
            status: Execution status
            step_results: Results of each step
            error_message: Error message if failed
            
        Returns:
            Execution ID
        """
        execution_id = await self.db.insert(
            """
            INSERT INTO workflow_executions (
                workflow_id, user_id, status, step_results, error_message
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                workflow_id, user_id, status,
                json_dumps(step_results) if step_results else None,
                error_message
            )
        )
        
        if status in ["completed", "failed"]:
            was_successful = status == "completed"
            await self.update_workflow_success(
                workflow_id, was_successful, step_results
            )
            
            if was_successful:
                await self.db.execute(
                    """
                    UPDATE workflow_executions 
                    SET completed_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                    """,
                    (execution_id,)
                )
        
        return execution_id
    
    async def get_execution_history(
        self,
        workflow_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get execution history for a workflow.
        
        Args:
            workflow_id: ID of the workflow
            limit: Maximum number of results
            
        Returns:
            List of execution records
        """
        return await self.db.fetchall(
            """
            SELECT * FROM workflow_executions 
            WHERE workflow_id = ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (workflow_id, limit)
        )
    
    async def get_statistics(
        self,
        user_id: int = None,
        category: str = None
    ) -> Dict[str, Any]:
        """
        Get workflow statistics.
        
        Args:
            user_id: Optional user filter
            category: Optional category filter
            
        Returns:
            Statistics dictionary
        """
        query = "SELECT COUNT(*) as total FROM workflows"
        count_params = []
        
        if user_id or category:
            query += " WHERE "
            conditions = []
            if user_id:
                conditions.append("user_id = ?")
                count_params.append(user_id)
            if category:
                conditions.append("category = ?")
                count_params.append(category)
            query += " AND ".join(conditions)
        
        total = await self.db.fetchone(query, tuple(count_params) if count_params else None)
        
        stats = {
            "total_workflows": total["total"] if total else 0,
            "successful_workflows": 0,
            "average_success_rate": 0.0,
            "top_categories": {},
            "top_intents": {}
        }
        
        success_query = """
            SELECT COUNT(*) as count FROM workflows 
            WHERE success_rate >= 0.8
        """
        success_params = []
        if user_id or category:
            success_query += " WHERE "
            conditions = []
            if user_id:
                conditions.append("user_id = ?")
                success_params.append(user_id)
            if category:
                conditions.append("category = ?")
                success_params.append(category)
            success_query += " AND ".join(conditions)
        
        success = await self.db.fetchone(success_query, tuple(success_params) if success_params else None)
        stats["successful_workflows"] = success["count"] if success else 0
        
        avg_query = "SELECT AVG(success_rate) as avg FROM workflows"
        avg_params = []
        if user_id or category:
            avg_query += " WHERE "
            conditions = []
            if user_id:
                conditions.append("user_id = ?")
                avg_params.append(user_id)
            if category:
                conditions.append("category = ?")
                avg_params.append(category)
            avg_query += " AND ".join(conditions)
        
        avg = await self.db.fetchone(avg_query, tuple(avg_params) if avg_params else None)
        stats["average_success_rate"] = avg["avg"] if avg and avg["avg"] else 0.0
        
        return stats
    
    def _row_to_workflow(self, row: Dict[str, Any]) -> Workflow:
        """Convert database row to Workflow object"""
        return Workflow(
            id=row["id"],
            user_id=row["user_id"],
            category=row["category"],
            intent_type=row["intent_type"],
            keywords=row["keywords"],
            original_prompt=row["original_prompt"],
            summary=row["summary"],
            steps=json_loads(row["steps"]),
            parameters=json_loads(row["parameters"]),
            success_rate=row["success_rate"],
            success_count=row["success_count"],
            total_count=row["total_count"],
            rating=row["rating"],
            is_template=bool(row["is_template"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
        )
