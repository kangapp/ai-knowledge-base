-- src/db/migrations/008_observability_tables.sql

CREATE TABLE IF NOT EXISTS collection_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES pipeline_runs(id),
    url             TEXT NOT NULL,
    title           TEXT,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    source_detail   TEXT,
    status          TEXT NOT NULL,
    reason          TEXT,
    raw_metadata    TEXT,
    article_id      INTEGER REFERENCES articles(id),
    created_at      TEXT DEFAULT (datetime('now', '+8 hours')),
    updated_at      TEXT DEFAULT (datetime('now', '+8 hours')),
    UNIQUE(run_id, url)
);

CREATE INDEX IF NOT EXISTS idx_collection_items_run_source
    ON collection_items(run_id, source_id);
CREATE INDEX IF NOT EXISTS idx_collection_items_status
    ON collection_items(status);

CREATE TABLE IF NOT EXISTS pipeline_source_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES pipeline_runs(id),
    source_id       TEXT NOT NULL,
    source          TEXT NOT NULL,
    source_detail   TEXT,
    collected       INTEGER DEFAULT 0,
    new_items       INTEGER DEFAULT 0,
    dedup_skipped   INTEGER DEFAULT 0,
    analyzed        INTEGER DEFAULT 0,
    analysis_failed INTEGER DEFAULT 0,
    approved        INTEGER DEFAULT 0,
    retry           INTEGER DEFAULT 0,
    discarded       INTEGER DEFAULT 0,
    inserted        INTEGER DEFAULT 0,
    failed          INTEGER DEFAULT 0,
    cost            REAL DEFAULT 0.0,
    tokens          INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now', '+8 hours')),
    updated_at      TEXT DEFAULT (datetime('now', '+8 hours')),
    UNIQUE(run_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_source_runs_source
    ON pipeline_source_runs(source_id, run_id);

ALTER TABLE cost_logs ADD COLUMN status TEXT DEFAULT 'success';
ALTER TABLE cost_logs ADD COLUMN error TEXT;
ALTER TABLE cost_logs ADD COLUMN latency_ms INTEGER;
ALTER TABLE cost_logs ADD COLUMN attempt_no INTEGER DEFAULT 1;
ALTER TABLE cost_logs ADD COLUMN prompt_name TEXT;
ALTER TABLE cost_logs ADD COLUMN prompt_version TEXT;

CREATE INDEX IF NOT EXISTS idx_cost_logs_status
    ON cost_logs(status);

INSERT OR REPLACE INTO schema_version (version) VALUES (8);
