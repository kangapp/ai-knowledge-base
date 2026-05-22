# 仪表盘增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将仪表盘从 4 KPI 1 图表增强为三 Tab（数据质量/运行状态/资源消耗）完整监控面板

**Architecture:** 后端新增 3 个专用 API 端点（quality/runtime/consumption），前端 dashboard.html 改造为三 Tab 结构，使用 CSS display 切换，各 Tab 首次激活时 fetch 数据并缓存。

**Tech Stack:** FastAPI (src/api/stats.py), aiosqlite migrations, Jinja2 templates, vanilla JS + Chart.js

---

## 文件结构映射

| 文件 | 职责 |
|------|------|
| `src/db/migrations/003_cost_logs_ref_url.sql` | cost_logs 新增 ref_url 字段 |
| `src/core/health.py` | HealthTracker 写入 circuit_events |
| `src/db/operations.py` | 新增 quality/runtime/consumption 查询函数 |
| `src/api/stats.py` | 新增 /quality /runtime /consumption 三个 API |
| `src/site/templates/dashboard.html` | 三 Tab HTML 结构 |
| `src/site/static/js/app.js` | Tab 切换逻辑 + 各 Tab 渲染 |
| `src/site/static/css/style.css` | Tab 样式、进度条、标签云样式 |

---

## Task 1: Migration — cost_logs 新增 ref_url 字段

**Files:**
- Create: `src/db/migrations/003_cost_logs_ref_url.sql`
- Modify: `src/graph/analyzers/base.py:99` (传 ref_url)
- Modify: `src/graph/reviewer.py:92` (传 ref_url)

- [ ] **Step 1: 创建 migration 文件**

```sql
-- src/db/migrations/003_cost_logs_ref_url.sql
-- 为 cost_logs 添加 ref_url 字段，记录每次 LLM 调用的目标 URL
ALTER TABLE cost_logs ADD COLUMN ref_url TEXT;
CREATE INDEX IF NOT EXISTS idx_cost_logs_ref_url ON cost_logs(ref_url);
```

- [ ] **Step 2: 修改 base.py 传入 ref_url 到 CostRecord**

Read `src/graph/analyzers/base.py` 第 113 行，找到：
```python
costs.append(CostRecord(agent=agent_name, provider=provider, model=model_id, tokens_in=tokens_in, tokens_out=tokens_out, cost=cost))
```

改为（添加 ref_url 字段）：
```python
costs.append(CostRecord(agent=agent_name, provider=provider, model=model_id, tokens_in=tokens_in, tokens_out=tokens_out, cost=cost, ref_url=item.url))
```

- [ ] **Step 3: 修改 reviewer.py 传入 ref_url 到 CostRecord**

Read `src/graph/reviewer.py` 第 101-104 行，找到：
```python
cost_records.append(CostRecord(
    agent="reviewer", provider=provider, model=model_id,
    tokens_in=tokens_in, tokens_out=tokens_out, cost=cost
))
```

改为（添加 ref_url 字段）：
```python
cost_records.append(CostRecord(
    agent="reviewer", provider=provider, model=model_id,
    tokens_in=tokens_in, tokens_out=tokens_out, cost=cost,
    ref_url=item.ref_url
))
```

- [ ] **Step 4: 修改 CostRecord 模型添加 ref_url 字段**

Read `src/graph/state.py`，找到 `CostRecord` 模型，添加 `ref_url: str = ""` 字段。

- [ ] **Step 5: 测试 migration 执行**

Run: `sqlite3 data/knowledge.db < src/db/migrations/003_cost_logs_ref_url.sql`
Expected: 无报错，cost_logs 表新增 ref_url 列

- [ ] **Step 6: 运行 pytest**

Run: `uv run pytest -m "not integration and not e2e" -q`
Expected: 46 passed

- [ ] **Step 7: Commit**

```bash
git add src/db/migrations/003_cost_logs_ref_url.sql src/graph/analyzers/base.py src/graph/reviewer.py src/graph/state.py
git commit -m "feat: migration cost_logs ref_url 字段"
```

---

## Task 2: HealthTracker 持久化 circuit_events

