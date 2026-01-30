-- Database schema for Telegram Browser Agent
-- This schema supports multi-user, workflow storage, and learning capabilities

PRAGMA foreign_keys = ON;

-- Users table: stores user information and preferences
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    display_name TEXT,
    preferences TEXT,  -- JSON for user preferences (LinkedIn settings, etc.)
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversations table: stores conversation history for context
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    conversation_type TEXT DEFAULT 'general',  -- 'general', 'linkedin', 'youtube'
    message TEXT,
    response TEXT,
    intent TEXT,  -- Classified intent from the message
    metadata TEXT,  -- JSON for additional context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Workflows table: stores successful workflow executions for learning
CREATE TABLE IF NOT EXISTS workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    category TEXT,  -- 'linkedin', 'youtube', 'general', 'research'
    intent_type TEXT,  -- Type of task (e.g., 'connection_request', 'profile_visit')
    keywords TEXT,  -- Comma-separated keywords for retrieval
    original_prompt TEXT,  -- The original user prompt
    summary TEXT,  -- Brief summary of what was done
    steps TEXT,  -- JSON array of steps taken
    parameters TEXT,  -- JSON for parameters used
    success_rate REAL DEFAULT 1.0,
    success_count INTEGER DEFAULT 1,
    total_count INTEGER DEFAULT 1,
    rating INTEGER DEFAULT 5,  -- User rating 1-5
    embedding BLOB,  -- Store embedding for semantic search
    is_template INTEGER DEFAULT 0,  -- If 1, can be used as template for other users
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Workflow execution logs: tracks each workflow execution
CREATE TABLE IF NOT EXISTS workflow_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER,
    user_id INTEGER,
    status TEXT,  -- 'started', 'in_progress', 'completed', 'failed', 'cancelled'
    step_results TEXT,  -- JSON array of step execution results
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Task queue: for managing async task execution
CREATE TABLE IF NOT EXISTS task_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task_type TEXT,  -- 'browser_action', 'youtube_download', 'custom'
    task_data TEXT,  -- JSON for task parameters
    status TEXT DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'failed'
    priority INTEGER DEFAULT 5,  -- 1-10, higher = more urgent
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result TEXT,  -- JSON for task result
    error TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Async messages: stores messages to be sent asynchronously
CREATE TABLE IF NOT EXISTS async_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    chat_id INTEGER,  -- Telegram chat ID
    message_type TEXT,  -- 'progress', 'result', 'error', 'notification'
    content TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending', 'sent', 'failed'
    send_at TIMESTAMP,  -- When to send (for scheduled messages)
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Tool registry: stores available tools and their configurations
CREATE TABLE IF NOT EXISTS tool_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    description TEXT,
    category TEXT,  -- 'browser', 'youtube', 'research', 'custom'
    parameters TEXT,  -- JSON schema for parameters
    is_enabled INTEGER DEFAULT 1,
    version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User tool preferences: user's preferred tools for specific tasks
CREATE TABLE IF NOT EXISTS user_tool_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task_category TEXT,  -- 'linkedin', 'youtube'
    preferred_tools TEXT,  -- JSON array of tool names
    custom_parameters TEXT,  -- JSON for custom tool settings
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, task_category)
);

-- LinkedIn specific data
CREATE TABLE IF NOT EXISTS linkedin_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    profile_url TEXT,
    profile_name TEXT,
    title TEXT,
    company TEXT,
    notes TEXT,
    connection_status TEXT,  -- 'connected', 'pending', 'rejected'
    last_contacted TIMESTAMP,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Create indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_category ON workflows(category);
CREATE INDEX IF NOT EXISTS idx_workflows_keywords ON workflows(keywords);
CREATE INDEX IF NOT EXISTS idx_workflows_intent ON workflows(intent_type);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status);
CREATE INDEX IF NOT EXISTS idx_task_queue_priority ON task_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_linkedin_profiles_user ON linkedin_profiles(user_id);

-- Full-text search virtual table for workflows
CREATE VIRTUAL TABLE IF NOT EXISTS workflows_fts USING fts5(
    original_prompt,
    summary,
    content='workflows',
    content_rowid='id'
);

-- Trigger to keep FTS index updated
CREATE TRIGGER IF NOT EXISTS workflows_ai AFTER INSERT ON workflows
BEGIN
    INSERT INTO workflows_fts(rowid, original_prompt, summary)
    VALUES (new.id, new.original_prompt, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS workflows_ad AFTER DELETE ON workflows
BEGIN
    INSERT INTO workflows_fts(workflows_fts, rowid, original_prompt, summary)
    VALUES ('delete', old.id, old.original_prompt, old.summary);
END;
