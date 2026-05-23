-- src/db/migrations/004_source_health.sql

CREATE TABLE IF NOT EXISTS source_health (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       TEXT NOT NULL,
    date            TEXT NOT NULL,          -- YYYY-MM-DD
    total_collected INTEGER DEFAULT 0,
    approved        INTEGER DEFAULT 0,
    rejected        INTEGER DEFAULT 0,
    failed          INTEGER DEFAULT 0,
    avg_score       REAL,
    recorded_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, date)
);

CREATE INDEX idx_source_health_source_date ON source_health(source_id, date);

CREATE TABLE IF NOT EXISTS discovered_sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT UNIQUE NOT NULL,
    name            TEXT,
    type            TEXT NOT NULL,
    discovered_at   TEXT DEFAULT (datetime('now')),
    status          TEXT DEFAULT 'candidate',
    added_at        TEXT,
    rejected_at     TEXT,
    reject_reason   TEXT
);