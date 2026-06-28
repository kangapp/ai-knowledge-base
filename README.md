# AI Knowledge Base

个人 AI 知识库系统 — 自动采集 AI/LLM/Agent 领域资讯，经 LLM 分析审核后生成静态网站展示。

## 项目概览

| 指标 | 说明 |
|------|------|
| **技术栈** | Python 3.12+ / LangGraph / FastAPI / SQLite / Jinja2 / Chart.js |
| **部署** | Docker Compose (1C2G VPS) |
| **日均采集** | ~50 条，年数据量 ~20MB |
| **成本** | ¥85-125/月 (VPS + 域名 + LLM API) |

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           GitHub Actions CI/CD                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         VPS (1C2G)                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                 Docker Compose                                │  │
│  │  ┌─────────────────┐    ┌─────────────────┐                    │  │
│  │  │   pipeline      │    │      web        │                    │  │
│  │  │  (Python/FastAPI)│    │    (Caddy)     │                    │  │
│  │  │  - APScheduler  │    │  - 静态文件服务  │                    │  │
│  │  │  - LangGraph    │───▶│  - API 反向代理  │                    │  │
│  │  │  - Site Builder │    │                 │                    │  │
│  │  └─────────────────┘    └─────────────────┘                    │  │
│  │         │                       │                              │  │
│  │         ▼                       ▼                              │  │
│  │  ┌─────────────────────────────────────────────────────┐      │  │
│  │  │              ./data (SQLite)  │  ./output (静态站)   │      │  │
│  │  └─────────────────────────────────────────────────────┘      │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## 完整数据流程

```mermaid
flowchart TD
    subgraph Scheduler["定时调度"]
        A["APScheduler\ncron 触发"] --> B["skip_if_running\n防重叠"]
    end

    subgraph Collection["采集阶段"]
        B --> C["Collector\n按源并行采集"]
        C --> D["DB 批量查重\nWHERE url IN (...)"]
        D --> E["采集完成回调\n写入 health log"]
    end

    subgraph Analysis["分析阶段"]
        E --> F["Router\n100% 规则分流"]
        F --> G["Analyzer Fan-out\n4 并行"]
        G --> H["Aggregator\n汇总 + 校验"]
    end

    subgraph Review["审核阶段"]
        H --> I["Reviewer\n四维评分"]
        I --> J{"评分结果"}
        J -->|≥80| K["approved → 入库"]
        J -->|50-79| L["retry (≤2轮)"]
        J -->|<50| M["discarded"]
    end

    subgraph Storage["存储阶段"]
        K --> N["SQLite 入库\narticles + tags + cost_logs"]
        N --> O["Site Builder\n去抖构建"]
    end

    O --> P["静态站点上线"]

    subgraph Maintenance["数据源健康维护（每周）"]
        Q["每周一 09:00"] --> R["SourceHealthTracker\n检查并淘汰低质量源"]
        Q --> S["SourceDiscovery\nGitHub Topic 扩展"]
        Q --> T["SourceDiscovery\nRSS 友链扫描"]
        R --> U{"approved率<30%<br/>连续3次?"}
        U -->|是| V["SourceManager.remove\n自动删除数据源"]
        U -->|否| W["跳过"]
        S --> X["新 topic → 添加 github 源"]
        T --> Y["新 RSS → 添加 rss 源"]
    end
```

### 数据源健康管理系统

```mermaid
flowchart LR
    subgraph HealthLog["健康记录"]
        H1["每次采集完成\nrecord health"] --> H2["source_health 表\n存储每日快照"]
    end

    subgraph WeeklyJob["周维护 Job"]
        J1["淘汰检查"] --> J2{"连续3次\napproved率<30%?"}
        J2 -->|是| J3["自动删除源"]
        J2 -->|否| J4["保留"]
        J5["GitHub Topic 发现"] --> J6["新 topic → 添加源"]
        J7["RSS 友链扫描"] --> J8["新 RSS → 添加源"]
    end

    subgraph Dashboard["仪表盘"]
        D1["/api/sources"] --> D2["数据源列表\n含健康分"]
        D2 --> D3["Approved 率趋势\n折线图"]
        D3 --> D4["贡献分布\n柱状图"]
    end

    H2 --> J1
    J3 --> D2
    J6 --> D2
    J8 --> D2
```

