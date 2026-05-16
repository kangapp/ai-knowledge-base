# AI 个人知识库 — 设计规格说明

**日期**：2026-05-16 | **状态**：已确认

## 1. 项目概述

构建个人 AI 知识库系统，定时从 GitHub Trending、RSS 源、飞书知识文档、arXiv 等来源采集 AI/LLM/Agent 相关资讯，通过 LangGraph 工作流进行自动分析、审核、入库，最终生成静态网站展示。

**目标用户**：纯个人使用

**部署方式**：云 VPS（1C2G），Docker Compose

## 2. 功能需求

### 2.1 数据采集
- 支持数据源：GitHub Trending、RSS、飞书知识文档、arXiv（配置驱动，可增删）
- 每种源独立配置：优先级、定时 cron、获取数量、过滤关键词
- GitHub API（带 Token 认证）、RSS/Atom 解析、飞书开放平台 API、arXiv API
- **飞书认证**：惰性刷新策略 — 内存缓存 `tenant_access_token` + 过期时间，采集时自动检查有效性（有效期不足 3 分钟则提前刷新）。token 请求频率由有效期（2h）决定而非采集频率，不会触发飞书限频（100 次/小时）。`FEISHU_APP_ID` / `FEISHU_APP_SECRET` 存放于 `.env`

### 2.2 工作流（LangGraph）
- **Collector**：按源并行采集原始数据；单源失败不影响其余源（try/except 隔离，失败返回空列表 + 记 error_log）；空数据源的 Analyzer 直接跳过不调 LLM；仅所有源全挂时 pipeline 才标记 failed
- **Router**：按 source 字段纯规则匹配分流（100% 规则，无需 LLM）
- **Fan-out Analyzers**：4 个 SubAgent 并行分析（github/rss/feishu/arxiv），各自使用专属 Prompt 和模型；分析时自动建议 1-3 个标签（新标签自动收录到 tags 表，管理员可后续维护）
- **Aggregator**：汇总并行结果，附加成本统计
- **Reviewer**：结构化四维评分（AI相关度0-40 + 内容深度0-30 + 信息密度0-15 + 时效性0-15=100），temperature=0 保证一致性；≥80 入库，50-79 带具体改进反馈打回重分析（限 2 轮，同维度连续低分不再重试），<50 丢弃
- **Cost Monitor**：LLM 客户端层的 TrackedClient wrapper（非 LangGraph 节点），每次 `chat.completions.create()` 调用自动记录 token/花费 + 检查熔断，调用方无感。两种熔断独立运作：Provider 熔断（per-provider 连续 3 次失败 → circuit open，指数退避 60/120/240/480/600s 试探恢复 → 自动 fallback 到 agent 配置的备选模型）；预算熔断（全局 80% 软熔断切便宜模型 / 100% 硬熔断停服）

### 2.3 前端展示（静态网站）
- **首页**：日期范围过滤（快捷按钮 + 自定义）+ 搜索 + 来源/标签筛选 + 文章列表（分页 + 评分标签）
- **文章详情页**：AI 摘要、原始链接、标签、元数据（来源/评分/token 花费）
- **仪表盘**：KPI 卡片、来源分布图、每日花费趋势（日期范围联动）
- 纯静态 HTML + 少量 Vanilla JS（客户端过滤全量 data.json，日均 50 条，1 年约 9MB）；首屏预渲染近 30 天；3 年后 data.json 超 25MB 时可切换按月分片加载；FastAPI /api/articles 作为兜底服务端查询
- 站点构建：去抖合并（5min 计时器）+ 双目录原子 rename 切换，防止高频渲染和半写文件

### 2.4 LLM 多模型管理
- 所有 Provider 统一走 OpenAI 兼容协议（base_url + api_key）
- 三层配置解耦：llm.yaml（Provider 注册）→ agents.yaml（SubAgent 绑定 + fallback + 参数）→ .env（密钥）
- 健康检查：被动探测（调用记录失败）+ 主动探测（定时最小请求）+ 余额检查
- Provider 熔断：per-provider 独立计数，连续失败 3 次 → circuit open → 指数退避冷却（60s/120s/240s/480s cap 600s）→ half_open 试探；LLMRegistry.get_client() 遍历 primary → fallback[] 自动切换

