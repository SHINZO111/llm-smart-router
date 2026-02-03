-- LLM Smart Router - Conversation History Database Schema
-- SQLite Database Schema

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Topics table for organizing conversations
create table if not exists topics (
    id          integer primary key autoincrement,
    name        text not null unique,
    created_at  datetime default current_timestamp
);

-- Conversations table
create table if not exists conversations (
    id          integer primary key autoincrement,
    title       text not null default 'New Conversation',
    created_at  datetime default current_timestamp,
    updated_at  datetime default current_timestamp,
    topic_id    integer,
    foreign key (topic_id) references topics(id) on delete set null
);

-- Messages table
create table if not exists messages (
    id              integer primary key autoincrement,
    conversation_id integer not null,
    role            text not null check(role in ('user', 'assistant', 'system')),
    content         text not null,
    model           text,
    timestamp       datetime default current_timestamp,
    foreign key (conversation_id) references conversations(id) on delete cascade
);

-- Indexes for performance
-- Index for conversation lookups by topic
CREATE INDEX IF NOT EXISTS idx_conversations_topic_id ON conversations(topic_id);

-- Index for conversation date range queries
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at);

-- Index for message lookups by conversation
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);

-- Index for message timestamps
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);

-- Index for full-text search on messages
CREATE INDEX IF NOT EXISTS idx_messages_content ON messages(content);

-- Index for model filtering
CREATE INDEX IF NOT EXISTS idx_messages_model ON messages(model);

-- Trigger to update conversations.updated_at when a message is added
CREATE TRIGGER IF NOT EXISTS update_conversation_timestamp
AFTER INSERT ON messages
BEGIN
    UPDATE conversations 
    SET updated_at = current_timestamp 
    WHERE id = NEW.conversation_id;
END;

-- Insert default topic
INSERT OR IGNORE INTO topics (name) VALUES ('General');
INSERT OR IGNORE INTO topics (name) VALUES ('Development');
INSERT OR IGNORE INTO topics (name) VALUES ('Research');