## 数据流程

```mermaid
flowchart TD
    subgraph Scheduler["定时调度"]
        A["APScheduler\ncron 触发"] --> B["skip_if_running\n防重叠"]
    end

    subgraph Collection["采集阶段"]
        B --> C["Collector\n按源并行采集"]
        C --> D["DB 批量查重\nWHERE url IN (...)"]
    end

    subgraph Analysis["分析阶段"]
        D --> E["Router\n100% 规则分流"]
        E --> F["Analyzer Fan-out\n4 并行"]
        F --> G["Aggregator\n汇总 + 校验"]
    end

    subgraph Review["审核阶段"]
        G --> H["Reviewer\n四维评分"]
        H --> I{"评分结果"}
        I -->|≥80| J["approved → 入库"]
        I -->|50-79| K["retry (≤2轮)"]
        I -->|<50| L["discarded"]
    end

    subgraph Storage["存储阶段"]
        J --> M["SQLite 入库\narticles + tags + cost_logs"]
        M --> N["Site Builder\n去抖构建"]
    end

    N --> O["静态站点上线"]
```

### LangGraph DAG 详细流程

```mermaid
flowchart LR
    subgraph Input["输入"]
        RSS[/"RSS Feed\nGitHub Trending\n飞书文档\narXiv"/]
    end

    subgraph Pipeline["LangGraph Pipeline"]
        direction TB
        A1["Collector\n并行采集 + DB查重"] --> A2["Router\n按source字段分流"]
        A2 --> A3["Analyzers\nGitHub/RSS/飞书/arXiv"]
        A3 --> A4["Aggregator\n汇总 + 成本统计"]
        A4 --> A5["Reviewer\n四维评分"]
        A5 --> A6["入库\narticles + tags"]
    end

    subgraph Output["输出"]
        A6 --> B1["Site Builder\n预渲染 + 原子切换"]
        B1 --> B2["静态站点\nindex.html + 详情页"]
    end

    Input --> Pipeline
    Pipeline --> Output
```

## 目录结构

```
ai-knowledge-base/
├── config/                     # 配置文件
│   ├── llm.yaml               #   LLM Provider 注册 (base_url, api_key, models, 价格)
│   ├── sources.yaml           #   数据源定义 (RSS/GitHub/飞书/arXiv)
│   └── agents.yaml            #   SubAgent 绑定 (primary/fallback model, params)
│
├── prompts/                    # Agent Prompt 模板
│   ├── github.md / rss.md / feishu.md / arxiv.md
│   └── reviewer.md            #   四维评分锚点 + retry 格式
│
├── src/
│   ├── main.py                # FastAPI 入口 + APScheduler
│   │
│   ├── core/                  # 基础设施
│   │   ├── config.py          #   YAML → Pydantic 配置
│   │   ├── llm_client.py     #   TrackedClient (记账 + 熔断 + fallback)
│   │   ├── budget.py          #   全局预算熔断
│   │   ├── health.py          #   Provider 健康检查
│   │   ├── source_health.py   #   数据源健康追踪 + 淘汰逻辑
│   │   ├── source_manager.py  #   sources.yaml 读写 + 增删操作
│   │   └── source_discovery.py #   发现策略 (GitHub Topic / RSS 友链)
│   │
│   ├── graph/                 # LangGraph 工作流
│   │   ├── pipeline.py        #   DAG 编排
│   │   ├── state.py           #   State + Pydantic 模型
│   │   ├── collector.py       #   采集 + 查重
│   │   ├── router.py          #   规则分流
│   │   ├── aggregator.py      #   汇总 + 校验
│   │   ├── reviewer.py        #   四维评分
│   │   └── analyzers/         #   4 个 Analyzer 节点
│   │
│   ├── db/                    # 数据访问层
│   │   ├── database.py        #   SQLite 连接 + migration
│   │   ├── articles.py        #   文章 CRUD + FTS5 搜索
│   │   ├── tags.py           #   标签 CRUD
│   │   ├── queries.py         #   仪表盘聚合
│   │   └── migrations/        #   版本化 SQL (001-004)
│   │
│   ├── api/                   # FastAPI 路由
│   │   ├── health.py          #   /api/health
│   │   ├── search.py          #   /api/search
│   │   ├── article.py         #   /api/articles/{id}
│   │   ├── cost.py           #   /api/cost
│   │   ├── pipeline.py        #   /api/pipeline
│   │   └── sources.py         #   /api/sources (数据源健康)
│   │
│   ├── scheduler/             # 定时任务
│   │   └── source_scheduler.py #   每周数据源健康维护 Job
│   │
│   └── site/                  # 静态站点生成
│       ├── builder.py         #   去抖构建 + 原子切换
│       └── templates/         #   Jinja2 模板
│
├── data/                       # SQLite 数据库 (volume mount)
├── output/                     # 静态站点产物 (volume mount)
├── tests/                      # pytest 分层测试
└── docs/                       # 设计文档
```