**Files:**
- Modify: `src/core/health.py`

- [ ] **Step 1: HealthTracker 接收 db 引用**

Read `src/core/health.py`，找到 `HealthTracker.__init__`，添加：
```python
def __init__(self, db=None):
    self._db = db  # Database 实例
    self._state: dict[str, dict] = {}
```

- [ ] **Step 2: 添加 _record_event 方法**

在 HealthTracker 类中添加：
```python
async def _record_event(self, provider: str, event: str, reason: str = ""):
    if self._db:
        await self._db.execute(
            "INSERT INTO circuit_events (provider, event, reason) VALUES (?,?,?)",
            (provider, event, reason)
        )
        await self._db.commit()
```

注意：`_record_event` 是 async 方法，需要在调用处 await。

- [ ] **Step 3: 修改 record_failure 写入 circuit_events**

找到 `record_failure` 方法中 `circuit="open"` 的分支，改为：
```python
if s["circuit"] == "half_open":
    s["circuit"] = "open"
    s["cooldown_level"] += 1
    s["opened_at"] = time.time()
    s["status"] = "unhealthy"
    asyncio.create_task(self._record_event(provider, "open", error))
elif s["error_count"] >= self.FAILURE_THRESHOLD and s["circuit"] == "closed":
    s["circuit"] = "open"
    s["opened_at"] = time.time()
    s["status"] = "unhealthy"
    asyncio.create_task(self._record_event(provider, "open", f"error_count={s['error_count']}"))
```

需要在文件顶部添加 `import asyncio`。

- [ ] **Step 4: 在成功恢复时记录 half_open→close**

找到 `record_success` 中 `circuit == "half_open"` 的分支，添加：
```python
if s["circuit"] == "half_open":
    s["circuit"] = "closed"
    asyncio.create_task(self._record_event(provider, "close", "recovery success"))
```

- [ ] **Step 5: Main.py 中注入 db 到 HealthTracker**

Read `src/main.py`，找到 `LLMRegistry` 创建位置，在创建后添加：
```python
_registry.health._db = _db
```

- [ ] **Step 6: Commit**

```bash
git add src/core/health.py src/main.py
git commit -m "feat: HealthTracker 持久化 circuit_events"
```

---

## Task 3: 新增 API 端点 — quality / runtime / consumption

**Files:**
- Modify: `src/db/operations.py` (新增 3 个查询函数)
- Modify: `src/api/stats.py` (新增 3 个路由)

### Task 3a: quality 查询 (src/db/operations.py)

- [ ] **Step 1: 添加 get_quality_stats 函数**

在 `src/db/operations.py` 末尾添加：

```python
async def get_quality_stats(db: Database, days: int = 30) -> dict:
    """数据质量 Tab 查询"""
    # 评分分布
    score_buckets = await db.fetch_all("""
        SELECT
            CASE
                WHEN relevance_score <= 20 THEN '0-20'
                WHEN relevance_score <= 40 THEN '20-40'
                WHEN relevance_score <= 60 THEN '40-60'
                WHEN relevance_score <= 80 THEN '60-80'
                ELSE '80-100'
            END as bucket,
            COUNT(*) as count
        FROM articles
        WHERE status='approved' AND collected_at >= date('now', ?)
        GROUP BY bucket
    """, (f"-{days} days",))

    # 来源细分评分
    source_scores = await db.fetch_all("""
        SELECT source, source_detail,
               COUNT(*) as article_count,
               AVG(relevance_score) as avg_score
        FROM articles
        WHERE status='approved' AND collected_at >= date('now', ?)
        GROUP BY source, source_detail
        ORDER BY avg_score DESC
    """, (f"-{days} days",))

    # 标签云
    top_tags = await db.fetch_all("""
        SELECT t.name, COUNT(*) as count
        FROM tags t JOIN article_tags at ON t.id=at.tag_id
        JOIN articles a ON a.id=at.article_id
        WHERE a.status='approved' AND a.collected_at >= date('now', ?)
        GROUP BY t.id
        ORDER BY count DESC LIMIT 20
    """, (f"-{days} days",))

    # 本周 vs 上月同期
    this_week = await db.fetch_one("""
        SELECT COUNT(*) as c FROM articles
        WHERE status='approved' AND collected_at >= date('now', '-7 days')
    """)
    last_week = await db.fetch_one("""
        SELECT COUNT(*) as c FROM articles
        WHERE collected_at >= date('now', '-14 days') AND collected_at < date('now', '-7 days')
    """)

    return {
        "score_distribution": [{"bucket": r["bucket"], "count": r["count"]} for r in score_buckets],
        "source_scores": [{"source": r["source"], "source_detail": r["source_detail"],
                            "article_count": r["article_count"], "avg_score": round(r["avg_score"], 1)} for r in source_scores],
        "top_tags": [{"name": r["name"], "count": r["count"]} for r in top_tags],
        "freshness": {
            "this_week": this_week["c"] if this_week else 0,
            "last_week": last_week["c"] if last_week else 0,
        }
    }
```

