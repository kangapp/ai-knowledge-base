# 仪表盘增强设计

Date: 2026-05-23
Status: Approved

## 背景

当前仪表盘仅有 4 个简单 KPI + 1 个成本趋势图，无法满足三个核心监控场景的需求：
- 观察数据质量
- 排查运行问题
- 优化资源分配

## 解决方案

采用 **三 Tab 并列结构**，每个 Tab 独立全套 KPI + 图表。

## 布局结构

```
┌────────────────────────────────────────────────────┐
│  [数据质量]    [运行状态]    [资源消耗]              │
├────────────────────────────────────────────────────┤
│  KPI: 总文章 / 周期新增 / 通过率 / 平均分 / 活跃源   │
├────────────────────────────────────────────────────┤
│  各 Tab 独立内容区                                   │
└────────────────────────────────────────────────────┘
```

Tab 切换时保留用户选择的 time range（day/week/month）。

## Tab 1：数据质量

### KPI 卡片
| KPI | 数据来源 | SQL |
|-----|---------|-----|
| 总文章数 | COUNT(status='approved') | `SELECT COUNT(*) FROM articles WHERE status='approved'` |
| 周期新增 | COUNT(collected_at >= -30d) | `SELECT COUNT(*) FROM articles WHERE status='approved' AND collected_at >= date('now', '-30 days')` |
| 平均分 | AVG(relevance_score) | `SELECT AVG(relevance_score) FROM articles WHERE status='approved'` |
| 通过率 | approved / total | `SELECT SUM(CASE status='approved' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) FROM articles WHERE collected_at >= date('now', '-30 days')` |
| 活跃源数 | COUNT(DISTINCT source_detail) | `SELECT COUNT(DISTINCT source_detail) FROM articles WHERE status='approved' AND collected_at >= date('now', '-30 days')` |

### 图表
1. **评分分布直方图**：relevance_score 0-20/20-40/40-60/60-80/80-100 各区间文章数（柱状图）
2. **来源细分评分排行**：每个 source_detail 的 avg_score + 文章数（气泡图 或 水平条形图）
3. **标签云**：Top 20 标签，按频率缩放文字大小（CSS word-cloud 实现）
4. **数据新鲜度**：本周新增 vs 上月同期对比（分组柱状图）

## Tab 2：运行状态

### KPI 卡片
| KPI | 数据来源 |
|-----|---------|
| 上次运行 | `SELECT id, started_at FROM pipeline_runs ORDER BY started_at DESC LIMIT 1` |
| 运行时长 | ended_at - started_at |
| 本次成功率 | approved / total items |
| 失败 item 数 | retry + discarded count |
| 熔断状态 | circuit_events 表最新状态 |

### 图表
1. **Pipeline DAG 状态**：collect → route → analyze → aggregate → review 每阶段耗时（水平甘特图）
2. **详细失败日志表**（可折叠）：
   - 列：时间、URL（或前40字）、阶段、错误原因
   - 支持按阶段/来源筛选
   - 数据来自 `cost_logs` + `articles` JOIN 查询
3. **Provider 健康状态表**：每 Provider 的 error_count、circuit 状态（closed/open/half_open）、最后错误时间

### 新增查询
```sql
-- 失败 item 详细（需关联 articles 获取 title）
SELECT
    cl.created_at,
    a.url,
    cl.agent AS stage,
    cl.provider,
    cl.cost,
    cl.tokens_in + cl.tokens_out AS tokens
FROM cost_logs cl
JOIN articles a ON a.url = cl.agent  -- 需要修正：cost_logs.agent 是字符串，不是 URL
-- 重新设计：cost_logs 需要记录 ref_url 才能 JOIN
```

**注意**：当前 `cost_logs` 表的 `agent` 字段是 `github_analyzer`/`reviewer` 等 Agent 名称，不是 URL。`run_id` 关联到 `pipeline_runs`，但 pipeline_runs 的 summary 字段包含 JSON 格式的失败信息。