## 数据模型

### 数据库表

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `articles` | 文章主表 | title, url (UNIQUE), description, summary, source, relevance_score, status, collected_at |
| `tags` | 标签字典 | name (UNIQUE) |
| `article_tags` | 文章-标签关联 | article_id → articles.id, tag_id → tags.id |
| `pipeline_runs` | 流水线运行记录 | id, started_at, ended_at, status, trigger, summary (JSON) |
| `cost_logs` | LLM 调用花费 | run_id, agent, provider, model, tokens_in, tokens_out, cost, **ref_url** |
| `provider_health` | Provider 健康状态 | provider, status, latency_ms, circuit (closed/open/half_open) |
| `circuit_events` | 熔断事件记录 | provider, event, reason, created_at |
| `source_health` | 数据源健康快照 | source_id, date, total_collected, approved, rejected, avg_score |
| `discovered_sources` | 已发现待审核的数据源 | url, name, type, status (candidate/added/rejected) |

**FTS5 全文索引**：`articles_fts` over (title, summary, description)

### extra_data JSON 结构

`articles.extra_data` 存储 Reviewer 四维评分：

```json
{
  "dimensions": {
    "ai_relevance": {"score": 35, "reason": "..."},
    "内容深度": {"score": 25, "reason": "..."},
    "信息密度": {"score": 12, "reason": "..."},
    "时效性": {"score": 10, "reason": "..."}
  }
}
```

### Dashboard API 端点

| 端点 | 说明 | 返回字段 |
|------|------|----------|
| `GET /api/stats/quality-detail?period=week` | 数据质量详细统计 | content_quality, audit_efficiency, tag_coverage, dimensions, reason_keywords |
| `GET /api/stats/consumption-detail?period=month` | 资源消耗详细统计 | period_cost, daily_avg, cost_per_million_tokens, budget_progress, trend, source_trend, provider_trend |

### 采集流程产生的数据

```
每次采集产生一条 pipeline_runs 记录
    └── cost_logs: 每次 LLM 调用产生一条记录（记录 ref_url 用于追踪来源）
    └── articles: 入库时产生记录，status = approved/retry/discarded，extra_data 存储四维评分
    └── source_health: 每周一 09:00 汇总上周数据源表现
```

### sources.yaml 配置结构

```yaml
sources:
  - id: github_trending
    name: GitHub Trending
    type: github
    enabled: true
    priority: 1
    cron: "0 */6 * * *"
    max_items: 10
    config:
      languages: [python, typescript]
      topics: [ai, llm, agent]

  - id: github_ai_devtools
    name: GitHub AI 开发工具
    type: github
    enabled: true
    cron: "0 */6 * * *"
    max_items: 10
    config:
      topics: []
      keywords: ["interactive knowledge graph", "codebase knowledge graph", "code understanding", "codebase understanding", "repository analysis"]
      lookback_type: pushed
      lookback_days: 90
      min_stars: 100

  - id: rss_the_batch
    name: The Batch
    type: rss
    enabled: true
    cron: "0 9 * * 1"        # 周刊
    max_items: 5
    config:
      url: "https://www.deeplearning.ai/the-batch/feed/"
```