### Task 3b: runtime 查询

- [ ] **Step 2: 添加 get_runtime_stats 函数**

在 `src/db/operations.py` 末尾添加：

```python
async def get_runtime_stats(db: Database, days: int = 7) -> dict:
    """运行状态 Tab 查询"""
    # 最新一次 pipeline run
    last_run = await db.fetch_one(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
    )

    if not last_run:
        return {"run": None, "phases": [], "failures": [], "providers": []}

    run_id = last_run["id"]

    # Phase logs
    phases = await db.fetch_all("""
        SELECT phase, status, started_at, ended_at, duration_ms, details
        FROM pipeline_phase_logs WHERE run_id=? ORDER BY id
    """, (run_id,))

    # 失败日志（通过 ref_url JOIN articles 获取标题）
    failures = await db.fetch_all("""
        SELECT cl.created_at, cl.agent, cl.provider, cl.ref_url,
               cl.cost, cl.tokens_in, cl.tokens_out,
               a.title as article_title
        FROM cost_logs cl
        LEFT JOIN articles a ON a.url = cl.ref_url
        WHERE cl.run_id=? AND cl.cost = 0
        ORDER BY cl.created_at DESC LIMIT 50
    """, (run_id,))

    # Provider 健康状态（从 circuit_events 最近 10 条）
    provider_events = await db.fetch_all("""
        SELECT provider, event, reason, created_at
        FROM circuit_events ORDER BY created_at DESC LIMIT 20
    """)

    # 按 provider 聚合最新状态
    provider_latest = {}
    for e in provider_events:
        p = e["provider"]
        if p not in provider_latest:
            provider_latest[p] = e

    return {
        "run": dict(last_run) if last_run else None,
        "phases": [dict(p) for p in phases],
        "failures": [{
            "time": f["created_at"][11:19] if f["created_at"] else "",
            "stage": f["agent"],
            "provider": f["provider"],
            "url": f["ref_url"] or "",
            "title": f["article_title"] or "",
        } for f in failures],
        "providers": [{
            "name": p,
            "last_event": e["event"],
            "last_reason": e["reason"] or "",
            "last_time": e["created_at"] or "",
        } for p, e in provider_latest.items()]
    }
```

### Task 3c: consumption 查询

- [ ] **Step 3: 添加 get_consumption_stats 函数**

在 `src/db/operations.py` 末尾添加：