**修正方案**：在 `cost_logs` 中新增 `ref_url` 字段记录每个调用的目标 URL（需要 migration）。这样失败日志可以通过 `cost_logs.agent='analyzer'` + `cost_logs.cost=0` 筛选出 parse 失败的记录，JOIN articles 获取标题。

## Tab 3：资源消耗

### KPI 卡片
| KPI | 计算方式 |
|-----|---------|
| 周期花费 | SUM(cost) WHERE created_at >= -30d |
| 日均花费 | 周期花费 / 天数 |
| Token 效率 | 平均 cost per 1M tokens = SUM(cost) / SUM(tokens_in+tokens_out) * 1e6 |
| 预算进度 | 周期花费 / (monthly_budget / 30 * days) |
| 预估剩余 | daily_cost > 0 ? (monthly_budget - spent) / daily_cost : null |

### 图表
1. **Provider 费用分解**：MiniMax vs DeepSeek 堆叠柱状图（按日）
2. **Agent 费用分解**：github_analyzer / rss_analyzer / feishu_analyzer / arxiv_analyzer / reviewer 各自费用（分组柱状图）
3. **$/M Token 效率**：实际单价 vs 官方定价对比表（检验计费准确性）
4. **月度预算进度条**：进度条组件 + 每日消耗速率

### 官方定价参考
| Provider | Model | Input $/M | Output $/M |
|----------|-------|-----------|------------|
| MiniMax | MiniMax-M2.7 | $0.3 | $1.2 |
| DeepSeek | deepseek-chat | $0.14 | $0.28 |

## 数据模型变更

### Migration: cost_logs 新增 ref_url 字段
```sql
ALTER TABLE cost_logs ADD COLUMN ref_url TEXT;
CREATE INDEX IF NOT EXISTS idx_cost_logs_ref_url ON cost_logs(ref_url);
```

### 新增表: circuit_events（已存在于 data-model.md）
```sql
CREATE TABLE IF NOT EXISTS circuit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    event TEXT NOT NULL,  -- 'open' | 'half_open' | 'close'
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

需要修改 `HealthTracker` 在每次状态转换时写入 `circuit_events` 表。

## API 变更

### 新增 `GET /api/stats/quality`
数据质量 Tab 的专用 API：
- 评分分布
- 来源细分评分
- 标签云
- 数据新鲜度

### 新增 `GET /api/stats/runtime`
运行状态 Tab 的专用 API：
- pipeline_runs 最新状态
- phase logs
- 失败日志（带分页和筛选）
- provider 健康状态

### 新增 `GET /api/stats/consumption`
资源消耗 Tab 的专用 API：
- provider 费用分解
- agent 费用分解
- token 效率
- 预算进度

### 修改 `GET /api/stats/enhanced`
扩展返回结构，新增 `quality` / `runtime` / `consumption` 三个子对象。

## 前端变更

### 文件修改
- `src/site/templates/dashboard.html` — 三 Tab 结构改造
- `src/site/static/js/app.js` — 新增 Tab 切换逻辑、各 Tab 图表渲染
- `src/site/static/css/style.css` — 新增 Tab 样式、图表样式、标签云样式

### Tab 切换行为
- 使用 CSS `display: none` 切换内容区，不刷新数据
- 保留 time range 选择（day/week/month）跨 Tab 共享
- 每个 Tab 首次激活时请求对应 API，之后使用缓存

## 实现优先级

1. **Phase 1**: 数据库 migration（cost_logs.ref_url + circuit_events）
2. **Phase 2**: API 端点（quality / runtime / consumption）
3. **Phase 3**: 前端 Tab 结构 + KPI 卡片
4. **Phase 4**: 各 Tab 图表实现
5. **Phase 5**: HealthTracker 写入 circuit_events

## 验收标准

- 三个 Tab 均可正常切换
- 每个 Tab 的 KPI 数值与数据库查询一致
- 图表数据随 time range 切换实时更新
- 仪表盘在移动端可横向滚动查看