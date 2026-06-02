-- src/db/migrations/009_pipeline_events.sql

CREATE TABLE IF NOT EXISTS pipeline_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES pipeline_runs(id),
    ts              TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    phase           TEXT NOT NULL,
    event           TEXT NOT NULL,
    level           TEXT NOT NULL DEFAULT 'info',
    status          TEXT,
    source_id       TEXT,
    source          TEXT,
    source_detail   TEXT,
    ref_url         TEXT,
    title           TEXT,
    agent           TEXT,
    provider        TEXT,
    model           TEXT,
    attempt_no      INTEGER,
    latency_ms      INTEGER,
    cost            REAL,
    tokens          INTEGER,
    message         TEXT,
    payload         TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_events_run_id
    ON pipeline_events(run_id, id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_run_phase
    ON pipeline_events(run_id, phase);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_run_status
    ON pipeline_events(run_id, status);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_ref_url
    ON pipeline_events(ref_url);

INSERT OR REPLACE INTO schema_version (version) VALUES (9);