```python
async def get_consumption_stats(db: Database, days: int = 30) -> dict:
    """资源消耗 Tab 查询"""
    # Provider 费用分解（按日）
    provider_daily = await db.fetch_all("""
        SELECT date(created_at) as date, provider,
               SUM(cost) as cost, SUM(tokens_in+tokens_out) as tokens
        FROM cost_logs
        WHERE created_at >= date('now', ?)
        GROUP BY date(created_at), provider
        ORDER BY date
    """, (f"-{days} days",))

    # Agent 费用分解（按日）
    agent_daily = await db.fetch_all("""
        SELECT date(created_at) as date, agent,
               SUM(cost) as cost, SUM(tokens_in+tokens_out) as tokens
        FROM cost_logs
        WHERE created_at >= date('now', ?)
        GROUP BY date(created_at), agent
        ORDER BY date
    """, (f"-{days} days",))

    # 周期总花费
    period_cost = await db.fetch_one("""
        SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs
        WHERE created_at >= date('now', ?)
    """, (f"-{days} days",))

    # 周期总 token
    period_tokens = await db.fetch_one("""
        SELECT COALESCE(SUM(tokens_in + tokens_out), 0) as total FROM cost_logs
        WHERE created_at >= date('now', ?)
    """, (f"-{days} days",))

    # 官方定价（用于效率对比）
    official_prices = {
        "minimax": {"in": 0.3, "out": 1.2},
        "deepseek": {"in": 0.14, "out": 0.28},
        "openai": {"in": 0.15, "out": 0.6},
    }

    # per-provider 汇总
    provider_summary = await db.fetch_all("""
        SELECT provider, SUM(cost) as total_cost,
               SUM(tokens_in) as total_in, SUM(tokens_out) as total_out
        FROM cost_logs WHERE created_at >= date('now', ?)
        GROUP BY provider
    """, (f"-{days} days",))

    return {
        "provider_daily": [dict(r) for r in provider_daily],
        "agent_daily": [dict(r) for r in agent_daily],
        "period_cost": round(period_cost["total"], 4) if period_cost else 0,
        "period_tokens": period_tokens["total"] if period_tokens else 0,
        "provider_summary": [{
            "provider": r["provider"],
            "total_cost": round(r["total_cost"], 4),
            "total_in": r["total_in"],
            "total_out": r["total_out"],
        } for r in provider_summary],
        "official_prices": official_prices,
    }
```

### Task 3d: API 路由

- [ ] **Step 4: 在 stats.py 添加三个新路由**

Read `src/api/stats.py`，在文件末尾添加：

```python
@router.get("/quality")
async def get_stats_quality(days: int = Query(default=30, ge=1, le=3650)):
    db = get_db()
    return envelope(await operations.get_quality_stats(db, days))

@router.get("/runtime")
async def get_stats_runtime(days: int = Query(default=7, ge=1, le=365)):
    db = get_db()
    return envelope(await operations.get_runtime_stats(db, days))

@router.get("/consumption")
async def get_stats_consumption(days: int = Query(default=30, ge=1, le=3650)):
    db = get_db()
    return envelope(await operations.get_consumption_stats(db, days))
```

- [ ] **Step 5: 运行测试**

Run: `uv run pytest -m "not integration and not e2e" -q`
Expected: 46 passed

- [ ] **Step 6: Commit**

```bash
git add src/db/operations.py src/api/stats.py
git commit -m "feat: 新增 quality/runtime/consumption API 端点"
```

---

## Task 4: 前端 — 三 Tab 结构

**Files:**
- Modify: `src/site/templates/dashboard.html`
- Modify: `src/site/static/js/app.js`
- Modify: `src/site/static/css/style.css`

### Task 4a: dashboard.html 三 Tab 结构

- [ ] **Step 1: 重写 dashboard.html Tab 区域**

Read `src/site/templates/dashboard.html`，找到 `<div class="dashboard-page">` 区块，将其替换为：

