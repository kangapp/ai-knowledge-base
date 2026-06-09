-- src/db/migrations/010_deep_reports.sql

CREATE TABLE IF NOT EXISTS deep_reports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_url            TEXT NOT NULL,
    repo_name           TEXT NOT NULL,
    article_id          INTEGER REFERENCES articles(id),
    run_id              TEXT REFERENCES pipeline_runs(id),
    commit_sha          TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL,
    candidate_score     INTEGER NOT NULL DEFAULT 0,
    trigger_reason      TEXT NOT NULL DEFAULT '',
    report_json         TEXT NOT NULL DEFAULT '{}',
    report_markdown     TEXT NOT NULL DEFAULT '',
    evidence_json       TEXT NOT NULL DEFAULT '[]',
    tech_stack_json     TEXT NOT NULL DEFAULT '{}',
    file_tree_summary   TEXT NOT NULL DEFAULT '',
    analysis_cost       REAL NOT NULL DEFAULT 0,
    analysis_tokens     INTEGER NOT NULL DEFAULT 0,
    error               TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    UNIQUE(repo_url, commit_sha)
);

CREATE INDEX IF NOT EXISTS idx_deep_reports_status_created
    ON deep_reports(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deep_reports_repo_url
    ON deep_reports(repo_url);
CREATE INDEX IF NOT EXISTS idx_deep_reports_run_id
    ON deep_reports(run_id);

INSERT OR REPLACE INTO schema_version (version) VALUES (10);