### 2.5 CI/CD
- GitHub Actions：push main → pytest → docker build → SSH deploy to VPS
- VPS 初始化：5 步完成（装 Docker、clone、配 .env、docker compose up、验证）

## 3. 技术架构

### 3.1 技术栈

| 层 | 组件 | 说明 |
|----|------|------|
| 语言 | Python 3.12+ | |
| 依赖管理 | uv | uv.lock 锁版本 |
| 工作流 | langgraph | DAG 编排，短 pipeline 无需 checkpoint |
| LLM SDK | openai (AsyncOpenAI) | 统一 OpenAI 兼容协议调用 |
| 数据校验 | pydantic v2 | State + 配置 + API |
| HTTP | httpx | 异步采集 + API 调用 |
| RSS | feedparser | |
| 数据库 | SQLite (aiosqlite) | FTS5 全文索引 |
| Web 框架 | FastAPI | API 端点 + 定时调度 |
| 模板引擎 | Jinja2 | 静态站点生成 |
| 调度 | APScheduler | cron 表达式 |
| Web 服务 | Caddy | 静态文件 + 自动 HTTPS + 反向代理 |
| 部署 | Docker Compose | 2 容器 (pipeline + web) |
| CI/CD | GitHub Actions | test → build → deploy |
| 可观测性 | langfuse | LLM 追踪（Cloud 免费层） |

### 3.2 部署架构

```
VPS (1C2G)
└── Docker Compose
    ├── pipeline (Python)      ← 采集/分析/API/静态生成
    │   ├── FastAPI (:8000)
    │   ├── APScheduler
    │   ├── LangGraph Pipeline
    │   └── Jinja2 Site Builder → /output
    ├── web (Caddy)            ← 静态文件 serve + HTTPS + 反向代理
    │   ├── / → /srv (静态站)
    │   └── /api/* → pipeline:8000
    ├── volumes:
    │   ├── ./data → SQLite + 备份
    │   ├── ./output → 静态站点
    │   └── ./config → 配置文件
```

### 3.3 项目结构

```
ai-knowledge-base/
├── pyproject.toml / uv.lock
├── Dockerfile / docker-compose.yml / .env.example / Caddyfile
├── .github/workflows/deploy.yml
├── config/
│   ├── llm.yaml              # Provider 注册
│   ├── sources.yaml          # 数据源定义
│   └── agents.yaml           # SubAgent + LLM 绑定 + 预算
├── prompts/                  # 各 Agent 的 Prompt 模板
├── src/
│   ├── main.py
│   ├── core/                 # config / llm_client / budget / health
│   ├── graph/                # LangGraph 工作流
│   │   ├── pipeline.py / state.py
│   │   ├── collector.py / router.py / aggregator.py / reviewer.py
│   │   └── analyzers/        # github / rss / feishu / arxiv
│   ├── db/                   # database / articles / queries
│   ├── api/                  # health / cost / pipeline 路由
│   └── site/                 # builder + templates
├── data/                     # SQLite (volume mount)
├── output/                   # 静态站点 (volume mount)
└── tests/
```

## 4. 数据模型

### 4.1 SQLite Schema

**articles** — 文章主表（id, title, url, description, summary, source, source_detail, relevance_score, status, retry_count, collected_at, published_at, raw_metadata, analysis_cost, analysis_tokens, created_at, updated_at）；FTS5 全文索引 over (title, summary, description)；url UNIQUE 约束防同源重复采集；不做跨源去重（不同源的视角和 Prompt 不同，产出有差异，重叠率低）

**tags** — 标签字典（id, name, color）

**article_tags** — 文章-标签关联（article_id, tag_id）

**pipeline_runs** — 流水线运行记录（id, started_at, ended_at, status, trigger, summary）

**cost_logs** — LLM 调用花费（id, run_id, agent, provider, model, tokens_in, tokens_out, cost）