```html
<div class="dashboard-page">
    <header class="page-header">
        <h1>📈 仪表盘</h1>
        <div class="tabs">
            <button class="tab active" data-tab="quality">数据质量</button>
            <button class="tab" data-tab="runtime">运行状态</button>
            <button class="tab" data-tab="consumption">资源消耗</button>
        </div>
    </header>

    <!-- 全局 KPI 卡片（跨 Tab 共享） -->
    <div class="kpi-cards" id="global-kpis">
        <div class="kpi-card">
            <div class="kpi-label">总文章数</div>
            <div class="kpi-value" id="kpi-total">-</div>
            <div class="kpi-sub" id="kpi-period">-</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">周期新增</div>
            <div class="kpi-value" id="kpi-period-count">-</div>
            <div class="kpi-sub">近 <span class="range-label">30</span> 天</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">通过率</div>
            <div class="kpi-value" id="kpi-approve-rate">-</div>
            <div class="kpi-sub">审核通过</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">平均分</div>
            <div class="kpi-value" id="kpi-avg-score">-</div>
            <div class="kpi-sub">质量评分</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">活跃源</div>
            <div class="kpi-value" id="kpi-active-sources">-</div>
            <div class="kpi-sub">数据源</div>
        </div>
    </div>

    <!-- Tab 内容区 -->
    <div id="tab-quality" class="tab-content active">
        <div class="charts-layout">
            <div class="chart-card">
                <h3>评分分布</h3>
                <div class="chart-canvas-wrapper"><canvas id="score-dist-chart"></canvas></div>
            </div>
            <div class="chart-card">
                <h3>来源评分排行</h3>
                <div class="source-score-list" id="source-score-list"></div>
            </div>
        </div>
        <div class="chart-card" style="margin-top:1rem">
            <h3>标签云</h3>
            <div class="tag-cloud" id="tag-cloud"></div>
        </div>
    </div>

    <div id="tab-runtime" class="tab-content">
        <div class="kpi-row" style="display:flex;gap:1rem;margin-bottom:1rem">
            <div class="kpi-card" style="flex:1">
                <div class="kpi-label">上次运行</div>
                <div class="kpi-value" id="rt-run-id">-</div>
                <div class="kpi-sub" id="rt-run-time">-</div>
            </div>
            <div class="kpi-card" style="flex:1">
                <div class="kpi-label">运行时长</div>
                <div class="kpi-value" id="rt-duration">-</div>
            </div>
            <div class="kpi-card" style="flex:1">
                <div class="kpi-label">成功率</div>
                <div class="kpi-value" id="rt-success-rate">-</div>
            </div>
            <div class="kpi-card" style="flex:1">
                <div class="kpi-label">失败数</div>
                <div class="kpi-value" id="rt-fail-count">-</div>
            </div>
        </div>
        <div class="chart-card" style="margin-bottom:1rem">
            <h3>Pipeline DAG 状态</h3>
            <div class="pipeline-flow" id="pipeline-flow"></div>
        </div>
        <div class="chart-card">
            <h3>失败日志 <button class="toggle-btn" data-target="failure-table">折叠</button></h3>
            <div id="failure-table" class="log-table-wrapper">
                <table class="log-table">
                    <thead><tr><th>时间</th><th>阶段</th><th>Provider</th><th>标题</th></tr></thead>
                    <tbody id="failure-tbody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <div id="tab-consumption" class="tab-content">
        <div class="kpi-row" style="display:flex;gap:1rem;margin-bottom:1rem">
            <div class="kpi-card" style="flex:1">
                <div class="kpi-label">周期花费</div>
                <div class="kpi-value" id="cs-period-cost">-</div>
            </div>
            <div class="kpi-card" style="flex:1">
                <div class="kpi-label">Token 效率</div>
                <div class="kpi-value" id="cs-token-efficiency">-</div>
                <div class="kpi-sub">$/M tokens</div>
            </div>
            <div class="kpi-card" style="flex:1">
                <div class="kpi-label">预算进度</div>
                <div class="kpi-value" id="cs-budget-progress">-</div>
                <div class="progress-bar-wrapper"><div class="progress-bar" id="cs-progress-bar"></div></div>
            </div>
        </div>
        <div class="charts-layout">
            <div class="chart-card">
                <h3>Provider 费用分解</h3>
                <div class="chart-canvas-wrapper"><canvas id="provider-cost-chart"></canvas></div>
            </div>
            <div class="chart-card">
                <h3>Agent 费用分解</h3>
                <div class="chart-canvas-wrapper"><canvas id="agent-cost-chart"></canvas></div>
            </div>
        </div>
    </div>
</div>
```

### Task 4b: style.css 新增样式

- [ ] **Step 2: 添加 Tab 样式**

在 `src/site/static/css/style.css` 末尾添加：