### agents.yaml 配置结构

```yaml
budget:
  monthly: 10.0          # 月预算 ($)
  soft_limit: 0.8        # 80% 触发软熔断

agents:
  github_analyzer:
    primary:
      provider: deepseek
      model: deepseek-chat
    fallback:
      - provider: minimax
        model: MiniMax-M3
    prompt: prompts/github.md
    budget_weight: 1.0
```

## 快速开始

### 本地开发

```bash
# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API 密钥

# 运行服务
uv run uvicorn src.main:app --reload

# 触发采集
curl -X POST http://localhost:8000/api/pipeline/run

# 强制构建站点
curl -X POST http://localhost:8000/api/pipeline/build
```

### 部署到 VPS

```bash
# 1. VPS 安装 Docker + Docker Compose

# 2. Clone 仓库
git clone https://github.com/kangapp/ai-knowledge-base.git
cd ai-knowledge-base

# 3. 创建 .env
cp .env.example .env
vim .env  # 填入密钥

# 4. 启动服务
docker compose up -d

# 5. 验证
curl http://localhost:8090/api/health
```

## 使用指南

### 手动触发采集

```bash
# 全量采集（所有已启用的数据源）
curl -X POST http://localhost:8000/api/pipeline/run

# 指定数据源采集（按 source id）
curl -X POST "http://localhost:8000/api/pipeline/run?source=github_trending"

# 指定多个源（多次调用）
curl -X POST "http://localhost:8000/api/pipeline/run?source=hn_ai"
```

**查看已配置的数据源 ID：**
```bash
curl http://localhost:8000/api/sources
```

### 查看状态和日志

```bash
# 查看 DAG 状态（当前运行阶段和日志）
curl http://localhost:8000/api/pipeline/dag

# 查看 pipeline 日志 (JSON 格式)
docker logs pipeline --since 24h | grep '"event"' | jq .

# 查看错误
docker logs pipeline --since 24h | grep '"error"'

# 查看指定 run_id 的日志
docker logs pipeline --since 24h | grep '"run_id": "20260523-0900"'
```

### 数据源管理

```bash
# 查看所有数据源（含健康状态）
curl http://localhost:8000/api/sources

# 查看数据源健康统计
curl http://localhost:8000/api/sources/stats

# 查看已发现待审核的数据源
curl http://localhost:8000/api/sources/discovered

# 启用/禁用数据源
curl -X POST "http://localhost:8000/api/sources/{source_id}/action?action=enable"
curl -X POST "http://localhost:8000/api/sources/{source_id}/action?action=disable"
```

### 查看统计数据

```bash
# 仪表盘 KPI（30天）
curl http://localhost:8000/api/stats

# 指定天数
curl http://localhost:8000/api/stats?days=7

# 花费统计
curl http://localhost:8000/api/cost/summary?days=30

# 搜索文章
curl "http://localhost:8000/api/search?q=LLM&limit=20"

# 文章列表（支持分页、来源筛选）
curl "http://localhost:8000/api/articles?page=1&page_size=20&source=github"

# 按来源筛选
curl "http://localhost:8000/api/articles?source=rss"
```

### 强制构建站点

```bash
# 强制重新构建静态站点（跳过去抖）
curl -X POST http://localhost:8000/api/pipeline/build
```

## 运维指南

### CI/CD 流程

```mermaid
flowchart TD
    A["push to master"] --> B["GitHub Actions"]
    B --> C["单元测试\npytest -m 'not integration and not e2e'"]
    C -->|通过| D["构建镜像\ndocker build + push to ghcr.io"]
    C -->|失败| E["终止"]
    D --> F["部署到 VPS\ndocker pull + docker compose up -d"]
```

