-- src/db/migrations/006_cost_logs_source_fields.sql

ALTER TABLE cost_logs ADD COLUMN source TEXT;
ALTER TABLE cost_logs ADD COLUMN source_detail TEXT;
ALTER TABLE cost_logs ADD COLUMN source_id TEXT;

CREATE INDEX IF NOT EXISTS idx_cost_logs_source
    ON cost_logs(source, source_detail);

INSERT OR REPLACE INTO schema_version (version) VALUES (6);
