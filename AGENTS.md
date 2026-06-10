# AGENTS.md

**回复语言：始终使用中文**

## 1. 项目概述

### 产品定位
个人 AI 知识库系统 — 自动采集 AI/LLM/Agent 领域资讯，经 LLM 分析审核后生成静态网站展示。

### 要做
- 定时从 GitHub Trending、RSS、飞书知识文档、arXiv 采集数据（配置驱动，可增删源）
- LangGraph 工作流：图外 Collector（含 DB 查重）→ 100% 规则路由 → 4×Analyzer 并行 fan-out → 汇总 → 四维评分审核 → 图外入库；retry 循环在图外，最多 2 轮
- LLM 多模型管理（OpenAI 兼容协议），含 per-provider 独立熔断 + fallback + 全局预算熔断
- 纯静态网站展示（首页 Jinja2 预渲染首屏 + JS 交互 + 详情页 API + 仪表盘 Chart.js）
- 数据拆分：`data.json`（列表不含 summary）+ `stats.json`（KPI/趋势 <10KB）+ 详情走 `/api/articles/{id}`
- GitHub Actions CI/CD（分层测试） → Docker Compose 部署到 1C2G VPS

### 不做
- 多用户 / 登录 / 权限系统（纯个人使用）
- 实时推送 / 消息通知
- Anthropic 原生协议适配（先走 OpenAI 兼容协议）
- 数据库分库分表（SQLite 单文件，年数据量 ~20MB）
- 语义去重（跨源同一事件允许各自分析视角）
- 异地备份（一期不做，数据量小且可从采集重建）
- Alembic/SQLAlchemy 迁移（版本化纯 SQL 文件 + 30 行 Python）

### 技术栈

| 层 | 组件 | 说明 |
|----|------|------|
| 语言 | Python 3.12+ | |
| 依赖管理 | uv | uv.lock 锁版本 |
| 工作流 | langgraph | DAG 编排，短 pipeline 无需 checkpoint |
| LLM SDK | openai (AsyncOpenAI) | 统一 OpenAI 兼容协议 |
| 数据校验 | pydantic v2 | State + 配置 + API + LLM 输出校验 |
| HTTP 客户端 | httpx | 异步采集 + API 调用 |
| RSS 解析 | feedparser | |
| 数据库 | SQLite (aiosqlite) | FTS5 全文索引 |
| Web 框架 | FastAPI | API 端点 + 定时调度 |
| 模板引擎 | Jinja2 | 静态站点生成（预渲染首屏） |
| 调度 | APScheduler | 北京时间 cron 分组，进程内锁排队防重叠 |
| Web 服务 | Caddy | 静态文件 + 自动 HTTPS + 反向代理 |
| 部署 | Docker Compose | 2 容器 (pipeline + web) |
| CI/CD | GitHub Actions | 分层测试 → build → deploy |
| 可观测性 | langfuse + logging | LLM 追踪（Cloud 免费层）+ 结构化 stdout JSON lines |
| 前端图表 | Chart.js | CDN 加载，~70KB gzipped |

### 部署与运维预期
- **目标环境**：云 VPS 1C2G，Docker Compose 单机部署（仅一个应用）
- **月费用**：¥85-125（VPS ¥50-70 + 域名 ¥3-5 + LLM $3-8）
- **数据量**：日均 ~50 条，年约 1.8 万条，SQLite 文件 ~20MB/年
- **静态站**：`data.json` 全量 ~5MB/年（不含 summary，description 截断至 200 字符），3 年后 >25MB 切按月分片 + `manifest.json` 索引；FastAPI `/api/articles` 始终兜底
- **依赖服务**：GitHub API、飞书 API、各 LLM Provider（任一出问题影响当天采集）

## 2. 工程规范

### 2.1 行为指令 — Karpathy 4 大原则

本项目所有代码变更遵循以下原则，优先级从高到低：

**原则 1：简单优于聪明 (Simple > Clever)**

50 行能解决的问题不写成 200 行。不引入不必要的抽象层、设计模式、工具库。本项目是个人项目，一个开发者维护，过度工程化的代价高于收益。

- 能用一个函数解决就不拆三个类
- 能用标准库就不装第三方包
- 拒绝 speculative coding — 不要为"未来可能需要"写代码
- 反例：为了未来可能换数据库而加 ORM 抽象层 → SQLite 直接用 aiosqlite 裸 SQL

**原则 2：可读优于紧凑 (Readable > Compact)**

代码是给人读的，不给机器读。三年后的你打开这个仓库，应该能在 30 秒内理解一个模块在做什么。

- 变量名自解释：`approved_items` 优于 `ret`，`collect_and_dedup()` 优于 `do_step1()`
- 不要单行黑魔法：列表推导式超过 2 层嵌套就拆成 for 循环
- 相同逻辑只写一次：复制粘贴是技术债的第一个信号
- 反例：`items = [x for x in [y for y in z if y["s"]] if x["c"]]` → 拆成两个命名的中间变量

**原则 3：显式优于隐式 (Explicit > Implicit)**