### 数据库迁移

迁移文件位于 `src/db/migrations/`，格式为 `001_*.sql`, `002_*.sql`...

- 启动时 `Database._run_migrations()` 自动检测并执行未应用迁移
- `schema_version` 表记录当前版本
- 迁移后版本号自动更新

### 备份与恢复

```bash
# 备份 (自动每日备份)
docker logs pipeline | grep 'backup'  # 查看备份记录

# 恢复
docker compose stop pipeline
cp data/backup/knowledge-YYYYMMDD.db data/kb.db
docker compose start pipeline
```

### 密钥轮换

```bash
# 编辑 .env
vim /opt/ai-knowledge-base/.env

# 重启服务
docker compose restart pipeline
```

### 扩展数据源

数据源支持手动和自动两种扩展方式：

**手动添加**：编辑 `config/sources.yaml`

**自动发现（每周维护）**：
1. **GitHub Topic 扩展** — 扫描 Trending 仓库的新 topic，自动添加为 github 类型数据源
2. **RSS 友链扫描** — 解析已配置 RSS 源的 HTML 首页，发现新的 RSS 链接并自动添加

**自动淘汰**：
- 连续 3 次采集 approved 率 < 30% 的数据源会自动删除
- 新添加的数据源有保护期（前 3 次采集不计入淘汰计算）

## API 接口

| 接口 | 说明 |
|------|------|
| `GET /api/health` | 健康检查 |
| `GET /api/articles` | 文章列表 (分页) |
| `GET /api/articles/{id}` | 文章详情 |
| `GET /api/search?q=xxx` | 全文搜索 |
| `GET /api/stats` | 仪表盘统计 |
| `GET /api/cost/summary` | 花费统计 |
| `POST /api/pipeline/run` | 手动触发采集 |
| `POST /api/pipeline/build` | 强制构建站点 |
| `GET /api/sources` | 数据源列表（含健康状态） |
| `GET /api/sources/stats` | 数据源健康统计 |
| `GET /api/sources/discovered` | 已发现待审核的数据源 |
| `GET /api/stats/quality-detail?period=week` | 数据质量详细统计（四维评分、Reason关键词） |
| `GET /api/stats/consumption-detail?period=month` | 资源消耗详细统计（费用趋势、Provider分解） |
| `POST /api/sources/{id}/action` | 数据源操作（enable/disable/remove） |

响应格式：

```json
{
  "code": 0,
  "data": { ... },
  "message": "ok"
}
```

错误码：

| code | 含义 |
|------|------|
| 0 | 成功 |
| 40001 | 参数校验失败 |
| 40401 | 资源不存在 |
| 50001 | 服务内部错误 |
| 50002 | 数据库错误 |
| 50003 | 上游 API 超时 |
| 50004 | LLM Provider 不可用 |

## 评审算法

Reviewer 采用四维评分，总分 0-100：

| 维度 | 权重 | 评分标准 |
|------|------|---------|
| AI 相关度 | 0-40 | 35-40: 核心 AI/LLM/Agent；25-34: AI 基础设施；10-24: 泛技术提及 |
| 内容深度 | 0-30 | 25-30: 深度原创；15-24: 有具体细节；5-14: 简要介绍 |
| 信息密度 | 0-15 | 12-15: 新颖/独家；7-11: 有一定信息量；0-6: 重复/营销 |
| 时效性 | 0-15 | 12-15: 本周内；7-11: 本月；0-6: 较早 |

评审结果：
- **≥80 分**: approved → 入库
- **50-79 分**: retry (最多 2 轮，带修改建议)
- **<50 分**: discarded

## LLM 交互流程

### Prompt 模板内容

#### github_analyzer.md
```
分析以下 GitHub 仓库，输出 JSON（不要 markdown 包裹）。

仓库: {title}
描述: {description}
URL: {url}
元数据: {metadata}

输出 JSON (schema={schema})
标签从 AI/LLM/Agent/MCP/RAG/Open Source/Tool/Framework/Benchmark 中选择，也可建议新标签。
```

