# AI 个人知识库 实现计划 v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建个人 AI 知识库系统，定时采集 → LangGraph 分析 → 静态站点展示，Docker Compose 部署

**Architecture:** Python 全栈单进程应用，FastAPI 承载 API + 调度 + 静态渲染，LangGraph 编排采集分析流水线（无 checkpoint），SQLite 存储 + 版本化迁移，Caddy 前置 serve 静态文件 + HTTPS。LLM 调用通过 TrackedClient wrapper 自动记账 + 熔断，Cost Monitor 在客户端层而非 LangGraph 节点。

**Tech Stack:** Python 3.12+ / uv / LangGraph (无 checkpoint-sqlite) / openai SDK / FastAPI + Jinja2 / SQLite (aiosqlite) + FTS5 / httpx + feedparser / APScheduler / Chart.js / Docker Compose + Caddy

**Spec:** docs/superpowers/specs/2026-05-16-ai-knowledge-base-design.md

---

## 关键设计决策（25 项 review 结论）

| # | 主题 | 决策 |
|---|------|------|
| 1 | Router | 100% 规则匹配，按 source 字段分流 |
| 2 | Reviewer | 四维评分（AI相关度0-40+内容深度0-30+信息密度0-15+时效性0-15=100），temperature=0，retry_feedback，限2轮 |
| 3 | 熔断 | per-provider 独立计数 + 指数退避 60/120/240/480/600s + fallback 链自动切换 |
| 4 | 站点构建 | 去抖合并（5min）+ 双目录原子 rename |
| 5 | Checkpoint | 移除 langgraph-checkpoint-sqlite，幂等重跑 |
| 6 | 飞书认证 | FeishuAuth 惰性刷新，内存缓存 + 过期前 3min 提前刷新 |
| 7 | 错误处理 | 单源 try/except 隔离，部分成功继续，仅全挂才 failed |
| 8 | 去重 | url UNIQUE 防同源重复，不做跨源去重；采集后 DB 批量查重跳过 LLM |
| 9 | Cost Monitor | LLM 客户端 TrackedClient wrapper，非 LangGraph 节点 |
| 10 | 标签 | Analyzer LLM 自动建议 1-3 个，新标签自动收录 tags 表 |
| 11 | 调度 | AsyncIOScheduler + skip_if_running，async 全链路不阻塞 |
| 12 | .env 管理 | 手动维护 VPS，.env.example 模板驱动 |
| 13 | 备份 | sqlite3 .backup 在线热备份，pipeline 完成后触发，本地 7 天滚动 |
| 14 | 迁移 | 版本化 SQL 文件 (001_init.sql, 002_xxx.sql)，启动时自动按序执行 |
| 15 | 可观测性 | 结构化日志 stdout JSON lines + pipeline_runs 表 + docker logs 排查 |
| 16 | Prompt 管理 | response_format json_object + markdown 容错 + Pydantic 校验 + 两次重试；种子数据回归测试 |
| 17 | RSS 配置 | 按订阅源拆分为独立条目，各自 cron + enabled |
| 18 | GitHub 采集 | /search/repositories (created:>7d + sort=stars) 近似 trending |
| 19 | 测试分层 | CI 只跑单元测试 (LLM mock + API fixture)；手动跑集成测试；本地跑 E2E |
| 20 | 前端渲染 | Jinja2 预渲染近 30 天首屏 + JS 接管全量过滤 + Chart.js 图表 |
| 21 | 搜索 | 首页过滤走客户端 data.json，搜索框走 /api/search FTS5 |
| 22 | Analyzer 架构 | base.analyze_items() 通用实现 + 4 个薄层文件（~8 行） |
| 23 | 字段流 | RawItem → AnalyzedItem → ReviewedItem，ref_url 关联，最终合并入 articles |
| 24 | 数据拆分 | data.json（列表字段无 summary）+ stats.json（仪表盘）；详情 /api/articles/{id} |
| 25 | 备份 | 同 #13 |

---

## 文件结构

```
ai-knowledge-base/
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── docker-compose.yml
├── Caddyfile
├── .env.example
├── .gitignore
├── .github/workflows/deploy.yml
├── config/
│   ├── llm.yaml
│   ├── sources.yaml
│   └── agents.yaml
├── prompts/
│   ├── github_analyzer.md
│   ├── rss_analyzer.md
│   ├── feishu_analyzer.md
│   ├── arxiv_analyzer.md
│   └── reviewer.md
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── llm_client.py
│   │   ├── budget.py
│   │   └── health.py
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── pipeline.py
│   │   ├── collector.py
│   │   ├── router.py
│   │   ├── aggregator.py
│   │   ├── reviewer.py
│   │   └── analyzers/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── github.py
│   │       ├── rss.py
│   │       ├── feishu.py
│   │       └── arxiv.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── migrations/
│   │   │   └── 001_init.sql
│   │   └── operations.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   └── site/
│       ├── __init__.py
│       ├── builder.py
│       └── templates/
│           ├── base.html
│           ├── index.html
│           ├── article.html
│           └── dashboard.html
├── data/                   # SQLite (volume mount)
├── output/                 # 静态站点 (volume mount)
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    │   └── llm_responses.py
    ├── test_config.py
    ├── test_database.py
    ├── test_llm_client.py
    ├── test_budget.py
    ├── test_health.py
    ├── test_collector.py
    ├── test_router.py
    ├── test_analyzer.py
    ├── test_reviewer.py
    ├── test_pipeline.py
    └── test_prompt_regression.py
```

---

### Phase 1: 基础设施铺设

**验收标准**：`uv sync` 成功，配置可加载并通过 Pydantic 校验，DB 启动时自动迁移至最新版本

---

### Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`, `.env.example`, `.gitignore`
- Create: `config/llm.yaml`, `config/sources.yaml`, `config/agents.yaml`
- Create: `prompts/github_analyzer.md`, `prompts/rss_analyzer.md`, `prompts/feishu_analyzer.md`, `prompts/arxiv_analyzer.md`, `prompts/reviewer.md`
- Create: `src/`, `tests/` 目录结构

- [ ] **Step 1: 创建 pyproject.toml（不含 langgraph-checkpoint-sqlite）**

```toml
[project]
name = "ai-knowledge-base"
version = "0.1.0"
description = "个人 AI 知识库 — 自动化采集、分析、展示"
requires-python = ">=3.12"
dependencies = [
    "openai>=1.0",
    "langgraph>=0.2",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "jinja2>=3.1",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "httpx>=0.27",
    "feedparser>=6.0",
    "apscheduler>=3.10",
    "aiosqlite>=0.20",
    "pyyaml>=6.0",
    "langfuse>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-httpx>=0.30",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: 安装依赖**

```bash
cd /Users/liufukang/Workplace/ai-knowledge-base
uv sync
```

- [ ] **Step 3: 创建 .env.example 和 .gitignore**

`.env.example`:
```bash
# LLM Provider API Keys
DEEPSEEK_API_KEY=sk-xxx
MINIMAX_API_KEY=xxx
OPENAI_API_KEY=sk-xxx

# GitHub API
GITHUB_TOKEN=ghp_xxx

# 飞书开放平台
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# 域名（Caddy 自动 HTTPS，替换为真实域名）
KB_DOMAIN=kb.your-domain.com

# Langfuse (可选)
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

`.gitignore`:
```
# 密钥
.env

# 运行时数据
data/
output/

# Python
__pycache__/
*.pyc
*.egg-info/
dist/
.venv/

# 测试
.pytest_cache/
.coverage

# IDE
.vscode/
.idea/
```

- [ ] **Step 4: 创建 config/llm.yaml（Provider 注册）**

```yaml
providers:
  deepseek:
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_API_KEY}
    supports_json_mode: true
    models:
      - id: deepseek-chat
        price_per_1k_in: 0.000014
        price_per_1k_out: 0.000028
        max_tokens: 8192

  openai:
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
    supports_json_mode: true
    models:
      - id: gpt-4o-mini
        price_per_1k_in: 0.00015
        price_per_1k_out: 0.0006
        max_tokens: 16384
      - id: gpt-4o
        price_per_1k_in: 0.0025
        price_per_1k_out: 0.01
        max_tokens: 4096

  minimax:
    base_url: https://api.minimax.chat/v1
    api_key: ${MINIMAX_API_KEY}
    supports_json_mode: false
    models:
      - id: abab6.5s-chat
        price_per_1k_in: 0.001
        price_per_1k_out: 0.001
        max_tokens: 8192
```

- [ ] **Step 5: 创建 config/sources.yaml（RSS 按订阅源拆分）**

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
      topics: [ai, llm, agent, machine-learning, rag, mcp]
      min_stars: 50
      lookback_days: 7

  - id: rss_anthropic
    name: Anthropic Blog
    type: rss
    enabled: true
    priority: 2
    cron: "0 9 * * *"
    max_items: 5
    config:
      url: "https://www.anthropic.com/blog/feed.xml"
      filter_keywords: []

  - id: rss_openai
    name: OpenAI Blog
    type: rss
    enabled: true
    priority: 2
    cron: "0 9 * * *"
    max_items: 5
    config:
      url: "https://openai.com/blog/rss.xml"
      filter_keywords: []

  - id: rss_langchain
    name: LangChain Blog
    type: rss
    enabled: true
    priority: 2
    cron: "0 10 * * *"
    max_items: 5
    config:
      url: "https://blog.langchain.dev/feed"
      filter_keywords: [AI, LLM, Agent, RAG]

  - id: feishu
    name: 飞书知识文档
    type: feishu
    enabled: false
    priority: 3
    cron: "0 10 * * *"
    max_items: 10
    config:
      space_ids: []

  - id: arxiv
    name: arXiv
    type: arxiv
    enabled: false
    priority: 3
    cron: "0 11 * * 1"
    max_items: 10
    config:
      categories: [cs.AI, cs.CL, cs.LG]
      keywords: [LLM, agent, RAG, transformer]
      lookback_days: 7
```

- [ ] **Step 6: 创建 config/agents.yaml（含 fallback 链）**

```yaml
agents:
  github_analyzer:
    model:
      primary: { provider: deepseek, model: deepseek-chat }
      fallback: [{ provider: openai, model: gpt-4o-mini }]
    params: { temperature: 0.3, max_tokens: 2048 }
    prompt: prompts/github_analyzer.md
    budget_weight: 1.0

  rss_analyzer:
    model:
      primary: { provider: deepseek, model: deepseek-chat }
      fallback: []
    params: { temperature: 0.3, max_tokens: 2048 }
    prompt: prompts/rss_analyzer.md
    budget_weight: 1.0

  feishu_analyzer:
    model:
      primary: { provider: minimax, model: abab6.5s-chat }
      fallback: [{ provider: deepseek, model: deepseek-chat }]
    params: { temperature: 0.3, max_tokens: 2048 }
    prompt: prompts/feishu_analyzer.md
    budget_weight: 1.0

  arxiv_analyzer:
    model:
      primary: { provider: deepseek, model: deepseek-chat }
      fallback: [{ provider: openai, model: gpt-4o-mini }]
    params: { temperature: 0.3, max_tokens: 4096 }
    prompt: prompts/arxiv_analyzer.md
    budget_weight: 1.0

  reviewer:
    model:
      primary: { provider: deepseek, model: deepseek-chat }
      fallback: []
    params: { temperature: 0.0, max_tokens: 1024 }
    prompt: prompts/reviewer.md
    budget_weight: 0.5

budget:
  monthly: 10.0
  soft_limit: 0.8
  hard_limit: 1.0
```

- [ ] **Step 7: 创建 prompts/*.md 占位文件**

每个 Analyzer prompt 包含 schema 输出要求 + 标签建议指令：

`prompts/github_analyzer.md`:
```
分析以下 GitHub 仓库，输出 JSON（不要 markdown 包裹）。

仓库: {title}
描述: {description}
URL: {url}
元数据: {metadata}

输出 JSON (schema={schema})
标签从 AI/LLM/Agent/MCP/RAG/Open Source/Tool/Framework/Benchmark 中选择，也可建议新标签。relevance_score 评估文章与 AI 领域的相关度和质量（0-100）。
注意：schema 中的 relevance_score 是你评估的相关度分数（0-100），不是 schema 的示例值。
```

`prompts/rss_analyzer.md`:
```
分析以下技术文章，输出 JSON（不要 markdown 包裹）。

文章: {title}
摘要: {description}
链接: {url}
来源: {metadata}

输出 JSON (schema={schema})
注意：schema 中的 relevance_score 是你评估的相关度分数（0-100），不是 schema 的示例值。
```

`prompts/feishu_analyzer.md`:
```
分析以下飞书文档，输出 JSON（不要 markdown 包裹）。

飞书文档: {title}
内容: {description}
元数据: {metadata}

输出 JSON (schema={schema})
注意：schema 中的 relevance_score 是你评估的相关度分数（0-100），不是 schema 的示例值。
```

`prompts/arxiv_analyzer.md`:
```
分析以下学术论文摘要，输出 JSON（不要 markdown 包裹）。

论文: {title}
摘要: {description}
URL: {url}
分类: {metadata}

