# 增强管理界面实现计划

**目标**: 新增配置查看页、DAG 状态页、增强仪表盘

**架构**: 扩展现有 Jinja2 + Chart.js 模式，新增 3 个 API 端点，CSS 复用现有风格（暗色主题）

**技术栈**: FastAPI, Jinja2, Chart.js CDN, 纯 CSS（无 Tailwind）

---

## 文件结构

```
src/
├── api/
│   ├── config.py          # 新建: /api/config/{type}
│   ├── stats.py           # 新建: /api/stats/enhanced
│   └── routes.py          # 修改: 增加 /api/pipeline/dag
├── graph/
│   └── pipeline.py        # 修改: 阶段时间戳记录
├── site/templates/
│   ├── config.html        # 新建: 配置查看页
│   ├── dag.html          # 新建: DAG 状态页
│   └── dashboard.html    # 修改: 增强仪表盘（替换现有）
└── static/css/
    └── style.css          # 修改: 添加新页面样式

src/db/migrations/
└── 002_phase_logs.sql     # 新建: pipeline_phase_logs 表
```

---

## Task 1: 数据库迁移 - 新建 pipeline_phase_logs 表

**文件:**
- 创建: `src/db/migrations/002_phase_logs.sql`

```sql
-- src/db/migrations/002_phase_logs.sql
CREATE TABLE IF NOT EXISTS pipeline_phase_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL REFERENCES pipeline_runs(id),
    phase       TEXT NOT NULL,
    status      TEXT NOT NULL,
    started_at  TEXT,
    ended_at    TEXT,
    duration_ms INTEGER,
    details     TEXT
);

CREATE INDEX IF NOT EXISTS idx_phase_logs_run ON pipeline_phase_logs(run_id);
```

- [ ] **Step 1: 创建迁移文件**

```bash
cat > /Users/liufukang/Workplace/ai-knowledge-base/src/db/migrations/002_phase_logs.sql << 'EOF'
CREATE TABLE IF NOT EXISTS pipeline_phase_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL REFERENCES pipeline_runs(id),
    phase       TEXT NOT NULL,
    status      TEXT NOT NULL,
    started_at  TEXT,
    ended_at    TEXT,
    duration_ms INTEGER,
    details     TEXT
);

CREATE INDEX IF NOT EXISTS idx_phase_logs_run ON pipeline_phase_logs(run_id);
EOF
```

- [ ] **Step 2: 在 database.py 中添加迁移逻辑**

查看 `src/core/database.py` 确认迁移机制，添加对 002 的处理。

- [ ] **Step 3: 测试迁移执行**

```bash
cd /Users/liufukang/Workplace/ai-knowledge-base
uv run python -c "import asyncio; from src.core.database import Database; asyncio.run(Database('data/knowledge.db').run_migrations())"
```

---

## Task 2: 修改 pipeline.py 添加阶段时间戳记录

**文件:**
- 修改: `src/graph/pipeline.py`

- [ ] **Step 1: 在 pipeline.py 添加阶段记录函数**

在文件顶部添加:

```python
from datetime import datetime, timezone
from ..db.operations import save_phase_log, update_phase_log

PHASES = ["collect", "route", "analyze", "aggregate", "review"]

async def record_phase_start(db, run_id: str, phase: str):
    await db.execute(
        "INSERT INTO pipeline_phase_logs (run_id, phase, status, started_at) VALUES (?, ?, ?, ?)",
        (run_id, phase, "running", datetime.now(timezone.utc).isoformat())
    )

async def record_phase_end(db, run_id: str, phase: str, status: str, details: str = None):
    ended_at = datetime.now(timezone.utc).isoformat()
    row = await db.fetch_one(
        "SELECT started_at FROM pipeline_phase_logs WHERE run_id=? AND phase=? AND status='running' ORDER BY id DESC LIMIT 1",
        (run_id, phase)
    )
    duration_ms = None
    if row and row["started_at"]:
        start = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    await db.execute(
        "UPDATE pipeline_phase_logs SET status=?, ended_at=?, duration_ms=?, details=? WHERE run_id=? AND phase=? AND status='running'",
        (status, ended_at, duration_ms, details, run_id, phase)
    )
```

- [ ] **Step 2: 在 main.py 的 run_pipeline 中调用记录函数**

