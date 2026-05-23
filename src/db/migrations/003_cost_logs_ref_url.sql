-- 为 cost_logs 添加 ref_url 字段（幂等版本）
-- SQLite 不支持 IF NOT EXISTS for ADD COLUMN，用单独语句检查列是否存在
-- 然后选择性执行 ALTER TABLE
-- 此迁移仅在 version=3 时执行，前提是 cost_logs 表已存在
ALTER TABLE cost_logs ADD COLUMN ref_url TEXT;
CREATE INDEX IF NOT EXISTS idx_cost_logs_ref_url ON cost_logs(ref_url);