#### rss_analyzer.md
```
分析以下技术文章，输出 JSON（不要 markdown 包裹）。

文章: {title}
摘要: {description}
链接: {url}
来源: {metadata}

输出 JSON (schema={schema})
```

#### feishu_analyzer.md
```
分析以下飞书文档，输出 JSON（不要 markdown 包裹）。

飞书文档: {title}
内容: {description}
元数据: {metadata}

输出 JSON (schema={schema})
```

#### arxiv_analyzer.md
```
分析以下学术论文摘要，输出 JSON（不要 markdown 包裹）。

论文: {title}
摘要: {description}
URL: {url}
分类: {metadata}

输出 JSON (schema={schema})
```

#### reviewer.md
```
你是内容审核员。对文章按四维评分（0-100）:
- AI相关度(0-40): 核心AI/LLM/Agent/MCP/RAG=35-40, AI基础设施=25-34, 泛技术提及=10-24, 无关=0-9
- 内容深度(0-30): 深度原创=25-30, 有细节=15-24, 简要=5-14, 空内容=0-4
- 信息密度(0-15): 新颖独家=12-15, 有信息量=7-11, 重复营销=0-6
- 时效性(0-15): 本周内=12-15, 本月=7-11, 较早=0-6

输出 JSON:
{ "total_score": 85, "dimensions": { "ai_relevance": {"score": 35, "reason": "..."}, ... }, "verdict": "approved"|"retry"|"discarded", "retry_feedback": null|{"suggestions": ["..."]} }
```

### Agent 配置

| Agent | Prompt 文件 | Primary Model | Fallback | temperature | max_tokens |
|-------|------------|---------------|----------|-------------|------------|
| `github_analyzer` | `prompts/github_analyzer.md` | MiniMax-M3 | deepseek-chat | 0.3 | 2048 |
| `rss_analyzer` | `prompts/rss_analyzer.md` | MiniMax-M3 | — | 0.3 | 2048 |
| `feishu_analyzer` | `prompts/feishu_analyzer.md` | MiniMax-M3 | — | 0.3 | 2048 |
| `arxiv_analyzer` | `prompts/arxiv_analyzer.md` | MiniMax-M3 | deepseek-chat | 0.3 | 4096 |
| `reviewer` | `prompts/reviewer.md` | MiniMax-M3 | — | 0.0 | 1024 |

### 完整数据流

```
采集阶段（Collector）
    │
    ▼
路由阶段（Router）── 100% 规则分流
    │
    ├── github ──▶ github_analyzer ──prompts/github_analyzer.md──┐
    ├── rss    ──▶ rss_analyzer    ──prompts/rss_analyzer.md─────┤
    ├── feishu ──▶ feishu_analyzer ──prompts/feishu_analyzer.md─┤──▶ Aggregator（汇总）
    └── arxiv  ──▶ arxiv_analyzer  ──prompts/arxiv_analyzer.md─┘
                                                                  │
                                                                  ▼
                                                              Reviewer
                                                        ──prompts/reviewer.md──▶ 四维评分
                                                                  │
                                        ┌──────────────────┬─────┴─────┐
                                        ▼                  ▼            ▼
                                    ≥80: 入库      50-79: retry     <50: discarded
                                                     (最多 2 轮)
```

### Prompt 填充与调用

1. `load_prompt(agent_name, registry)` 从 `config/agents.yaml` 读取 `prompt` 路径，加载 `prompts/*.md` 文件
2. 用户消息用 Python `.format()` 填充占位符：`{title}` `{description}` `{url}` `{metadata}` `{schema}`
3. System prompt 默认：`"你是一个技术分析助手。只输出 JSON，格式：{schema}"`
4. 调用 `Chat Completions API`，`response_format={"type": "json_object"}`（仅对支持 json_mode 的 provider 传入）
5. 响应通过 `parse_and_validate()` 解析：剥离 markdown 包裹、思考标签，提取 JSON

### Analyzer 输出 Schema

