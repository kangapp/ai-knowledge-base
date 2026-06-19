-- src/db/migrations/011_deep_report_v2.sql

ALTER TABLE deep_reports RENAME TO deep_reports_v1;

CREATE TABLE deep_reports (
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
    report_version      INTEGER NOT NULL DEFAULT 1,
    UNIQUE(repo_url, commit_sha, report_version)
);

INSERT INTO deep_reports (
    id, repo_url, repo_name, article_id, run_id, commit_sha, status,
    candidate_score, trigger_reason, report_json, report_markdown,
    evidence_json, tech_stack_json, file_tree_summary, analysis_cost,
    analysis_tokens, error, created_at, updated_at, report_version
)
SELECT
    id, repo_url, repo_name, article_id, run_id, commit_sha, status,
    candidate_score, trigger_reason, report_json, report_markdown,
    evidence_json, tech_stack_json, file_tree_summary, analysis_cost,
    analysis_tokens, error, created_at, updated_at, 1
FROM deep_reports_v1;

DROP TABLE deep_reports_v1;

CREATE TABLE deep_report_settings (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    public_version  INTEGER NOT NULL
);

INSERT INTO deep_report_settings (id, public_version) VALUES (1, 1);

CREATE INDEX idx_deep_reports_status_created
    ON deep_reports(status, created_at DESC);
CREATE INDEX idx_deep_reports_repo_url
    ON deep_reports(repo_url);
CREATE INDEX idx_deep_reports_run_id
    ON deep_reports(run_id);
CREATE INDEX idx_deep_reports_public
    ON deep_reports(report_version, status, updated_at DESC);

INSERT OR REPLACE INTO schema_version (version) VALUES (11);
