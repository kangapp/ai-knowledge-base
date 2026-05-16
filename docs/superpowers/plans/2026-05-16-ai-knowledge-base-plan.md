# AI 个人知识库 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建个人 AI 知识库系统，定时采集 → LangGraph 分析 → 静态站点展示，Docker Compose 部署

**Architecture:** Python 全栈单进程应用，FastAPI 承载 API + 调度 + 静态渲染，LangGraph 编排采集分析流水线，SQLite 存储，Caddy 前置 serve 静态文件 + HTTPS

**Tech Stack:** Python 3.12+ / uv / LangGraph + langgraph-checkpoint-sqlite / openai SDK / FastAPI + Jinja2 / SQLite (aiosqlite) + FTS5 / httpx + feedparser / APScheduler / Docker Compose + Caddy

**Spec:** docs/superpowers/specs/2026-05-16-ai-knowledge-base-design.md

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
│   ├── router.md
│   ├── github_analyzer.md
│   ├── rss_analyzer.md
│   ├── feishu_analyzer.md
│   ├── arxiv_analyzer.md
│   └── reviewer.md
├── src/
│   ├── main.py                          # FastAPI + APScheduler 入口
│   ├── core/
│   │   ├── config.py                    # yaml 配置加载 + pydantic 模型
│   │   ├── database.py                  # SQLite 初始化 + 连接
│   │   ├── llm_client.py               # LLMRegistry：provider → AsyncOpenAI
│   │   ├── budget.py                    # BudgetTracker：花费累计 + 熔断判断
│   │   └── health.py                    # HealthTracker：provider 健康状态
│   ├── graph/
│   │   ├── state.py                     # PipelineState (pydantic)
│   │   ├── pipeline.py                  # StateGraph 组装 + 编译
│   │   ├── collector.py                 # Collector 采集节点
│   │   ├── router.py                    # Router 路由节点
│   │   ├── aggregator.py               # Aggregator 汇总节点
│   │   ├── reviewer.py                  # Reviewer 审核节点
│   │   └── analyzers/
│   │       ├── __init__.py
│   │       ├── base.py                  # 分析器抽象基类
│   │       ├── github.py
│   │       ├── rss.py
│   │       ├── feishu.py
│   │       └── arxiv.py
│   ├── db/
│   │   └── operations.py               # articles/tags/cost CRUD
│   ├── api/
│   │   └── routes.py                    # /api/* FastAPI 路由
│   └── site/
│       ├── builder.py                   # Jinja2 渲染引擎 + data.json/stats.json
│       └── templates/
│           ├── base.html
│           ├── index.html
│           ├── article.html
│           └── dashboard.html
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_database.py
    ├── test_llm_client.py
    ├── test_budget.py
    ├── test_health.py
    ├── test_collector.py
    ├── test_router.py
    ├── test_analyzer.py
    ├── test_reviewer.py
    └── test_pipeline.py