在 `run_pipeline` 的各阶段开始/结束处添加 `record_phase_start` / `record_phase_end` 调用。具体位置需要根据 main.py 中 pipeline 调用的位置确定。

- [ ] **Step 3: 验证阶段记录**

```bash
curl -X POST http://localhost:8000/api/pipeline/run
# 检查数据库
uv run python -c "import asyncio; from src.core.database import Database; asyncio.run(Database('data/knowledge.db').fetch_all('SELECT * FROM pipeline_phase_logs'))"
```

---

## Task 3: 新建 /api/config/{type} 端点

**文件:**
- 创建: `src/api/config.py`
- 修改: `src/main.py`（注册路由）

- [ ] **Step 1: 创建 config.py**

```python
# src/api/config.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import yaml
from ..core.config import load_llm_config, load_sources_config, load_agents_config

router = APIRouter(prefix="/api/config")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"

@router.get("/{config_type}")
async def get_config(config_type: str):
    if config_type not in ("llm", "sources", "agents"):
        raise HTTPException(400, "无效的配置类型")

    loaders = {
        "llm": (load_llm_config, CONFIG_DIR / "llm.yaml"),
        "sources": (load_sources_config, CONFIG_DIR / "sources.yaml"),
        "agents": (load_agents_config, CONFIG_DIR / "agents.yaml"),
    }

    loader, path = loaders[config_type]
    try:
        config = loader(path)
    except Exception as e:
        raise HTTPException(500, f"加载配置失败: {e}")

    with open(path) as f:
        raw = f.read()

    return {
        "code": 0,
        "data": {
            "raw": raw,
            "parsed": config.model_dump(),
        },
        "message": "ok"
    }
```

- [ ] **Step 2: 在 main.py 注册路由**

在 `main.py` 中添加:
```python
from .api.config import router as config_router
app.include_router(config_router)
```

- [ ] **Step 3: 测试端点**

```bash
curl http://localhost:8000/api/config/llm
curl http://localhost:8000/api/config/sources
curl http://localhost:8000/api/config/agents
```

---

## Task 4: 新建 /api/stats/enhanced 端点

**文件:**
- 创建: `src/api/stats.py`
- 修改: `src/main.py`（注册路由）

- [ ] **Step 1: 创建 stats.py**

```python
# src/api/stats.py
from fastapi import APIRouter, Query
from datetime import datetime, timezone, timedelta
from ..core.database import Database

router = APIRouter(prefix="/api/stats")

@router.get("/enhanced")
async def get_stats_enhanced(db: Database, days: int = Query(default=30, ge=1, le=3650)):
    # 获取基础统计
    total = await db.fetch_one("SELECT COUNT(*) as c FROM articles WHERE status='approved'")
    period = await db.fetch_one(
        "SELECT COUNT(*) as c FROM articles WHERE status='approved' AND collected_at >= date('now', ?)",
        (f"-{days} days",)
    )
    cost_period = await db.fetch_one(
        "SELECT COALESCE(SUM(cost),0) as t FROM cost_logs WHERE created_at >= date('now', ?)",
        (f"-{days} days",)
    )
    cost_total = await db.fetch_one("SELECT COALESCE(SUM(cost),0) as t FROM cost_logs")
    active_sources = await db.fetch_one(
        "SELECT COUNT(DISTINCT source) as c FROM articles WHERE status='approved' AND collected_at >= date('now', ?)",
        (f"-{days} days",)
    )

    # 小时粒度 (过去 48 小时)
    hourly = await db.fetch_all("""
        SELECT strftime('%Y-%m-%dT%H:00', created_at) as hour,
               SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= datetime('now', '-2 days')
        GROUP BY hour ORDER BY hour
    """)

    # 日粒度
    daily = await db.fetch_all("""
        SELECT date(created_at) as date, SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= date('now', ?)
        GROUP BY date(created_at) ORDER BY date
    """, (f"-{days} days",))

    # 周粒度 (过去 12 周)
    weekly = await db.fetch_all("""
        SELECT strftime('%Y-W%W', created_at) as week,
               SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= datetime('now', '-12 weeks')
        GROUP BY week ORDER BY week
    """)

    # 月粒度 (过去 12 月)
    monthly = await db.fetch_all("""
        SELECT strftime('%Y-%m', created_at) as month,
               SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= datetime('now', '-12 months')
        GROUP BY month ORDER BY month
    """)

    # 来源分布
    source_dist = await db.fetch_all("""
        SELECT source, COUNT(*) as count
        FROM articles WHERE status='approved'
        GROUP BY source ORDER BY count DESC
    """)

    return {
        "code": 0,
        "data": {
            "summary": {
                "total_articles": total["c"] if total else 0,
                "period_articles": period["c"] if period else 0,
                "period_cost": round(cost_period["t"] if cost_period else 0, 4),
                "total_cost": round(cost_total["t"] if cost_total else 0, 4),
                "active_sources": active_sources["c"] if active_sources else 0,
            },
            "hourly_cost": [dict(r) for r in hourly],
            "daily_cost": [dict(r) for r in daily],
            "weekly_cost": [dict(r) for r in weekly],
            "monthly_cost": [dict(r) for r in monthly],
            "source_distribution": [dict(r) for r in source_dist],
        },
        "message": "ok"
    }
```

