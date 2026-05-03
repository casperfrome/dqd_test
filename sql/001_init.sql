PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    nickname TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('super_admin', 'fan_circle_owner', 'normal_user')),
    avatar_url TEXT NOT NULL,
    bio TEXT DEFAULT '',
    following_count INTEGER NOT NULL DEFAULT 0,
    followers_count INTEGER NOT NULL DEFAULT 0,
    total_likes_received INTEGER NOT NULL DEFAULT 0,
    total_dislikes_received INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_follows (
    follower_user_id INTEGER NOT NULL,
    followed_user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (follower_user_id, followed_user_id),
    FOREIGN KEY (follower_user_id) REFERENCES users(id),
    FOREIGN KEY (followed_user_id) REFERENCES users(id),
    CHECK (follower_user_id != followed_user_id)
);

CREATE TABLE IF NOT EXISTS fan_circles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_name TEXT NOT NULL UNIQUE,
    board_name TEXT NOT NULL UNIQUE,
    league_name TEXT NOT NULL,
    logo_url TEXT NOT NULL,
    owner_user_id INTEGER,
    description TEXT DEFAULT '',
    post_count INTEGER NOT NULL DEFAULT 0,
    follower_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fan_circle_id INTEGER NOT NULL,
    author_user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('discussion', 'news', 'transfer', 'match', 'off_topic')),
    like_count INTEGER NOT NULL DEFAULT 0,
    dislike_count INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    has_poll INTEGER NOT NULL DEFAULT 0,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_locked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (fan_circle_id) REFERENCES fan_circles(id),
    FOREIGN KEY (author_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS post_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    tag_name TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

CREATE TABLE IF NOT EXISTS post_polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL UNIQUE,
    question TEXT NOT NULL,
    allow_multiple INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

CREATE TABLE IF NOT EXISTS post_poll_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id INTEGER NOT NULL,
    option_text TEXT NOT NULL,
    vote_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (poll_id) REFERENCES post_polls(id)
);

CREATE TABLE IF NOT EXISTS post_poll_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id INTEGER NOT NULL,
    option_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (poll_id) REFERENCES post_polls(id),
    FOREIGN KEY (option_id) REFERENCES post_poll_options(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE (poll_id, option_id, user_id)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    author_user_id INTEGER NOT NULL,
    parent_comment_id INTEGER,
    content TEXT NOT NULL,
    depth INTEGER NOT NULL DEFAULT 0,
    path TEXT NOT NULL DEFAULT '',
    like_count INTEGER NOT NULL DEFAULT 0,
    dislike_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (author_user_id) REFERENCES users(id),
    FOREIGN KEY (parent_comment_id) REFERENCES comments(id)
);

CREATE TABLE IF NOT EXISTS user_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    target_user_id INTEGER,
    event_type TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (actor_user_id) REFERENCES users(id),
    FOREIGN KEY (target_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS fan_circle_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    fan_circle_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (actor_user_id) REFERENCES users(id),
    FOREIGN KEY (fan_circle_id) REFERENCES fan_circles(id)
);

CREATE TABLE IF NOT EXISTS post_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    post_id INTEGER NOT NULL,
    comment_id INTEGER,
    event_type TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (actor_user_id) REFERENCES users(id),
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (comment_id) REFERENCES comments(id)
);

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO system_settings (key, value, updated_at)
VALUES ('database_access_level', 'public', CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS ai_database_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_database_path TEXT NOT NULL,
    source_table_name TEXT,
    source_column_name TEXT,
    fact_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL UNIQUE,
    generated_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS ai_database_fact_fts
USING fts5(title, content);

CREATE TABLE IF NOT EXISTS ai_chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    owner_user_id INTEGER,
    client_id_hash TEXT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ai_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    retrieved_fact_ids_json TEXT NOT NULL DEFAULT '[]',
    thinking_enabled INTEGER NOT NULL DEFAULT 0,
    thinking_content TEXT NOT NULL DEFAULT '',
    input_token_count INTEGER NOT NULL DEFAULT 0,
    output_token_count INTEGER NOT NULL DEFAULT 0,
    is_stopped INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES ai_chat_sessions(id)
);

CREATE TABLE IF NOT EXISTS ai_chat_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    session_id INTEGER,
    message_id INTEGER,
    actor_user_id INTEGER,
    model TEXT NOT NULL,
    retrieved_fact_ids_json TEXT NOT NULL DEFAULT '[]',
    retrieved_fact_count INTEGER NOT NULL DEFAULT 0,
    thinking_enabled INTEGER NOT NULL DEFAULT 0,
    input_token_count INTEGER NOT NULL DEFAULT 0,
    output_token_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES ai_chat_sessions(id),
    FOREIGN KEY (message_id) REFERENCES ai_chat_messages(id),
    FOREIGN KEY (actor_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ai_code_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_path TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT '',
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL UNIQUE,
    generated_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS ai_code_fact_fts
USING fts5(source_file_path, title, content);

CREATE TABLE IF NOT EXISTS ai_code_chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    owner_user_id INTEGER,
    client_id_hash TEXT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ai_code_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    retrieved_fact_ids_json TEXT NOT NULL DEFAULT '[]',
    thinking_enabled INTEGER NOT NULL DEFAULT 0,
    thinking_content TEXT NOT NULL DEFAULT '',
    input_token_count INTEGER NOT NULL DEFAULT 0,
    output_token_count INTEGER NOT NULL DEFAULT 0,
    is_stopped INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES ai_code_chat_sessions(id)
);

CREATE TABLE IF NOT EXISTS ai_code_chat_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    session_id INTEGER,
    message_id INTEGER,
    actor_user_id INTEGER,
    model TEXT NOT NULL,
    retrieved_fact_ids_json TEXT NOT NULL DEFAULT '[]',
    retrieved_fact_count INTEGER NOT NULL DEFAULT 0,
    thinking_enabled INTEGER NOT NULL DEFAULT 0,
    input_token_count INTEGER NOT NULL DEFAULT 0,
    output_token_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES ai_code_chat_sessions(id),
    FOREIGN KEY (message_id) REFERENCES ai_code_chat_messages(id),
    FOREIGN KEY (actor_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_posts_circle_created ON posts(fan_circle_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_post_path ON comments(post_id, path);
CREATE INDEX IF NOT EXISTS idx_post_tags_post_id ON post_tags(post_id);
CREATE INDEX IF NOT EXISTS idx_user_events_target ON user_events(target_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_circle_events_circle ON fan_circle_events(fan_circle_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_post_events_post ON post_events(post_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_database_facts_source ON ai_database_facts(source_database_path, source_table_name, fact_type);
CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_owner ON ai_chat_sessions(owner_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_client ON ai_chat_sessions(client_id_hash, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_session ON ai_chat_messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_chat_events_session ON ai_chat_events(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_code_facts_source ON ai_code_facts(source_file_path, start_line, end_line);
CREATE INDEX IF NOT EXISTS idx_ai_code_chat_sessions_owner ON ai_code_chat_sessions(owner_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_code_chat_sessions_client ON ai_code_chat_sessions(client_id_hash, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_code_chat_messages_session ON ai_code_chat_messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_code_chat_events_session ON ai_code_chat_events(session_id, created_at DESC);
