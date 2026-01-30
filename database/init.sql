-- PostgreSQL initialization script for pgvector support
-- This file is used when running with PostgreSQL instead of SQLite

-- Create extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT UNIQUE,
    display_name TEXT,
    preferences JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    conversation_type TEXT DEFAULT 'general',
    message TEXT NOT NULL,
    response TEXT,
    intent TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);

-- Workflows table with vector embeddings
CREATE TABLE IF NOT EXISTS workflows (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    category TEXT,
    intent_type TEXT,
    keywords TEXT,
    original_prompt TEXT NOT NULL,
    summary TEXT,
    steps JSONB DEFAULT '[]',
    parameters JSONB DEFAULT '{}',
    success_rate REAL DEFAULT 1.0,
    success_count INTEGER DEFAULT 1,
    total_count INTEGER DEFAULT 1,
    rating INTEGER DEFAULT 5,
    embedding VECTOR(384),
    is_template BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_category ON workflows(category);
CREATE INDEX IF NOT EXISTS idx_workflows_intent ON workflows(intent_type);
CREATE INDEX IF NOT EXISTS idx_workflows_keywords ON workflows USING gin(to_tsvector('english', keywords));
CREATE INDEX IF NOT EXISTS idx_workflows_embedding ON workflows USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Workflow executions table
CREATE TABLE IF NOT EXISTS workflow_executions (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER REFERENCES workflows(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    status TEXT,
    step_results JSONB DEFAULT '[]',
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Task queue table
CREATE TABLE IF NOT EXISTS task_queue (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    task_type TEXT,
    task_data JSONB DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    result JSONB,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status);
CREATE INDEX IF NOT EXISTS idx_task_queue_priority ON task_queue(priority DESC);

-- Async messages table
CREATE TABLE IF NOT EXISTS async_messages (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    chat_id BIGINT,
    message_type TEXT,
    content TEXT,
    status TEXT DEFAULT 'pending',
    send_at TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tool registry table
CREATE TABLE IF NOT EXISTS tool_registry (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    category TEXT,
    parameters JSONB DEFAULT '{}',
    is_enabled BOOLEAN DEFAULT TRUE,
    version TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- LinkedIn profiles table
CREATE TABLE IF NOT EXISTS linkedin_profiles (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    profile_url TEXT NOT NULL,
    profile_name TEXT,
    title TEXT,
    company TEXT,
    notes TEXT,
    connection_status TEXT,
    last_contacted TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_linkedin_profiles_user ON linkedin_profiles(user_id);

-- Functions
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_workflows_updated_at BEFORE UPDATE ON workflows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_tool_registry_updated_at BEFORE UPDATE ON tool_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Insert default tools
INSERT INTO tool_registry (name, description, category, parameters, version)
VALUES
    ('browser', 'Browser automation tool', 'browser', '{"actions": ["navigate", "click", "type", "extract", "screenshot"]}', '1.0.0'),
    ('linkedin', 'LinkedIn-specific actions', 'linkedin', '{"actions": ["visit_profile", "send_connection", "send_message", "search_people"]}', '1.0.0'),
    ('youtube_transcript', 'YouTube transcript extraction', 'youtube', '{"actions": ["extract_transcript"]}', '1.0.0'),
    ('youtube_summary', 'YouTube video summarization', 'youtube', '{"actions": ["summarize_video"]}', '1.0.0')
ON CONFLICT (name) DO NOTHING;