- [ ] **Step 2: 在 main.py 注册路由**

```python
from .api.stats import router as stats_router
app.include_router(stats_router)
```

- [ ] **Step 3: 测试端点**

```bash
curl http://localhost:8000/api/stats/enhanced
```

---

## Task 5: 新建 /api/pipeline/dag 端点

**文件:**
- 修改: `src/api/routes.py`

- [ ] **Step 1: 在 routes.py 添加 dag 端点**

在 `_run_pipeline_cb` 附近添加:

```python
@router.get("/pipeline/dag")
async def get_pipeline_dag():
    if not _db:
        raise HTTPException(500, "DB not initialized")
    # 获取最近一次运行的 ID
    last_run = await _db.fetch_one(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
    )
    if not last_run:
        return envelope({"status": "idle", "phases": [], "logs": []})

    run_id = last_run["id"]
    phases = await _db.fetch_all(
        "SELECT phase, status, started_at, ended_at, duration_ms, details FROM pipeline_phase_logs WHERE run_id=? ORDER BY id",
        (run_id,)
    )

    # 生成执行日志摘要
    logs = []
    for p in phases:
        if p["status"] == "done":
            logs.append({"time": p["started_at"][11:19] if p["started_at"] else "", "message": f"{p['phase']} 完成", "level": "success"})
        elif p["status"] == "running":
            logs.append({"time": p["started_at"][11:19] if p["started_at"] else "", "message": f"{p['phase']} 进行中", "level": "info"})

    return envelope({
        "run_id": run_id,
        "status": last_run["status"],
        "current_phase": phases[-1]["phase"] if phases and phases[-1]["status"] == "running" else phases[-1]["phase"] if phases else None,
        "phases": [dict(p) for p in phases],
        "logs": logs,
    })
```

- [ ] **Step 2: 测试端点**

```bash
# 先触发一次 pipeline
curl -X POST http://localhost:8000/api/pipeline/run
# 等待几秒后查询
curl http://localhost:8000/api/pipeline/dag
```

---

## Task 6: 配置查看页模板

**文件:**
- 创建: `src/site/templates/config.html`

- [ ] **Step 1: 创建 config.html**

