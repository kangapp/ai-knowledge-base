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
│   │   ├── collector.py    #   按源并行采集 + DB 批量查重 (WHERE url IN (...))
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
│   │   ├── database.py     #   SQLite 连接 + 启动时自动 migration
│   │   ├── articles.py     #   文章 CRUD + FTS5 全文搜索
│   │   ├── tags.py         #   标签 CRUD（新标签自动收录）
│   │   ├── queries.py      #   仪表盘聚合统计
│   │   └── migrations/     #   版本化 SQL 文件（001_init.sql, 002_xxx.sql, ...）
│   │
│   ├── api/                # FastAPI 路由
│   │   ├── health.py       #   /api/health
│   │   ├── search.py       #   /api/search?q=xxx (FTS5 全文检索)
│   │   ├── article.py      #   /api/articles/{id} (详情页按需加载)
│   │   ├── cost.py         #   /api/cost
│   │   └── pipeline.py     #   /api/pipeline (手动触发、状态查询)
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
