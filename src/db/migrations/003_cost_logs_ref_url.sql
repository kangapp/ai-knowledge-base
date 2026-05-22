-- 为 cost_logs 添加 ref_url 字段，记录每次 LLM 调用的目标 URL
ALTER TABLE cost_logs ADD COLUMN ref_url TEXT;
CREATE INDEX IF NOT EXISTS idx_cost_logs_ref_url ON cost_logs(ref_url);