```html
{% extends "base.html" %}
{% block title %}配置查看{% endblock %}
{% block content %}
<div class="config-page">
    <header class="page-header">
        <h1>⚙️ 配置管理</h1>
        <span class="badge">只读</span>
    </header>

    <div class="config-grid">
        <div class="config-card">
            <h3>🤖 LLM Providers</h3>
            <div id="llm-content">加载中...</div>
        </div>
        <div class="config-card">
            <h3>📡 数据源</h3>
            <div id="sources-content">加载中...</div>
        </div>
        <div class="config-card">
            <h3>🧠 Agents</h3>
            <div id="agents-content">加载中...</div>
        </div>
    </div>
</div>

<script>
async function loadConfig(type, containerId) {
    try {
        const res = await fetch(`/api/config/${type}`);
        const json = await res.json();
        if (json.code !== 0) throw new Error(json.message);
        renderConfig(type, json.data.parsed, document.getElementById(containerId));
    } catch (e) {
        document.getElementById(containerId).innerHTML = `<p class="error">加载失败: ${e.message}</p>`;
    }
}

function renderConfig(type, data, container) {
    if (type === 'llm') {
        container.innerHTML = Object.entries(data.providers).map(([name, p]) => `
            <div class="config-item">
                <div class="config-item-header">
                    <span class="dot active"></span>
                    <span class="name">${name}</span>
                    <span class="meta">${p.models.length} models</span>
                </div>
                <div class="config-models">
                    ${p.models.map(m => `<span class="model-tag">${m.id}</span>`).join('')}
                </div>
            </div>
        `).join('');
    } else if (type === 'sources') {
        container.innerHTML = data.sources.map(s => `
            <div class="config-item ${s.enabled ? '' : 'disabled'}">
                <div class="config-item-header">
                    <span class="dot ${s.enabled ? 'active' : ''}"></span>
                    <span class="name">${s.id}</span>
                    <span class="meta">${s.cron}</span>
                </div>
            </div>
        `).join('');
    } else if (type === 'agents') {
        container.innerHTML = Object.entries(data.agents).map(([name, a]) => `
            <div class="config-item">
                <div class="config-item-header">
                    <span class="dot active"></span>
                    <span class="name">${name}</span>
                    <span class="meta">${a.model.primary.provider}/${a.model.primary.model}</span>
                </div>
            </div>
        `).join('');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadConfig('llm', 'llm-content');
    loadConfig('sources', 'sources-content');
    loadConfig('agents', 'agents-content');
});
</script>
{% endblock %}
```

---

## Task 7: DAG 状态页模板

**文件:**
- 创建: `src/site/templates/dag.html`

- [ ] **Step 1: 创建 dag.html**

```html
{% extends "base.html" %}
{% block title %}Pipeline DAG 状态{% endblock %}
{% block content %}
<div class="dag-page">
    <header class="page-header">
        <h1>📊 Pipeline DAG 状态</h1>
    </header>

    <div class="dag-status-bar" id="status-bar">
        <div class="status-dot" id="status-dot"></div>
        <div>
            <div class="status-text" id="status-text">加载中...</div>
            <div class="phase-text" id="phase-text"></div>
        </div>
        <div class="run-info" id="run-info"></div>
    </div>

    <div class="pipeline-flow" id="pipeline-flow">
        <div class="stage" data-phase="collect"><div class="stage-box"><div class="stage-icon">📥</div><div class="stage-name">采集</div><div class="stage-time" id="time-collect">-</div></div></div>
        <div class="arrow">→</div>
        <div class="stage" data-phase="route"><div class="stage-box"><div class="stage-icon">🔀</div><div class="stage-name">路由</div><div class="stage-time" id="time-route">-</div></div></div>
        <div class="arrow">→</div>
        <div class="stage" data-phase="analyze"><div class="stage-box"><div class="stage-icon">🧠</div><div class="stage-name">分析</div><div class="stage-time" id="time-analyze">-</div></div></div>
        <div class="arrow">→</div>
        <div class="stage" data-phase="aggregate"><div class="stage-box"><div class="stage-icon">📝</div><div class="stage-name">汇总</div><div class="stage-time" id="time-aggregate">-</div></div></div>
        <div class="arrow">→</div>
        <div class="stage" data-phase="review"><div class="stage-box"><div class="stage-icon">✅</div><div class="stage-name">审核</div><div class="stage-time" id="time-review">-</div></div></div>
    </div>

    <div class="dag-details">
        <h3>📋 执行日志</h3>
        <div class="logs" id="logs">
            <div class="log-entry"><span class="log-time">-</span><span class="log-msg">加载中...</span></div>
        </div>
    </div>
</div>

<script>
const PHASE_NAMES = {collect:'采集', route:'路由', analyze:'分析', aggregate:'汇总', review:'审核'};

async function fetchDag() {
    try {
        const res = await fetch('/api/pipeline/dag');
        const json = await res.json();
        if (json.code !== 0) throw new Error(json.message);
        updateDag(json.data);
    } catch (e) {
        console.error(e);
    }
}

function updateDag(data) {
    // 更新状态栏
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const phaseText = document.getElementById('phase-text');
    const runInfo = document.getElementById('run-info');

    statusDot.className = 'status-dot ' + data.status;
    statusText.textContent = data.status === 'running' ? '运行中' : data.status === 'done' ? '已完成' : '空闲';
    phaseText.textContent = data.current_phase ? `阶段: ${PHASE_NAMES[data.current_phase] || data.current_phase}` : '';
    runInfo.innerHTML = data.run_id ? `<div>${data.run_id}</div><div class="run-time">${data.phases[0]?.started_at || ''}</div>` : '';

    // 更新阶段状态
    const phases = data.phases || [];
    const phaseMap = {};
    phases.forEach(p => phaseMap[p.phase] = p);

    ['collect', 'route', 'analyze', 'aggregate', 'review'].forEach(phase => {
        const stage = document.querySelector(`.stage[data-phase="${phase}"]`);
        const timeEl = document.getElementById(`time-${phase}`);
        const p = phaseMap[phase];

        stage.className = 'stage';
        if (p) {
            if (p.status === 'done') stage.classList.add('done');
            else if (p.status === 'running') stage.classList.add('active');
            else stage.classList.add('waiting');

            if (p.duration_ms) {
                timeEl.textContent = (p.duration_ms / 1000).toFixed(0) + 's';
            } else if (p.status === 'running') {
                timeEl.textContent = '进行中';
            }
        } else {
            stage.classList.add('waiting');
        }
    });

    // 更新日志
    const logsEl = document.getElementById('logs');
    if (data.logs && data.logs.length) {
        logsEl.innerHTML = data.logs.map(l => `
            <div class="log-entry ${l.level}">
                <span class="log-time">${l.time}</span>
                <span class="log-msg">${l.message}</span>
            </div>
        `).join('');
    } else {
        logsEl.innerHTML = '<div class="log-entry"><span class="log-time">-</span><span class="log-msg">暂无日志</span></div>';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    fetchDag();
    setInterval(fetchDag, 5000);
});
</script>
{% endblock %}
```

