"""
Embedding Store Module

This module provides hybrid embedding storage using sentence transformers
for semantic search combined with SQLite FTS5 for keyword-based search.
"""

import os
import logging
import pickle
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import numpy as np

from sentence_transformers import SentenceTransformer

from .database import Database, json_dumps


logger = logging.getLogger(__name__)


class EmbeddingStore:
    """
    Hybrid embedding store combining semantic search with keyword matching.
    
    This class provides:
    - Sentence transformer embeddings for semantic similarity
    - SQLite FTS5 full-text search for keyword matching
    - Hybrid search combining both approaches
    - Efficient storage using pickle for embeddings in SQLite
    """
    
    DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384
    
    def __init__(self, db: Database, embedding_model: str = None):
        """
        Initialize the embedding store.
        
        Args:
            db: Database instance for storage
            embedding_model: Sentence transformer model name
        """
        self.db = db
        self.model_name = embedding_model or os.getenv(
            "EMBEDDING_MODEL", self.DEFAULT_EMBEDDING_MODEL
        )
        self._model: Optional[SentenceTransformer] = None
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the embedding model"""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding
        """
        embedding = self.model.encode(text).tolist()
        return embedding
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(texts).tolist()
        return embeddings
    
    async def store_embedding(
        self,
        content_id: int,
        table_name: str,
        content: str,
        embedding: List[float] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        Store content with its embedding.
        
        Args:
            content_id: ID of the content in the source table
            table_name: Name of the source table
            content: Text content to embed
            embedding: Pre-computed embedding (optional)
            metadata: Additional metadata to store
        """
        if embedding is None:
            embedding = await self.embed_text(content)
        
        embedding_blob = pickle.dumps(np.array(embedding))
        metadata_json = json_dumps(metadata) if metadata else None
        
        await self.db.execute(
            f"""
            INSERT INTO embeddings (content_id, table_name, content, embedding, metadata)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(content_id, table_name) DO UPDATE SET
                content = excluded.content,
                embedding = excluded.embedding,
                metadata = excluded.metadata,
                updated_at = CURRENT_TIMESTAMP
            """,
            (content_id, table_name, content, embedding_blob, metadata_json)
        )
        
        logger.debug(f"Stored embedding for {table_name}:{content_id}")
    
    async def search_similar(
        self,
        query: str,
        table_name: str,
        limit: int = 10,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar content using semantic embeddings.
        
        Args:
            query: Search query
            table_name: Table to search in
            limit: Maximum number of results
            threshold: Minimum similarity threshold (0-1)
            
        Returns:
            List of matching records with similarity scores
        """
        query_embedding = await self.embed_text(query)
        
        results = await self.db.fetchall(
            f"""
            SELECT 
                content_id,
                content,
                metadata,
                (
                    1 - (
                        embedding <=> CAST(? AS BLOB)
                    )
                ) as similarity
            FROM embeddings
            WHERE table_name = ?
            ORDER BY similarity DESC
            LIMIT ?
            """,
            (pickle.dumps(np.array(query_embedding)), table_name, limit)
        )
        
        filtered_results = [
            {**r, "similarity": float(r["similarity"])}
            for r in results
            if r["similarity"] >= threshold
        ]
        
        return filtered_results
    
    async def search_keyword(
        self,
        query: str,
        table_name: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for content using keyword matching (FTS5).
        
        Args:
            query: Search query (keywords)
            table_name: Table to search in
            limit: Maximum number of results
            
        Returns:
            List of matching records with relevance scores
        """
        keywords = query.lower().split()
        keyword_conditions = " OR ".join(
            f'content MATCH "{keyword}"'
            for keyword in keywords
            if keyword
        )
        
        if not keyword_conditions:
            return []
        
        results = await self.db.fetchall(
            f"""
            SELECT 
                content_id,
                content,
                bm25(workflows_fts) as relevance
            FROM workflows_fts
            WHERE {keyword_conditions}
            AND content_id IN (
                SELECT rowid FROM workflows WHERE category = ?
            )
            ORDER BY relevance ASC
            LIMIT ?
            """,
            (table_name, limit)
        )
        
        return results
    
    async def hybrid_search(
        self,
        query: str,
        table_name: str,
        limit: int = 10,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword search.
        
        Args:
            query: Search query
            table_name: Table to search in
            limit: Maximum number of results
            semantic_weight: Weight for semantic similarity (0-1)
            keyword_weight: Weight for keyword relevance (0-1)
            
        Returns:
            List of results with combined scores
        """
        semantic_results = await self.search_similar(
            query, table_name, limit=limit * 2
        )
        
        keyword_results = await self.search_keyword(
            query, table_name, limit=limit * 2
        )
        
        combined_scores = {}
        
        for result in semantic_results:
            content_id = result["content_id"]
            combined_scores[content_id] = {
                **result,
                "semantic_score": result["similarity"],
                "keyword_score": 0,
                "combined_score": result["similarity"] * semantic_weight
            }
        
        for result in keyword_results:
            content_id = result["content_id"]
            if content_id in combined_scores:
                combined_scores[content_id]["keyword_score"] = 1.0 / (result["relevance"] + 1)
                combined_scores[content_id]["combined_score"] = (
                    combined_scores[content_id]["semantic_score"] * semantic_weight +
                    combined_scores[content_id]["keyword_score"] * keyword_weight
                )
            else:
                combined_scores[content_id] = {
                    **result,
                    "semantic_score": 0,
                    "keyword_score": 1.0 / (result["relevance"] + 1),
                    "combined_score": (1.0 / (result["relevance"] + 1)) * keyword_weight
                }
        
        sorted_results = sorted(
            combined_scores.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        return sorted_results[:limit]
    
    async def delete_embeddings(
        self,
        content_id: int,
        table_name: str
    ):
        """
        Delete embeddings for specific content.
        
        Args:
            content_id: ID of the content
            table_name: Name of the source table
        """
        await self.db.execute(
            "DELETE FROM embeddings WHERE content_id = ? AND table_name = ?",
            (content_id, table_name)
        )
    
    async def cleanup_orphaned_embeddings(self):
        """
        Remove embeddings that no longer have matching content.
        """
        await self.db.execute(
            """
            DELETE FROM embeddings 
            WHERE (content_id, table_name) NOT IN (
                SELECT id, 'workflows' FROM workflows
            )
            """
        )
        logger.info("Cleaned up orphaned embeddings")
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings from this model.
        
        Returns:
            Integer dimension
        """
        return self.EMBEDDING_DIMENSION


class KeywordExtractor:
    """
    Extract keywords from text for keyword-based search.
    """
    
    STOPWORDS = {
        'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
        'can', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'as', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'under', 'again', 'further', 'then', 'once',
        'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also',
        'now', 'this', 'that', 'these', 'those', 'i', 'me', 'my', 'we', 'our',
        'you', 'your', 'he', 'him', 'his', 'she', 'her', 'it', 'its', 'they',
        'them', 'their', 'what', 'which', 'who', 'whom', 'how', 'please',
        'thanks', 'thank', 'sorry', 'help', 'make', 'want', 'like', 'know',
        'think', 'take', 'see', 'come', 'want', 'use', 'find', 'give', 'tell'
    }
    
    def __init__(self, max_keywords: int = 10):
        """
        Initialize keyword extractor.
        
        Args:
            max_keywords: Maximum keywords to extract
        """
        self.max_keywords = max_keywords
    
    def extract(self, text: str) -> List[str]:
        """
        Extract keywords from text.
        
        Args:
            text: Input text
            
        Returns:
            List of extracted keywords
        """
        import re
        
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        
        keywords = [
            word for word in words
            if word not in self.STOPWORDS and len(word) > 2
        ]
        
        from collections import Counter
        word_counts = Counter(keywords)
        
        return [word for word, _ in word_counts.most_common(self.max_keywords)]
    
    def extract_as_string(self, text: str) -> str:
        """
        Extract keywords and return as comma-separated string.
        
        Args:
            text: Input text
            
        Returns:
            Comma-separated keyword string
        """
        keywords = self.extract(text)
        return ",".join(keywords)
