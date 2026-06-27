CREATE TABLE IF NOT EXISTS source_registry (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    enabled         INTEGER NOT NULL DEFAULT 1,
    priority        INTEGER NOT NULL DEFAULT 3,
    cron            TEXT NOT NULL,
    max_items       INTEGER NOT NULL DEFAULT 10,
    config_json     TEXT NOT NULL DEFAULT '{}',
    manual_override INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now', '+8 hours')),
    updated_at      TEXT DEFAULT (datetime('now', '+8 hours'))
);

CREATE TABLE IF NOT EXISTS source_health_daily (
    source_id             TEXT NOT NULL,
    date                  TEXT NOT NULL,
    request_success_rate  REAL NOT NULL DEFAULT 0,
    collected             INTEGER NOT NULL DEFAULT 0,
    new_items             INTEGER NOT NULL DEFAULT 0,
    analyzed              INTEGER NOT NULL DEFAULT 0,
    analysis_failed       INTEGER NOT NULL DEFAULT 0,
    approved              INTEGER NOT NULL DEFAULT 0,
    discarded             INTEGER NOT NULL DEFAULT 0,
    avg_score             REAL,
    cost                  REAL NOT NULL DEFAULT 0,
    tokens                INTEGER NOT NULL DEFAULT 0,
    health_score          REAL,
    budget_blocked        INTEGER NOT NULL DEFAULT 0,
    updated_at            TEXT DEFAULT (datetime('now', '+8 hours')),
    PRIMARY KEY (source_id, date)
);

CREATE TABLE IF NOT EXISTS source_governance_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT NOT NULL,
    event        TEXT NOT NULL,
    from_status  TEXT NOT NULL DEFAULT '',
    to_status    TEXT NOT NULL DEFAULT '',
    reason       TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT DEFAULT (datetime('now', '+8 hours'))
);

CREATE INDEX IF NOT EXISTS idx_source_registry_status
ON source_registry(status, enabled);

CREATE INDEX IF NOT EXISTS idx_source_health_daily_source_date
ON source_health_daily(source_id, date);

CREATE INDEX IF NOT EXISTS idx_source_governance_events_source_time
ON source_governance_events(source_id, created_at);
