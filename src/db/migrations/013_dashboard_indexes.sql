CREATE INDEX IF NOT EXISTS idx_cost_logs_created_at
ON cost_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status_started
ON pipeline_runs(status, started_at);

CREATE INDEX IF NOT EXISTS idx_pipeline_source_runs_run_id
ON pipeline_source_runs(run_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_source_runs_updated_at
ON pipeline_source_runs(updated_at);

CREATE INDEX IF NOT EXISTS idx_articles_status_collected
ON articles(status, collected_at);

INSERT OR REPLACE INTO schema_version (version) VALUES (13);