---

## Task 8: 增强仪表盘模板

**文件:**
- 修改: `src/site/templates/dashboard.html`

- [ ] **Step 1: 创建增强 dashboard.html**

```html
{% extends "base.html" %}
{% block title %}仪表盘{% endblock %}
{% block content %}
<div class="dashboard-page">
    <header class="page-header">
        <h1>📈 仪表盘</h1>
        <div class="tabs">
            <button class="tab active" data-view="day">天</button>
            <button class="tab" data-view="week">周</button>
            <button class="tab" data-view="month">月</button>
        </div>
    </header>

    <div class="kpi-cards">
        <div class="kpi-card">
            <div class="kpi-label">总文章数</div>
            <div class="kpi-value" id="kpi-total">-</div>
            <div class="kpi-sub"><span id="kpi-period" class="trend">-</span> 本周期新增</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">周期费用</div>
            <div class="kpi-value" id="kpi-cost">-</div>
            <div class="kpi-sub" id="kpi-cost-trend">-</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">日均采集</div>
            <div class="kpi-value" id="kpi-daily">-</div>
            <div class="kpi-sub">近 30 天</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">活跃源</div>
            <div class="kpi-value" id="kpi-sources">-</div>
            <div class="kpi-sub" id="kpi-sources-sub">-</div>
        </div>
    </div>

    <div class="charts-layout">
        <div class="chart-card">
            <h3>💰 成本趋势</h3>
            <canvas id="cost-chart"></canvas>
            <div class="chart-legend">
                <span><span class="dot" style="background:#3b82f6"></span> 实际成本</span>
                <span><span class="dot" style="background:#22c55e"></span> 滚动均值</span>
            </div>
        </div>
        <div class="chart-card">
            <h3>📊 来源分布</h3>
            <div class="source-list" id="source-list"></div>
        </div>
    </div>
</div>

<script>
let costChart = null;
let currentView = 'day';

async function loadStats() {
    const res = await fetch('/api/stats/enhanced');
    const json = await res.json();
    if (json.code !== 0) return;
    updateDashboard(json.data);
}

function updateDashboard(data) {
    const s = data.summary;
    document.getElementById('kpi-total').textContent = s.total_articles.toLocaleString();
    document.getElementById('kpi-period').textContent = '↑ ' + s.period_articles;
    document.getElementById('kpi-cost').textContent = '$' + s.period_cost.toFixed(2);
    document.getElementById('kpi-daily').textContent = '~' + Math.round(s.period_articles / 30);
    document.getElementById('kpi-sources').textContent = s.active_sources;
    document.getElementById('kpi-sources-sub').textContent = '个活跃数据源';

    // 来源分布
    const list = document.getElementById('source-list');
    const max = Math.max(...data.source_distribution.map(s => s.count), 1);
    list.innerHTML = data.source_distribution.map(src => `
        <div class="source-item">
            <div class="source-info">
                <span class="source-name">${src.source}</span>
                <span class="source-count">${src.count.toLocaleString()}</span>
            </div>
            <div class="source-bar"><div class="source-bar-fill" style="width:${(src.count/max*100).toFixed(0)}%"></div></div>
        </div>
    `).join('');

    updateChart(data);
}

function updateChart(data) {
    const ctx = document.getElementById('cost-chart').getContext('2d');
    let labels, costData;

    if (currentView === 'day') {
        labels = data.daily_cost.map(d => d.date.slice(5));
        costData = data.daily_cost.map(d => d.cost);
    } else if (currentView === 'week') {
        labels = data.weekly_cost.map(d => d.week);
        costData = data.weekly_cost.map(d => d.cost);
    } else {
        labels = data.monthly_cost.map(d => d.month);
        costData = data.monthly_cost.map(d => d.cost);
    }

    // 计算滚动均值 (7日或4周)
    const windowSize = currentView === 'day' ? 7 : currentView === 'week' ? 4 : 3;
    const avgData = costData.map((_, i) => {
        const start = Math.max(0, i - windowSize + 1);
        const slice = costData.slice(start, i + 1);
        return slice.reduce((a, b) => a + b, 0) / slice.length;
    });

    if (costChart) costChart.destroy();
    costChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label: '成本', data: costData, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)', fill: true, tension: 0.4 },
                { label: '均值', data: avgData, borderColor: '#22c55e', borderDash: [5, 5], fill: false, tension: 0.4 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
                y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', callback: v => '$' + v.toFixed(2) } }
            }
        }
    });
}

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        currentView = tab.dataset.view;
        loadStats();
    });
});

document.addEventListener('DOMContentLoaded', loadStats);
</script>
{% endblock %}
```

