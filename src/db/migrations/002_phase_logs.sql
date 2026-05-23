-- Phase-level timing logs for DAG visualization
CREATE TABLE IF NOT EXISTS pipeline_phase_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL REFERENCES pipeline_runs(id),
    phase       TEXT NOT NULL,
    status      TEXT NOT NULL,
    started_at  TEXT,
    ended_at    TEXT,
    duration_ms INTEGER,
    details     TEXT
);

CREATE INDEX IF NOT EXISTS idx_phase_logs_run ON pipeline_phase_logs(run_id);

INSERT OR REPLACE INTO schema_version (version) VALUES (2);