输出 JSON (schema={schema})
注意：schema 中的 relevance_score 是你评估的相关度分数（0-100），不是 schema 的示例值。
```

`prompts/reviewer.md`:
```
你是内容审核员。对文章按四维评分（0-100）:
- AI相关度(0-40): 核心AI/LLM/Agent/MCP/RAG=35-40, AI基础设施=25-34, 泛技术提及=10-24, 无关=0-9
- 内容深度(0-30): 深度原创=25-30, 有细节=15-24, 简要=5-14, 空内容=0-4
- 信息密度(0-15): 新颖独家=12-15, 有信息量=7-11, 重复营销=0-6
- 时效性(0-15): 本周内=12-15, 本月=7-11, 较早=0-6

输出 JSON:
{ "total_score": 85, "dimensions": { "ai_relevance": {"score": 35, "reason": "..."}, ... }, "verdict": "approved"|"retry"|"discarded", "retry_feedback": null|{"suggestions": ["..."]} }
```

- [ ] **Step 8: 创建目录结构**

```bash
mkdir -p src/core src/graph/analyzers src/db/migrations src/api src/site/templates tests/fixtures config prompts
touch src/__init__.py src/core/__init__.py src/graph/__init__.py src/graph/analyzers/__init__.py src/db/__init__.py src/api/__init__.py src/site/__init__.py tests/__init__.py
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock .env.example config/ prompts/ src/ tests/ .gitignore
git commit -m "feat: 初始化项目脚手架 v2 — 无 checkpoint，RSS 拆分，四维评分 prompt"
```

---

### Task 2: 配置加载模块

**Files:**
- Create: `src/core/config.py`
- Create: `tests/conftest.py`, `tests/test_config.py`

- [ ] **Step 1: 编写测试**

```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def config_dir(tmp_path):
    d = tmp_path / "config"
    d.mkdir()
    return d

@pytest.fixture
def sample_llm_yaml(config_dir):
    p = config_dir / "llm.yaml"
    p.write_text("""
providers:
  deepseek:
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_API_KEY}
    supports_json_mode: true
    models:
      - id: deepseek-chat
        price_per_1k_in: 0.000014
        price_per_1k_out: 0.000028
        max_tokens: 8192
""")
    return p

@pytest.fixture
def sample_sources_yaml(config_dir):
    p = config_dir / "sources.yaml"
    p.write_text("""
sources:
  - id: rss_anthropic
    name: Anthropic Blog
    type: rss
    enabled: true
    priority: 2
    cron: "0 9 * * *"
    max_items: 5
    config:
      url: "https://www.anthropic.com/blog/feed.xml"
""")
    return p

@pytest.fixture
def sample_agents_yaml(config_dir):
    p = config_dir / "agents.yaml"
    p.write_text("""
agents:
  github_analyzer:
    model:
      primary: {provider: deepseek, model: deepseek-chat}
      fallback: [{provider: openai, model: gpt-4o-mini}]
    params: {temperature: 0.3, max_tokens: 2048}
    prompt: prompts/github_analyzer.md
    budget_weight: 1.0
budget:
  monthly: 10.0
  soft_limit: 0.8
  hard_limit: 1.0
""")
    return p
```

```python
# tests/test_config.py
import os
from src.core.config import load_llm_config, load_sources_config, load_agents_config

def test_load_llm_config(sample_llm_yaml):
    cfg = load_llm_config(sample_llm_yaml)
    assert "deepseek" in cfg.providers
    assert cfg.providers["deepseek"].base_url == "https://api.deepseek.com/v1"
    assert cfg.providers["deepseek"].supports_json_mode is True

def test_load_sources_config(sample_sources_yaml):
    cfg = load_sources_config(sample_sources_yaml)
    assert len(cfg.sources) == 1
    assert cfg.sources[0].type == "rss"
    assert cfg.sources[0].config["url"] == "https://www.anthropic.com/blog/feed.xml"

def test_load_agents_config(sample_agents_yaml):
    cfg = load_agents_config(sample_agents_yaml)
    assert "github_analyzer" in cfg.agents
    assert cfg.agents["github_analyzer"].model.primary.provider == "deepseek"
    assert len(cfg.agents["github_analyzer"].model.fallback) == 1
    assert cfg.budget.monthly == 10.0

def test_env_interpolation(sample_llm_yaml, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-123")
    cfg = load_llm_config(sample_llm_yaml)
    assert cfg.providers["deepseek"].api_key == "sk-test-123"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_config.py -v
# 预期: ModuleNotFoundError
```

- [ ] **Step 3: 实现配置加载**

```python
# src/core/config.py
import os
import re
from pathlib import Path
import yaml
from pydantic import BaseModel

# ===== LLM Config =====

class ModelInfo(BaseModel):
    id: str
    price_per_1k_in: float
    price_per_1k_out: float
    max_tokens: int

class ProviderConfig(BaseModel):
    base_url: str
    api_key: str
    supports_json_mode: bool = False
    models: list[ModelInfo]

class LLMConfig(BaseModel):
    providers: dict[str, ProviderConfig]

# ===== Sources Config =====

class SourceConfig(BaseModel):
    id: str
    name: str
    type: str  # github / rss / feishu / arxiv
    enabled: bool
    priority: int
    cron: str
    max_items: int
    config: dict = {}

class SourcesConfig(BaseModel):
    sources: list[SourceConfig]

# ===== Agents Config =====

class ModelRef(BaseModel):
    provider: str
    model: str

class ModelBinding(BaseModel):
    primary: ModelRef
    fallback: list[ModelRef] = []

class AgentConfig(BaseModel):
    model: ModelBinding
    params: dict = {}
    prompt: str = ""
    budget_weight: float = 1.0

class BudgetConfig(BaseModel):
    monthly: float
    soft_limit: float = 0.8
    hard_limit: float = 1.0

class AgentsConfig(BaseModel):
    agents: dict[str, AgentConfig]
    budget: BudgetConfig


def _interpolate_env(value: str) -> str:
    def replacer(match):
        return os.environ.get(match.group(1), "")
    return re.sub(r'\$\{(\w+)\}', replacer, value)

def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        raw = f.read()
    raw = _interpolate_env(raw)
    return yaml.safe_load(raw)

def load_llm_config(path: Path) -> LLMConfig:
    return LLMConfig(**_load_yaml(path))

def load_sources_config(path: Path) -> SourcesConfig:
    return SourcesConfig(**_load_yaml(path))

def load_agents_config(path: Path) -> AgentsConfig:
    return AgentsConfig(**_load_yaml(path))
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_config.py -v
# 预期: 4 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/core/config.py tests/conftest.py tests/test_config.py
git commit -m "feat: 配置加载模块 — yaml + pydantic + 环境变量插值"
```

---

### Task 3: 数据库初始化 + 版本化迁移

**Files:**
- Create: `src/core/database.py`
- Create: `src/db/migrations/001_init.sql`
- Create: `tests/test_database.py`

- [ ] **Step 1: 创建初始迁移 SQL**

```sql
-- src/db/migrations/001_init.sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
INSERT OR IGNORE INTO schema_version (version) VALUES (0);

CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    url             TEXT NOT NULL UNIQUE,
    description     TEXT,
    summary         TEXT,
    source          TEXT NOT NULL,
    source_detail   TEXT,
    relevance_score INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',
    retry_count     INTEGER DEFAULT 0,
    collected_at    TEXT NOT NULL,
    published_at    TEXT,
    extra_data      TEXT,
    analysis_cost   REAL DEFAULT 0.0,
    analysis_tokens INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_collected ON articles(collected_at);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, summary, description, content='articles'
);

-- FTS5 同步触发器（外部内容表需手动维护）
CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, summary, description) VALUES (new.id, new.title, new.summary, new.description);
END;

CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary, description) VALUES ('delete', old.id, old.title, old.summary, old.description);
END;

CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary, description) VALUES ('delete', old.id, old.title, old.summary, old.description);
    INSERT INTO articles_fts(rowid, title, summary, description) VALUES (new.id, new.title, new.summary, new.description);
END;

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    color TEXT
);

CREATE TABLE IF NOT EXISTS article_tags (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id         TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    status     TEXT DEFAULT 'running',
    trigger    TEXT,
    summary    TEXT
);

