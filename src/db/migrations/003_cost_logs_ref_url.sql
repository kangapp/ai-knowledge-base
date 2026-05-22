-- 为 cost_logs 添加 ref_url 字段，记录每次 LLM 调用的目标 URL
-- 幂等：如果列已存在，PRAGMA 会检测到（SQLite 没有 IF NOT EXISTS for ADD COLUMN，所以用子查询捕获）
PRAGMA table_info(cost_logs);
-- 检查 ref_url 是否已存在
SELECT 'checking' WHERE 0 = (SELECT COUNT(*) FROM pragma_table_info('cost_logs') WHERE name = 'ref_url');
-- 如果上面查询没有返回结果（列不存在），则添加
ALTER TABLE cost_logs ADD COLUMN ref_url TEXT;
-- 添加索引
CREATE INDEX IF NOT EXISTS idx_cost_logs_ref_url ON cost_logs(ref_url);