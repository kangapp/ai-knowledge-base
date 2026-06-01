# 代码组织规范

## 目录结构

```
ai-knowledge-base/
├── pyproject.toml          # 项目元数据 + 依赖
├── uv.lock                 # 锁版本
├── Dockerfile
├── docker-compose.yml
├── .env.example            # 密钥清单模板（入 Git），VPS 据此手动维护 .env
├── Caddyfile
├── .github/workflows/deploy.yml
│
├── config/                 # 配置文件（YAML）
│   ├── llm.yaml            #   Provider 注册 (base_url, api_key, models, 价格)
│   ├── sources.yaml        #   数据源定义（RSS 按订阅源独立条目，各自 cron）
│   └── agents.yaml         #   SubAgent 绑定 (primary/fallback model, params, prompt 路径) + 全局预算
│
├── prompts/                # 各 Agent 的 Prompt 模板（Git 版本管理）
│   ├── github.md           #   共用 AnalyzedItem schema 模板变量注入
│   ├── rss.md
│   ├── feishu.md
│   ├── arxiv.md
│   └── reviewer.md         #   四维评分锚点 + retry_feedback 格式
│
├── src/
│   ├── main.py             # FastAPI 入口 + APScheduler (skip_if_running)
│   │
│   ├── core/               # 基础设施
│   │   ├── config.py       #   配置加载 (llm/sources/agents YAML → Pydantic)
│   │   ├── llm_client.py   #   TrackedClient wrapper → 统一记账 + 熔断检查 + fallback 遍历
│   │   ├── budget.py       #   全局预算控制 (80% 软熔断 / 100% 硬熔断)
│   │   └── health.py       #   Provider 健康检查 (被动探测 + 主动探测 + 余额检查)
│   │
│   ├── graph/              # LangGraph 工作流
│   │   ├── pipeline.py     #   DAG 编排入口
│   │   ├── state.py        #   State + AnalyzedItem/ReviewedItem Pydantic 模型定义
│   │   ├── collector.py    #   按源并行采集；GitHub topic/keyword 查询；DB 批量查重
│   │   ├── router.py       #   100% 规则匹配（按 RawItem.source 字段分流）
│   │   ├── aggregator.py   #   汇总并行结果 + Pydantic 校验 + 成本统计
│   │   ├── reviewer.py     #   四维评分 (AI相关度0-40/内容深度0-30/信息密度0-15/时效性0-15)
│   │   └── analyzers/      #   4 个独立 LangGraph 节点（薄层文件 ~8 行）
│   │       ├── base.py     #     通用 analyze_items() 实现
│   │       ├── github.py
│   │       ├── rss.py
│   │       ├── feishu.py
│   │       └── arxiv.py
│   │
│   ├── db/                 # 数据访问层
│   │   ├── operations.py   #   文章/标签/成本/pipeline/统计 SQL 操作
│   │   └── migrations/     #   版本化 SQL 文件（001_init.sql, 002_xxx.sql, ...）
│   │
│   ├── api/                # FastAPI 路由
│   │   ├── responses.py    #   统一响应信封 + 错误码映射 + exception handlers
│   │   ├── routes.py       #   /api/articles /api/search /api/stats /api/cost /api/pipeline /api/health
│   │   ├── stats.py        #   /api/stats/* 仪表盘统计接口
│   │   ├── dashboard.py    #   /api/dashboard/summary 首屏 KPI 聚合
│   │   ├── sources.py      #   /api/sources/* 数据源管理与健康统计
│   │   └── config.py       #   /api/config/{llm|sources|agents}
│   │
│   ├── services/           # API-facing 服务层
│   │   └── dashboard_stats.py # 仪表盘 summary/enhanced 统计口径
│   │
│   └── site/               # 静态站点生成
│       ├── builder.py      #   去抖合并（5min 计时器）+ output.tmp 原子 rename
│       └── templates/      #   Jinja2 模板
│           ├── index.html  #     预渲染 30 天首屏 + <script>window.__INIT__</script>
│           ├── article.html#     JS 读 URL param + fetch /api/articles/{id}
│           └── dashboard.html # 内联 window.__STATS__ + Chart.js
│
├── data/                   # SQLite + backup/ (volume mount)
├── output/                 # 静态站点产物 (volume mount, Caddy serve)
├── docs/task.md            # 当前任务拆解、优先级和状态
├── docs/codemap.md         # 模块职责和常见改动入口
└── tests/                  # pytest 分层
    ├── unit/               #   CI 跑，LLM mock + HTTP fixture，<30s
    ├── integration/        #   手动跑（真实 API + 真实 LLM，少量数据）
    ├── e2e/                #   部署前本地跑（全 mock 完整流程）
    └── fixtures/           #   种子数据 + mock response
```

## 核心约定

- **配置三层解耦**：llm.yaml（Provider）→ agents.yaml（SubAgent 绑定）→ .env（密钥），绝不硬编码密钥
- **所有 LLM 调用统一走 `core.llm_client.TrackedClient`**，wrapper 自动记账 + 熔断检查 + fallback 遍历，调用方无感
- **每个 Analyzer 是独立 LangGraph 节点**（薄层 ~8 行），共享 `base.analyze_items()` 通用实现，差异仅 Prompt + model
- **LLM 输出三层校验**：`response_format={"type": "json_object"}` → json.loads + markdown 容错 → Pydantic `model_validate()`，两次重试
- **数据校验在边界**：collector API 返回 → Pydantic 校验；analyzer 输出 → Pydantic 校验；入库前 → Pydantic 校验
- **Prompt 变更需回归测试**：改 prompt 后跑 `test_prompt_regression.py` 验证输出结构合法
- **错误隔离**：单源采集失败不影响其余源（try/except 隔离），空数据跳过 analyzer 不调 LLM；仅所有源全挂才标记 pipeline failed
- **GitHub 采集**：`topics` 生成 `topic:` qualifier，`keywords` 作为补充搜索词，`exclude_terms` 用于排除明显非技术噪音；`trend_mode` 仅过滤对应配置源自己的采集结果
- **RSS 采集**：先用 `httpx.AsyncClient(timeout=30)` 获取 feed 文本，再由 `feedparser` 解析；英文关键词按词边界匹配；综合媒体源用 `filter_scope: title` 只匹配标题，减少长正文偶然提及 AI 带来的误采集
- **Reviewer 审核**：模型只输出四维分，代码负责维度 key 规范化、总分重算和最终 verdict 裁决
- **API 响应统一入口**：除 `/api/health` 外，成功响应走 `api.responses.envelope()`；`HTTPException`、参数校验错误、未捕获异常统一由 `src/main.py` 注册 handler。
- **仪表盘统计口径集中化**：首屏 KPI 和 `/api/stats/enhanced` 的 summary 口径在 `src/services/dashboard_stats.py` 维护，避免前端重构时出现多个互相打架的统计来源。
- **文章 API 契约**：`/api/articles` 的 `total` 是真实匹配总数；列表和详情都返回 `tags` 数组。