---

## Task 9: 更新 CSS 样式

**文件:**
- 修改: `src/static/css/style.css`

- [ ] **Step 1: 添加新页面样式**

在 style.css 末尾添加:

```css
/* ===== 配置页 ===== */
.config-page .page-header { display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem; }
.config-page .badge { background: #1e40af; color: #93c5fd; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; }
.config-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
.config-card { background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }
.config-card h3 { font-size: 0.875rem; color: #94a3b8; margin-bottom: 1rem; text-transform: uppercase; }
.config-item { background: #0f172a; border-radius: 8px; padding: 0.75rem; margin-bottom: 0.5rem; }
.config-item.disabled { opacity: 0.5; }
.config-item-header { display: flex; align-items: center; gap: 0.75rem; }
.config-item .dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; }
.config-item.disabled .dot { background: #64748b; }
.config-item .name { flex: 1; font-size: 0.875rem; }
.config-item .meta { font-size: 0.75rem; color: #94a3b8; }
.config-models { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }
.model-tag { background: #334155; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }

/* ===== DAG 状态页 ===== */
.dag-page .page-header { margin-bottom: 2rem; }
.dag-status-bar { background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; border: 1px solid #334155; display: flex; align-items: center; gap: 1.5rem; }
.dag-status-bar .status-dot { width: 12px; height: 12px; border-radius: 50%; background: #64748b; }
.dag-status-bar .status-dot.running { background: #22c55e; animation: pulse 2s infinite; }
.dag-status-bar .status-dot.done { background: #22c55e; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.dag-status-bar .run-info { margin-left: auto; text-align: right; font-size: 0.875rem; }
.dag-status-bar .run-time { font-size: 0.75rem; color: #94a3b8; }
.pipeline-flow { display: flex; align-items: center; gap: 0; margin-bottom: 2rem; }
.stage { flex: 1; text-align: center; }
.stage-box { background: #1e293b; border: 2px solid #334155; border-radius: 12px; padding: 1.25rem 1rem; margin: 0 0.5rem; }
.stage.done .stage-box { border-color: #22c55e; background: #052e16; }
.stage.active .stage-box { border-color: #fbbf24; background: #451a03; animation: glow 2s infinite; }
@keyframes glow { 0%, 100% { box-shadow: 0 0 0 0 rgba(251,191,36,0.4); } 50% { box-shadow: 0 0 20px 4px rgba(251,191,36,0.2); } }
.stage.waiting .stage-box { opacity: 0.5; }
.stage-icon { font-size: 1.5rem; margin-bottom: 0.5rem; }
.stage-name { font-size: 0.875rem; font-weight: 500; }
.stage-time { font-size: 0.75rem; color: #94a3b8; margin-top: 0.25rem; }
.pipeline-flow .arrow { color: #334155; font-size: 1.5rem; }
.dag-details { background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }
.dag-details h3 { font-size: 0.875rem; color: #94a3b8; margin-bottom: 1rem; text-transform: uppercase; }
.logs { max-height: 200px; overflow-y: auto; }
.log-entry { display: flex; gap: 1rem; padding: 0.5rem 0; border-bottom: 1px solid #334155; font-size: 0.875rem; }
.log-time { color: #64748b; min-width: 80px; }
.log-entry.success .log-msg { color: #22c55e; }
.log-entry.info .log-msg { color: #60a5fa; }

/* ===== 仪表盘 ===== */
.dashboard-page .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
.dashboard-page .tabs { display: flex; gap: 0.5rem; background: #1e293b; padding: 0.25rem; border-radius: 8px; }
.dashboard-page .tab { padding: 0.5rem 1rem; border-radius: 6px; font-size: 0.875rem; cursor: pointer; color: #94a3b8; border: none; background: none; }
.dashboard-page .tab.active { background: #3b82f6; color: white; }
.kpi-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
.kpi-card { background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }
.kpi-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; margin-bottom: 0.5rem; }
.kpi-value { font-size: 2rem; font-weight: 700; }
.kpi-sub { font-size: 0.75rem; color: #64748b; margin-top: 0.25rem; }
.kpi-sub .trend { color: #22c55e; }
.kpi-sub .trend.down { color: #ef4444; }
.charts-layout { display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; }
.chart-card { background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }
.chart-card h3 { font-size: 0.875rem; color: #94a3b8; margin-bottom: 1rem; text-transform: uppercase; }
.chart-legend { display: flex; gap: 1.5rem; margin-top: 1rem; font-size: 0.75rem; color: #94a3b8; }
.chart-legend .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 0.5rem; }
.source-list { display: flex; flex-direction: column; gap: 0.5rem; }
.source-info { display: flex; justify-content: space-between; margin-bottom: 0.25rem; }
.source-name { font-size: 0.875rem; }
.source-count { font-size: 0.875rem; color: #94a3b8; }
.source-bar { height: 4px; background: #334155; border-radius: 2px; overflow: hidden; }
.source-bar-fill { height: 100%; background: #3b82f6; border-radius: 2px; transition: width 0.3s; }
```

