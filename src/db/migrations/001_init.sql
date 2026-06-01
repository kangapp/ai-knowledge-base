-- src/db/migrations/001_init.sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
INSERT OR IGNORE INTO schema_version (version) VALUES (0);

CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    url             TEXT NOT NULL UNIQUE,
    description     TEXT,
    summary         TEXT,
    source          TEXT NOT NULL,
    source_detail   TEXT,
    relevance_score INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',
    retry_count     INTEGER DEFAULT 0,
    collected_at    TEXT NOT NULL,
    published_at    TEXT,
    extra_data      TEXT,
    analysis_cost   REAL DEFAULT 0.0,
    analysis_tokens INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now', '+8 hours')),
    updated_at      TEXT DEFAULT (datetime('now', '+8 hours'))
);

CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_collected ON articles(collected_at);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, summary, description, content='articles'
);

-- FTS5 同步触发器（外部内容表需手动维护）
CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, summary, description) VALUES (new.id, new.title, new.summary, new.description);
END;

CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary, description) VALUES ('delete', old.id, old.title, old.summary, old.description);
END;

CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary, description) VALUES ('delete', old.id, old.title, old.summary, old.description);
    INSERT INTO articles_fts(rowid, title, summary, description) VALUES (new.id, new.title, new.summary, new.description);
END;

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    color TEXT
);

CREATE TABLE IF NOT EXISTS article_tags (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id         TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    status     TEXT DEFAULT 'running',
    trigger    TEXT,
    summary    TEXT
);

CREATE TABLE IF NOT EXISTS cost_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     TEXT REFERENCES pipeline_runs(id),
    agent      TEXT NOT NULL,
    provider   TEXT NOT NULL,
    model      TEXT NOT NULL,
    tokens_in  INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    cost       REAL NOT NULL DEFAULT 0.0,
    created_at TEXT DEFAULT (datetime('now', '+8 hours'))
);

CREATE TABLE IF NOT EXISTS provider_health (
    provider    TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'healthy',
    latency_ms  INTEGER,
    error_count INTEGER DEFAULT 0,
    last_error  TEXT,
    last_check  TEXT,
    circuit     TEXT NOT NULL DEFAULT 'closed',
    cooldown_level INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS circuit_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    provider   TEXT NOT NULL,
    event      TEXT NOT NULL,
    reason     TEXT,
    created_at TEXT DEFAULT (datetime('now', '+8 hours'))
);

-- 更新 schema_version
-- 001 本身不更新版本号，由 Database 类在检测到 current=0 后自动更新