```css
/* ===== Dashboard Tabs ===== */
.dashboard-page .tabs { display: flex; gap: 0.5rem; background: #1e293b; padding: 0.25rem; border-radius: 8px; margin-bottom: 1.5rem; }
.dashboard-page .tab { padding: 0.5rem 1rem; border-radius: 6px; font-size: 0.875rem; cursor: pointer; color: #94a3b8; border: none; background: none; }
.dashboard-page .tab.active { background: #3b82f6; color: white; }
.dashboard-page .tab:hover:not(.active) { background: #334155; color: #fff; }

.tab-content { display: none; }
.tab-content.active { display: block; }

/* Source score list */
.source-score-list { display: flex; flex-direction: column; gap: 0.5rem; max-height: 250px; overflow-y: auto; }
.source-score-item { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem; background: #f8f8f8; border-radius: 6px; }
.source-score-item .source-name { font-size: 0.85rem; }
.source-score-item .score { font-size: 0.85rem; color: #22c55e; font-weight: bold; }
.source-score-item .count { font-size: 0.75rem; color: #999; }

/* Tag cloud */
.tag-cloud { display: flex; flex-wrap: wrap; gap: 0.5rem; padding: 0.5rem; min-height: 80px; }
.tag-cloud .tag-item { padding: 0.2rem 0.5rem; border-radius: 4px; background: #e8f4ff; color: #1a73e8; }
.tag-cloud .tag-item.large { font-size: 1.1rem; padding: 0.3rem 0.7rem; }
.tag-cloud .tag-item.medium { font-size: 0.9rem; }
.tag-cloud .tag-item.small { font-size: 0.75rem; opacity: 0.7; }

/* Pipeline DAG */
.pipeline-flow { display: flex; align-items: center; gap: 0; margin-bottom: 0.5rem; }
.pipeline-flow .stage { flex: 1; text-align: center; }
.pipeline-flow .stage-box { background: #fff; border: 2px solid #e0e0e0; border-radius: 8px; padding: 0.75rem 0.5rem; margin: 0 0.25rem; }
.pipeline-flow .stage.done .stage-box { border-color: #22c55e; background: #f0fff4; }
.pipeline-flow .stage.running .stage-box { border-color: #fbbf24; background: #fffbeb; animation: glow 2s infinite; }
.pipeline-flow .stage.failed .stage-box { border-color: #ef4444; background: #fff0f0; }
.pipeline-flow .stage-name { font-size: 0.75rem; font-weight: 500; }
.pipeline-flow .stage-duration { font-size: 0.65rem; color: #999; margin-top: 0.2rem; }
.pipeline-flow .arrow { color: #999; font-size: 1rem; }

/* Log table */
.log-table-wrapper { max-height: 200px; overflow-y: auto; }
.log-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.log-table th { text-align: left; padding: 0.5rem; border-bottom: 1px solid #eee; color: #666; }
.log-table td { padding: 0.5rem; border-bottom: 1px solid #f5f5f5; }
.log-table tr:hover { background: #f8f8f8; }

/* Progress bar */
.progress-bar-wrapper { height: 6px; background: #334155; border-radius: 3px; margin-top: 0.5rem; overflow: hidden; }
.progress-bar { height: 100%; background: #3b82f6; border-radius: 3px; transition: width 0.3s; }
.progress-bar.warning { background: #f97316; }
.progress-bar.danger { background: #ef4444; }
```

### Task 4c: app.js Tab 切换逻辑

- [ ] **Step 3: 重写 dashboard 初始化和 Tab 切换逻辑**

Read `src/site/static/js/app.js`，在文件末尾添加（不要修改原有代码）：