---

## Task 10: 更新导航

**文件:**
- 修改: `src/site/templates/base.html`

- [ ] **Step 1: 添加新页面导航链接**

将 nav 修改为:

```html
<nav>
    <a href="/">首页</a> |
    <a href="/dashboard.html">仪表盘</a> |
    <a href="/dag.html">DAG</a> |
    <a href="/config.html">配置</a>
</nav>
```

---

## Task 11: 端到端测试

- [ ] **Step 1: 测试配置页**

```bash
open http://localhost:8000/config.html
# 验证三个配置卡片正确显示
```

- [ ] **Step 2: 测试 DAG 页**

```bash
# 先触发 pipeline
curl -X POST http://localhost:8000/api/pipeline/run
# 等待几秒
open http://localhost:8000/dag.html
# 验证阶段状态更新
```

- [ ] **Step 3: 测试仪表盘**

```bash
open http://localhost:8000/dashboard.html
# 验证 Tab 切换 (天/周/月) 和图表渲染
```

- [ ] **Step 4: 验证响应信封**

```bash
curl http://localhost:8000/api/config/llm | jq .
curl http://localhost:8000/api/stats/enhanced | jq .
curl http://localhost:8000/api/pipeline/dag | jq .
```

---

## 执行选项

**计划完成并保存至 `docs/superpowers/plans/2026-05-17-enhance-admin-ui-plan.md`**

两种执行方式：

**1. 子代理驱动（推荐）** - 每个任务由新的子代理执行，任务间有检查点

**2. 批量执行** - 在本会话中按批次执行任务，带检查点

选择哪种方式？