-- ============================================================
-- Playground UI - PostgreSQL Initialization Script
-- ============================================================

-- Users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    user_name VARCHAR(100) NOT NULL,
    user_email VARCHAR(200) NOT NULL UNIQUE,
    user_password VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Models table
CREATE TABLE models (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Chatbots table
CREATE TABLE chatbots (
    chatbot_id SERIAL PRIMARY KEY,
    chatbot_title VARCHAR(100) NOT NULL,
    description VARCHAR(500) DEFAULT '',
    chatbot_visibility BOOLEAN DEFAULT FALSE,
    chatbot_plugin_key VARCHAR(100),
    model_id INT REFERENCES models(model_id),
    chatbot_prompt TEXT DEFAULT '',
    user_id INT NOT NULL REFERENCES users(user_id),
    update_version INT DEFAULT 1,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions table
CREATE TABLE chatbot_sessions (
    session_id VARCHAR(50) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    title VARCHAR(200) NOT NULL DEFAULT '새 채팅',
    user_id INT NOT NULL REFERENCES users(user_id),
    chatbot_id INT NOT NULL REFERENCES chatbots(chatbot_id) ON DELETE CASCADE,
    update_version INT DEFAULT 1,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages table
CREATE TABLE chatbot_messages (
    message_id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) NOT NULL REFERENCES chatbot_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(4) NOT NULL CHECK (role IN ('user', 'bot')),
    content TEXT NOT NULL,
    tool_calls TEXT[] DEFAULT '{}',
    sources TEXT[] DEFAULT '{}',
    elapsed_ms DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Guard rulesets table
CREATE TABLE guard_rulesets (
    guard_ruleset_id SERIAL PRIMARY KEY,
    chatbot_id INT NOT NULL REFERENCES chatbots(chatbot_id) ON DELETE CASCADE,
    rule TEXT NOT NULL,
    order_index INT NOT NULL DEFAULT 0
);

-- Chatbot tool agents table
CREATE TABLE chatbot_tool_agents (
    id SERIAL PRIMARY KEY,
    chatbot_id INT NOT NULL REFERENCES chatbots(chatbot_id) ON DELETE CASCADE,
    tool_agent_key VARCHAR(100) NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_chatbots_user_id ON chatbots(user_id);
CREATE INDEX idx_sessions_chatbot_id ON chatbot_sessions(chatbot_id);
CREATE INDEX idx_sessions_user_id ON chatbot_sessions(user_id);
CREATE INDEX idx_messages_session_id ON chatbot_messages(session_id);
CREATE INDEX idx_messages_created_at ON chatbot_messages(created_at ASC);
CREATE INDEX idx_guard_rulesets_chatbot ON guard_rulesets(chatbot_id);
CREATE INDEX idx_tool_agents_chatbot ON chatbot_tool_agents(chatbot_id);

-- ============================================================
-- Seed Data
-- ============================================================

-- Default models
INSERT INTO models (model_name, provider) VALUES
  ('gpt-4o', 'openai'),
  ('gpt-4o-mini', 'openai'),
  ('claude-3.5-sonnet', 'anthropic');

-- Admin user (password: admin123)
INSERT INTO users (user_name, user_email, user_password, is_admin)
VALUES ('Admin', 'admin@playground.local',
  '$2b$10$EixZaYVK1fsbw1ZfbX3OXe.PaWXc0vC3xkLdZo0aHH3h.qQ8H7rCe', TRUE);