CREATE TABLE IF NOT EXISTS cost_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     TEXT REFERENCES pipeline_runs(id),
    agent      TEXT NOT NULL,
    provider   TEXT NOT NULL,
    model      TEXT NOT NULL,
    tokens_in  INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    cost       REAL NOT NULL DEFAULT 0.0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS provider_health (
    provider    TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'healthy',
    latency_ms  INTEGER,
    error_count INTEGER DEFAULT 0,
    last_error  TEXT,
    last_check  TEXT,
    circuit     TEXT NOT NULL DEFAULT 'closed',
    cooldown_level INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS circuit_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    provider   TEXT NOT NULL,
    event      TEXT NOT NULL,
    reason     TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 更新 schema_version
UPDATE schema_version SET version = 1;
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_database.py
import pytest
from src.core.database import Database

@pytest.mark.asyncio
async def test_initialize_and_migrate(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path, migrations_dir=tmp_path.parent.parent / "src" / "db" / "migrations")
    await db.initialize()

    tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    names = {t["name"] for t in tables}
    assert "articles" in names
    assert "tags" in names
    assert "pipeline_runs" in names
    assert "cost_logs" in names
    assert "provider_health" in names
    assert "circuit_events" in names
    assert "schema_version" in names

    # 验证迁移版本
    v = await db.fetch_one("SELECT version FROM schema_version")
    assert v["version"] == 1

@pytest.mark.asyncio
async def test_url_unique_constraint(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.initialize()

    await db.execute(
        "INSERT INTO articles (title, url, source, collected_at) VALUES (?, ?, ?, ?)",
        ("Test", "https://example.com/1", "github", "2026-05-16T10:00:00Z")
    )
    with pytest.raises(Exception):
        await db.execute(
            "INSERT INTO articles (title, url, source, collected_at) VALUES (?, ?, ?, ?)",
            ("Test2", "https://example.com/1", "rss", "2026-05-16T11:00:00Z")
        )

@pytest.mark.asyncio
async def test_fts5_sync(tmp_path):
    """验证 FTS5 外部内容表与 articles 表自动同步"""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.initialize()

    # INSERT → FTS5 自动索引
    await db.execute(
        "INSERT INTO articles (title, url, source, summary, description, collected_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("LLM 框架", "https://example.com/2", "github", "高性能 LLM 推理", "描述文本", "2026-05-16T10:00:00Z")
    )
    await db.commit()

    rows = await db.fetch_all("SELECT * FROM articles_fts WHERE articles_fts MATCH ?", ("LLM",))
    assert len(rows) == 1

    # UPDATE → FTS5 同步更新
    row = await db.fetch_one("SELECT id FROM articles WHERE url = ?", ("https://example.com/2",))
    await db.execute(
        "UPDATE articles SET title = ?, summary = ? WHERE id = ?",
        ("Agent 框架", "Agent 相关推理", row["id"])
    )
    await db.commit()

    # 旧内容搜不到
    rows = await db.fetch_all("SELECT * FROM articles_fts WHERE articles_fts MATCH ?", ("LLM",))
    assert len(rows) == 0
    # 新内容可搜
    rows = await db.fetch_all("SELECT * FROM articles_fts WHERE articles_fts MATCH ?", ("Agent",))
    assert len(rows) == 1

    # DELETE → FTS5 同步删除
    await db.execute("DELETE FROM articles WHERE id = ?", (row["id"],))
    await db.commit()
    rows = await db.fetch_all("SELECT * FROM articles_fts WHERE articles_fts MATCH ?", ("Agent",))
    assert len(rows) == 0
```

- [ ] **Step 3: 运行测试确认失败**

```bash
uv run pytest tests/test_database.py -v
# 预期: ImportError
```

- [ ] **Step 4: 实现数据库模块（含自动迁移）**

```python
# src/core/database.py
import os
from pathlib import Path
import aiosqlite

class Database:
    def __init__(self, db_path: Path | str, migrations_dir: Path | str | None = None):
        self.db_path = str(db_path)
        if migrations_dir:
            self.migrations_dir = str(migrations_dir)
        else:
            self.migrations_dir = None
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._run_migrations()

    async def _run_migrations(self):
        # 确保 schema_version 表存在（最简 bootstrap）
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        row = await self._conn.execute("SELECT version FROM schema_version")
        result = await row.fetchone()
        current = result["version"] if result else 0

        if not self.migrations_dir:
            return

        mig_dir = Path(self.migrations_dir)
        if not mig_dir.exists():
            return

        migrations = sorted(
            [f for f in os.listdir(str(mig_dir)) if f.endswith(".sql")],
            key=lambda f: int(f.split("_")[0])
        )

        for filename in migrations:
            num = int(filename.split("_")[0])
            if num > current:
                sql = (mig_dir / filename).read_text()
                await self._conn.executescript(sql)
                await self._conn.commit()

    async def fetch_one(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchone()

    async def fetch_all(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchall()

    async def execute(self, sql: str, params: tuple = ()):
        return await self._conn.execute(sql, params)

    async def execute_many(self, sql: str, params_list: list[tuple]):
        return await self._conn.executemany(sql, params_list)

    async def commit(self):
        await self._conn.commit()

    async def backup(self, target_path: str):
        """在线热备份到 target_path（使用 aiosqlite 自带 API，不依赖 sqlite3 CLI）"""
        target = await aiosqlite.connect(target_path)
        await self._conn.backup(target)
        await target.close()

    async def close(self):
        if self._conn:
            await self._conn.close()
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/test_database.py -v
# 预期: 3 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/core/database.py src/db/migrations/001_init.sql tests/test_database.py
git commit -m "feat: 数据库初始化 + 版本化迁移 — schema_version 自动升级"
```

---

### Phase 2: LLM 基础设施

**验收标准**：LLMRegistry 可正常获取 client，TrackedClient 自动记账，BudgetTracker 软硬熔断生效，HealthTracker 指数退避状态机正确

---

### Task 4: 预算追踪器

**Files:**
- Create: `src/core/budget.py`
- Create: `tests/test_budget.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_budget.py
import pytest
from src.core.config import BudgetConfig
from src.core.budget import BudgetTracker

@pytest.fixture
def tracker():
    return BudgetTracker(BudgetConfig(monthly=10.0, soft_limit=0.8, hard_limit=1.0))

def test_initial_state(tracker):
    assert tracker.current_daily() == 0.0
    assert not tracker.is_soft_exceeded()

def test_add_cost(tracker):
    tracker.add_cost("deepseek", 0.5)
    assert tracker.current_daily() == 0.5

def test_soft_exceeded(tracker):
    tracker._daily_spend["__global__"] = tracker.daily_limit * 0.85
    assert tracker.is_soft_exceeded()
    assert not tracker.is_hard_exceeded()

def test_hard_exceeded(tracker):
    tracker._daily_spend["__global__"] = tracker.daily_limit
    assert tracker.is_hard_exceeded()

def test_per_provider_tracking(tracker):
    tracker.add_cost("deepseek", 1.0)
    tracker.add_cost("openai", 0.5)
    assert tracker.current_daily() == 1.5

def test_reset_daily(tracker):
    tracker.add_cost("deepseek", 5.0)
    tracker.reset_daily()
    assert tracker.current_daily() == 0.0
```

- [ ] **Step 2: 实现 BudgetTracker**

```python
# src/core/budget.py
from .config import BudgetConfig

class BudgetTracker:
    def __init__(self, budget_cfg: BudgetConfig):
        self.monthly_limit = budget_cfg.monthly
        self.soft_limit = budget_cfg.soft_limit
        self.hard_limit = budget_cfg.hard_limit
        self.daily_limit = budget_cfg.monthly / 30
        self._daily_spend: dict[str, float] = {}
        self._monthly_spend: dict[str, float] = {}

    def add_cost(self, provider: str, cost: float):
        self._daily_spend["__global__"] = self._daily_spend.get("__global__", 0) + cost
        self._daily_spend[provider] = self._daily_spend.get(provider, 0) + cost

    def current_daily(self) -> float:
        return self._daily_spend.get("__global__", 0.0)

    def is_soft_exceeded(self) -> bool:
        return self.current_daily() >= self.daily_limit * self.soft_limit

    def is_hard_exceeded(self) -> bool:
        return self.current_daily() >= self.daily_limit * self.hard_limit

    def reset_daily(self):
        self._daily_spend.clear()
```

- [ ] **Step 3: 运行测试确认通过**

```bash
uv run pytest tests/test_budget.py -v
# 预期: 5 passed
```

- [ ] **Step 4: Commit**

```bash
git add src/core/budget.py tests/test_budget.py
git commit -m "feat: 预算追踪器 — 软硬熔断 + per-provider 独立限额"
```

---

### Task 5: Provider 健康追踪（指数退避）

**Files:**
- Create: `src/core/health.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_health.py
import time
from src.core.health import HealthTracker

def test_initial_healthy():
    ht = HealthTracker()
    assert ht.is_healthy("deepseek")

def test_consecutive_failures_open_circuit():
    ht = HealthTracker()
    ht.record_failure("deepseek", "500")
    ht.record_failure("deepseek", "500")
    ht.record_failure("deepseek", "timeout")  # 3rd → open
    assert ht._state["deepseek"]["circuit"] == "open"
    assert not ht.is_healthy("deepseek")

def test_half_open_trial_success():
    ht = HealthTracker()
    ht._state["deepseek"] = {"circuit": "open", "error_count": 3, "cooldown_level": 1, "opened_at": time.time() - 999, "status": "unhealthy", "last_error": "timeout"}
    # 冷却时间过 → half_open
    assert ht.is_healthy("deepseek")  # half_open allows
    ht.record_success("deepseek", 100)
    assert ht._state["deepseek"]["circuit"] == "closed"

def test_exponential_backoff():
    ht = HealthTracker()
    assert ht._cooldown_seconds("deepseek") == 60   # level 1 (default)
    ht._state["deepseek"]["cooldown_level"] = 2
    assert ht._cooldown_seconds("deepseek") == 120
    ht._state["deepseek"]["cooldown_level"] = 3
    assert ht._cooldown_seconds("deepseek") == 240
    ht._state["deepseek"]["cooldown_level"] = 5
    assert ht._cooldown_seconds("deepseek") == 600  # capped

def test_record_success_resets():
    ht = HealthTracker()
    ht._state["deepseek"]["error_count"] = 2
    ht.record_success("deepseek", 150)
    assert ht._state["deepseek"]["error_count"] == 0
    assert ht._state["deepseek"]["cooldown_level"] == 1

def test_half_open_failure_back_to_open():
    ht = HealthTracker()
    ht._state["deepseek"] = {"circuit": "half_open", "error_count": 0, "cooldown_level": 1, "opened_at": time.time(), "status": "healthy", "last_error": None}
    ht.record_failure("deepseek", "still failing")
    assert ht._state["deepseek"]["circuit"] == "open"
    assert ht._state["deepseek"]["cooldown_level"] == 2
```

- [ ] **Step 2: 实现 HealthTracker（含指数退避）**

```python
# src/core/health.py
import time

class HealthTracker:
    BASE_COOLDOWN = 60
    MAX_COOLDOWN = 600
    FAILURE_THRESHOLD = 3

    def __init__(self):
        self._state: dict[str, dict] = {}

    def _ensure(self, provider: str):
        if provider not in self._state:
            self._state[provider] = {
                "status": "healthy",
                "error_count": 0,
                "last_error": None,
                "latency_ms": None,
                "circuit": "closed",
                "cooldown_level": 1,
                "opened_at": 0.0,
                "last_check": None,
            }

    def _cooldown_seconds(self, provider: str) -> int:
        level = self._state[provider].get("cooldown_level", 1)
        return min(self.BASE_COOLDOWN * (2 ** (level - 1)), self.MAX_COOLDOWN)

    def is_healthy(self, provider: str) -> bool:
        self._ensure(provider)
        s = self._state[provider]
        if s["circuit"] == "closed":
            return True
        if s["circuit"] == "open":
            elapsed = time.time() - s["opened_at"]
            if elapsed >= self._cooldown_seconds(provider):
                s["circuit"] = "half_open"
                return True
            return False
        # half_open
        return True

    def circuit_is_open(self, provider: str) -> bool:
        return not self.is_healthy(provider)

    def record_success(self, provider: str, latency_ms: int):
        self._ensure(provider)
        s = self._state[provider]
        s["error_count"] = 0
        s["cooldown_level"] = 1
        s["latency_ms"] = latency_ms
        s["status"] = "healthy"
        s["last_check"] = time.time()
        if s["circuit"] == "half_open":
            s["circuit"] = "closed"

    def record_failure(self, provider: str, error: str):
        self._ensure(provider)
        s = self._state[provider]
        s["error_count"] += 1
        s["last_error"] = error
        s["last_check"] = time.time()

        if s["circuit"] == "half_open":
            s["circuit"] = "open"
            s["cooldown_level"] += 1
            s["opened_at"] = time.time()
            s["status"] = "unhealthy"
        elif s["error_count"] >= self.FAILURE_THRESHOLD and s["circuit"] == "closed":
            s["circuit"] = "open"
            s["opened_at"] = time.time()
            s["status"] = "unhealthy"
```

- [ ] **Step 3: 运行测试确认通过**

```bash
uv run pytest tests/test_health.py -v
# 预期: 6 passed
```

- [ ] **Step 4: Commit**

```bash
git add src/core/health.py tests/test_health.py
git commit -m "feat: Provider 健康追踪 — 指数退避 + half_open 试探"
```

---

### Task 6: LLM 客户端注册表 + TrackedClient

**Files:**
- Create: `src/core/llm_client.py`
- Create: `tests/test_llm_client.py`, `tests/fixtures/llm_responses.py`

- [ ] **Step 1: 创建 LLM 响应 fixture**

```python
# tests/fixtures/llm_responses.py
import json

GITHUB_ANALYZE_RESPONSE = {
    "choices": [{"message": {"content": json.dumps({
        "title": "llama.cpp",
        "summary": "高性能 LLM 推理框架",
        "tags": ["LLM", "Open Source"],
        "language": "en",
        "relevance_score": 85
    })}}],
    "usage": {"prompt_tokens": 420, "completion_tokens": 88}
}

REVIEWER_RESPONSE = {
    "choices": [{"message": {"content": json.dumps({
        "total_score": 85,
        "dimensions": {
            "ai_relevance": {"score": 35, "reason": "核心 LLM 推理"},
            "content_depth": {"score": 25, "reason": "有技术细节"},
            "info_density": {"score": 12, "reason": "有新信息"},
            "timeliness": {"score": 13, "reason": "本周发布"}
        },
        "verdict": "approved",
        "retry_feedback": None
    })}}],
    "usage": {"prompt_tokens": 300, "completion_tokens": 120}
}
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_llm_client.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.core.llm_client import LLMRegistry, AllProvidersUnavailable
from src.core.config import (
    LLMConfig, AgentsConfig, ProviderConfig, ModelInfo,
    AgentConfig, ModelBinding, ModelRef, BudgetConfig
)

@pytest.fixture
def llm_cfg():
    return LLMConfig(providers={
        "deepseek": ProviderConfig(
            base_url="https://api.deepseek.com/v1", api_key="sk-test",
            models=[ModelInfo(id="deepseek-chat", price_per_1k_in=0.000014, price_per_1k_out=0.000028, max_tokens=8192)]
        ),
        "openai": ProviderConfig(
            base_url="https://api.openai.com/v1", api_key="sk-test",
            models=[ModelInfo(id="gpt-4o-mini", price_per_1k_in=0.000015, price_per_1k_out=0.00006, max_tokens=4096)]
        )
    })

@pytest.fixture
def agents_cfg():
    return AgentsConfig(
        agents={
            "github_analyzer": AgentConfig(
                model=ModelBinding(
                    primary=ModelRef(provider="deepseek", model="deepseek-chat"),
                    fallback=[ModelRef(provider="openai", model="gpt-4o-mini")]
                ),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
        },
        budget=BudgetConfig(monthly=10.0, soft_limit=0.8, hard_limit=1.0)
    )

def test_get_client_primary(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    client, provider, model_id, params = registry.get_client("github_analyzer")
    assert provider == "deepseek"
    assert model_id == "deepseek-chat"
    assert params["temperature"] == 0.3

def test_fallback_on_unhealthy(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    registry.health.record_failure("deepseek", "500")
    registry.health.record_failure("deepseek", "500")
    registry.health.record_failure("deepseek", "500")  # open
    client, provider, model_id, _ = registry.get_client("github_analyzer")
    assert provider == "openai"  # fallback provider
    assert model_id == "gpt-4o-mini"  # fallback model

def test_soft_limit_skips_primary(llm_cfg, agents_cfg):
    """软熔断 (80%) → 跳过 primary，只用 fallback"""
    registry = LLMRegistry(llm_cfg, agents_cfg)
    # 设置花费超过软熔断阈值
    registry.budget._daily_spend["__global__"] = registry.budget.daily_limit * 0.85
    client, provider, model_id, _ = registry.get_client("github_analyzer")
    assert provider == "openai"  # fallback
    assert model_id == "gpt-4o-mini"

def test_hard_limit_raises(llm_cfg, agents_cfg):
    """硬熔断 (100%) → 全部不可用"""
    registry = LLMRegistry(llm_cfg, agents_cfg)
    registry.budget._daily_spend["__global__"] = registry.budget.daily_limit
    with pytest.raises(AllProvidersUnavailable):
        registry.get_client("github_analyzer")

def test_all_unavailable_raises(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    for _ in range(3):
        registry.health.record_failure("deepseek", "500")
        registry.health.record_failure("openai", "500")
    with pytest.raises(AllProvidersUnavailable):
        registry.get_client("github_analyzer")

def test_calc_cost(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    cost = registry.calc_cost("deepseek", "deepseek-chat", 1000, 500)
    # 1000/1000 * 0.000014 + 500/1000 * 0.000028 = 0.000014 + 0.000014 = 0.000028
    assert cost == pytest.approx(0.000028, rel=1e-6)
```

- [ ] **Step 3: 实现 LLMRegistry + TrackedClient**

```python
# src/core/llm_client.py
from openai import AsyncOpenAI
from .config import LLMConfig, AgentsConfig, ModelRef
from .budget import BudgetTracker
from .health import HealthTracker

class AllProvidersUnavailable(Exception):
    pass

class LLMRegistry:
    def __init__(self, llm_cfg: LLMConfig, agents_cfg: AgentsConfig):
        self._clients: dict[str, AsyncOpenAI] = {}
        self._models: dict[str, list] = {}

        for name, p in llm_cfg.providers.items():
            self._clients[name] = AsyncOpenAI(base_url=p.base_url, api_key=p.api_key)
            self._models[name] = p.models

        self._llm_cfg = llm_cfg
        self._agents = agents_cfg.agents
        self.budget = BudgetTracker(agents_cfg.budget)
        self.health = HealthTracker()

    def get_client(self, agent_name: str) -> tuple[AsyncOpenAI, str, str, dict]:
        """返回 (client, provider_name, model_id, params)。

        预算控制：
        - 硬熔断 (100%): 全部不可用 → AllProvidersUnavailable
        - 软熔断 (80%):  跳过 primary，只用 fallback[]（切便宜模型）
        """
        agent = self._agents[agent_name]

        if self.budget.is_hard_exceeded():
            raise AllProvidersUnavailable(f"Budget hard limit reached")

        chain = [agent.model.primary] + agent.model.fallback

        if self.budget.is_soft_exceeded():
            chain = agent.model.fallback  # 软熔断：只用 fallback

        if not chain:
            raise AllProvidersUnavailable(f"No available provider for '{agent_name}' (soft limit, no fallback)")

        for ref in chain:
            if self.health.circuit_is_open(ref.provider):
                continue
            return (
                self._clients[ref.provider],
                ref.provider,
                ref.model,
                agent.params,
            )

        raise AllProvidersUnavailable(f"No available provider for '{agent_name}'")

    def supports_json_mode(self, provider_name: str) -> bool:
        cfg = self._llm_cfg.providers.get(provider_name)
        return cfg.supports_json_mode if cfg else False

    def get_prompt_path(self, agent_name: str) -> str:
        """返回 agent 配置的 prompt 文件路径"""
        return self._agents[agent_name].prompt

    def calc_cost(self, provider: str, model_id: str, tokens_in: int, tokens_out: int) -> float:
        models = self._models.get(provider, [])
        for m in models:
            if m.id == model_id:
                return (tokens_in * m.price_per_1k_in + tokens_out * m.price_per_1k_out) / 1000
        return 0.0
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_llm_client.py -v
# 预期: 6 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/core/llm_client.py tests/test_llm_client.py tests/fixtures/
git commit -m "feat: LLMRegistry + 自动 fallback + 软硬分级熔断 — per-provider 熔断 + 预算控制"
```

---

### Phase 3: LangGraph 工作流

**验收标准**：Pipeline DAG 结构正确，Collector 支持 4 源 + 错误隔离 + DB 查重，Router 100% 规则分流，Analyzer 输出通过 schema 校验，Reviewer 四维评分正确分类

---

### Task 7: Pipeline State 定义

**Files:**
- Create: `src/graph/state.py`

- [ ] **Step 1: 实现三阶段数据模型**

```python
# src/graph/state.py
from pydantic import BaseModel, Field
import operator
from typing import Literal, Optional, Annotated

class RawItem(BaseModel):
    """Collector 产出 — 原始采集数据"""
    url: str
    title: str
    description: str = ""
    source: Literal["github", "rss", "feishu", "arxiv"]
    source_detail: str = ""
    published_at: str = ""
    raw_metadata: dict = {}
    collected_at: str = ""

class AnalyzedItem(BaseModel):
    """Analyzer 产出 — LLM 分析后的结构化结果"""
    ref_url: str  # 关联 RawItem.url
    title: str
    summary: str
    tags: list[str] = Field(default_factory=list, max_length=3)
    language: Literal["zh", "en"] = "zh"
    relevance_score: int = Field(default=0, ge=0, le=100)
    retry_count: int = Field(default=0, ge=0)

class ReviewedItem(BaseModel):
    """Reviewer 产出 — 四维评分 + 判决"""
    ref_url: str
    total_score: int = Field(ge=0, le=100)
    dimensions: dict = {}  # {ai_relevance: {score, reason}, ...}
    verdict: Literal["approved", "retry", "discarded"]
    retry_feedback: Optional[dict] = None

class CostRecord(BaseModel):
    """单次 LLM 调用花费"""
    agent: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost: float

class PipelineState(BaseModel):
    """LangGraph 工作流全局状态"""
    raw_items: list[RawItem] = []
    routed_github: list[RawItem] = []
    routed_rss: list[RawItem] = []
    routed_feishu: list[RawItem] = []
    routed_arxiv: list[RawItem] = []
    analyzed_items: Annotated[list[AnalyzedItem], operator.add] = []
    reviewed_items: list[ReviewedItem] = []
    cost_records: Annotated[list[CostRecord], operator.add] = []
    error_log: list[dict] = []
    run_id: str = ""
    trigger: str = "cron"
```

- [ ] **Step 2: Commit**

```bash
git add src/graph/state.py
git commit -m "feat: Pipeline State — RawItem → AnalyzedItem → ReviewedItem 字段流 + operator.add reducer 支持 fan-out 合并"
```

---

### Task 8: Collector 采集节点（含错误隔离 + 飞书认证 + DB 查重）

**Files:**
- Create: `src/graph/collector.py`
- Create: `tests/test_collector.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_collector.py
import pytest
from unittest.mock import AsyncMock, patch
from src.graph.collector import collect_github, collect_rss, collect_all
from src.graph.state import RawItem
from src.core.config import SourceConfig

def make_source(**kw):
    defaults = {"id": "test", "name": "Test", "type": "github", "enabled": True, "priority": 1, "cron": "0 9 * * *", "max_items": 10, "config": {}}
    defaults.update(kw)
    return SourceConfig(**defaults)

@pytest.mark.asyncio
async def test_collect_github_mock():
    source = make_source(type="github", config={"topics": ["ai"], "min_stars": 1, "lookback_days": 7})
    mock_resp = AsyncMock(status_code=200, json=lambda: {"items": [{"full_name": "test/x", "name": "x", "html_url": "https://github.com/test/x", "description": "desc", "stargazers_count": 100, "language": "Python", "topics": ["ai"], "pushed_at": "2026-05-15T10:00:00Z"}]})
    mock_resp.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        items = await collect_github(source)

    assert len(items) == 1
    assert items[0].source == "github"
    assert items[0].url == "https://github.com/test/x"

@pytest.mark.asyncio
async def test_collector_single_source_failure_isolated():
    """一个源挂了，其余正常返回"""
    async def fail():
        raise Exception("API down")
    async def ok():
        return [RawItem(url="x", title="x", source="rss", collected_at="")]
    async def ok_empty():
        return []

    results, errors = await collect_all(
        [mock_source("rss"), mock_source("feishu")],
        collectors={"rss": ok, "feishu": fail}
    )
    assert len(results) == 1
    assert len(errors) == 1
    assert errors[0]["source"] == "feishu"

def mock_source(t):
    return make_source(type=t)
```

- [ ] **Step 2: 实现 Collector**

```python
# src/graph/collector.py
import asyncio
import logging
from datetime import datetime, timedelta, timezone
import httpx
import feedparser
from .state import RawItem
from ..core.config import SourceConfig, SourcesConfig

logger = logging.getLogger("pipeline")

async def collect_github(source: SourceConfig) -> list[RawItem]:
    cfg = source.config
    topics = " OR ".join(cfg.get("topics", ["ai"]))
    since = (datetime.now(timezone.utc) - timedelta(days=cfg.get("lookback_days", 7))).strftime("%Y-%m-%d")
    url = "https://api.github.com/search/repositories"
    params = {"q": f"{topics} created:>{since}", "sort": "stars", "order": "desc", "per_page": source.max_items}
    headers = {"Accept": "application/vnd.github.v3+json"}
    import os
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    items = []
    now = datetime.now(timezone.utc).isoformat()
    min_stars = cfg.get("min_stars", 0)
    for repo in data.get("items", []):
        if repo.get("stargazers_count", 0) < min_stars:
            continue
        items.append(RawItem(
            url=repo["html_url"],
            title=repo["name"],
            description=repo.get("description") or "",
            source="github",
            source_detail=repo["full_name"],
            published_at=repo.get("pushed_at", ""),
            raw_metadata={"stars": repo.get("stargazers_count", 0), "language": repo.get("language", ""), "topics": repo.get("topics", [])},
            collected_at=now,
        ))
    return items


async def collect_rss(source: SourceConfig) -> list[RawItem]:
    cfg = source.config
    items = []
    now = datetime.now(timezone.utc).isoformat()
    keywords = cfg.get("filter_keywords", [])

    feed = feedparser.parse(cfg["url"])
    for entry in feed.entries[:source.max_items]:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        if keywords and not any(kw.lower() in f"{title} {summary}".lower() for kw in keywords):
            continue
        items.append(RawItem(
            url=entry.get("link", ""),
            title=title,
            description=(summary or "")[:500],
            source="rss",
            source_detail=cfg.get("url", ""),
            published_at=entry.get("published", ""),
            raw_metadata={"feed": cfg["url"]},
            collected_at=now,
        ))
    return items


# ===== 飞书认证 =====
class FeishuAuth:
    """惰性 token 管理"""
    def __init__(self):
        import os
        self.app_id = os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        self._token = ""
        self._expires_at = 0.0

    async def get_token(self) -> str:
        import time
        if self._token and time.time() < self._expires_at - 180:
            return self._token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        self._token = data["tenant_access_token"]
        self._expires_at = time.time() + data.get("expire", 7200)
        return self._token


_feishu_auth = FeishuAuth()

async def collect_feishu(source: SourceConfig) -> list[RawItem]:
    if not _feishu_auth.app_id:
        return []
    token = await _feishu_auth.get_token()
    # 一期返回空，后续实现飞书 API 调用
    return []


async def collect_arxiv(source: SourceConfig) -> list[RawItem]:
    cfg = source.config
    items = []
    now = datetime.now(timezone.utc).isoformat()
    for cat in cfg.get("categories", []):
        url = f"http://export.arxiv.org/api/query?search_query=cat:{cat}&start=0&max_results={source.max_items}&sortBy=submittedDate&sortOrder=descending"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        keywords = cfg.get("keywords", [])
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "").strip()
            if keywords and not any(kw.lower() in f"{title} {summary}".lower() for kw in keywords):
                continue
            items.append(RawItem(
                url=entry.get("id", ""),
                title=title,
                description=summary[:500],
                source="arxiv",
                source_detail=cat,
                published_at=entry.get("published", ""),
                raw_metadata={"categories": [t.get("term", "") for t in entry.get("tags", [])]},
                collected_at=now,
            ))
    return items


COLLECTOR_MAP = {
    "github": collect_github,
    "rss": collect_rss,
    "feishu": collect_feishu,
    "arxiv": collect_arxiv,
}


async def collect_all(sources: list[SourceConfig], collectors: dict | None = None) -> tuple[list[RawItem], list[dict]]:
    """并行采集所有启用的源，单个源失败不影响其余。返回 (all_items, error_log)。"""
    cmap = collectors or COLLECTOR_MAP
    tasks = {}
    for src in sources:
        if not src.enabled:
            continue
        fn = cmap.get(src.type)
        if fn:
            tasks[src.id] = asyncio.ensure_future(fn(src))

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    all_items = []
    error_log = []
    for (src_id, src), result in zip(tasks.items(), results):
        if isinstance(result, Exception):
            logger.warning("collector.error", extra={"source": src_id, "error": str(result)})
            error_log.append({"source": src_id, "error": str(result), "retry_in": "next cron"})
        elif isinstance(result, list):
            all_items.extend(result)

    return all_items, error_log
```

- [ ] **Step 3: 运行测试确认通过**

```bash
uv run pytest tests/test_collector.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/graph/collector.py tests/test_collector.py
git commit -m "feat: Collector — 4 源采集 + 错误隔离 + 飞书惰性认证"
```

---

### Task 9: Router 路由节点

**Files:**
- Create: `src/graph/router.py`
- Create: `tests/test_router.py`

```python
# tests/test_router.py
import pytest
from src.graph.state import PipelineState, RawItem
from src.graph.router import router_node

@pytest.mark.asyncio
async def test_router_classifies_by_source():
    state = PipelineState(raw_items=[
        RawItem(url="a", title="a", source="github", collected_at=""),
        RawItem(url="b", title="b", source="rss", collected_at=""),
        RawItem(url="c", title="c", source="feishu", collected_at=""),
        RawItem(url="d", title="d", source="arxiv", collected_at=""),
    ])
    result = await router_node(state)
    assert len(result["routed_github"]) == 1
    assert len(result["routed_rss"]) == 1
    assert len(result["routed_feishu"]) == 1
    assert len(result["routed_arxiv"]) == 1

@pytest.mark.asyncio
async def test_router_empty():
    state = PipelineState()
    result = await router_node(state)
    assert result["routed_github"] == []
```

```python
# src/graph/router.py
from .state import PipelineState

ROUTE_MAP = {"github": "routed_github", "rss": "routed_rss", "feishu": "routed_feishu", "arxiv": "routed_arxiv"}

async def router_node(state: PipelineState) -> dict:
    result = {"routed_github": [], "routed_rss": [], "routed_feishu": [], "routed_arxiv": []}
    for item in state.raw_items:
        key = ROUTE_MAP.get(item.source)
        if key:
            result[key].append(item)
        else:
            result["routed_rss"].append(item)  # 兜底
    return result
```

```bash
uv run pytest tests/test_router.py -v
git add src/graph/router.py tests/test_router.py
git commit -m "feat: Router — 100% 规则按 source 分流"
```

---

### Task 10: Analyzer SubAgent 框架（schema 校验 + 容错 + 重试）

**Files:**
- Create: `src/graph/analyzers/base.py`, `github.py`, `rss.py`, `feishu.py`, `arxiv.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_analyzer.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.graph.state import RawItem, AnalyzedItem
from tests.fixtures.llm_responses import GITHUB_ANALYZE_RESPONSE

@pytest.mark.asyncio
async def test_parse_and_validate_success():
    from src.graph.analyzers.base import parse_and_validate
    raw = json.dumps({"title": "Test", "summary": "A test", "tags": ["AI"], "language": "zh", "relevance_score": 75})
    result = parse_and_validate(raw)
    assert result.title == "Test"
    assert result.tags == ["AI"]
    assert result.relevance_score == 75
    assert result.retry_count == 0

def test_parse_markdown_wrapped_json():
    from src.graph.analyzers.base import parse_and_validate
    raw = '```json\n{"title": "T", "summary": "S", "tags": ["X"], "language": "en"}\n```'
    result = parse_and_validate(raw)
    assert result.title == "T"

def test_invalid_output_raises():
    from src.graph.analyzers.base import parse_and_validate
    with pytest.raises(Exception):
        parse_and_validate('not json at all')
```

- [ ] **Step 2: 实现 base.py + 4 个薄层**

```python
# src/graph/analyzers/base.py
import json
import re
import logging
from pathlib import Path
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

logger = logging.getLogger("pipeline")
ANALYZED_SCHEMA_DESC = '{"title": "string", "summary": "100-200字中文", "tags": ["标签1", "标签2"], "language": "zh|en", "relevance_score": 85}'


def load_prompt(agent_name: str, registry: LLMRegistry) -> str:
    """从 prompts/*.md 文件加载 prompt 模板，作为 .format() 模板使用"""
    path = Path(registry.get_prompt_path(agent_name))
    return path.read_text(encoding="utf-8")


def parse_and_validate(raw: str) -> AnalyzedItem:
    # 1. 尝试直接解析
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 2. 容错：剥离 markdown ```json 包裹
        m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
        else:
            raise ValueError("LLM output is not valid JSON")

    return AnalyzedItem.model_validate(data)


async def analyze_items(
    items: list[RawItem], agent_name: str, registry: LLMRegistry,
    prompt_template: str, system_prompt: str = ""
) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    if not items:
        return [], []

    results = []
    costs = []

    for item in items:
        # 每条独立获取 client（provider 可能随熔断状态变化）
        client, provider, model_id, params = registry.get_client(agent_name)

        user_prompt = prompt_template.format(
            title=item.title, description=item.description,
            url=item.url, metadata=str(item.raw_metadata),
            schema=ANALYZED_SCHEMA_DESC,
        )

        for attempt in range(2):
            try:
                kwargs = dict(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt or f"你是一个技术分析助手。只输出 JSON，格式：{ANALYZED_SCHEMA_DESC}"},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=params.get("temperature", 0.3),
                    max_tokens=params.get("max_tokens", 2048),
                )
                # 仅 provider 支持 JSON mode 时才传 response_format
                if registry.supports_json_mode(provider):
                    kwargs["response_format"] = {"type": "json_object"}

                response = await client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or "{}"
                analyzed = parse_and_validate(content)

                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0
                cost = registry.calc_cost(provider, model_id, tokens_in, tokens_out)

                registry.budget.add_cost(provider, cost)
                registry.health.record_success(provider, 0)

                results.append(analyzed)
                costs.append(CostRecord(agent=agent_name, provider=provider, model=model_id, tokens_in=tokens_in, tokens_out=tokens_out, cost=cost))
                break

            except Exception as e:
                registry.health.record_failure(provider, str(e))
                if attempt == 1:
                    logger.warning("analyzer.parse_failed", extra={"agent": agent_name, "url": item.url, "error": str(e)})
                continue

    return results, costs
```

```python
# src/graph/analyzers/github.py
from .base import analyze_items, load_prompt
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

async def analyze_github(items: list[RawItem], registry: LLMRegistry) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    prompt = load_prompt("github_analyzer", registry)
    return await analyze_items(items, "github_analyzer", registry, prompt)
```

```python
# src/graph/analyzers/rss.py
from .base import analyze_items, load_prompt
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

async def analyze_rss(items: list[RawItem], registry: LLMRegistry) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    prompt = load_prompt("rss_analyzer", registry)
    return await analyze_items(items, "rss_analyzer", registry, prompt)
```

```python
# src/graph/analyzers/feishu.py
from .base import analyze_items, load_prompt
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

async def analyze_feishu(items: list[RawItem], registry: LLMRegistry) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    prompt = load_prompt("feishu_analyzer", registry)
    return await analyze_items(items, "feishu_analyzer", registry, prompt)
```

```python
# src/graph/analyzers/arxiv.py
from .base import analyze_items, load_prompt
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

async def analyze_arxiv(items: list[RawItem], registry: LLMRegistry) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    prompt = load_prompt("arxiv_analyzer", registry)
    return await analyze_items(items, "arxiv_analyzer", registry, prompt)
```

- [ ] **Step 3: 运行测试确认通过**

```bash
uv run pytest tests/test_analyzer.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/graph/analyzers/ tests/test_analyzer.py
git commit -m "feat: Analyzer 框架 — base.analyze_items + schema 校验 + 容错重试"
```

---

### Task 11: Aggregator + Reviewer（LLM 四维评分）

**Files:**
- Create: `src/graph/aggregator.py`, `src/graph/reviewer.py`
- Create: `tests/test_reviewer.py`

- [ ] **Step 1: 实现 Aggregator**

```python
# src/graph/aggregator.py
from .state import PipelineState

async def aggregator_node(state: PipelineState) -> dict:
    return {}  # analyzed_items 和 cost_records 由 operator.add reducer 自动累积
```

- [ ] **Step 2: 编写 Reviewer 测试**

```python
# tests/test_reviewer.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.graph.state import PipelineState, AnalyzedItem, ReviewedItem
from src.graph.reviewer import reviewer_node, parse_reviewer_output
from tests.fixtures.llm_responses import REVIEWER_RESPONSE

def test_parse_reviewer_output():
    raw = json.dumps({
        "total_score": 85,
        "dimensions": {
            "ai_relevance": {"score": 35, "reason": "核心 LLM 推理框架"},
            "content_depth": {"score": 25, "reason": "有技术细节"},
            "info_density": {"score": 12, "reason": "有新信息"},
            "timeliness": {"score": 13, "reason": "本周发布"}
        },
        "verdict": "approved",
        "retry_feedback": None
    })
    result = parse_reviewer_output(raw)
    assert isinstance(result, ReviewedItem)
    assert result.total_score == 85
    assert result.verdict == "approved"
    assert result.dimensions["ai_relevance"]["score"] == 35
    assert result.retry_feedback is None

def test_parse_reviewer_output_retry():
    raw = json.dumps({
        "total_score": 65,
        "dimensions": {
            "ai_relevance": {"score": 25, "reason": "AI 基础设施"},
            "content_depth": {"score": 18, "reason": "有部分细节"},
            "info_density": {"score": 10, "reason": "有一定信息量"},
            "timeliness": {"score": 12, "reason": "本周"}
        },
        "verdict": "retry",
        "retry_feedback": {"suggestions": ["补充 AI 相关度分析", "增加技术深度"]}
    })
    result = parse_reviewer_output(raw)
    assert result.verdict == "retry"
    assert result.retry_feedback["suggestions"] == ["补充 AI 相关度分析", "增加技术深度"]

def test_parse_reviewer_output_markdown_wrapped():
    raw = '```json\n{"total_score": 30, "dimensions": {"ai_relevance": {"score": 5, "reason": "无关"}, "content_depth": {"score": 8, "reason": "简要"}, "info_density": {"score": 5, "reason": "重复"}, "timeliness": {"score": 12, "reason": "本周"}}, "verdict": "discarded", "retry_feedback": null}\n```'
    result = parse_reviewer_output(raw)
    assert result.verdict == "discarded"

@pytest.mark.asyncio
async def test_reviewer_node_mocked():
    """Mock LLM 调用，验证 Reviewer 节点正确分类"""
    from src.core.llm_client import LLMRegistry
    from src.core.config import (
        LLMConfig, AgentsConfig, ProviderConfig, ModelInfo,
        AgentConfig, ModelBinding, ModelRef, BudgetConfig
    )

    llm_cfg = LLMConfig(providers={
        "deepseek": ProviderConfig(
            base_url="https://api.deepseek.com/v1", api_key="sk-test",
            models=[ModelInfo(id="deepseek-chat", price_per_1k_in=0.000014, price_per_1k_out=0.000028, max_tokens=8192)]
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "reviewer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.0, "max_tokens": 1024}
            ),
        },
        budget=BudgetConfig(monthly=10.0)
    )
    registry = LLMRegistry(llm_cfg, agents_cfg)

    # Mock AsyncOpenAI client
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "total_score": 88, "dimensions": {
                "ai_relevance": {"score": 38, "reason": "核心 Agent 框架"},
                "content_depth": {"score": 25, "reason": "深度原创"},
                "info_density": {"score": 13, "reason": "新颖"},
                "timeliness": {"score": 12, "reason": "本周"}
            }, "verdict": "approved", "retry_feedback": None
        })))
    ]
    mock_response.usage = MagicMock(prompt_tokens=300, completion_tokens=120)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    registry._clients["deepseek"] = mock_client

    state = PipelineState(analyzed_items=[
        AnalyzedItem(ref_url="https://example.com/1", title="Test Agent", summary="A new agent framework", tags=["Agent", "Framework"], language="zh", relevance_score=0, retry_count=0)
    ])
    result = await reviewer_node(state, registry)

    assert len(result["reviewed_items"]) == 1
    reviewed = result["reviewed_items"][0]
    assert reviewed.verdict == "approved"
    assert reviewed.total_score == 88
    assert len(result["cost_records"]) == 1
```

- [ ] **Step 3: 运行测试确认失败**

```bash
uv run pytest tests/test_reviewer.py -v
# 预期: ImportError (reviewer.py 不存在)
```

- [ ] **Step 4: 实现 Reviewer（LLM 四维评分）**

```python
# src/graph/reviewer.py
import json
import re
import logging
from .state import PipelineState, AnalyzedItem, ReviewedItem, CostRecord
from ..core.llm_client import LLMRegistry

logger = logging.getLogger("pipeline")
MAX_RETRIES = 2


def _load_reviewer_prompt(registry: LLMRegistry) -> str:
    """从 prompts/reviewer.md 加载系统 prompt；文件缺失时使用内置默认"""
    from pathlib import Path
    try:
        path = Path(registry.get_prompt_path("reviewer"))
        return path.read_text(encoding="utf-8")
    except Exception:
        return """你是内容审核员。对文章按四维评分（0-100）:
- AI相关度(0-40): 核心AI/LLM/Agent/MCP/RAG=35-40, AI基础设施=25-34, 泛技术提及=10-24, 无关=0-9
- 内容深度(0-30): 深度原创=25-30, 有细节=15-24, 简要=5-14, 空内容=0-4
- 信息密度(0-15): 新颖独家=12-15, 有信息量=7-11, 重复营销=0-6
- 时效性(0-15): 本周内=12-15, 本月=7-11, 较早=0-6

输出 JSON:
{"total_score": 85, "dimensions": {"ai_relevance": {"score": 35, "reason": "..."}, "content_depth": {"score": 25, "reason": "..."}, "info_density": {"score": 12, "reason": "..."}, "timeliness": {"score": 13, "reason": "..."}}, "verdict": "approved"|"retry"|"discarded", "retry_feedback": null|{"suggestions": ["..."]}}"""


def parse_reviewer_output(raw: str) -> ReviewedItem:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
        else:
            raise ValueError("Reviewer output is not valid JSON")
    return ReviewedItem.model_validate(data)


async def reviewer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.analyzed_items:
        return {"reviewed_items": [], "cost_records": []}

    system_prompt = _load_reviewer_prompt(registry)
    reviewed_items = []
    cost_records = []

    for item in state.analyzed_items:
        # 超过最大重试次数直接丢弃
        if item.retry_count >= MAX_RETRIES:
            reviewed_items.append(ReviewedItem(
                ref_url=item.ref_url, total_score=0, dimensions={},
                verdict="discarded",
                retry_feedback={"reason": f"exceeded max retries ({MAX_RETRIES})"}
            ))
            continue

        client, provider, model_id, params = registry.get_client("reviewer")
        user_prompt = f"标题: {item.title}\n摘要: {item.summary}\n标签: {', '.join(item.tags)}\n来源: {item.ref_url}"

        for attempt in range(2):
            try:
                kwargs = dict(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=params.get("max_tokens", 1024),
                )
                if registry.supports_json_mode(provider):
                    kwargs["response_format"] = {"type": "json_object"}

                response = await client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or "{}"
                reviewed = parse_reviewer_output(content)

                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0
                cost = registry.calc_cost(provider, model_id, tokens_in, tokens_out)
                registry.budget.add_cost(provider, cost)
                registry.health.record_success(provider, 0)

                reviewed_items.append(reviewed)
                cost_records.append(CostRecord(
                    agent="reviewer", provider=provider, model=model_id,
                    tokens_in=tokens_in, tokens_out=tokens_out, cost=cost
                ))
                break

            except Exception as e:
                registry.health.record_failure(provider, str(e))
                if attempt == 1:
                    logger.warning("reviewer.parse_failed", extra={"url": item.ref_url, "error": str(e)})
                    reviewed_items.append(ReviewedItem(
                        ref_url=item.ref_url, total_score=0, dimensions={},
                        verdict="discarded",
                        retry_feedback={"reason": f"parse failed after 2 attempts: {str(e)}"}
                    ))

    logger.info("reviewer.done", extra={
        "total": len(reviewed_items),
        "approved": sum(1 for r in reviewed_items if r.verdict == "approved"),
        "retry": sum(1 for r in reviewed_items if r.verdict == "retry"),
        "discarded": sum(1 for r in reviewed_items if r.verdict == "discarded"),
    })

    return {"reviewed_items": reviewed_items, "cost_records": cost_records}
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/test_reviewer.py -v
# 预期: 4 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/graph/aggregator.py src/graph/reviewer.py tests/test_reviewer.py
git commit -m "feat: Aggregator + Reviewer — LLM 四维评分 (AI相关度+内容深度+信息密度+时效性)"
```

---

### Task 12: Pipeline 组装（LangGraph StateGraph）

**Files:**
- Create: `src/graph/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: 确认 Task 7 的 PipelineState 已完成 reducer 注解**

Task 7 的 `analyzed_items` 和 `cost_records` 使用了 `Annotated[list[...], operator.add]`，这是 LangGraph fan-out 并行分支结果合并所必需的。

- [ ] **Step 2: 编写测试**

```python
# tests/test_pipeline.py
import pytest
from unittest.mock import AsyncMock
from src.graph.pipeline import build_pipeline
from src.graph.state import PipelineState, RawItem, AnalyzedItem, CostRecord, ReviewedItem
from src.core.llm_client import LLMRegistry
from src.core.config import (
    LLMConfig, AgentsConfig, ProviderConfig, ModelInfo,
    AgentConfig, ModelBinding, ModelRef, BudgetConfig
)

@pytest.fixture
def registry():
    llm_cfg = LLMConfig(providers={
        "deepseek": ProviderConfig(
            base_url="https://api.deepseek.com/v1", api_key="sk-test",
            models=[ModelInfo(id="deepseek-chat", price_per_1k_in=0.000014, price_per_1k_out=0.000028, max_tokens=8192)]
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "github_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
            "rss_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
            "feishu_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
            "arxiv_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 4096}
            ),
        },
        budget=BudgetConfig(monthly=10.0)
    )
    return LLMRegistry(llm_cfg, agents_cfg)

def test_pipeline_structure(registry):
    graph = build_pipeline(registry)
    nodes = graph.get_graph().nodes
    names = {n for n in nodes}
    assert "router" in names
    assert "github_analyzer" in names
    assert "rss_analyzer" in names
    assert "feishu_analyzer" in names
    assert "arxiv_analyzer" in names
    assert "aggregator" in names
    assert "reviewer" in names

@pytest.mark.asyncio
async def test_pipeline_e2e_mocked(registry):
    """全链路 mock 测试：router → fan-out → aggregator → reviewer"""
    # Mock LLM 调用，让 analyzer 返回固定结果
    async def mock_analyze_github(items, reg):
        return [
            AnalyzedItem(ref_url=items[0].url, title="Test", summary="Mocked", tags=["AI"], language="zh")
        ], [CostRecord(agent="github_analyzer", provider="deepseek", model="deepseek-chat", tokens_in=100, tokens_out=50, cost=0.001)]

    # 替换 registry 的 get_client，避免真实 LLM 调用
    # 测试中通过 monkeypatch 覆盖 analyzer 函数

    graph = build_pipeline(registry)
    state = PipelineState(
        raw_items=[
            RawItem(url="https://github.com/test/x", title="x", description="desc", source="github", collected_at="2026-05-16T10:00:00Z"),
            RawItem(url="https://example.com/y", title="y", description="desc", source="rss", collected_at="2026-05-16T10:00:00Z"),
        ],
        run_id="test_run", trigger="manual"
    )

    # Router 先跑一次得到 routed_*
    from src.graph.router import router_node
    routed = await router_node(state)
    state = state.model_copy(update=routed)

    # 用 patch 替换 analyzer 和 reviewer 函数，避免真实 LLM 调用
    import src.graph.pipeline as pl
    with patch.object(pl, "github_analyzer_node", new=AsyncMock(return_value={
        "analyzed_items": [AnalyzedItem(ref_url="https://github.com/test/x", title="Test", summary="Mocked", tags=["AI"], language="zh")],
        "cost_records": [CostRecord(agent="github_analyzer", provider="deepseek", model="deepseek-chat", tokens_in=100, tokens_out=50, cost=0.001)]
    })), \
         patch.object(pl, "rss_analyzer_node", new=AsyncMock(return_value={
             "analyzed_items": [],
             "cost_records": []
         })), \
         patch.object(pl, "reviewer_node", new=AsyncMock(return_value={
             "reviewed_items": [ReviewedItem(ref_url="https://github.com/test/x", total_score=85, dimensions={}, verdict="approved")],
             "cost_records": []
         })):
        result = await graph.ainvoke(state)

    assert len(result["analyzed_items"]) == 1
    assert result["analyzed_items"][0].ref_url == "https://github.com/test/x"
    assert len(result["reviewed_items"]) == 1
    assert result["reviewed_items"][0].verdict == "approved"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_pipeline.py -v
# 预期: ImportError (pipeline.py 不存在)
```

- [ ] **Step 3: 实现 build_pipeline（含闭包注入 registry）**

```python
# src/graph/pipeline.py
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send
from .state import PipelineState
from .router import router_node
from .aggregator import aggregator_node
from .reviewer import reviewer_node
from .analyzers.github import analyze_github
from .analyzers.rss import analyze_rss
from .analyzers.feishu import analyze_feishu
from .analyzers.arxiv import analyze_arxiv
from ..core.llm_client import LLMRegistry


async def github_analyzer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.routed_github:
        return {"analyzed_items": [], "cost_records": []}
    items, costs = await analyze_github(state.routed_github, registry)
    return {"analyzed_items": items, "cost_records": costs}


async def rss_analyzer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.routed_rss:
        return {"analyzed_items": [], "cost_records": []}
    items, costs = await analyze_rss(state.routed_rss, registry)
    return {"analyzed_items": items, "cost_records": costs}


async def feishu_analyzer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.routed_feishu:
        return {"analyzed_items": [], "cost_records": []}
    items, costs = await analyze_feishu(state.routed_feishu, registry)
    return {"analyzed_items": items, "cost_records": costs}


async def arxiv_analyzer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.routed_arxiv:
        return {"analyzed_items": [], "cost_records": []}
    items, costs = await analyze_arxiv(state.routed_arxiv, registry)
    return {"analyzed_items": items, "cost_records": costs}


def continue_to_analyzers(state: PipelineState):
    sends = []
    if state.routed_github:
        sends.append(Send("github_analyzer", state))
    if state.routed_rss:
        sends.append(Send("rss_analyzer", state))
    if state.routed_feishu:
        sends.append(Send("feishu_analyzer", state))
    if state.routed_arxiv:
        sends.append(Send("arxiv_analyzer", state))
    return sends


def build_pipeline(registry: LLMRegistry):
    """构建并编译 LangGraph pipeline。

    Collector 和 DB 查重在图外执行（需要 DB 连接），
    图内编排：Router → Fan-out(4×Analyzer) → Aggregator → Reviewer。

    analyzed_items 和 cost_records 使用 operator.add reducer，
    fan-out 并行分支的结果自动合并。
    """
    graph = StateGraph(PipelineState)

    graph.add_node("router", router_node)
    graph.add_node("github_analyzer", lambda s: github_analyzer_node(s, registry))
    graph.add_node("rss_analyzer", lambda s: rss_analyzer_node(s, registry))
    graph.add_node("feishu_analyzer", lambda s: feishu_analyzer_node(s, registry))
    graph.add_node("arxiv_analyzer", lambda s: arxiv_analyzer_node(s, registry))
    graph.add_node("aggregator", aggregator_node)
    graph.add_node("reviewer", lambda s: reviewer_node(s, registry))

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", continue_to_analyzers)
    graph.add_edge("github_analyzer", "aggregator")
    graph.add_edge("rss_analyzer", "aggregator")
    graph.add_edge("feishu_analyzer", "aggregator")
    graph.add_edge("arxiv_analyzer", "aggregator")
    graph.add_edge("aggregator", "reviewer")
    graph.add_edge("reviewer", END)

    return graph.compile()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_pipeline.py -v
# 预期: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/graph/pipeline.py tests/test_pipeline.py
git commit -m "feat: LangGraph Pipeline — 编译图含 Router→Fan-out(4×Analyzer)→Aggregator→Reviewer"
```

---

### Phase 4: 存储与 API

**验收标准**：CRUD 操作正确，`/api/articles`、`/api/search`、`/api/stats`、`/api/health` 可正常调用

---

### Task 13: 数据库操作 + 备份

**Files:**
- Create: `src/db/operations.py`

- [ ] **Step 1: 实现 DB 操作**

```python
# src/db/operations.py
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from ..core.database import Database
from ..graph.state import AnalyzedItem, CostRecord, ReviewedItem

async def save_article(db: Database, raw, analyzed: AnalyzedItem, reviewed: ReviewedItem, cost: float, tokens: int) -> int | None:
    """保存文章，返回 article id（新插入或已存在行的 id）"""
    extra = json.dumps({
        "dimensions": reviewed.dimensions,
        "language": analyzed.language,
        "raw": raw.raw_metadata,
    }, ensure_ascii=False)
    row = await db.fetch_one("""
        INSERT INTO articles
        (title, url, description, summary, source, source_detail,
         relevance_score, status, retry_count, collected_at, published_at, extra_data, analysis_cost, analysis_tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            summary = excluded.summary,
            relevance_score = excluded.relevance_score,
            status = excluded.status,
            retry_count = excluded.retry_count,
            extra_data = excluded.extra_data,
            analysis_cost = excluded.analysis_cost,
            analysis_tokens = excluded.analysis_tokens,
            updated_at = datetime('now')
        RETURNING id
    """, (
        analyzed.title, raw.url, raw.description, analyzed.summary,
        raw.source, raw.source_detail, reviewed.total_score,
        reviewed.verdict, analyzed.retry_count,
        raw.collected_at, raw.published_at,
        extra,
        cost, tokens,
    ))
    return row["id"] if row else None

async def save_tags(db: Database, article_id: int, tags: list[str]):
    # 先清旧标签，再插入新标签（retry 重分析时标签可能变化）
    await db.execute("DELETE FROM article_tags WHERE article_id = ?", (article_id,))
    for tag_name in tags:
        await db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        row = await db.fetch_one("SELECT id FROM tags WHERE name = ?", (tag_name,))
        if row:
            await db.execute("INSERT OR IGNORE INTO article_tags (article_id, tag_id) VALUES (?, ?)", (article_id, row["id"]))

async def start_pipeline_run(db: Database, run_id: str, trigger: str):
    now = datetime.now(timezone.utc).isoformat()
    await db.execute("INSERT INTO pipeline_runs (id, started_at, trigger) VALUES (?, ?, ?)", (run_id, now, trigger))

async def end_pipeline_run(db: Database, run_id: str, status: str, summary: str):
    now = datetime.now(timezone.utc).isoformat()
    await db.execute("UPDATE pipeline_runs SET ended_at=?, status=?, summary=? WHERE id=?", (now, status, summary, run_id))

async def save_cost_log(db: Database, run_id: str, record: CostRecord):
    await db.execute("INSERT INTO cost_logs (run_id, agent, provider, model, tokens_in, tokens_out, cost) VALUES (?,?,?,?,?,?,?)",
        (run_id, record.agent, record.provider, record.model, record.tokens_in, record.tokens_out, record.cost))

async def batch_check_existing_urls(db: Database, urls: list[str]) -> set[str]:
    """Collector 后批量查重"""
    if not urls:
        return set()
    placeholders = ",".join("?" * len(urls))
    rows = await db.fetch_all(f"SELECT url FROM articles WHERE url IN ({placeholders})", tuple(urls))
    return {r["url"] for r in rows}

async def search_articles(db: Database, query: str, source: str = "", days: int = 30, limit: int = 20, offset: int = 0) -> list[dict]:
    if query:
        rows = await db.fetch_all(
            "SELECT a.* FROM articles a JOIN articles_fts fts ON a.rowid = fts.rowid WHERE articles_fts MATCH ? ORDER BY a.collected_at DESC LIMIT ? OFFSET ?",
            (query, limit, offset))
    else:
        where = ["status = 'approved'"]
        params = []
        if source:
            where.append("source = ?"); params.append(source)
        if days:
            where.append("collected_at >= date('now', ?)"); params.append(f"-{days} days")
        params.extend([limit, offset])
        rows = await db.fetch_all(f"SELECT * FROM articles WHERE {' AND '.join(where)} ORDER BY collected_at DESC LIMIT ? OFFSET ?", tuple(params))
    return [dict(r) for r in rows]

async def get_stats(db: Database, days: int = 30) -> dict:
    total = await db.fetch_one("SELECT COUNT(*) as c FROM articles WHERE status='approved'")
    period = await db.fetch_one("SELECT COUNT(*) as c FROM articles WHERE status='approved' AND collected_at >= date('now', ?)", (f"-{days} days",))
    source_dist = await db.fetch_all("SELECT source, COUNT(*) as c FROM articles WHERE status='approved' GROUP BY source ORDER BY c DESC")
    cost_period = await db.fetch_one("SELECT COALESCE(SUM(cost),0) as t FROM cost_logs WHERE created_at >= date('now', ?)", (f"-{days} days",))
    cost_total = await db.fetch_one("SELECT COALESCE(SUM(cost),0) as t FROM cost_logs")
    daily_cost = await db.fetch_all("SELECT date(created_at) as date, SUM(cost) as cost, COUNT(*) as articles FROM cost_logs WHERE created_at >= date('now', ?) GROUP BY date(created_at) ORDER BY date", (f"-{days} days",))
    top_tags = await db.fetch_all("SELECT t.name, COUNT(*) as c FROM tags t JOIN article_tags at ON t.id=at.tag_id GROUP BY t.id ORDER BY c DESC LIMIT 10")
    return {
        "total_articles": total["c"] if total else 0,
        "period_articles": period["c"] if period else 0,
        "source_distribution": [{"source": s["source"], "count": s["c"]} for s in source_dist],
        "period_cost": round(cost_period["t"] if cost_period else 0, 4),
        "total_cost": round(cost_total["t"] if cost_total else 0, 4),
        "daily_cost": [{"date": d["date"], "cost": d["cost"], "articles": d["articles"]} for d in daily_cost],
        "top_tags": [{"name": t["name"], "count": t["c"]} for t in top_tags],
    }

async def backup_database(db: Database, backup_dir: str):
    """aiosqlite .backup() 在线热备份，保留 7 天"""
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    backup_file = Path(backup_dir) / f"knowledge-{today}.db"
    await db.backup(str(backup_file))

    # 清理 7 天前
    cutoff = datetime.now() - timedelta(days=7)
    for f in Path(backup_dir).glob("knowledge-*.db"):
        try:
            date_str = f.stem.replace("knowledge-", "")
            f_date = datetime.strptime(date_str, "%Y%m%d")
            if f_date < cutoff:
                f.unlink()
        except ValueError:
            pass
```

- [ ] **Step 2: Commit**

```bash
git add src/db/operations.py
git commit -m "feat: DB 操作 — CRUD + 批量查重 + stats + FTS 搜索 + 备份"
```

---

### Task 14: FastAPI 端点（含统一响应信封）

**Files:**
- Create: `src/api/routes.py`

- [ ] **Step 1: 实现统一信封 + 端点**

```python
# src/api/routes.py
from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import JSONResponse
from ..core.database import Database
from ..db import operations

router = APIRouter(prefix="/api")
_db: Database | None = None

def set_db(db: Database):
    global _db; _db = db

# ===== 统一响应信封 =====

def envelope(data=None, message="ok", code=0):
    """成功响应信封"""
    return {"code": code, "data": data, "message": message}


async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTPException → 结构化错误响应"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "data": None,
            "message": exc.detail,
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """未捕获异常 → 50001"""
    return JSONResponse(
        status_code=500,
        content={"code": 50001, "data": None, "message": "服务内部错误"},
    )


# ===== 端点 =====

@router.get("/articles")
async def list_articles(
    query: str = Query(default=""),
    source: str = Query(default=""),
    days: int = Query(default=30, ge=1, le=3650),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    offset = (page - 1) * page_size
    rows = await operations.search_articles(_db, query, source, days, page_size, offset)
    total = len(rows)  # 简化：实际应 COUNT 查询
    return envelope({
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/articles/{article_id}")
async def get_article(article_id: int):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    row = await _db.fetch_one("SELECT * FROM articles WHERE id = ?", (article_id,))
    if not row:
        raise HTTPException(status_code=404, detail=f"文章 {article_id} 不存在")
    return envelope(dict(row))


@router.get("/search")
async def search(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    rows = await operations.search_articles(_db, q, days=3650, limit=limit)
    return envelope({"items": rows, "total": len(rows)})


@router.get("/stats")
async def get_stats(days: int = Query(default=30, ge=1, le=3650)):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    return envelope(await operations.get_stats(_db, days))


@router.get("/health")
async def health():
    return {"status": "ok"}  # 不包信封，Caddy/Compose healthcheck 直接读


@router.get("/cost/summary")
async def cost_summary(days: int = Query(default=30)):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    rows = await _db.fetch_all(
        "SELECT provider, model, SUM(cost) as total_cost, SUM(tokens_in+tokens_out) as total_tokens "
        "FROM cost_logs WHERE created_at >= date('now', ?) GROUP BY provider, model",
        (f"-{days} days",),
    )
    return envelope([dict(r) for r in rows])


_run_pipeline_cb = None

def set_run_pipeline(cb):
    global _run_pipeline_cb; _run_pipeline_cb = cb

@router.post("/pipeline/run")
async def trigger_pipeline(source: str = Query(default="")):
    if not _run_pipeline_cb:
        raise HTTPException(500, "Pipeline not initialized")
    import asyncio
    asyncio.create_task(_run_pipeline_cb(
        trigger="manual",
        source_filter=source or None,  # 空字符串 = 全量
    ))
    return envelope({"status": "queued"}, "Pipeline triggered")
```

- [ ] **Step 2: 在 main.py 中注册异常处理器**

Task 16 的 `create_app()` 需注册两个 exception handler：

```python
def create_app() -> FastAPI:
    from .api.routes import http_exception_handler, general_exception_handler

    app = FastAPI(lifespan=lifespan, title="AI Knowledge Base")
    app.include_router(router)
    app.add_exception_handler(HTTPException, http_exception_handler)  # FastAPI 的 HTTPException
    app.add_exception_handler(Exception, general_exception_handler)
    return app
```

注意：FastAPI 自带 `HTTPException` 的默认 handler，需要覆盖它。`exception_handler` 注册在 app 级别，不会影响 middleware/startup 等。

- [ ] **Step 3: Commit**

```bash
git add src/api/routes.py src/main.py
git commit -m "feat: FastAPI 端点 — 统一响应信封 + 结构化错误 + 分页元数据"
```

---

### Phase 5: 静态站点生成

**验收标准**：Pipeline 完成后自动渲染 index.html + dashboard.html + data.json + stats.json，原子 rename 切换，首页 30 天预渲染

---

### Task 15: 静态站点生成器（去抖 + 原子 rename + 数据拆分）

**Files:**
- Create: `src/site/builder.py`
- Create: `src/site/templates/base.html`, `index.html`, `article.html`, `dashboard.html`

- [ ] **Step 1: 实现 SiteBuilder + DebouncedBuilder**

```python
# src/site/builder.py
import asyncio, json, shutil
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from ..core.database import Database
from ..db.operations import search_articles, get_stats

class SiteBuilder:
    def __init__(self, db: Database, output_dir: Path, template_dir: Path):
        self.db = db
        self.output_dir = output_dir
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)

    async def build(self):
        tmp_dir = self.output_dir.parent / "output.tmp"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir()
        (tmp_dir / "articles").mkdir()

        all_articles = await search_articles(self.db, "", days=3650, limit=100000)
        stats = await get_stats(self.db, days=30)

        # 首页 — Jinja2 预渲染最近 30 天
        recent = [a for a in all_articles[:100]]  # 实际按 collected_at 排序取前 100
        index_html = self.env.get_template("index.html").render(
            articles=recent, stats=stats, updated=datetime.now().isoformat()
        )
        (tmp_dir / "index.html").write_text(index_html, encoding="utf-8")

        # 仪表盘 — Jinja2 内联 stats.json
        dash_html = self.env.get_template("dashboard.html").render(stats=stats)
        (tmp_dir / "dashboard.html").write_text(dash_html, encoding="utf-8")

        # data.json — 列表字段不含 summary，description 截断到 200 字符（详情页走 API）
        json_articles = []
        for a in all_articles:
            desc = a.get("description", "") or ""
            json_articles.append({
                "id": a["id"], "title": a["title"], "url": a["url"],
                "description": desc[:200],
                "source": a["source"], "source_detail": a.get("source_detail", ""),
                "relevance_score": a["relevance_score"],
                "published_at": a.get("published_at", ""),
                "collected_at": a.get("collected_at", ""),
            })
        (tmp_dir / "data.json").write_text(json.dumps(json_articles, ensure_ascii=False), encoding="utf-8")

        # stats.json
        (tmp_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")

        # 原子 rename 切换
        old_dir = self.output_dir.parent / "output.old"
        if old_dir.exists():
            shutil.rmtree(old_dir)
        if self.output_dir.exists():
            self.output_dir.rename(old_dir)
        tmp_dir.rename(self.output_dir)
        if old_dir.exists():
            shutil.rmtree(old_dir)


class DebouncedBuilder:
    """去抖渲染器：pipeline 完成后 schedule()，5min 无新触发才真正构建"""
    def __init__(self, builder: SiteBuilder, debounce_seconds: int = 300):
        self.builder = builder
        self.debounce_seconds = debounce_seconds
        self._timer: asyncio.Task | None = None

    async def schedule(self):
        if self._timer:
            self._timer.cancel()
        self._timer = asyncio.create_task(self._wait_and_build())

    async def _wait_and_build(self):
        await asyncio.sleep(self.debounce_seconds)
        await self.builder.build()

    async def build_now(self):
        if self._timer:
            self._timer.cancel()
        await self.builder.build()
```

- [ ] **Step 2: 创建模板**

`src/site/templates/base.html`:
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}AI Knowledge Base{% endblock %}</title>
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <nav><a href="/">首页</a> | <a href="/dashboard.html">仪表盘</a></nav>
    <main>{% block content %}{% endblock %}</main>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <script src="/js/app.js"></script>
</body>
</html>
```

`src/site/templates/index.html`:
```html
{% extends "base.html" %}
{% block title %}AI Knowledge Base{% endblock %}
{% block content %}
<div class="filters">
    <input type="search" id="search-box" placeholder="搜索... (FTS5)">
    <select id="source-filter"><option value="">全部来源</option></select>
    <select id="tag-filter"><option value="">全部标签</option></select>
    <div class="date-filters">
        <button data-days="7">近 7 天</button>
        <button data-days="30">近 30 天</button>
        <button data-days="0">全部</button>
    </div>
</div>
<div id="article-list">
    {% for article in articles %}
    <div class="article-card" data-score="{{ article.relevance_score }}" data-source="{{ article.source }}">
        <h3><a href="/article.html?id={{ article.id }}">{{ article.title }}</a></h3>
        <p>{{ article.description[:200] }}</p>
        <div class="meta">
            <span>{{ article.source_detail or article.source }}</span>
            <span>{{ article.collected_at[:10] }}</span>
            <span class="score">{{ article.relevance_score }}分</span>
        </div>
    </div>
    {% endfor %}
</div>
<script>window.__INIT__ = {articles: {{ articles|tojson }}, stats: {{ stats|tojson }}};</script>
{% endblock %}
```

`src/site/templates/article.html`:
```html
{% extends "base.html" %}
{% block title %}文章详情{% endblock %}
{% block content %}
<div id="article-detail"><p>加载中...</p></div>
<script>
const id = new URLSearchParams(location.search).get('id');
if (id) fetch('/api/articles/' + id).then(r => r.json()).then(a => {
    document.getElementById('article-detail').innerHTML = `
        <h1>${a.title}</h1>
        <div class="meta">${a.source_detail || a.source} · ${a.collected_at}</div>
        <a href="${a.url}" target="_blank">查看原文</a>
        <div class="summary">${a.summary}</div>
        <div class="meta-footer">评分: ${a.relevance_score} · 花费: $${a.analysis_cost}</div>
    `;
});
</script>
{% endblock %}
```

`src/site/templates/dashboard.html`:
```html
{% extends "base.html" %}
{% block title %}仪表盘{% endblock %}
{% block content %}
<div class="kpi-cards">
    <div class="kpi"><h3>{{ stats.total_articles }}</h3><p>文章总数</p></div>
    <div class="kpi"><h3>{{ stats.period_articles }}</h3><p>近 30 天</p></div>
    <div class="kpi"><h3>${{ stats.total_cost }}</h3><p>总花费</p></div>
</div>
<div class="charts">
    <canvas id="source-chart"></canvas>
    <canvas id="cost-chart"></canvas>
</div>
<script>window.__STATS__ = {{ stats|tojson }};</script>
<script>
const stats = window.__STATS__;
new Chart(document.getElementById('source-chart'), {
    type: 'pie',
    data: {labels: stats.source_distribution.map(s=>s.source), datasets: [{data: stats.source_distribution.map(s=>s.count)}]}
});
new Chart(document.getElementById('cost-chart'), {
    type: 'line',
    data: {labels: stats.daily_cost.map(d=>d.date), datasets: [{label: '每日花费($)', data: stats.daily_cost.map(d=>d.cost)}]}
});
</script>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add src/site/
git commit -m "feat: 静态站点生成器 — 去抖 + 原子 rename + data.json/stats.json 拆分 + Chart.js 仪表盘"
```

---

### Phase 6: 主入口与部署

**验收标准**：`docker compose up` 后服务可访问，健康检查 200，pipeline 可手动触发

---

### Task 16: 主入口（FastAPI + APScheduler + Pipeline + 结构化日志）

**Files:**
- Create: `src/main.py`

```python
# src/main.py
import os, json, logging, sys, uuid
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .core.config import load_llm_config, load_sources_config, load_agents_config
from .core.database import Database
from .core.llm_client import LLMRegistry
from .graph.pipeline import build_pipeline
from .graph.state import PipelineState, ReviewedItem
from .graph.collector import collect_all
from .graph.router import router_node  # retry 循环中手动路由 retry items
from .api.routes import router, set_db, set_run_pipeline
from .db.operations import (
    start_pipeline_run, end_pipeline_run, save_article, save_tags,
    save_cost_log, batch_check_existing_urls, backup_database,
)
from .site.builder import SiteBuilder, DebouncedBuilder

# 结构化日志：stdout JSON lines（每行一条合法 JSON）
class JSONFormatter(logging.Formatter):
    _SKIP_KEYS = {
        "name", "msg", "args", "created", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs", "pathname",
        "process", "processName", "relativeCreated", "stack_info",
        "exc_info", "exc_text", "thread", "threadName", "message",
    }

    def format(self, record):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in self._SKIP_KEYS and not k.startswith("_"):
                entry[k] = v
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("pipeline")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH = DATA_DIR / "kb.db"
BACKUP_DIR = DATA_DIR / "backup"

_registry: LLMRegistry | None = None
_db: Database | None = None
_scheduler: AsyncIOScheduler | None = None
_builder: DebouncedBuilder | None = None
_graph = None  # LangGraph 编译图
_running = False


async def run_pipeline(trigger: str = "cron", source_filter: str | None = None):
    """source_filter 为 None 时采集所有源，否则只采集指定 source.id"""
    global _registry, _db, _builder, _running, _graph

    if _running:
        logger.warning("pipeline.skip", extra={"reason": "previous run still in progress"})
        return
    _running = True

    try:
        if _registry is None or _db is None or _graph is None:
            logger.error("pipeline.not_initialized")
            return

        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        await start_pipeline_run(_db, run_id, trigger)

        sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")
        active_sources = [s for s in sources_cfg.sources if s.enabled]
        if source_filter:
            active_sources = [s for s in active_sources if s.id == source_filter]

        # ====== 图外：Collector + DB 查重（需要 DB 连接） ======
        raw_items, error_log = await collect_all(active_sources)
        logger.info("collector.done", extra={"total": len(raw_items), "errors": len(error_log)})

        if not raw_items and error_log:
            summary = json.dumps({"collected": 0, "errors": error_log})
            await end_pipeline_run(_db, run_id, "failed", summary)
            return

        all_urls = [item.url for item in raw_items]
        existing = await batch_check_existing_urls(_db, all_urls)
        new_items = [item for item in raw_items if item.url not in existing]
        logger.info("collector.dedup", extra={"total": len(raw_items), "new": len(new_items), "skipped": len(raw_items) - len(new_items)})

        if not new_items:
            summary = json.dumps({"collected": {"total": len(raw_items), "new": 0}, "message": "all items already exist"})
            await end_pipeline_run(_db, run_id, "completed", summary)
            return

        # ====== 图内：Router → Fan-out(4×Analyzer) → Aggregator → Reviewer ======
        state = PipelineState(raw_items=new_items, run_id=run_id, trigger=trigger, error_log=error_log)
        final_state = await _graph.ainvoke(state)

        # ====== Retry 循环（图外，最多 2 轮） ======
        all_reviewed = list(final_state["reviewed_items"])
        all_costs = list(final_state["cost_records"])
        all_analyzed = list(final_state["analyzed_items"])

        for retry_round in range(1, 3):  # 第 1、2 轮 retry
            retry_reviewed = [r for r in all_reviewed if r.verdict == "retry"]
            if not retry_reviewed:
                break

            # 找到对应的 analyzed items + raw items，递增 retry_count
            retry_raw_items = []
            retry_analyzed_items = []
            for rr in retry_reviewed:
                matched = next((a for a in all_analyzed if a.ref_url == rr.ref_url), None)
                raw = next((r for r in new_items if r.url == rr.ref_url), None)
                if matched and raw and matched.retry_count < 2:
                    matched.retry_count += 1
                    retry_raw_items.append(raw)
                    retry_analyzed_items.append(matched)

            if not retry_raw_items:
                break

            logger.info("pipeline.retry", extra={"round": retry_round, "items": len(retry_raw_items)})

            # 构建 retry state：直接跳过 Router，手动设置 routed_* 再跑图
            retry_state = PipelineState(raw_items=retry_raw_items, run_id=run_id, trigger=trigger)
            retry_state = retry_state.model_copy(update=await router_node(retry_state))
            retry_result = await _graph.ainvoke(retry_state)

            # 合并结果（同一 ref_url 的 reviewed_item 用最新一轮的覆盖）
            existing_urls = {r.ref_url for r in all_reviewed}
            for r in retry_result["reviewed_items"]:
                if r.ref_url in existing_urls:
                    # 替换旧结果
                    all_reviewed = [x for x in all_reviewed if x.ref_url != r.ref_url]
                all_reviewed.append(r)
                existing_urls.add(r.ref_url)

            all_costs.extend(retry_result["cost_records"])
            all_analyzed.extend(retry_result["analyzed_items"])

        logger.info("pipeline.graph_done", extra={
            "analyzed": len(all_analyzed),
            "reviewed": len(all_reviewed),
            "llm_calls": len(all_costs),
        })

        # ====== 图外：入库（需要 DB 连接） ======
        passed_count = 0
        retry_count = 0
        discarded_count = 0

        for reviewed in all_reviewed:
            raw = next((r for r in new_items if r.url == reviewed.ref_url), None)
            analyzed = next((a for a in all_analyzed if a.ref_url == reviewed.ref_url), None)
            if raw is None or analyzed is None:
                continue

            if reviewed.verdict == "approved":
                article_id = await save_article(_db, raw, analyzed, reviewed, 0, 0)
                if article_id:
                    await save_tags(_db, article_id, analyzed.tags)
                passed_count += 1
            elif reviewed.verdict == "retry":
                if analyzed.retry_count >= 2:
                    discarded_count += 1
                else:
                    await save_article(_db, raw, analyzed, reviewed, 0, 0)
                    retry_count += 1
            else:  # discarded
                discarded_count += 1

        for record in all_costs:
            await save_cost_log(_db, run_id, record)

        summary = json.dumps({
            "collected": {"total": len(raw_items), "new": len(new_items)},
            "analyzed": len(all_analyzed),
            "approved": passed_count,
            "retry": retry_count,
            "discarded": discarded_count,
            "errors": error_log,
        })
        await end_pipeline_run(_db, run_id, "completed", summary)
        logger.info("pipeline.done", extra={
            "run_id": run_id,
            "passed": passed_count,
            "retry": retry_count,
            "discarded": discarded_count,
            "cost": sum(c.cost for c in all_costs),
        })

        # ====== 图外：备份 + 站点构建 ======
        await backup_database(_db, str(BACKUP_DIR))
        if _builder:
            await _builder.schedule()

    except Exception as e:
        logger.error("pipeline.failed", extra={"error": str(e)})
        await end_pipeline_run(_db, run_id, "failed", str(e)) if _db else None
    finally:
        _running = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _registry, _db, _scheduler, _builder, _graph

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    migrations_dir = BASE_DIR / "src" / "db" / "migrations"
    _db = Database(DB_PATH, migrations_dir)
    await _db.initialize()

    llm_cfg = load_llm_config(CONFIG_DIR / "llm.yaml")
    agents_cfg = load_agents_config(CONFIG_DIR / "agents.yaml")
    _registry = LLMRegistry(llm_cfg, agents_cfg)

    set_db(_db)
    set_run_pipeline(run_pipeline)

    _graph = build_pipeline(_registry)

    template_dir = BASE_DIR / "src" / "site" / "templates"
    site_builder = SiteBuilder(_db, OUTPUT_DIR, template_dir)
    _builder = DebouncedBuilder(site_builder, debounce_seconds=300)

    # APScheduler
    sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")
    _scheduler = AsyncIOScheduler()
    for source in sources_cfg.sources:
        if not source.enabled:
            continue
        parts = source.cron.strip().split()
        # 用 functools.partial 绑定 source_filter，每个 cron job 只采集自己的源
        from functools import partial
        _scheduler.add_job(
            partial(run_pipeline, source_filter=source.id),
            "cron",
            minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4],
            id=f"collect-{source.id}",
        )
    _scheduler.start()

    yield

    if _scheduler:
        _scheduler.shutdown()
    if _db:
        await _db.close()


def create_app() -> FastAPI:
    from .api.routes import http_exception_handler, general_exception_handler

    app = FastAPI(lifespan=lifespan, title="AI Knowledge Base")
    app.include_router(router)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
```

```bash
git add src/main.py
git commit -m "feat: 主入口 — FastAPI + APScheduler + LangGraph 图驱动 pipeline + 结构化日志 + 备份 + 站点构建"
```

---

### Task 17: 部署配置（Docker + Caddy + CI/CD）

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `Caddyfile`
- Create: `.github/workflows/deploy.yml`

```dockerfile
# Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY config/ ./config/    # compose volume mount 会覆盖，仅作为非 compose 场景的 fallback
COPY prompts/ ./prompts/
COPY src/ ./src/
RUN mkdir -p /app/data /app/output && apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
services:
  pipeline:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./output:/app/output
      - ./config:/app/config:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      retries: 3
      start_period: 10s

  web:
    image: caddy:alpine
    ports:
      - "80:80"
      - "443:443"
    environment:
      - KB_DOMAIN=${KB_DOMAIN:-kb.your-domain.com}
    volumes:
      - ./output:/srv:ro
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
    restart: unless-stopped
    depends_on:
      - pipeline
```

```
# Caddyfile
# 注意：部署前将 your-domain.com 替换为实际域名，
# 或设置环境变量 KB_DOMAIN=kb.example.com 通过 docker-compose.yml 传入
{$KB_DOMAIN:kb.your-domain.com} {
    root * /srv
    file_server
    header Cache-Control "public, max-age=3600"
    handle /api/* {
        reverse_proxy pipeline:8000
    }
    encode gzip
}
```

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run pytest -m "not integration and not e2e"

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/ai-knowledge-base
            git pull origin main
            docker compose up -d --build
```

```bash
git add Dockerfile docker-compose.yml Caddyfile .github/workflows/deploy.yml
git commit -m "feat: 部署配置 — Docker Compose + Caddy + GitHub Actions CI/CD"
```

---

### Task 18: Prompt 回归测试 + E2E 清理

**Files:**
- Create: `tests/fixtures/seed_articles.json`
- Create: `tests/test_prompt_regression.py`
- Update: `tests/test_pipeline.py`

- [ ] **Step 1: 创建种子数据**

```json
// tests/fixtures/seed_articles.json
[
  {"url": "https://github.com/test/llm-framework", "title": "LLM Framework", "description": "A framework for LLM applications", "source": "github", "source_detail": "test/llm-framework"},
  {"url": "https://example.com/ai-article", "title": "The Future of AI Agents", "description": "Exploring agent architectures", "source": "rss", "source_detail": "https://example.com/feed"}
]
```

- [ ] **Step 2: Prompt 回归测试**

```python
# tests/test_prompt_regression.py
import json, pytest
from pathlib import Path
from src.graph.analyzers.base import parse_and_validate
from src.graph.state import AnalyzedItem

PROMPT_FILES = ["github_analyzer.md", "rss_analyzer.md", "feishu_analyzer.md", "arxiv_analyzer.md"]

@pytest.mark.parametrize("prompt_file", PROMPT_FILES)
def test_prompt_has_schema_instruction(prompt_file):
    content = (Path(__file__).parent.parent / "prompts" / prompt_file).read_text()
    assert "json" in content.lower()
    assert "summary" in content.lower()
    assert "tags" in content.lower()

@pytest.mark.parametrize("seed", json.loads(Path(__file__).parent / "fixtures" / "seed_articles.json"))
def test_seed_article_valid_structure(seed):
    assert "url" in seed
    assert "title" in seed
    assert "source" in seed

def test_parse_and_validate_all_seeds():
    """验证 parse_and_validate 函数对各种 LLM 输出格式的容错能力"""
    # 正常 JSON
    result = parse_and_validate('{"title": "T", "summary": "S", "tags": ["AI"], "language": "zh"}')
    assert isinstance(result, AnalyzedItem)
    # markdown 包裹
    result2 = parse_and_validate('```json\n{"title": "T2", "summary": "S2", "tags": ["LLM"], "language": "en"}\n```')
    assert isinstance(result2, AnalyzedItem)
    # 缺少字段抛异常
    with pytest.raises(Exception):
        parse_and_validate('{"title": "T"}')  # 缺少 summary
```

- [ ] **Step 3: Commit**

```bash
uv run pytest -m "not integration and not e2e" -v
git add tests/
git commit -m "feat: Prompt 回归测试 + 种子数据"
```

---

## 实现顺序

严格按 Task 1→18 顺序执行：

| Phase | Tasks | 内容 |
|-------|-------|------|
| 1. 基础设施 | 1-3 | 脚手架 + 配置加载 + DB 迁移 |
| 2. LLM 内核 | 4-6 | 预算 + 健康 + LLMRegistry |
| 3. 工作流 | 7-12 | State + Collector + Router + Analyzer + Aggregator + Reviewer + Pipeline |
| 4. 存储/API | 13-14 | DB 操作 + FastAPI 端点 |
| 5. 站点生成 | 15 | SiteBuilder + 去抖 + 原子 rename |
| 6. 入口/部署 | 16-18 | main.py + Docker + CI/CD + 测试 |