```javascript
// Dashboard Tab Controller
(function() {
    let activeTab = 'quality';
    let cachedData = { quality: null, runtime: null, consumption: null };
    let currentRange = 30; // day/week/month

    async function loadTab(tab) {
        if (cachedData[tab]) return cachedData[tab];
        const res = await fetch(`/api/stats/${tab}`);
        const json = await res.json();
        if (json.code !== 0) return null;
        cachedData[tab] = json.data;
        return cachedData[tab];
    }

    function switchTab(tab) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.querySelector(`.tab[data-tab="${tab}"]`).classList.add('active');
        document.getElementById(`tab-${tab}`).classList.add('active');
        activeTab = tab;
        renderTab(tab);
    }

    async function renderTab(tab) {
        const data = await loadTab(tab);
        if (!data) return;
        if (tab === 'quality') renderQuality(data);
        else if (tab === 'runtime') renderRuntime(data);
        else if (tab === 'consumption') renderConsumption(data);
    }

    function renderQuality(data) {
        // 评分分布
        const buckets = ['0-20','20-40','40-60','60-80','80-100'];
        const counts = buckets.map(b => {
            const found = data.score_distribution.find(s => s.bucket === b);
            return found ? found.count : 0;
        });
        renderBarChart('score-dist-chart', buckets, counts, '#3b82f6');

        // 来源评分排行
        const list = document.getElementById('source-score-list');
        if (list) {
            list.innerHTML = (data.source_scores || []).map(s => `
                <div class="source-score-item">
                    <div>
                        <div class="source-name">${s.source_detail || s.source}</div>
                        <div class="count">${s.article_count} 篇</div>
                    </div>
                    <div class="score">${s.avg_score}分</div>
                </div>
            `).join('');
        }

        // 标签云
        const cloud = document.getElementById('tag-cloud');
        if (cloud && data.top_tags) {
            const maxCount = Math.max(...data.top_tags.map(t => t.count));
            cloud.innerHTML = data.top_tags.map(t => {
                const ratio = t.count / maxCount;
                const size = ratio > 0.7 ? 'large' : ratio > 0.4 ? 'medium' : 'small';
                return `<span class="tag-item ${size}">${t.name}</span>`;
            }).join('');
        }
    }

    function renderRuntime(data) {
        if (!data.run) return;
        const run = data.run;
        document.getElementById('rt-run-id').textContent = run.id.slice(-8);
        document.getElementById('rt-run-time').textContent = run.started_at ? run.started_at.slice(0, 16) : '-';

        if (run.started_at && run.ended_at) {
            const start = new Date(run.started_at);
            const end = new Date(run.ended_at);
            const dur = ((end - start) / 1000).toFixed(1);
            document.getElementById('rt-duration').textContent = dur + 's';
        }

        // 解析 summary
        let summary = {};
        try { summary = JSON.parse(run.summary || '{}'); } catch(e) {}
        const total = (summary.approved || 0) + (summary.discarded || 0);
        const rate = total > 0 ? ((summary.approved || 0) / total * 100).toFixed(0) + '%' : '-';
        document.getElementById('rt-success-rate').textContent = rate;
        document.getElementById('rt-fail-count').textContent = (summary.retry || 0) + (summary.discarded || 0);

        // Pipeline DAG
        const flow = document.getElementById('pipeline-flow');
        if (flow && data.phases) {
            const phases = ['collect', 'route', 'analyze', 'aggregate', 'review'];
            const phaseMap = {};
            data.phases.forEach(p => { phaseMap[p.phase] = p; });
            flow.innerHTML = phases.map((p, i) => {
                const info = phaseMap[p] || {};
                const status = info.status || 'pending';
                const duration = info.duration_ms ? (info.duration_ms / 1000).toFixed(1) + 's' : '-';
                return `
                    <div class="stage ${status}">
                        <div class="stage-box">
                            <div class="stage-name">${p}</div>
                            <div class="stage-duration">${duration}</div>
                        </div>
                    </div>
                    ${i < phases.length - 1 ? '<div class="arrow">→</div>' : ''}
                `;
            }).join('');
        }

        // 失败日志
        const tbody = document.getElementById('failure-tbody');
        if (tbody) {
            tbody.innerHTML = (data.failures || []).map(f => `
                <tr>
                    <td>${f.time}</td>
                    <td>${f.stage}</td>
                    <td>${f.provider}</td>
                    <td>${f.title || f.url || '-'}</td>
                </tr>
            `).join('') || '<tr><td colspan="4" style="text-align:center;color:#999">无失败记录</td></tr>';
        }
    }

    function renderConsumption(data) {
        document.getElementById('cs-period-cost').textContent = '$' + (data.period_cost || 0).toFixed(4);
        const tokens = data.period_tokens || 1;
        const cost = data.period_cost || 0;
        const efficiency = (cost / tokens * 1e6).toFixed(2);
        document.getElementById('cs-token-efficiency').textContent = '$' + efficiency;

        // 预算进度（月度 $10）
        const budget = 10.0;
        const progress = Math.min((cost / budget) * 100, 100);
        const bar = document.getElementById('cs-progress-bar');
        if (bar) {
            bar.style.width = progress + '%';
            bar.className = 'progress-bar' + (progress > 80 ? ' danger' : progress > 50 ? ' warning' : '');
        }
        document.getElementById('cs-budget-progress').textContent = progress.toFixed(0) + '%';

        // Provider 费用图
        if (data.provider_daily) {
            const dates = [...new Set(data.provider_daily.map(d => d.date))].sort();
            const providers = [...new Set(data.provider_daily.map(d => d.provider))];
            const datasets = providers.map(p => {
                const pData = data.provider_daily.filter(d => d.provider === p);
                return {
                    label: p,
                    data: dates.map(dt => {
                        const found = pData.find(d => d.date === dt);
                        return found ? found.cost : 0;
                    })
                };
            });
            renderStackedBar('provider-cost-chart', dates.map(d => d.slice(5)), datasets);
        }

        // Agent 费用图
        if (data.agent_daily) {
            const dates = [...new Set(data.agent_daily.map(d => d.date))].sort();
            const agents = [...new Set(data.agent_daily.map(d => d.agent))];
            const colors = ['#3b82f6', '#22c55e', '#f97316', '#ef4444', '#8b5cf6'];
            const datasets = agents.map((a, i) => {
                const aData = data.agent_daily.filter(d => d.agent === a);
                return {
                    label: a,
                    data: dates.map(dt => {
                        const found = aData.find(d => d.date === dt);
                        return found ? found.cost : 0;
                    }),
                    backgroundColor: colors[i % colors.length]
                };
            });
            renderGroupedBar('agent-cost-chart', dates.map(d => d.slice(5)), datasets);
        }
    }

    function renderBarChart(canvasId, labels, data, color) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets: [{ data, backgroundColor: color }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }

    function renderStackedBar(canvasId, labels, datasets) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets: datasets.map(d => ({ ...d, backgroundColor: d.backgroundColor || randomColor() })) },
            options: { responsive: true, maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true } } }
        });
    }

    function renderGroupedBar(canvasId, labels, datasets) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    function randomColor() {
        return '#' + Math.floor(Math.random()*16777215).toString(16);
    }

    document.addEventListener('DOMContentLoaded', async () => {
        // 加载全局 KPI
        const res = await fetch('/api/stats/enhanced');
        const json = await res.json();
        if (json.code === 0) {
            const s = json.data.summary;
            document.getElementById('kpi-total').textContent = (s.total_articles || 0).toLocaleString();
            document.getElementById('kpi-period').textContent = '↑ ' + (s.period_articles || 0);
            document.getElementById('kpi-period-count').textContent = s.period_articles || 0;
            document.getElementById('kpi-avg-score').textContent = (s.avg_score || 0).toFixed(0);
            document.getElementById('kpi-active-sources').textContent = s.active_sources || 0;
        }

        // Tab 切换事件
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => switchTab(tab.dataset.tab));
        });

        // 渲染默认 Tab
        renderTab('quality');
    });
})();
```

- [ ] **Step 4: Commit**

```bash
git add src/site/templates/dashboard.html src/site/static/css/style.css src/site/static/js/app.js
git commit -m "feat: dashboard 三 Tab 结构实现"
```

---

## 自检清单

- [ ] Spec 覆盖检查：每个 Tab 的 KPI + 图表都能在 plan 中找到对应 Task
- [ ] 无 placeholder：所有 SQL、HTML、JS 代码均为完整可执行
- [ ] 类型一致性：CostRecord.ref_url 字段在各文件中统一命名
- [ ] Migration 文件名排序：003 在 001、002 之后

---

**Plan complete.**

Save to: `docs/superpowers/plans/2026-05-23-dashboard-enhancement-plan.md`

**两个执行选项：**

**1. Subagent-Driven（推荐）** — 每 Task 由独立 subagent 执行，两阶段 review

**2. Inline Execution** — 在当前 session 执行，batch 加 checkpoint

选择哪个？