```

---

### Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore` (已存在)
- Create: `config/llm.yaml`, `config/sources.yaml`, `config/agents.yaml`
- Create: `prompts/router.md`, `prompts/github_analyzer.md`, `prompts/rss_analyzer.md`, `prompts/feishu_analyzer.md`, `prompts/arxiv_analyzer.md`, `prompts/reviewer.md`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "ai-knowledge-base"
version = "0.1.0"
description = "个人 AI 知识库 — 自动化采集、分析、展示"
requires-python = ">=3.12"
dependencies = [
    "openai>=1.0",
    "langgraph>=0.2",
    "langgraph-checkpoint-sqlite>=2.0",
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

- [ ] **Step 2: 安装依赖并锁定版本**

```bash
cd /Users/liufukang/Workplace/ai-knowledge-base
uv sync
```

- [ ] **Step 3: 创建 .env.example**

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

# Langfuse
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

- [ ] **Step 4: 创建 config/llm.yaml**

```yaml
providers:
  deepseek:
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_API_KEY}
    models:
      - id: deepseek-chat
        price_per_1k_in: 0.000014
        price_per_1k_out: 0.000028
        max_tokens: 8192
  minimax:
    base_url: https://api.minimax.chat/v1
    api_key: ${MINIMAX_API_KEY}
    models:
      - id: abab6.5s-chat
        price_per_1k_in: 0.001
        price_per_1k_out: 0.001
        max_tokens: 8192
  openai:
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
    models:
      - id: gpt-4o-mini
        price_per_1k_in: 0.000015
        price_per_1k_out: 0.00006
        max_tokens: 4096
```

- [ ] **Step 5: 创建 config/sources.yaml**

```yaml
sources:
  - name: github-trending
    enabled: true
    priority: 1
    schedule: "0 9 * * *"
    max_items: 20
    config:
      query: "AI OR LLM OR agent OR MCP OR RAG"
      sort: stars
      min_stars: 50
      lookback_days: 7
  - name: rss
    enabled: true
    priority: 1
    schedule: "0 */6 * * *"
    max_items: 15
    config:
      feeds:
        - url: https://www.anthropic.com/blog/feed.xml
          name: Anthropic Blog
        - url: https://openai.com/blog/rss.xml
          name: OpenAI Blog
        - url: https://blog.langchain.dev/feed
          name: LangChain Blog
      filter_keywords: ["AI", "LLM", "Agent", "model", "RAG", "GPT", "Claude"]
  - name: feishu
    enabled: true
    priority: 2
    schedule: "0 10 * * *"
    max_items: 10
    config:
      space_ids: []
  - name: arxiv
    enabled: false
    priority: 2
    schedule: "0 11 * * 1"
    max_items: 10
    config:
      categories: ["cs.AI", "cs.CL", "cs.LG"]
      keywords: ["LLM", "agent", "RAG", "transformer"]
      lookback_days: 7
```

- [ ] **Step 6: 创建 config/agents.yaml**

```yaml
agents:
  router:
    model:
      primary: { provider: deepseek, model: deepseek-chat }
      fallback: []
    params: { temperature: 0.0, max_tokens: 256 }
  github_analyzer:
    model:
      primary: { provider: deepseek, model: deepseek-chat }
      fallback: [{ provider: openai, model: gpt-4o-mini }]
    params: { temperature: 0.3, max_tokens: 2048 }
  rss_analyzer:
    model:
      primary: { provider: deepseek, model: deepseek-chat }
      fallback: []
    params: { temperature: 0.3, max_tokens: 2048 }
  feishu_analyzer:
    model:
      primary: { provider: minimax, model: abab6.5s-chat }
      fallback: [{ provider: deepseek, model: deepseek-chat }]
    params: { temperature: 0.3, max_tokens: 2048 }
  arxiv_analyzer:
    model:
      primary: { provider: deepseek, model: deepseek-chat }
      fallback: [{ provider: openai, model: gpt-4o-mini }]
    params: { temperature: 0.3, max_tokens: 4096 }
  reviewer:
    model:
      primary: { provider: deepseek, model: deepseek-chat }
      fallback: []
    params: { temperature: 0.0, max_tokens: 512 }

budget:
  global:
    daily_limit: 2.0
    monthly_limit: 30.0
    soft_threshold: 0.8
    hard_threshold: 1.0
```

- [ ] **Step 7: 创建所有 prompts/*.md 占位文件**

每个文件包含一行简要说明，后续 Task 中替换为实际 Prompt：

`prompts/router.md`:
```
你是数据分类器。根据输入数据的来源和内容判断其类型……
```

`prompts/github_analyzer.md`:
```
分析以下 GitHub 仓库，提取核心功能、技术栈、适用场景……
```

`prompts/rss_analyzer.md`:
```
分析以下技术文章，提取核心观点、关键技术细节、与 AI/LLM 的关联……
```

`prompts/feishu_analyzer.md`:
```
分析以下飞书文档内容，提取关键信息并进行结构化整理……
```

`prompts/arxiv_analyzer.md`:
```
分析以下学术论文摘要，提取研究问题、方法、贡献点……
```

`prompts/reviewer.md`:
```
审核以下分析结果，评估相关性(0-100)和质量。完全无关(<50)直接丢弃，质量不足(50-79)需重分析……
```

- [ ] **Step 8: 创建目录结构**

```bash
mkdir -p src/core src/graph/analyzers src/db src/api src/site/templates tests config prompts
touch src/__init__.py src/core/__init__.py src/graph/__init__.py src/graph/analyzers/__init__.py src/db/__init__.py src/api/__init__.py src/site/__init__.py
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock .env.example config/ prompts/ src/ .gitignore
git commit -m "feat: 初始化项目脚手架和配置文件"
```

---

### Task 2: 配置加载模块

**Files:**
- Create: `src/core/config.py`
- Create: `tests/test_config.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: 编写测试**

```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def project_root(tmp_path):
    """创建临时项目目录，包含最小配置文件"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    (config_dir / "llm.yaml").write_text("""
providers:
  deepseek:
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_API_KEY}
    models:
      - id: deepseek-chat
        price_per_1k_in: 0.000014
        price_per_1k_out: 0.000028
        max_tokens: 8192
""")

    (config_dir / "sources.yaml").write_text("""
sources:
  - name: github-trending
    enabled: true
    priority: 1
    schedule: "0 9 * * *"
    max_items: 20
    config:
      query: "AI OR LLM"
      sort: stars
""")

    (config_dir / "agents.yaml").write_text("""
agents:
  router:
    model:
      primary: {provider: deepseek, model: deepseek-chat}
      fallback: []
    params: {temperature: 0.0, max_tokens: 256}
budget:
  global:
    daily_limit: 2.0
    monthly_limit: 30.0
    soft_threshold: 0.8
    hard_threshold: 1.0
""")

    (prompts_dir / "router.md").write_text("router prompt")
    return tmp_path
```

```python
# tests/test_config.py
import os
from src.core.config import load_llm_config, load_sources_config, load_agents_config

def test_load_llm_config(project_root):
    cfg = load_llm_config(project_root / "config" / "llm.yaml")
    assert "deepseek" in cfg.providers
    assert cfg.providers["deepseek"].base_url == "https://api.deepseek.com/v1"
    assert cfg.providers["deepseek"].models[0].id == "deepseek-chat"

def test_load_sources_config(project_root):
    cfg = load_sources_config(project_root / "config" / "sources.yaml")
    assert len(cfg.sources) == 1
    assert cfg.sources[0].name == "github-trending"
    assert cfg.sources[0].enabled is True

def test_load_agents_config(project_root):
    cfg = load_agents_config(project_root / "config" / "agents.yaml")
    assert "router" in cfg.agents
    assert cfg.agents["router"].model.primary.provider == "deepseek"
    assert cfg.budget.global_config.daily_limit == 2.0

def test_api_key_interpolation(project_root, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    cfg = load_llm_config(project_root / "config" / "llm.yaml")
    assert cfg.providers["deepseek"].api_key == "sk-test"
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
from typing import Optional

# ===== LLM Config =====

class ModelInfo(BaseModel):
    id: str
    price_per_1k_in: float
    price_per_1k_out: float
    max_tokens: int

class ProviderConfig(BaseModel):
    base_url: str
    api_key: str
    models: list[ModelInfo]

class LLMConfig(BaseModel):
    providers: dict[str, ProviderConfig]

# ===== Sources Config =====

class SourceConfig(BaseModel):
    name: str
    enabled: bool
    priority: int
    schedule: str
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

class BudgetGlobal(BaseModel):
    daily_limit: float
    monthly_limit: float
    soft_threshold: float = 0.8
    hard_threshold: float = 1.0

class BudgetConfig(BaseModel):
    global_config: BudgetGlobal

    class Config:
        fields = {"global_config": "global"}

class AgentsConfig(BaseModel):
    agents: dict[str, AgentConfig]
    budget: BudgetConfig


def _interpolate_env(value: str) -> str:
    """替换 ${VAR} 为环境变量值"""
    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, "")
    return re.sub(r'\$\{(\w+)\}', replacer, value)

def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        raw = f.read()
    raw = _interpolate_env(raw)
    return yaml.safe_load(raw)

def load_llm_config(path: Path) -> LLMConfig:
    data = _load_yaml(path)
    return LLMConfig(**data)

def load_sources_config(path: Path) -> SourcesConfig:
    data = _load_yaml(path)
    return SourcesConfig(**data)

def load_agents_config(path: Path) -> AgentsConfig:
    data = _load_yaml(path)
    return AgentsConfig(**data)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_config.py -v
# 预期: 4 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/core/config.py tests/
git commit -m "feat: 配置加载模块 — yaml + pydantic + 环境变量插值"
```

---

### Task 3: 数据库初始化和 Schema

**Files:**
- Create: `src/core/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_database.py
import pytest
from src.core.database import Database

@pytest.mark.asyncio
async def test_create_tables(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.initialize()

    # 检查表已创建
    tables = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = [t["name"] for t in tables]
    assert "articles" in table_names
    assert "tags" in table_names
    assert "article_tags" in table_names
    assert "pipeline_runs" in table_names
    assert "cost_logs" in table_names
    assert "provider_health" in table_names
    assert "circuit_events" in table_names

    # 检查 FTS5 虚拟表
    fts_tables = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='virtual'"
    )
    fts_names = [t["name"] for t in fts_tables]
    assert "articles_fts" in fts_names

@pytest.mark.asyncio
async def test_insert_article(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    await db.initialize()

    await db.execute(
        "INSERT INTO articles (id, title, url, source, collected_at) VALUES (?, ?, ?, ?, ?)",
        ("github:test/repo", "Test Repo", "https://github.com/test/repo", "github", "2026-05-16T10:00:00Z")
    )
    row = await db.fetch_one("SELECT * FROM articles WHERE id = ?", ("github:test/repo",))
    assert row["title"] == "Test Repo"
    assert row["status"] == "pending"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_database.py -v
# 预期: ModuleNotFoundError / ImportError
```

- [ ] **Step 3: 实现数据库模块**

```python
# src/core/database.py
import aiosqlite
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    url             TEXT NOT NULL,
    description     TEXT,
    summary         TEXT,
    source          TEXT NOT NULL,
    source_detail   TEXT,
    relevance_score INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',
    retry_count     INTEGER DEFAULT 0,
    collected_at    TEXT NOT NULL,
    published_at    TEXT,
    raw_metadata    TEXT,
    analysis_cost   REAL DEFAULT 0.0,
    analysis_tokens INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_collected ON articles(collected_at);
CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(relevance_score);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, summary, description, content='articles'
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    color TEXT
);

CREATE TABLE IF NOT EXISTS article_tags (
    article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
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
    circuit     TEXT NOT NULL DEFAULT 'closed'
);

CREATE TABLE IF NOT EXISTS circuit_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    provider   TEXT NOT NULL,
    event      TEXT NOT NULL,
    reason     TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

class Database:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def execute(self, sql: str, params: tuple = ()):
        return await self._conn.execute(sql, params)

    async def execute_many(self, sql: str, params_list: list[tuple]):
        return await self._conn.executemany(sql, params_list)

    async def fetch_one(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchone()

    async def fetch_all(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchall()

    async def commit(self):
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_database.py -v
# 预期: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/core/database.py tests/test_database.py
git commit -m "feat: 数据库初始化 — SQLite schema + FTS5 全文索引"
```

---

### Task 4: LLM 客户端注册表

**Files:**
- Create: `src/core/llm_client.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_llm_client.py
import pytest
from unittest.mock import AsyncMock, patch
from src.core.llm_client import LLMRegistry, ModelRef, AllProvidersUnavailable
from src.core.config import LLMConfig, AgentsConfig, ProviderConfig, ModelInfo, AgentConfig, ModelBinding, BudgetConfig, BudgetGlobal

@pytest.fixture
def llm_cfg():
    return LLMConfig(providers={
        "deepseek": ProviderConfig(
            base_url="https://api.deepseek.com/v1",
            api_key="sk-test",
            models=[ModelInfo(id="deepseek-chat", price_per_1k_in=0.000014, price_per_1k_out=0.000028, max_tokens=8192)]
        ),
        "openai": ProviderConfig(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            models=[ModelInfo(id="gpt-4o-mini", price_per_1k_in=0.000015, price_per_1k_out=0.00006, max_tokens=4096)]
        )
    })

@pytest.fixture
def agents_cfg():
    return AgentsConfig(
        agents={
            "router": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.0, "max_tokens": 256}
            ),
            "github_analyzer": AgentConfig(
                model=ModelBinding(
                    primary=ModelRef(provider="deepseek", model="deepseek-chat"),
                    fallback=[ModelRef(provider="openai", model="gpt-4o-mini")]
                ),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
        },
        budget=BudgetConfig(global_config=BudgetGlobal(daily_limit=2.0, monthly_limit=30.0))
    )

@pytest.mark.asyncio
async def test_get_client_primary(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    client, model_id, params = registry.get_client("router")
    assert model_id == "deepseek-chat"
    assert params["temperature"] == 0.0
    assert client is not None

@pytest.mark.asyncio
async def test_fallback_on_unhealthy(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    # 手动标记 primary 不健康
    registry.health.mark_unhealthy("deepseek", "test failure")
    client, model_id, params = registry.get_client("github_analyzer")
    # 应 fallback 到 openai
    assert model_id == "gpt-4o-mini"

@pytest.mark.asyncio
async def test_fallback_on_budget_exceeded(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    # 模拟 primary 预算超限
    registry.budget._daily_spend["deepseek"] = 999.0
    client, model_id, params = registry.get_client("github_analyzer")
    assert model_id == "gpt-4o-mini"

@pytest.mark.asyncio
async def test_all_unavailable_raises(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    registry.health.mark_unhealthy("deepseek", "down")
    registry.health.mark_unhealthy("openai", "down")
    with pytest.raises(AllProvidersUnavailable):
        registry.get_client("github_analyzer")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_llm_client.py -v
# 预期: ImportError
```

- [ ] **Step 3: 实现 LLMRegistry**

```python
# src/core/llm_client.py
import os
from dataclasses import dataclass
from openai import AsyncOpenAI
from .config import LLMConfig, AgentsConfig, ModelRef
from .budget import BudgetTracker
from .health import HealthTracker

class AllProvidersUnavailable(Exception):
    pass

@dataclass
class AgentModelConfig:
    client: AsyncOpenAI
    model_id: str
    params: dict

class LLMRegistry:
    """Provider → AsyncOpenAI 客户端映射。支持 fallback、健康检查、预算控制。"""

    def __init__(self, llm_cfg: LLMConfig, agents_cfg: AgentsConfig):
        self._clients: dict[str, AsyncOpenAI] = {}
        self._models: dict[str, list] = {}

        for name, p in llm_cfg.providers.items():
            self._clients[name] = AsyncOpenAI(
                base_url=p.base_url,
                api_key=p.api_key,
            )
            self._models[name] = p.models

        self._agents = agents_cfg.agents
        self.budget = BudgetTracker(agents_cfg.budget)
        self.health = HealthTracker()

    def get_client(self, agent_name: str) -> tuple[AsyncOpenAI, str, dict]:
        agent = self._agents[agent_name]
        chain = [agent.model.primary] + agent.model.fallback

        for ref in chain:
            if not self.health.is_healthy(ref.provider):
                continue
            if self.budget.is_exceeded(ref.provider):
                continue
            return (
                self._clients[ref.provider],
                ref.model,
                agent.params,
            )

        raise AllProvidersUnavailable(f"No available provider for agent '{agent_name}'")

    def get_provider_client(self, provider_name: str) -> AsyncOpenAI:
        return self._clients[provider_name]
```

- [ ] **Step 4: 运行测试确认通过**（依赖 Task 5 和 Task 6 的 BudgetTracker/HealthTracker）

```bash
uv run pytest tests/test_llm_client.py -v
# 此时 BudgetTracker 和 HealthTracker 尚未实现，测试暂 fail
```

- [ ] **Step 5: Commit**（推迟到 Task 6 完成后一起 commit 可工作状态）

---

### Task 5: 预算追踪与熔断器

**Files:**
- Create: `src/core/budget.py`
- Create: `tests/test_budget.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_budget.py
import pytest
from src.core.config import BudgetConfig, BudgetGlobal
from src.core.budget import BudgetTracker

@pytest.fixture
def budget():
    return BudgetTracker(BudgetConfig(global_config=BudgetGlobal(
        daily_limit=2.0, monthly_limit=30.0, soft_threshold=0.8, hard_threshold=1.0
    )))

def test_initial_state(budget):
    assert budget.is_exceeded("deepseek") is False
    assert budget.current_daily() == 0.0

def test_record_and_check(budget):
    budget.record("deepseek", "deepseek-chat", 100, 200)
    assert budget.current_daily() > 0.0

def test_soft_threshold(budget):
    # 模拟花费达到 80%
    budget._daily_spend["__global__"] = 1.6
    assert budget.is_soft_exceeded() is True
    assert budget.is_hard_exceeded() is False

def test_hard_threshold(budget):
    budget._daily_spend["__global__"] = 2.0
    assert budget.is_hard_exceeded() is True
    # 硬熔断时所有 provider 不可用
    assert budget.is_exceeded("deepseek") is True

def test_provider_level_budget(budget):
    # per-provider 独立限额
    budget._daily_spend["deepseek"] = 0.6
    budget._provider_limits["deepseek"] = 0.5
    assert budget.is_exceeded("deepseek") is True
    assert budget.is_exceeded("openai") is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_budget.py -v
# 预期: ImportError
```

- [ ] **Step 3: 实现 BudgetTracker**

```python
# src/core/budget.py
from .config import BudgetConfig

class BudgetTracker:
    def __init__(self, budget_cfg: BudgetConfig):
        self.global_cfg = budget_cfg.global_config
        self._daily_spend: dict[str, float] = {}      # provider_name → amount or "__global__"
        self._monthly_spend: dict[str, float] = {}
        self._provider_limits: dict[str, float] = {}

    def record(self, provider: str, model: str, tokens_in: int, tokens_out: int):
        """记录一次 LLM 调用花费，支出记录到 cost_logs 表由上层负责"""
        pass  # 实际花费由调用方计算后通过 add_cost 记录

    def add_cost(self, provider: str, cost: float):
        self._daily_spend["__global__"] = self._daily_spend.get("__global__", 0) + cost
        self._daily_spend[provider] = self._daily_spend.get(provider, 0) + cost

    def current_daily(self) -> float:
        return self._daily_spend.get("__global__", 0.0)

    def is_exceeded(self, provider: str) -> bool:
        if self.is_hard_exceeded():
            return True
        limit = self._provider_limits.get(provider)
        if limit and self._daily_spend.get(provider, 0) >= limit:
            return True
        return False

    def is_soft_exceeded(self) -> bool:
        return self.current_daily() >= self.global_cfg.daily_limit * self.global_cfg.soft_threshold

    def is_hard_exceeded(self) -> bool:
        return self.current_daily() >= self.global_cfg.daily_limit * self.global_cfg.hard_threshold
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_budget.py -v
# 预期: 5 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/core/budget.py tests/test_budget.py
git commit -m "feat: 预算追踪 — 全局/Provider 级别花费控制 + 软硬熔断"
```

---

### Task 6: Provider 健康追踪

**Files:**
- Create: `src/core/health.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_health.py
from src.core.health import HealthTracker

def test_initial_healthy():
    ht = HealthTracker()
    assert ht.is_healthy("deepseek") is True
    assert ht.get_status("deepseek")["status"] == "healthy"

def test_mark_unhealthy():
    ht = HealthTracker()
    ht.mark_unhealthy("deepseek", "timeout")
    assert ht.is_healthy("deepseek") is False
    assert ht.get_status("deepseek")["status"] == "unhealthy"

def test_record_success_resets_error_count():
    ht = HealthTracker()
    ht._state["deepseek"]["error_count"] = 2
    ht.record_success("deepseek", 150)
    assert ht._state["deepseek"]["error_count"] == 0

def test_consecutive_failures_trigger_circuit_open():
    ht = HealthTracker()
    ht.record_failure("deepseek", "500 error")  # 1
    ht.record_failure("deepseek", "500 error")  # 2
    assert ht._state["deepseek"]["error_count"] == 2
    assert ht._state["deepseek"]["circuit"] == "closed"
    ht.record_failure("deepseek", "timeout")    # 3 → open
    assert ht._state["deepseek"]["circuit"] == "open"
    assert not ht.is_healthy("deepseek")

def test_half_open_trial():
    ht = HealthTracker()
    ht._state["deepseek"]["circuit"] = "open"
    # 不应允许调用
    assert not ht.is_healthy("deepseek")
    # 手动设为 half_open（模拟冷却时间到）
    ht._state["deepseek"]["circuit"] = "half_open"
    assert ht.is_healthy("deepseek")  # half_open 允许试探
    # 试探成功
    ht.record_success("deepseek", 100)
    assert ht._state["deepseek"]["circuit"] == "closed"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_health.py -v
# 预期: ImportError
```

- [ ] **Step 3: 实现 HealthTracker**

```python
# src/core/health.py
import time

class HealthTracker:
    def __init__(self):
        self._state: dict[str, dict] = {}
        self._consecutive_failures_to_open = 3

    def _ensure_provider(self, provider: str):
        if provider not in self._state:
            self._state[provider] = {
                "status": "healthy",
                "error_count": 0,
                "last_error": None,
                "latency_ms": None,
                "circuit": "closed",
                "last_check": None,
            }

    def is_healthy(self, provider: str) -> bool:
        self._ensure_provider(provider)
        s = self._state[provider]
        if s["circuit"] == "open":
            return False
        return s["status"] == "healthy"

    def get_status(self, provider: str) -> dict:
        self._ensure_provider(provider)
        return dict(self._state[provider])

    def mark_unhealthy(self, provider: str, reason: str):
        self._ensure_provider(provider)
        self._state[provider]["status"] = "unhealthy"
        self._state[provider]["last_error"] = reason

    def record_success(self, provider: str, latency_ms: int):
        self._ensure_provider(provider)
        s = self._state[provider]
        s["error_count"] = 0
        s["latency_ms"] = latency_ms
        s["status"] = "healthy"
        s["last_check"] = time.time()
        if s["circuit"] == "half_open":
            s["circuit"] = "closed"

    def record_failure(self, provider: str, error: str):
        self._ensure_provider(provider)
        s = self._state[provider]
        s["error_count"] += 1
        s["last_error"] = error
        s["last_check"] = time.time()
        if s["error_count"] >= self._consecutive_failures_to_open:
            s["circuit"] = "open"
            s["status"] = "unhealthy"

    def try_half_open(self, provider: str):
        """冷却时间过后尝试半开"""
        self._ensure_provider(provider)
        if self._state[provider]["circuit"] == "open":
            self._state[provider]["circuit"] = "half_open"
            self._state[provider]["status"] = "healthy"
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_health.py -v
# 预期: 5 passed
```

- [ ] **Step 5: Verify Task 4 tests now pass**

```bash
uv run pytest tests/test_llm_client.py -v
# 预期: 4 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/core/health.py tests/test_health.py src/core/llm_client.py tests/test_llm_client.py
git commit -m "feat: Provider 健康追踪 + LLMRegistry 完整实现"
```

---

### Task 7: Pipeline State 定义

**Files:**
- Create: `src/graph/state.py`

- [ ] **Step 1: 实现 PipelineState**（此任务为纯数据模型，无需单独测试）

```python
# src/graph/state.py
from typing import Annotated, Any, Optional, TypedDict
from langgraph.graph.message import add_messages
from dataclasses import field
from pydantic import BaseModel
import operator


class RawItem(BaseModel):
    """单条原始采集数据"""
    id: str
    title: str
    url: str
    description: str = ""
    source: str  # github / rss / feishu / arxiv
    source_detail: str = ""
    published_at: str = ""
    raw_metadata: dict = {}
    collected_at: str = ""


class AnalyzedItem(BaseModel):
    """单条分析结果"""
    id: str
    title: str
    url: str
    description: str = ""
    summary: str
    source: str
    source_detail: str = ""
    relevance_score: int = 0
    tags: list[str] = []
    retry_count: int = 0
    raw_metadata: dict = {}


class CostRecord(BaseModel):
    """单次 LLM 调用花费"""
    agent: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost: float


class PipelineState(BaseModel):
    """LangGraph PipelineState — 工作流全局状态"""
    # 原始采集数据
    raw_items: list[RawItem] = []

    # 路由后分类数据
    routed_github: list[RawItem] = []
    routed_rss: list[RawItem] = []
    routed_feishu: list[RawItem] = []
    routed_arxiv: list[RawItem] = []

    # 分析结果
    analyzed_items: list[AnalyzedItem] = []

    # 审核结果
    passed_items: list[AnalyzedItem] = []
    retry_items: list[AnalyzedItem] = []
    discarded_items: list[AnalyzedItem] = []

    # 花费记录
    cost_records: list[CostRecord] = []

    # 运行元数据
    run_id: str = ""
    trigger: str = "cron"  # cron / manual
    error_message: str = ""

    # 预算状态
    budget_exceeded: bool = False
    budget_soft_exceeded: bool = False
```

- [ ] **Step 1: Commit**

```bash
git add src/graph/state.py
git commit -m "feat: PipelineState 定义 — 采集、分析、审核、成本状态模型"
```

---

### Task 8: 数据采集节点

**Files:**
- Create: `src/graph/collector.py`
- Create: `tests/test_collector.py`

- [ ] **Step 1: 编写测试**（Mock httpx 调用）

```python
# tests/test_collector.py
import json
import pytest
from unittest.mock import AsyncMock, patch
from src.graph.state import PipelineState
from src.graph.collector import collect_github, collect_rss, collector_node
from src.core.config import SourceConfig

@pytest.mark.asyncio
async def test_collect_github():
    """Mock GitHub API 返回"""
    mock_response = {
        "items": [
            {
                "full_name": "test/repo",
                "name": "repo",
                "description": "An AI agent framework",
                "html_url": "https://github.com/test/repo",
                "stargazers_count": 1500,
                "language": "Python",
                "topics": ["ai", "agent"],
                "pushed_at": "2026-05-15T10:00:00Z"
            }
        ]
    }

    source = SourceConfig(
        name="github-trending", enabled=True, priority=1,
        schedule="0 9 * * *", max_items=20,
        config={"query": "AI OR LLM", "sort": "stars", "min_stars": 50, "lookback_days": 7}
    )

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response,
            raise_for_status=lambda: None
        )
        items = await collect_github(source)

    assert len(items) == 1
    assert items[0].title == "repo"
    assert items[0].source == "github"
    assert items[0].raw_metadata["stars"] == 1500

@pytest.mark.asyncio
async def test_collector_node(mocker):
    """测试完整的 collector_node"""
    state = PipelineState()
    sources_cfg = type("SourcesConfig", (), {
        "sources": [
            SourceConfig(name="github-trending", enabled=True, priority=1,
                         schedule="0 9 * * *", max_items=20,
                         config={"query": "AI", "sort": "stars", "min_stars": 50, "lookback_days": 7})
        ]
    })()

    # mock GitHub collector
    mock_items = [
        type("RawItem", (), {
            "id": "test/repo", "title": "test", "url": "https://x.com",
            "source": "github", "source_detail": "", "description": "",
            "published_at": "", "raw_metadata": {}, "collected_at": ""
        })()
    ]

    mocker.patch("src.graph.collector.collect_github", return_value=mock_items)

    result = await collector_node(state, sources_cfg)
    assert len(result["raw_items"]) == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_collector.py -v
# 预期: ImportError
```

- [ ] **Step 3: 实现 Collector**

```python
# src/graph/collector.py
import json
from datetime import datetime, timedelta, timezone
import httpx
import feedparser
from .state import PipelineState, RawItem
from ..core.config import SourceConfig, SourcesConfig


async def collect_github(source: SourceConfig) -> list[RawItem]:
    cfg = source.config
    since = (datetime.now(timezone.utc) - timedelta(days=cfg.get("lookback_days", 7))).strftime("%Y-%m-%d")
    url = "https://api.github.com/search/repositories"
    params = {
        "q": f'{cfg["query"]} created:>{since}',
        "sort": cfg.get("sort", "stars"),
        "order": "desc",
        "per_page": source.max_items,
    }
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token := __import__("os").environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    items = []
    now = datetime.now(timezone.utc).isoformat()
    for repo in data.get("items", []):
        stars = repo.get("stargazers_count", 0)
        min_stars = cfg.get("min_stars", 0)
        if stars < min_stars:
            continue
        items.append(RawItem(
            id=f"github:{repo['full_name']}",
            title=repo["name"],
            url=repo["html_url"],
            description=repo.get("description") or "",
            source="github",
            source_detail="GitHub Trending",
            published_at=repo.get("pushed_at", ""),
            raw_metadata={
                "stars": stars,
                "language": repo.get("language", ""),
                "topics": repo.get("topics", []),
            },
            collected_at=now,
        ))
    return items


async def collect_rss(source: SourceConfig) -> list[RawItem]:
    items = []
    now = datetime.now(timezone.utc).isoformat()
    keywords = source.config.get("filter_keywords", [])

    for feed_info in source.config.get("feeds", []):
        feed = feedparser.parse(feed_info["url"])
        for entry in feed.entries[:source.max_items]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            text = f"{title} {summary}".lower()

            if keywords:
                if not any(kw.lower() in text for kw in keywords):
                    continue

            items.append(RawItem(
                id=f"rss:{entry.get('id', entry.get('link', ''))}",
                title=title,
                url=entry.get("link", ""),
                description=summary[:500] if summary else "",
                source="rss",
                source_detail=feed_info.get("name", feed_info["url"]),
                published_at=entry.get("published", ""),
                raw_metadata={"feed": feed_info["url"]},
                collected_at=now,
            ))
    return items


async def collect_feishu(source: SourceConfig) -> list[RawItem]:
    """飞书采集器 — 一期返回空列表，后续实现飞书 API 集成"""
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

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "").strip()
            text = f"{title} {summary}".lower()
            keywords = cfg.get("keywords", [])
            if keywords and not any(kw.lower() in text for kw in keywords):
                continue

            items.append(RawItem(
                id=f"arxiv:{entry.get('id', '').split('/')[-1]}",
                title=title,
                url=entry.get("id", ""),
                description=summary[:500],
                source="arxiv",
                source_detail=cat,
                published_at=entry.get("published", ""),
                raw_metadata={"categories": [t.get("term", "") for t in entry.get("tags", [])]},
                collected_at=now,
            ))
    return items


COLLECTORS = {
    "github-trending": collect_github,
    "rss": collect_rss,
    "feishu": collect_feishu,
    "arxiv": collect_arxiv,
}


async def collector_node(state: PipelineState, sources_cfg: SourcesConfig) -> dict:
    """LangGraph 采集节点 — 并行采集所有启用的源"""
    all_items = []
    for source in sources_cfg.sources:
        if not source.enabled:
            continue
        collector_fn = COLLECTORS.get(source.name)
        if collector_fn is None:
            continue
        items = await collector_fn(source)
        all_items.extend(items)

    return {"raw_items": all_items}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_collector.py -v
# 预期: 2 passed (实际需 mock httpx)
```

- [ ] **Step 5: Commit**

```bash
git add src/graph/collector.py tests/test_collector.py
git commit -m "feat: 数据采集节点 — GitHub/RSS/飞书/arXiv 采集器"
```

---

### Task 9: Router 路由节点

**Files:**
- Create: `src/graph/router.py`
- Create: `tests/test_router.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_router.py
import pytest
from src.graph.state import PipelineState, RawItem
from src.graph.router import router_node

@pytest.mark.asyncio
async def test_router_classifies_by_source():
    state = PipelineState(raw_items=[
        RawItem(id="a", title="a", url="x", source="github", collected_at=""),
        RawItem(id="b", title="b", url="y", source="rss", collected_at=""),
        RawItem(id="c", title="c", url="z", source="feishu", collected_at=""),
        RawItem(id="d", title="d", url="w", source="arxiv", collected_at=""),
    ])

    result = await router_node(state)
    assert len(result["routed_github"]) == 1
    assert len(result["routed_rss"]) == 1
    assert len(result["routed_feishu"]) == 1
    assert len(result["routed_arxiv"]) == 1

@pytest.mark.asyncio
async def test_router_empty_input():
    state = PipelineState()
    result = await router_node(state)
    assert result["routed_github"] == []
    assert result["routed_rss"] == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_router.py -v
# 预期: ImportError
```

- [ ] **Step 3: 实现 Router**

```python
# src/graph/router.py
from .state import PipelineState

ROUTE_MAP = {
    "github": "routed_github",
    "rss": "routed_rss",
    "feishu": "routed_feishu",
    "arxiv": "routed_arxiv",
}

async def router_node(state: PipelineState) -> dict:
    """按 source 字段规则分类；规则无法判断的留到对应列表（一期纯规则）"""
    result = {
        "routed_github": [],
        "routed_rss": [],
        "routed_feishu": [],
        "routed_arxiv": [],
    }
    for item in state.raw_items:
        key = ROUTE_MAP.get(item.source)
        if key:
            result[key].append(item)
        else:
            # 未知来源放 rss 列表兜底
            result["routed_rss"].append(item)
    return result
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_router.py -v
# 预期: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/graph/router.py tests/test_router.py
git commit -m "feat: Router 路由节点 — 按 source 规则分类"
```

---

### Task 10: Analyzer 分析 SubAgent 框架

**Files:**
- Create: `src/graph/analyzers/base.py`
- Create: `src/graph/analyzers/github.py`
- Create: `src/graph/analyzers/rss.py`
- Create: `src/graph/analyzers/feishu.py`
- Create: `src/graph/analyzers/arxiv.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_analyzer.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.graph.state import PipelineState, RawItem
from src.graph.analyzers.github import analyze_github
from src.core.config import LLMConfig, AgentsConfig, ProviderConfig, ModelInfo, AgentConfig, ModelBinding, ModelRef, BudgetConfig, BudgetGlobal
from src.core.llm_client import LLMRegistry

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
            "router": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.0, "max_tokens": 256}
            ),
            "reviewer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.0, "max_tokens": 512}
            ),
        },
        budget=BudgetConfig(global_config=BudgetGlobal(daily_limit=2.0, monthly_limit=30.0))
    )
    return LLMRegistry(llm_cfg, agents_cfg)

@pytest.mark.asyncio
async def test_analyze_github_mock_llm(registry):
    items = [
        RawItem(id="github:test/repo", title="AI Agent SDK",
                url="https://github.com/test/repo",
                description="An agent framework",
                source="github", source_detail="GitHub", collected_at="2026-05-16T10:00:00Z")
    ]

    # Mock AsyncOpenAI chat completion
    with patch.object(registry._clients["deepseek"].chat.completions, "create") as mock_create:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """```json
{"summary": "An agent framework for AI applications.", "relevance_score": 85, "tags": ["Agent", "Python"]}
```"""
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
        mock_create.return_value = mock_response

        result = await analyze_github(items, registry)

    assert len(result) == 1
    assert result[0].summary == "An agent framework for AI applications."
    assert result[0].relevance_score == 85
    assert "Agent" in result[0].tags
```

- [ ] **Step 2: 实现 Analyzer 框架**

```python
# src/graph/analyzers/base.py
import json
import re
from typing import Optional
from ...core.llm_client import LLMRegistry
from ..state import RawItem, AnalyzedItem, CostRecord


def parse_llm_json(content: str) -> dict:
    """从 LLM 输出中提取 JSON — 兼容 ```json 代码块包裹"""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if match:
        content = match.group(1)
    return json.loads(content)


def calc_cost(provider: str, model_id: str, tokens_in: int, tokens_out: int,
              registry: LLMRegistry) -> float:
    """根据 provider 注册的价格计算花费"""
    models = registry._models.get(provider, [])
    for m in models:
        if m.id == model_id:
            return (tokens_in * m.price_per_1k_in + tokens_out * m.price_per_1k_out) / 1000
    return 0.0


async def analyze_items(
    items: list[RawItem],
    agent_name: str,
    registry: LLMRegistry,
    prompt_template: str,
) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    """通用分析函数 — 逐条调用 LLM 分析"""
    results = []
    costs = []

    for item in items:
        client, model_id, params = registry.get_client(agent_name)

        prompt = prompt_template.format(
            title=item.title,
            description=item.description,
            url=item.url,
            metadata=str(item.raw_metadata),
        )

        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "你是一个技术分析助手。请只输出 JSON，不要输出其他内容。"},
                {"role": "user", "content": prompt},
            ],
            temperature=params.get("temperature", 0.3),
            max_tokens=params.get("max_tokens", 2048),
        )

        content = response.choices[0].message.content or "{}"
        analysis = parse_llm_json(content)

        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0
        cost = calc_cost(registry._get_provider_name_for_model(model_id), model_id, tokens_in, tokens_out, registry)

        registry.budget.add_cost(agent_name, cost)
        registry.health.record_success(agent_name, 0)

        results.append(AnalyzedItem(
            id=item.id,
            title=item.title,
            url=item.url,
            description=item.description,
            summary=analysis.get("summary", ""),
            source=item.source,
            source_detail=item.source_detail,
            relevance_score=analysis.get("relevance_score", 0),
            tags=analysis.get("tags", []),
            raw_metadata=item.raw_metadata,
        ))

        costs.append(CostRecord(
            agent=agent_name,
            provider=registry._get_provider_name_for_model(model_id),
            model=model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
        ))

    return results, costs
```

```python
# src/graph/analyzers/github.py
from .base import analyze_items
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

SYSTEM_PROMPT = """分析以下 GitHub 仓库，返回 JSON:
{
  "summary": "仓库的核心功能和适用场景（100-200字中文）",
  "relevance_score": 0-100（与AI/LLM/Agent的相关度）,
  "tags": ["标签1", "标签2"]
}"""

PROMPT_TEMPLATE = """仓库名: {title}
描述: {description}
URL: {url}
元数据: {metadata}

请分析并返回 JSON。"""

async def analyze_github(
    items: list[RawItem],
    registry: LLMRegistry,
) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    return await analyze_items(items, "github_analyzer", registry, PROMPT_TEMPLATE)
```

```python
# src/graph/analyzers/rss.py
from .base import analyze_items
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

PROMPT_TEMPLATE = """文章标题: {title}
内容摘要: {description}
链接: {url}
来源: {metadata}

请分析这篇文章与AI/LLM/Agent领域的相关性，返回 JSON:
{
  "summary": "文章核心观点（100-200字中文）",
  "relevance_score": 0-100,
  "tags": ["标签"]
}"""

async def analyze_rss(
    items: list[RawItem],
    registry: LLMRegistry,
) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    return await analyze_items(items, "rss_analyzer", registry, PROMPT_TEMPLATE)
```

```python
# src/graph/analyzers/feishu.py
from .base import analyze_items
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

PROMPT_TEMPLATE = """飞书文档标题: {title}
内容: {description}
元数据: {metadata}

请分析并返回 JSON:
{
  "summary": "文档关键内容（100-200字中文）",
  "relevance_score": 0-100,
  "tags": ["标签"]
}"""

async def analyze_feishu(
    items: list[RawItem],
    registry: LLMRegistry,
) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    return await analyze_items(items, "feishu_analyzer", registry, PROMPT_TEMPLATE)
```

```python
# src/graph/analyzers/arxiv.py
from .base import analyze_items
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

PROMPT_TEMPLATE = """论文标题: {title}
摘要: {description}
URL: {url}
分类: {metadata}

请分析这篇论文，返回 JSON:
{
  "summary": "研究问题、方法、贡献点（100-200字中文）",
  "relevance_score": 0-100,
  "tags": ["标签"]
}"""

async def analyze_arxiv(
    items: list[RawItem],
    registry: LLMRegistry,
) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    return await analyze_items(items, "arxiv_analyzer", registry, PROMPT_TEMPLATE)
```

- [ ] **Step 3: 运行测试确认通过**

```bash
uv run pytest tests/test_analyzer.py -v
# 预期: 1 passed
```

- [ ] **Step 4: Commit**

```bash
git add src/graph/analyzers/ tests/test_analyzer.py
git commit -m "feat: Analyzer SubAgent 框架 — 通用分析基类 + 4 个专属 Analyzer"
```

---

### Task 11: Aggregator 汇总节点

**Files:**
- Create: `src/graph/aggregator.py`

- [ ] **Step 1: 实现 Aggregator**（纯逻辑节点，无外部依赖，TDD 可选）

```python
# src/graph/aggregator.py
from .state import PipelineState, AnalyzedItem, CostRecord


async def aggregator_node(state: PipelineState) -> dict:
    """收集 4 个 Analyzer 的并行结果，汇总 cost"""
    all_analyzed = []
    all_costs = []

    # 从 state 中收集（LangGraph Send 的结果会被 state reducer 合并）
    all_costs = list(state.cost_records)

    return {
        "cost_records": all_costs,
        # analyzed_items 由 LangGraph Send 返回的结果自动累积
    }
```

- [ ] **Step 2: Commit**

```bash
git add src/graph/aggregator.py
git commit -m "feat: Aggregator 汇总节点"
```

---

### Task 12: Reviewer 审核节点

**Files:**
- Create: `src/graph/reviewer.py`
- Create: `tests/test_reviewer.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_reviewer.py
import pytest
from src.graph.state import PipelineState, AnalyzedItem, CostRecord
from src.graph.reviewer import reviewer_node

@pytest.mark.asyncio
async def test_reviewer_no_items():
    state = PipelineState(analyzed_items=[])
    result = await reviewer_node(state)
    assert result["passed_items"] == []
    assert result["discarded_items"] == []

@pytest.mark.asyncio
async def test_reviewer_pure_rule_scoring():
    """不调 LLM 时纯规则评分"""
    items = [
        AnalyzedItem(id="a", title="high", url="x", summary="high quality",
                      source="github", relevance_score=85, tags=["Agent"]),
        AnalyzedItem(id="b", title="low", url="y", summary="low quality",
                      source="rss", relevance_score=30, tags=[]),
        AnalyzedItem(id="c", title="mid", url="z", summary="mid",
                      source="rss", relevance_score=60, tags=[], retry_count=0),
        AnalyzedItem(id="d", title="mid2", url="w", summary="mid retried",
                      source="rss", relevance_score=60, tags=[], retry_count=2),
    ]
    state = PipelineState(analyzed_items=items)

    # 使用纯规则评分（不调 LLM）
    from src.graph.reviewer import _rule_based_review
    passed, retry, discarded = _rule_based_review(items)
    assert len(passed) == 1      # score 85
    assert len(retry) == 1       # score 60, retry_count 0
    assert len(discarded) == 2   # score 30 + score 60 but retry_count >= 2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_reviewer.py -v
# 预期: ImportError
```

- [ ] **Step 3: 实现 Reviewer**

```python
# src/graph/reviewer.py
from .state import PipelineState, AnalyzedItem, CostRecord

PASS_THRESHOLD = 80
RETRY_THRESHOLD = 50
MAX_RETRIES = 2


def _rule_based_review(items: list[AnalyzedItem]) -> tuple[list[AnalyzedItem], list[AnalyzedItem], list[AnalyzedItem]]:
    """纯规则评分 — 基于 Analyzer 给出的 relevance_score 进行分类"""
    passed = []
    retry = []
    discarded = []

    for item in items:
        if item.relevance_score >= PASS_THRESHOLD:
            passed.append(item)
        elif item.relevance_score >= RETRY_THRESHOLD and item.retry_count < MAX_RETRIES:
            item.retry_count += 1
            retry.append(item)
        else:
            # < 50 直接丢弃，或 retry 次数已耗尽
            discarded.append(item)

    return passed, retry, discarded


async def reviewer_node(state: PipelineState) -> dict:
    """审核节点 — 一期使用 Analyzer 自带评分做规则过滤，后续可加 LLM 审核"""
    passed, retry, discarded = _rule_based_review(state.analyzed_items)

    return {
        "passed_items": passed,
        "retry_items": retry,
        "discarded_items": discarded,
    }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_reviewer.py -v
# 预期: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/graph/reviewer.py tests/test_reviewer.py
git commit -m "feat: Reviewer 审核节点 — 规则评分 pass/retry/discard"
```

---

### Task 13: Pipeline 组装（LangGraph StateGraph）

**Files:**
- Create: `src/graph/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_pipeline.py
import pytest
from src.graph.pipeline import build_pipeline
from src.graph.state import PipelineState

@pytest.mark.asyncio
async def test_pipeline_graph_structure():
    """验证 pipeline 图结构正确"""
    pipeline = build_pipeline()
    graph = pipeline.compile()

    # 检查所有节点存在
    nodes = graph.get_graph().nodes
    node_names = {n for n in nodes}
    expected = {"collector", "router", "aggregator", "reviewer"}
    # 注意: analyzer 节点可能是动态命名的
    assert expected.issubset(node_names) or all(
        any(n in name for name in node_names) for n in expected
    )
```

- [ ] **Step 2: 实现 Pipeline 组装**

```python
# src/graph/pipeline.py
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.constants import Send
from .state import PipelineState
from .collector import collector_node
from .router import router_node
from .aggregator import aggregator_node
from .reviewer import reviewer_node
from .analyzers.github import analyze_github
from .analyzers.rss import analyze_rss
from .analyzers.feishu import analyze_feishu
from .analyzers.arxiv import analyze_arxiv


async def github_analyzer_node(state: PipelineState) -> dict:
    items = state.routed_github
    if not items:
        return {"analyzed_items": [], "cost_records": []}
    results, costs = await analyze_github(items, state.llm_registry)  # registry 需注入
    return {"analyzed_items": results, "cost_records": costs}


async def rss_analyzer_node(state: PipelineState) -> dict:
    items = state.routed_rss
    if not items:
        return {"analyzed_items": [], "cost_records": []}
    results, costs = await analyze_rss(items, state.llm_registry)
    return {"analyzed_items": results, "cost_records": costs}


async def feishu_analyzer_node(state: PipelineState) -> dict:
    items = state.routed_feishu
    if not items:
        return {"analyzed_items": [], "cost_records": []}
    results, costs = await analyze_feishu(items, state.llm_registry)
    return {"analyzed_items": results, "cost_records": costs}


async def arxiv_analyzer_node(state: PipelineState) -> dict:
    items = state.routed_arxiv
    if not items:
        return {"analyzed_items": [], "cost_records": []}
    results, costs = await analyze_arxiv(items, state.llm_registry)
    return {"analyzed_items": results, "cost_records": costs}


def continue_to_analyzers(state: PipelineState):
    """Router 后根据是否有数据决定发送到哪些 Analyzer"""
    sends = []
    if state.routed_github:
        sends.append(Send("github_analyzer", state))
    if state.routed_rss:
        sends.append(Send("rss_analyzer", state))
    if state.routed_feishu:
        sends.append(Send("feishu_analyzer", state))
    if state.routed_arxiv:
        sends.append(Send("arxiv_analyzer", state))
    if not sends:
        return []  # no items → skip to aggregator
    return sends


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("collector", collector_node)
    graph.add_node("router", router_node)
    graph.add_node("github_analyzer", github_analyzer_node)
    graph.add_node("rss_analyzer", rss_analyzer_node)
    graph.add_node("feishu_analyzer", feishu_analyzer_node)
    graph.add_node("arxiv_analyzer", arxiv_analyzer_node)
    graph.add_node("aggregator", aggregator_node)
    graph.add_node("reviewer", reviewer_node)

    graph.add_edge(START, "collector")
    graph.add_edge("collector", "router")
    graph.add_conditional_edges("router", continue_to_analyzers, {
        "github_analyzer": "github_analyzer",
        "rss_analyzer": "rss_analyzer",
        "feishu_analyzer": "feishu_analyzer",
        "arxiv_analyzer": "arxiv_analyzer",
    })
    graph.add_edge("github_analyzer", "aggregator")
    graph.add_edge("rss_analyzer", "aggregator")
    graph.add_edge("feishu_analyzer", "aggregator")
    graph.add_edge("arxiv_analyzer", "aggregator")
    graph.add_edge("aggregator", "reviewer")
    graph.add_edge("reviewer", END)

    return graph
```

- [ ] **Step 3: Commit**

```bash
git add src/graph/pipeline.py tests/test_pipeline.py
git commit -m "feat: LangGraph Pipeline 组装 — Collector→Router→Fan-out→Aggregator→Reviewer"
```

---

### Task 14: 数据库 CRUD 操作

**Files:**
- Create: `src/db/operations.py`

- [ ] **Step 1: 实现 DB 操作**

```python
# src/db/operations.py
import json
from ..core.database import Database
from ..graph.state import AnalyzedItem, CostRecord


async def save_article(db: Database, item: AnalyzedItem, cost: float = 0.0, tokens: int = 0):
    await db.execute("""
        INSERT OR REPLACE INTO articles
        (id, title, url, description, summary, source, source_detail,
         relevance_score, status, retry_count, collected_at, published_at,
         raw_metadata, analysis_cost, analysis_tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'passed', ?, ?, ?, ?, ?, ?)
    """, (
        item.id, item.title, item.url, item.description, item.summary,
        item.source, item.source_detail, item.relevance_score,
        item.retry_count, item.collected_at if hasattr(item, 'collected_at') else "",
        item.published_at if hasattr(item, 'published_at') else "",
        json.dumps(item.raw_metadata), cost, tokens,
    ))

    # 更新 FTS 索引
    await db.execute(
        "INSERT INTO articles_fts(articles_fts) VALUES('rebuild')"
    )


async def save_cost_log(db: Database, run_id: str, record: CostRecord):
    await db.execute("""
        INSERT INTO cost_logs (run_id, agent, provider, model, tokens_in, tokens_out, cost)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (run_id, record.agent, record.provider, record.model,
          record.tokens_in, record.tokens_out, record.cost))


async def save_tag(db: Database, tag_name: str, color: str = "#2563eb"):
    await db.execute(
        "INSERT OR IGNORE INTO tags (name, color) VALUES (?, ?)",
        (tag_name, color)
    )


async def link_article_tag(db: Database, article_id: str, tag_name: str):
    row = await db.fetch_one("SELECT id FROM tags WHERE name = ?", (tag_name,))
    if row:
        await db.execute(
            "INSERT OR IGNORE INTO article_tags (article_id, tag_id) VALUES (?, ?)",
            (article_id, row["id"])
        )


async def start_pipeline_run(db: Database, run_id: str, trigger: str = "cron"):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO pipeline_runs (id, started_at, trigger) VALUES (?, ?, ?)",
        (run_id, now, trigger)
    )


async def end_pipeline_run(db: Database, run_id: str, status: str, summary: str = ""):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE pipeline_runs SET ended_at = ?, status = ?, summary = ? WHERE id = ?",
        (now, status, summary, run_id)
    )


async def get_stats(db: Database, days: int = 30) -> dict:
    """获取仪表盘统计数据"""
    total = await db.fetch_one("SELECT COUNT(*) as count FROM articles WHERE status = 'passed'")
    period = await db.fetch_one(
        "SELECT COUNT(*) as count FROM articles WHERE status = 'passed' AND collected_at >= date('now', ?)",
        (f"-{days} days",)
    )
    source_dist = await db.fetch_all("""
        SELECT source, COUNT(*) as count FROM articles
        WHERE status = 'passed'
        GROUP BY source ORDER BY count DESC
    """)
    cost_total = await db.fetch_one(
        "SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs"
    )
    cost_period = await db.fetch_one(
        "SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs WHERE created_at >= date('now', ?)",
        (f"-{days} days",)
    )

    return {
        "total_articles": total["count"] if total else 0,
        "period_articles": period["count"] if period else 0,
        "source_distribution": [{"source": s["source"], "count": s["count"]} for s in source_dist],
        "total_cost": round(cost_total["total"] if cost_total else 0, 4),
        "period_cost": round(cost_period["total"] if cost_period else 0, 4),
    }


async def search_articles(db: Database, query: str = "", source: str = "",
                          tag: str = "", days: int = 30, limit: int = 20, offset: int = 0) -> list[dict]:
    """全文搜索文章"""
    if query:
        rows = await db.fetch_all("""
            SELECT a.* FROM articles a
            JOIN articles_fts fts ON a.id = fts.rowid
            WHERE articles_fts MATCH ?
            ORDER BY a.collected_at DESC
            LIMIT ? OFFSET ?
        """, (query, limit, offset))
    else:
        where = ["a.status = 'passed'"]
        params = []
        if source:
            where.append("a.source = ?")
            params.append(source)
        if days:
            where.append("a.collected_at >= date('now', ?)")
            params.append(f"-{days} days")
        params.extend([limit, offset])
        rows = await db.fetch_all(
            f"SELECT a.* FROM articles a WHERE {' AND '.join(where)} ORDER BY a.collected_at DESC LIMIT ? OFFSET ?",
            tuple(params)
        )

    results = []
    for row in rows:
        d = dict(row)
        # 读取标签
        tag_rows = await db.fetch_all("""
            SELECT t.name, t.color FROM tags t
            JOIN article_tags at ON t.id = at.tag_id
            WHERE at.article_id = ?
        """, (d["id"],))
        d["tags"] = [{"name": t["name"], "color": t["color"]} for t in tag_rows]
        results.append(d)
    return results
```

- [ ] **Step 2: Commit**

```bash
git add src/db/operations.py
git commit -m "feat: 数据库 CRUD 操作 — 文章/标签/费用/统计/搜索"
```

---

### Task 15: FastAPI 端点

**Files:**
- Create: `src/api/routes.py`

- [ ] **Step 1: 实现 API 路由**

```python
# src/api/routes.py
from fastapi import APIRouter, Query, HTTPException
from ..core.database import Database
from ..db import operations

router = APIRouter(prefix="/api")

_db: Database | None = None


def set_db(db: Database):
    global _db
    _db = db


@router.get("/articles")
async def list_articles(
    query: str = Query(default=""),
    source: str = Query(default=""),
    tag: str = Query(default=""),
    days: int = Query(default=30, ge=1, le=3650),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return await operations.search_articles(_db, query, source, tag, days, limit, offset)


@router.get("/articles/{article_id}")
async def get_article(article_id: str):
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    row = await _db.fetch_one("SELECT * FROM articles WHERE id = ?", (article_id,))
    if not row:
        raise HTTPException(404, "Article not found")
    return dict(row)


@router.get("/stats")
async def get_stats(days: int = Query(default=30, ge=1, le=3650)):
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return await operations.get_stats(_db, days)


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/health/models")
async def models_health():
    # 返回各 provider 健康状态（由 main.py 注入）
    return {"providers": {}}


@router.get("/cost/summary")
async def cost_summary(days: int = Query(default=30)):
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    rows = await _db.fetch_all(
        "SELECT provider, model, SUM(cost) as total_cost, SUM(tokens_in+ tokens_out) as total_tokens "
        "FROM cost_logs WHERE created_at >= date('now', ?) GROUP BY provider, model",
        (f"-{days} days",)
    )
    return [dict(r) for r in rows]


@router.post("/pipeline/run")
async def trigger_pipeline():
    # 手动触发 — 依赖注入后调用 pipeline
    return {"status": "queued", "message": "Pipeline triggered"}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/routes.py
git commit -m "feat: FastAPI 端点 — /api/articles, /api/stats, /api/health, /api/cost"
```

---

### Task 16: 静态站点生成器

**Files:**
- Create: `src/site/builder.py`
- Create: `src/site/templates/base.html`
- Create: `src/site/templates/index.html`
- Create: `src/site/templates/article.html`
- Create: `src/site/templates/dashboard.html`

- [ ] **Step 1: 实现 Site Builder**

```python
# src/site/builder.py
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from ..core.database import Database
from ..db.operations import search_articles, get_stats


class SiteBuilder:
    def __init__(self, db: Database, output_dir: Path, template_dir: Path):
        self.db = db
        self.output_dir = output_dir
        self.env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)

    async def build(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "articles").mkdir(exist_ok=True)
        (self.output_dir / "css").mkdir(exist_ok=True)
        (self.output_dir / "js").mkdir(exist_ok=True)

        # 获取全量数据
        all_articles = await search_articles(self.db, days=3650, limit=100000)
        stats = await get_stats(self.db, days=30)

        # 渲染首页（预渲染近 30 天 + 搜索/筛选 UI）
        recent = [a for a in all_articles if a.get("collected_at", "") >= ""][:100]
        index_html = self.env.get_template("index.html").render(
            articles=recent, stats=stats,
        )
        (self.output_dir / "index.html").write_text(index_html, encoding="utf-8")

        # 渲染文章详情页
        article_tpl = self.env.get_template("article.html")
        for article in all_articles:
            html = article_tpl.render(article=article)
            safe_id = article["id"].replace("/", "-").replace(":", "-")
            (self.output_dir / "articles" / f"{safe_id}.html").write_text(html, encoding="utf-8")

        # 渲染仪表盘
        dashboard_html = self.env.get_template("dashboard.html").render(stats=stats)
        (self.output_dir / "dashboard.html").write_text(dashboard_html, encoding="utf-8")

        # 导出 data.json（全量）和 stats.json
        json_articles = []
        for a in all_articles:
            json_articles.append({
                "id": a["id"], "title": a["title"], "url": a["url"],
                "description": a.get("description", ""), "summary": a.get("summary", ""),
                "source": a["source"], "source_detail": a.get("source_detail", ""),
                "relevance_score": a["relevance_score"], "tags": a.get("tags", []),
                "collected_at": a.get("collected_at", ""), "analysis_cost": a.get("analysis_cost", 0),
            })
        (self.output_dir / "data.json").write_text(json.dumps(json_articles, ensure_ascii=False), encoding="utf-8")
        (self.output_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")

        print(f"Site built: {len(all_articles)} articles, {len(json_articles)} in data.json")
```

- [ ] **Step 2: 创建 Jinja2 模板**（简化版，完整版到实现时展开）

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
    <header><!-- nav --></header>
    <main>{% block content %}{% endblock %}</main>
    <script src="/js/app.js"></script>
</body>
</html>
```

`src/site/templates/index.html`:
```html
{% extends "base.html" %}
{% block title %}AI Knowledge Base{% endblock %}
{% block content %}
<div class="stats-bar"><!-- KPI --></div>
<div class="filters">
    <!-- 日期快捷按钮 + 自定义日期 + 搜索 + 来源/标签下拉 -->
</div>
<div id="article-list">
    {% for article in articles %}
    <div class="article-card" data-score="{{ article.relevance_score }}">
        <h3><a href="/articles/{{ article.id|replace('/', '-')|replace(':', '-') }}.html">{{ article.title }}</a></h3>
        <p>{{ article.summary[:200] }}</p>
        <div class="meta">
            <span>{{ article.source }}</span>
            <span>{{ article.collected_at[:10] }}</span>
            <span class="score score-{{ 'high' if article.relevance_score >= 80 else 'mid' if article.relevance_score >= 50 else 'low' }}">{{ article.relevance_score }}分</span>
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}
```

`src/site/templates/article.html`:
```html
{% extends "base.html" %}
{% block title %}{{ article.title }}{% endblock %}
{% block content %}
<article>
    <div class="source">{{ article.source_detail or article.source }} · {{ article.collected_at[:10] }}</div>
    <h1>{{ article.title }}</h1>
    <a href="{{ article.url }}" target="_blank">查看原文</a>
    <div class="tags">{% for tag in article.tags %}<span class="tag">{{ tag.name }}</span>{% endfor %}</div>
    <div class="summary">{{ article.summary }}</div>
    <div class="meta-footer">采集时间: {{ article.collected_at }} · 评分: {{ article.relevance_score }} · 花费: ${{ article.analysis_cost }}</div>
</article>
{% endblock %}
```

`src/site/templates/dashboard.html`: KPI 卡片 + 来源分布柱状图 + 每日花费趋势（内联 SVG）

- [ ] **Step 3: Commit**

```bash
git add src/site/
git commit -m "feat: 静态站点生成器 — Jinja2 模板 + data.json/stats.json 导出"
```

---

### Task 17: 主入口（FastAPI + APScheduler + Pipeline 集成）

**Files:**
- Create: `src/main.py`
- Modify: `src/graph/pipeline.py`（注入 registry）

- [ ] **Step 1: 实现 main.py**

```python
# src/main.py
import os
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi.staticfiles import StaticFiles

from .core.config import load_llm_config, load_sources_config, load_agents_config
from .core.database import Database
from .core.llm_client import LLMRegistry
from .graph.pipeline import build_pipeline
from .graph.state import PipelineState
from .api.routes import router, set_db
from .db.operations import start_pipeline_run, end_pipeline_run, save_article, save_cost_log, save_tag, link_article_tag
from .site.builder import SiteBuilder

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH = DATA_DIR / "kb.db"

_llm_registry: LLMRegistry | None = None
_db: Database | None = None
_scheduler: AsyncIOScheduler | None = None


async def run_pipeline(trigger: str = "cron"):
    global _llm_registry, _db

    if _llm_registry is None or _db is None:
        print("Pipeline not initialized")
        return

    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    await start_pipeline_run(_db, run_id, trigger)

    sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")

    pipeline = build_pipeline()
    compiled = pipeline.compile()

    initial_state = PipelineState(run_id=run_id, trigger=trigger)
    initial_state.llm_registry = _llm_registry  # 注入 registry

    try:
        result = await compiled.ainvoke(initial_state)

        # 入库 passed items
        for item in result.get("passed_items", []):
            await save_article(_db, item)
            for tag in item.tags:
                await save_tag(_db, tag)
                await link_article_tag(_db, item.id, tag)

        # 入库 cost logs
        for record in result.get("cost_records", []):
            await save_cost_log(_db, run_id, record)

        # 构建静态站点
        builder = SiteBuilder(_db, OUTPUT_DIR, BASE_DIR / "src" / "site" / "templates")
        await builder.build()

        await end_pipeline_run(_db, run_id, "completed",
            f"passed={len(result.get('passed_items', []))}, "
            f"retry={len(result.get('retry_items', []))}, "
            f"discarded={len(result.get('discarded_items', []))}"
        )
        print(f"Pipeline {run_id} completed successfully")

    except Exception as e:
        await end_pipeline_run(_db, run_id, "failed", str(e))
        print(f"Pipeline {run_id} failed: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _llm_registry, _db, _scheduler

    # 初始化
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    _db = Database(DB_PATH)
    await _db.initialize()

    llm_cfg = load_llm_config(CONFIG_DIR / "llm.yaml")
    agents_cfg = load_agents_config(CONFIG_DIR / "agents.yaml")
    _llm_registry = LLMRegistry(llm_cfg, agents_cfg)

    set_db(_db)

    # 定时调度
    sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")
    _scheduler = AsyncIOScheduler()
    for source in sources_cfg.sources:
        if not source.enabled:
            continue
        _scheduler.add_job(
            run_pipeline,
            "cron",
            **parse_cron(source.schedule),
            id=f"collect-{source.name}",
            name=f"Collect {source.name}",
        )
    _scheduler.start()

    yield

    # 清理
    if _scheduler:
        _scheduler.shutdown()
    if _db:
        await _db.close()


def parse_cron(expr: str) -> dict:
    """解析 cron 表达式为 APScheduler 参数"""
    parts = expr.strip().split()
    if len(parts) != 5:
        return {"minute": "0", "hour": "9"}  # 默认每天 9 点
    return {
        "minute": parts[0], "hour": parts[1],
        "day": parts[2], "month": parts[3],
        "day_of_week": parts[4],
    }


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="AI Knowledge Base")

    # API 路由
    app.include_router(router)

    # 静态站点（Caddy 前置时用不上，本地开发用）
    if OUTPUT_DIR.exists():
        app.mount("/", StaticFiles(directory=str(OUTPUT_DIR), html=True), name="static")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 2: Commit**

```bash
git add src/main.py
git commit -m "feat: 主入口 — FastAPI + APScheduler + Pipeline 集成"
```

---

### Task 18: 部署配置（Docker + Caddy + CI/CD）

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `Caddyfile`
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 安装依赖
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 复制代码和配置
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY src/ ./src/

# 创建数据目录
RUN mkdir -p /app/data /app/output

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "src.main"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
services:
  pipeline:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./output:/app/output
      - ./config:/app/config
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
    volumes:
      - ./output:/srv:ro
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
    restart: unless-stopped
    depends_on:
      - pipeline
```

- [ ] **Step 3: 创建 Caddyfile**

```
kb.your-domain.com {
    root * /srv
    file_server

    header Cache-Control "public, max-age=3600"

    handle /api/* {
        reverse_proxy pipeline:8000
    }

    encode gzip
}
```

- [ ] **Step 4: 创建 GitHub Actions workflow**

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
      - run: uv run pytest
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}

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

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml Caddyfile .github/workflows/deploy.yml
git commit -m "feat: 部署配置 — Docker Compose + Caddy + GitHub Actions CI/CD"
```

---

### Task 19: 端到端集成验证 & 清理

**Files:**
- Modify: `src/graph/state.py`（确保 llm_registry 字段存在）
- Create: `tests/test_pipeline.py`（端到端测试）
- Create: `src/site/templates/` → 完善模板 CSS/JS

- [ ] **Step 1: 完善 PipelineState 以支持 registry 注入**

在 `src/graph/state.py` 中添加一个非 Pydantic 字段：

```python
# 在 PipelineState 类外，使用 TypedDict 模式传递 registry
# 或使用 Annotated state key
# 实际实现中，通过 configurable 传递 registry 到每个节点
```

- [ ] **Step 2: 本地完整链路验证**

```bash
# 启动服务
uv run python -m src.main

# 手动触发采集
curl -X POST http://localhost:8000/api/pipeline/run

# 检查 API
curl http://localhost:8000/api/health
curl http://localhost:8000/api/stats
curl "http://localhost:8000/api/articles?days=7"

# 检查静态站点输出
ls -la output/
```

- [ ] **Step 3: 运行全部测试**

```bash
uv run pytest -v
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: 端到端集成完成，全部测试通过"
```

---

## 实现顺序说明

按依赖关系组织，必须严格按 Task 1→19 顺序执行：
1-3 基础设施 → 4-6 LLM 内核 → 7 状态模型 → 8-12 工作流节点 → 13 组装 → 14-16 存储/API/前端 → 17 入口 → 18 部署 → 19 集成