**provider_health** — Provider 健康状态（provider, status, latency_ms, error_count, last_error, last_check, circuit）

**circuit_events** — 熔断事件记录（id, provider, event, reason, created_at）

### 4.2 配置文件

**config/llm.yaml**：providers 注册（base_url, api_key, models 清单及价格）

**config/sources.yaml**：数据源定义（enabled, priority, schedule, max_items, 源特定配置）

**config/agents.yaml**：SubAgent 定义（primary/fallback model, params, prompt 路径）+ 全局预算配置

## 5. 数据流

1. APScheduler cron 触发 → Collector 按源并行采集 → raw_items[]
2. Router 规则分类 → 4 组数据分流
3. LangGraph Send fan-out → 4 个 SubAgent 并行分析 → analyzed_items[]
4. Aggregator 汇总 → 附加成本统计
5. Reviewer 结构四维评分（含逐维度 reason + retry_feedback） → pass/retry(限2轮)/discard
6. 入库 SQLite → articles + tags + cost_logs + pipeline_runs
7. Site Builder 去抖触发（5min 计时器合并多轮采集）→ 渲染到临时目录 → 原子 rename 切换 → 静态站上线
8. 横切：Cost Monitor（LLM 客户端 wrapper）每次 LLM 调用自动记账 + 熔断检查；Provider 熔断（per-provider 健康检查）和预算熔断（全局花费控制）独立运作

## 6. Reviewer 评分细则

### 四维评分锚点

| 维度 | 权重 | 评分标准 |
|------|------|---------|
| AI 相关度 | 0-40 | 35-40: 核心 AI/LLM/Agent/MCP/RAG；25-34: AI 基础设施；10-24: 泛技术提及 AI；0-9: 无关 |
| 内容深度 | 0-30 | 25-30: 深度内容有原创贡献；15-24: 有具体细节；5-14: 简要介绍；0-4: 空内容 |
| 信息密度 | 0-15 | 12-15: 新颖/独家信息；7-11: 有一定信息量；0-6: 重复/营销 |
| 时效性 | 0-15 | 12-15: 本周内；7-11: 本月；0-6: 较早 |

### 输出格式

Reviewer LLM 输出严格 JSON，每维包含 `score` + `reason`。verdict 为 retry 时附带 `retry_feedback.suggestions`，指出具体改进方向。temperature=0 保证一致性。同一维度连续两次低分且 reason 一致 → 不再 retry，标记 exhausted 入库。

## 7. LLM 配置推荐

| SubAgent | 推荐 Provider | 模型 | 理由 |
|----------|--------------|------|------|
| github_analyzer | deepseek | deepseek-chat | 代码/技术内容，性价比极高 |
| rss_analyzer | deepseek | deepseek-chat | 通用文本分析 |
| feishu_analyzer | minimax | abab6.5s-chat | 中文内容优化 |
| arxiv_analyzer | deepseek | deepseek-chat | 论文摘要分析 |
| reviewer | deepseek | deepseek-chat | 评分判断，低温度 |

## 8. 成本估算

| 项目 | 月费用 | 备注 |
|------|--------|------|
| VPS（1C2G） | ¥50-70 | 腾讯云/阿里云轻量 |
| 域名 | ¥3-5 | .top/.xyz 年费折月 |
| LLM 调用 | $3-8 | DeepSeek 为主，日均 50 条 |
| Langfuse | $0 | Cloud 免费层 |
| GitHub Actions | $0 | 公开仓库免费 |
| **合计** | **¥85-125/月** | 约 $12-17 |

## 9. 风险与约束

- 静态站日均 50 条，data.json 全量约 9MB/年，客户端过滤性能足够；3 年后超 25MB 可切换按月分片加载
- 放弃 Anthropic 原生协议（prompt caching 等），需时再加适配器即可
- 系统依赖 3 个外部服务（GitHub API、飞书 API、LLM Provider），任一出问题影响当天采集
- 全自动短 pipeline（< 5min），幂等设计保证重跑安全，无需 checkpoint
- SQLite 单文件，年数据量约 20MB，无需分库分表
