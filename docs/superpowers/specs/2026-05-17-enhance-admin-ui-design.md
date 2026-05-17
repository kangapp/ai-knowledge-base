# 增强管理界面设计

**日期**: 2026-05-17
**状态**: 已批准

## 1. 概述

为 ai-knowledge-base 项目新增三个管理页面，实现配置可视化、DAG 状态监控、增强型仪表盘。

## 2. 新增页面

| 路径 | 模板文件 | 说明 |
|------|----------|------|
| `/config.html` | `src/site/templates/config.html` | 配置查看页（只读） |
| `/dag.html` | `src/site/templates/dag.html` | Pipeline DAG 状态页 |
| `/dashboard.html` | `src/site/templates/dashboard.html` | 增强仪表盘（替换现有 Chart.js 页面） |

## 3. 新增 API 端点

### 3.1 GET /api/config/{type}

返回指定配置文件内容。

**路径参数**:
- `type`: `llm` | `sources` | `agents`

**响应**:
```json
{
  "code": 0,
  "data": { "raw": "...yaml内容...", "parsed": {...} },
  "message": "ok"
}
```

**实现位置**: `src/api/config.py`（新文件）

### 3.2 GET /api/pipeline/dag

返回当前/最近一次 pipeline run 的各阶段状态。

**响应**:
```json
{
  "code": 0,
  "data": {
    "run_id": "20250517-001",
    "status": "running",
    "current_phase": "analyzing",
    "phases": [
      { "name": "collect", "status": "done", "duration": 12, "started_at": "...", "ended_at": "..." },
      { "name": "route", "status": "done", "duration": 2, "started_at": "...", "ended_at": "..." },
      { "name": "analyze", "status": "running", "duration": 45, "started_at": "...", "ended_at": null },
      { "name": "aggregate", "status": "waiting", "duration": null, "started_at": null, "ended_at": null },
      { "name": "review", "status": "waiting", "duration": null, "started_at": null, "ended_at": null }
    ],
    "logs": [
      { "time": "14:30:00", "message": "Pipeline 启动", "level": "success" }
    ]
  },
  "message": "ok"
}
```

**实现位置**: `src/api/pipeline.py`（扩展现有文件）

**数据来源**:
- `pipeline_runs` 表记录每次 run 的起止时间、状态
- 各阶段状态通过在 `graph/pipeline.py` 中记录阶段转换时间戳到 State 或独立表
- 日志从 State 的 event_history 或独立 log 表获取

### 3.3 GET /api/stats/enhanced

返回增强统计数据（天/周/月粒度）。

**响应**:
```json
{
  "code": 0,
  "data": {
    "summary": {
      "total_articles": 18250,
      "period_articles": 127,
      "period_cost": 2.84,
      "total_cost": 48.52,
      "active_sources": 10
    },
    "hourly_cost": [
      { "hour": "2026-05-17T00", "cost": 0.02, "articles": 3 },
      ...
    ],
    "daily_cost": [
      { "date": "2026-05-01", "cost": 0.12, "articles": 52 },
      ...
    ],
    "weekly_cost": [
      { "week": "2026-W20", "cost": 0.85, "articles": 350 },
      ...
    ],
    "monthly_cost": [
      { "month": "2026-04", "cost": 3.21, "articles": 1450 },
      ...
    ],
    "source_distribution": [
      { "source": "github", "count": 4521 },
      ...
    ]
  },
  "message": "ok"
}
```

**实现位置**: `src/api/stats.py`（新文件或扩展 routes.py）

## 4. 页面设计

### 4.1 配置查看页 (config.html)

三列卡片布局：

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ LLM Providers│  │ 数据源      │  │ Agents     │
├─────────────┤  ├─────────────┤  ├─────────────┤
│ deepseek ✓ │  │ github ✓   │  │ github_an.. │
│ openai   ✓ │  │ 36kr     ✓ │  │ rss_anal..  │
│ minimax  ✓ │  │ 虎嗅     ✓ │  │ reviewer..  │
└─────────────┘  └─────────────┘  └─────────────┘
```

- 显示各配置的启用/禁用状态
- 每项显示关键信息（model 数量、cron 频率、绑定的 model）
- 纯展示，点击不编辑

### 4.2 DAG 状态页 (dag.html)

**状态显示**:

```
┌─────────────────────────────────────────────┐
│ Pipeline Run #123  ·  2026-05-17 14:30      │
│ 状态: ● 运行中  ·  阶段: 分析中              │
└─────────────────────────────────────────────┘

[  采集  ] → [  路由  ] → [  分析  ] → [  汇总  ] → [  审核  ]
   ✓ 完成       ✓ 完成       ● 进行中      ○ 等待       ○ 等待

耗时: 12s          2s          45s (进行中)   -           -
```

- 五个阶段横向排列，箭头连接
- 三种状态样式：完成（绿色）、进行中（黄色脉冲）、等待（灰色）
- 阶段下方显示耗时

**执行日志**:

```
📋 执行日志
14:30:00  Pipeline 启动 (手动触发)
14:30:02  开始采集 8 个数据源...
14:30:12  采集完成: github +8, rss +5...
...
```

- 实时刷新（每 5 秒轮询 /api/pipeline/dag）
- 不同级别日志用不同颜色标识

### 4.3 增强仪表盘 (dashboard.html)

**Tab 切换**: 天 / 周 / 月

**统计卡片** (4列):

| 总文章数 | 周期费用 | 日均采集 | 活跃源 |
|---------|---------|---------|-------|
| 18,250  | $2.84   | ~50     | 10    |

**图表区** (2/3 + 1/3 布局):

- 成本趋势图（折线图 + 滚动均值线）
- 来源分布图（水平条形图）

**时间粒度**:

- 天视图: 过去 48 小时小时粒度
- 周视图: 过去 12 周周聚合
- 月视图: 过去 12 月月聚合

## 5. 实现步骤

1. **数据层**
   - 扩展 `pipeline_runs` 表或新建 `pipeline_phase_logs` 表记录各阶段起止时间
   - 在 `graph/pipeline.py` 各阶段转换时写入时间戳
   - 扩展 `get_stats` 支持 hourly/weekly/monthly 聚合查询

2. **API 层**
   - 新建 `src/api/config.py` 实现 /api/config/{type}
   - 扩展 `src/api/routes.py` 添加 /api/pipeline/dag
   - 新建 `src/api/stats.py` 或扩展现有实现 /api/stats/enhanced

3. **前端层**
   - 新建 `src/site/templates/config.html`
   - 新建 `src/site/templates/dag.html`
   - 新建 `src/site/templates/dashboard.html`
   - 复用 Chart.js CDN，保持现有风格

## 6. 技术约束

- 不引入新的前端框架，保持 Jinja2 + 原生 JS
- 不修改现有 API 响应格式，保持统一信封
- 配置页为只读，不写 YAML 文件
- DAG 状态轮询间隔 5 秒，避免频繁刷新