调用方不看函数实现就能理解行为。副作用必须明确。

- 依赖显式传入：`analyze_items(items, client, prompt)` 而非在函数内部 `from core import get_client()`
- 函数签名说清楚输入输出：所有公共函数加类型注解
- 配置永不硬编码：cron 表达式、API base_url、文件名全部来自 config/*.yaml
- 反例：函数内 `os.environ.get("DEEPSEEK_KEY")` → 从 `config.py` 显式传入

**原则 4：专注做事 (Do One Thing Well)**

每个模块/函数/类只承载一个职责。如果你需要写"本模块既负责 X 也负责 Y"的注释，说明该拆了。

- Analyzer 只负责分析，不负责记账（记账是 TrackedClient 的事）
- Collector 只负责采集和去重，不负责评分
- `database.py` 只负责连接和迁移，不负责查询逻辑
- 反例：在 `collector.py` 里直接写 SQL INSERT → 入库是 db 层的事

### 2.2 编码规范

**命名**

| 对象 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | snake_case | `llm_client.py`, `pipeline_runs.py` |
| 函数/方法 | snake_case，动词开头 | `collect_items()`, `build_site()`, `get_client()` |
| 类/Pydantic 模型 | PascalCase | `RawItem`, `TrackedClient`, `LLMRegistry` |
| 常量 | UPPER_SNAKE | `MAX_RETRY_COUNT = 2`, `DEFAULT_TIMEOUT = 30` |
| 私有函数 | `_` 前缀 | `_parse_json_response()`, `_check_circuit()` |
| 布尔变量 | `is_` / `has_` / `should_` 前缀 | `is_running`, `has_fallback`, `should_skip` |

**导入顺序**

```
1. 标准库 (os, json, asyncio, ...)
2. 第三方库 (httpx, openai, langgraph, ...)
3. 本地模块 (from src.core import ...)
```

**错误处理**

只处理可恢复的错误。不可恢复的错误让它自然崩溃 — 不要 try/except 到处兜。

- **可恢复**：API 超时 → retry 或 fallback；LLM JSON 解析失败 → 容错 + 重试；单源采集故障 → 返回空列表，其余源继续
- **不可恢复**：配置文件缺失 → 直接抛异常崩溃（启动时 fail fast）；数据库连接丢失 → 崩溃（Docker 自动重启）；Schema 校验失败 → 抛出（数据有问题，不吞掉）
- **禁止**：裸 `except:` 不指定异常类型；`except Exception: pass` 吞掉异常不处理；catch 异常后只 print 不 raise 也不做恢复

**禁止项**

- 硬编码密钥、URL、路径 — 全部来自配置或 .env
- 裸 `except:` — 必须指定异常类型
- `except Exception: pass` 或 `logger.error()` 后继续执行 — 不确定能否恢复就让它崩
- 在函数内部 `os.environ.get()` 读环境变量 — 统一走 `config.py`
- 直接 `print()` 输出 — 走 `logging` 模块
- 在 Analyzer 内硬编码 Prompt 字符串 — 走 `load_prompt()` 从 `prompts/*.md` 读取
- 在 `src/graph/analyzers/` 里直接调用 `openai.AsyncOpenAI` — 走 `core.llm_client.LLMRegistry.get_client()`
- 在非 `db/` 模块里直接写 SQL — 走 `db/operations.py`
- 引入未写入 `pyproject.toml` 的依赖
- 用 `subprocess.run(["sqlite3", ...])` 备份 — 走 `aiosqlite` 的 `.backup()` API

### 2.3 接口规范

**路径约定**

```
GET    /api/health              # 健康检查
GET    /api/articles            # 文章列表（分页: ?page=1&page_size=20&source=github）
GET    /api/articles/{id}       # 文章详情
GET    /api/search              # 全文搜索 (?q=xxx&limit=20)
GET    /api/stats               # 仪表盘统计数据
GET    /api/cost/summary        # 花费统计 (?days=30)
GET    /api/pipeline/status     # 当前流水线状态
POST   /api/pipeline/run        # 手动触发采集
POST   /api/pipeline/build      # 手动触发站点构建
```

- 资源名用复数名词，动词用 HTTP method 表达
- 查询参数用 snake_case：`page_size` 而非 `pageSize`
- 路由文件与路径对应：`api/search.py` → `/api/search`

**统一响应信封**

```json
{
  "code": 0,
  "data": { ... },
  "message": "ok"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | 0 成功，非 0 见错误码表 |
| data | any | 响应数据，无数据时 `null`（不是省略字段） |
| message | string | 人类可读描述，仅非 0 时需关注 |

列表响应：

```json
{
  "code": 0,
  "data": {
    "items": [...],
    "total": 18250,
    "page": 1,
    "page_size": 20
  },
  "message": "ok"
}
```

**空值约定**

- 列表为空 → `"items": []`（不是 `null`，不省略字段）
- 对象为空 → `"data": {}`（不是 `null`）
- 字段无值 → 省略该字段或用 `null`，但不能用空字符串 `""` 代替缺失值
- 列表 empty 和列表不存在是两件事：采集失败 → 不返回该 source 的 key；采集成功但无新条目 → 返回 `"github": []`

**错误码**

| code | 含义 | HTTP 状态码 |
|------|------|------------|
| 0 | 成功 | 200 |
| 40001 | 参数校验失败 | 422 |
| 40101 | API 未认证（预留） | 401 |
| 40401 | 资源不存在 | 404 |
| 50001 | 服务内部错误 | 500 |
| 50002 | 数据库错误 | 500 |
| 50003 | 上游 API 超时 | 504 |
| 50004 | LLM Provider 不可用 | 503 |

`message` 字段携带具体上下文，不暴露内部调用栈：

```json
{ "code": 50003, "data": null, "message": "GitHub API 请求超时 (retry 3/3)" }
{ "code": 50004, "data": null, "message": "LLM Provider 'deepseek' 熔断中 (circuit=open)" }
{ "code": 40401, "data": null, "message": "文章 99999 不存在" }
```

实现方式：`envelope()` 辅助函数构造成功响应 + FastAPI `add_exception_handler(HTTPException, ...)` + `add_exception_handler(Exception, ...)` 统一捕获异常为结构化错误响应。`/api/health` 不包信封（Caddy/Compose healthcheck 直接读）。

## 3. 开发指南

- **安装**：`uv sync`
- **运行**：`uv run uvicorn src.main:app --reload`
- **测试**：`uv run pytest -m "not integration and not e2e"`（CI）/ `uv run pytest`（全量）
- **集成测试**：`uv run pytest -m integration`（需真实 API，手动触发）
- **触发采集（手动）**：`curl -X POST http://localhost:8000/api/pipeline/run`
- **强制构建站点**：`curl -X POST http://localhost:8000/api/pipeline/build`（跳过去抖）
- **查看日志**：`docker logs pipeline --since 24h | grep '"event"' | jq .`
- **代码生成前**：先读 `config/*.yaml` 了解当前配置
- **新增数据源**：在 `config/sources.yaml` 添加源配置 → 在 `src/graph/analyzers/` 新增薄层文件 → 注册到 `pipeline.py`
- **新增 LLM Provider**：在 `config/llm.yaml` 注册 Provider → `.env.example` + VPS `.env` 添加密钥
- **改 Prompt 后**：必跑 `uv run pytest tests/test_prompt_regression.py` 验证输出结构合法
- **不提交**：`.env`、`data/`、`output/`
- **关键实现约定**：
  - Prompt 文件从 `prompts/*.md` 加载（`load_prompt()` 读文件），模板使用 `.format()` 占位符 `{title}`, `{description}`, `{url}`, `{metadata}`, `{schema}`
  - `response_format={"type": "json_object"}` 仅对 `supports_json_mode: true` 的 Provider 启用
  - DB upsert 使用 `ON CONFLICT(url) DO UPDATE SET ... RETURNING id`，不用 `INSERT OR REPLACE`
  - 标签更新前先 `DELETE FROM article_tags WHERE article_id = ?`，再重新 INSERT
  - 数据库备份使用 `aiosqlite` 的 `.backup()` API，不依赖 `sqlite3` CLI
  - 结构化日志使用 `JSONFormatter` 类（stdout JSON lines），不用 `logging.basicConfig` format 字符串
  - API 响应统一信封：`envelope()` 辅助函数 + FastAPI `add_exception_handler` 覆盖 `HTTPException` 和通用 `Exception`
  - 调度使用 `functools.partial` 绑定 `source_filter`，每个源独立 cron job

## 4. 参考文档

需要了解具体设计细节时，读取对应文件：

- `@docs/structure.md` — 完整目录结构 + 模块职责 + 核心约定
- `@docs/architecture.md` — LangGraph DAG 流程、数据流阶段模型、Reviewer 四维评分锚点、LLM 管理、前端渲染策略
- `@docs/operations.md` — 部署拓扑、CI/CD、VPS 初始化、数据库迁移、备份恢复、应急处理、日志排查
- `@docs/data-model.md` — 全部 9 张表 Schema + 配置文件示例
- `@docs/bug-progress.md` — Bug 处理记录（踩坑记录 + 修复方案），后续同类问题可参考
- `@docs/vps-access.md` — VPS 连接信息、SSH 密钥、常用运维命令
- `@docs/api.md` — 所有 API 接口详细信息（请求/响应格式、错误码、变更记录）
- `@docs/task.md` — 当前任务拆解、优先级和状态
- `@docs/codemap.md` — 代码地图：模块位置、职责、常见改动入口

**文档维护原则：** 项目代码变更时，同步更新对应的引用文档。例如：
- 新增/修改 API 端点 → 更新 `docs/api.md`
- 修改数据模型 → 更新 `docs/data-model.md`
- 修改部署流程 → 更新 `docs/operations.md`
- 调整模块职责或常见入口 → 更新 `docs/codemap.md`
- 拆解/推进阶段性任务 → 更新 `docs/task.md`
