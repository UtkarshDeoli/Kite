"""
Database Management Module

This module provides SQLite database management with async support.
Handles connection pooling, migrations, and provides a clean API for database operations.
"""

import os
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from contextlib import asynccontextmanager
from datetime import datetime

import aiosqlite


logger = logging.getLogger(__name__)


class Database:
    """
    Async SQLite database manager with connection pooling.
    
    This class provides a clean interface for database operations with:
    - Async support via aiosqlite
    - Automatic connection management
    - Transaction support
    - Schema migration handling
    - Type-safe operations
    """
    
    def __init__(self, db_path: str = None, readonly: bool = False):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file
            readonly: Open database in read-only mode
        """
        self.db_path = db_path or os.getenv("DATABASE_PATH", "/app/data/agent.db")
        self.readonly = readonly
        self._pool: Optional[aiosqlite.Connection] = None
        self._initialized = False
        
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def get_connection(self) -> aiosqlite.Connection:
        """
        Get a database connection from the pool.
        
        Returns:
            Async SQLite connection
        """
        if self._pool is None:
            uri = f"file:{self.db_path}"
            if self.readonly:
                uri += "?mode=ro"
            
            self._pool = await aiosqlite.connect(
                uri,
                timeout=30.0,
                check_same_thread=False
            )
            
            self._pool.row_factory = sqlite3.Row
            await self._pool.execute("PRAGMA foreign_keys = ON")
            await self._pool.execute("PRAGMA journal_mode = WAL")
            await self._pool.execute("PRAGMA synchronous = NORMAL")
        
        return self._pool
    
    async def close(self):
        """Close all database connections"""
        if self._pool:
            await self._pool.close()
            self._pool = None
    
    async def initialize(self):
        """
        Initialize the database schema.
        Creates tables if they don't exist.
        """
        if self._initialized:
            return
        
        conn = await self.get_connection()
        
        schema_path = Path(__file__).parent.parent.parent / "database" / "schema.sql"
        
        if schema_path.exists():
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            await conn.executescript(schema_sql)
        else:
            logger.warning(f"Schema file not found at {schema_path}")
        
        self._initialized = True
        logger.info("Database initialized successfully")
    
    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for database transactions.
        
        Usage:
            async with db.transaction():
                await db.execute("INSERT INTO ...", params)
                await db.execute("UPDATE ...", params)
        """
        conn = await self.get_connection()
        try:
            await conn.execute("BEGIN TRANSACTION")
            yield conn
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
    
    async def execute(
        self,
        query: str,
        params: Tuple = None
    ) -> aiosqlite.Cursor:
        """
        Execute a single SQL statement.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            SQLite cursor
        """
        conn = await self.get_connection()
        return await conn.execute(query, params)
    
    async def executemany(
        self,
        query: str,
        params_list: List[Tuple]
    ) -> aiosqlite.Cursor:
        """
        Execute a SQL statement multiple times with different parameters.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
            
        Returns:
            SQLite cursor
        """
        conn = await self.get_connection()
        return await conn.executemany(query, params_list)
    
    async def fetchone(
        self,
        query: str,
        params: Tuple = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a query and fetch a single result.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Single result as dictionary or None
        """
        conn = await self.get_connection()
        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()
        await cursor.close()
        
        if row:
            return dict(row)
        return None
    
    async def fetchall(
        self,
        query: str,
        params: Tuple = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a query and fetch all results.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        conn = await self.get_connection()
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        
        return [dict(row) for row in rows]
    
    async def fetchmany(
        self,
        query: str,
        params: Tuple = None,
        size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Execute a query and fetch a batch of results.
        
        Args:
            query: SQL query string
            params: Query parameters
            size: Number of rows to fetch
            
        Returns:
            List of result dictionaries
        """
        conn = await self.get_connection()
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchmany(size)
        await cursor.close()
        
        return [dict(row) for row in rows]
    
    async def insert(
        self,
        query: str,
        params: Tuple = None
    ) -> int:
        """
        Execute an INSERT statement and return the row ID.
        
        Args:
            query: SQL INSERT string
            params: Query parameters
            
        Returns:
            Last inserted row ID
        """
        conn = await self.get_connection()
        cursor = await conn.execute(query, params)
        await conn.commit()
        return cursor.lastrowid
    
    async def upsert(
        self,
        query: str,
        params: Tuple = None
    ) -> int:
        """
        Execute an INSERT with ON CONFLICT clause and return the row ID.
        
        Args:
            query: SQL UPSERT string
            params: Query parameters
            
        Returns:
            Affected row ID
        """
        conn = await self.get_connection()
        cursor = await conn.execute(query, params)
        await conn.commit()
        return cursor.lastrowid
    
    async def execute_script(self, script: str):
        """
        Execute a SQL script.
        
        Args:
            script: SQL script string
        """
        conn = await self.get_connection()
        await conn.executescript(script)
        await conn.commit()
    
    async def vacuum(self):
        """
        Optimize the database file.
        Call periodically to reclaim space.
        """
        await self.execute("VACUUM")
        logger.info("Database vacuumed successfully")
    
    async def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get information about a table's columns.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column information dictionaries
        """
        return await self.fetchall(
            f"PRAGMA table_info({table_name})"
        )
    
    async def get_table_count(self, table_name: str) -> int:
        """
        Get the number of rows in a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Row count
        """
        result = await self.fetchone(
            f"SELECT COUNT(*) as count FROM {table_name}"
        )
        return result["count"] if result else 0


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for database operations"""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode('utf-8')
        return super().default(obj)


def json_dumps(data: Any) -> str:
    """Serialize data to JSON string"""
    return json.dumps(data, cls=JSONEncoder)


def json_loads(data: str) -> Any:
    """Deserialize JSON string to Python object"""
    if data is None:
        return None
    return json.loads(data)


async def get_database(db_path: str = None) -> Database:
    """
    Factory function to get a database instance.
    
    Args:
        db_path: Optional database path override
        
    Returns:
        Initialized Database instance
    """
    db = Database(db_path)
    await db.initialize()
    return db