```json
{
  "title": "string - 标题",
  "summary": "string - 100-200字中文摘要",
  "tags": ["标签1", "标签2"] - 最多3个，从 AI/LLM/Agent/MCP/RAG/Open Source/Tool/Framework/Benchmark 选择",
  "language": "zh|en - 文章语言"
}
```

> relevance_score 已移除 — Analyzer 不生成相关度分数，分数由 Reviewer 的四维评分决定

### Reviewer 输出 Schema

```json
{
  "total_score": 85,
  "dimensions": {
    "ai_relevance": {"score": 35, "reason": "..."},
    "depth": {"score": 25, "reason": "..."},
    "info_density": {"score": 15, "reason": "..."},
    "timeliness": {"score": 10, "reason": "..."}
  },
  "verdict": "approved|retry|discarded",
  "retry_feedback": null | {"suggestions": ["..."]}
}
```

### 错误处理与重试

| 场景 | 处理方式 |
|------|---------|
| Analyzer parse 失败 | 重试一次（最多 2 轮），仍失败则跳过该条，记录 warning |
| LLM Provider 熔断 | 自动切换 fallback provider，无 fallback 则跳过 |
| Reviewer verdict=retry | 返回修改建议，重新进入 analyzer 处理，最多 2 轮 |
| Reviewer verdict=discarded | 直接丢弃，不入库 |

### Prompt 扩展

新增 Analyzer 步骤：
1. 在 `prompts/` 添加 `xxx_analyzer.md`，使用 `{title}` `{description}` `{url}` `{metadata}` `{schema}` 占位符
2. 在 `config/agents.yaml` 注册 agent，指定 `prompt: prompts/xxx_analyzer.md`
3. 在 `src/graph/analyzers/` 添加 `xxx.py`，调用 `load_prompt("xxx_analyzer", registry)`
4. 在 `pipeline.py` 的 `continue_to_analyzers()` 中添加路由分支

## 扩展与优化方向

### 短期优化

- [ ] **数据源扩展**: 添加 Twitter/X、微博、知乎专栏等社交媒体源
- [ ] **评分维度优化**: 增加"原创性"、"可操作性"等评分维度
- [ ] **缓存优化**: 引入 Redis 缓存热门搜索结果
- [ ] **监控告警**: 对采集失败率、LLM 熔断次数等指标设置告警

### 中期优化

- [ ] **增量采集**: 支持增量更新，只采集新内容
- [ ] **分布式采集**: 多节点并行采集不同数据源
- [ ] **语义去重**: 跨源同一事件允许多视角，但添加关联标识
- [ ] **历史数据挖掘**: 分析文章传播链路、热点趋势

### 长期优化

- [ ] **多语言支持**: 自动翻译非中文内容
- [ ] **个性化推荐**: 基于用户阅读历史推荐相关文章
- [ ] **自动化报告**: 自动生成周报/月报
- [ ] **知识图谱**: 将文章内容结构化为知识图谱

## 故障排查

### 采集失败

```bash
# 查看采集日志
docker logs pipeline --since 24h | grep 'collector'

# 检查数据源配置
cat config/sources.yaml

# 测试数据源连通性
curl -I <数据源URL>
```

### LLM 调用失败

```bash
# 查看熔断日志
docker logs pipeline --since 24h | grep 'circuit'

# 检查 Provider 状态
curl http://localhost:8000/api/stats

# 检查预算
curl http://localhost:8000/api/cost/summary
```

### 站点构建失败

```bash
# 查看构建日志
docker logs pipeline --since 24h | grep 'build'

# 检查 output 目录权限
ls -la output/

# 手动触发构建
curl -X POST http://localhost:8000/api/pipeline/build
```

## 相关文档

- [架构设计](docs/architecture.md) — LangGraph DAG、数据流、LLM 管理
- [目录结构](docs/structure.md) — 代码组织规范、核心约定
- [运维手册](docs/operations.md) — 部署、备份、应急处理
- [数据模型](docs/data-model.md) — 数据库 Schema、配置文件
- [Bug 记录](docs/bug-progress.md) — 问题与解决方案
