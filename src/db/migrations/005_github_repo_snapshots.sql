-- src/db/migrations/005_github_repo_snapshots.sql

CREATE TABLE IF NOT EXISTS github_repo_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_url        TEXT NOT NULL,
    repo_name       TEXT NOT NULL,
    stars           INTEGER DEFAULT 0,
    forks           INTEGER DEFAULT 0,
    watchers        INTEGER DEFAULT 0,
    snapshot_date   TEXT NOT NULL,          -- YYYY-MM-DD
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repo_url, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_github_repo_snapshots_url_date
    ON github_repo_snapshots(repo_url, snapshot_date);

INSERT OR REPLACE INTO schema_version (version) VALUES (5);