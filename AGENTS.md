# AGENTS.md

## 0. 基本要求

- 始终使用中文回复。
- 先读相关代码和文档，再改代码；不确定时先说明假设。
- 简单优先，只做用户要求的事，不写 speculative 代码。
- 精准改动，只触碰完成任务必须改的文件。
- 有多种解释时说明取舍；风险高或需求冲突时先问清楚。

## 1. 项目定位

个人 AI 知识库系统：自动采集 AI/LLM/Agent 领域资讯，经 LLM 分析审核后生成静态网站展示。

核心流程：Collector 采集去重 -> LangGraph 规则路由和并行分析 -> Reviewer 四维评分 -> 入库 -> 静态站/API 展示。

## 2. 不做什么

- 不做多用户、登录、权限系统。
- 不做实时推送或消息通知。
- 不做 Anthropic 原生协议适配，统一走 OpenAI 兼容协议。
- 不做数据库分库分表，SQLite 单文件足够。
- 不做语义去重，跨源同一事件允许保留不同分析视角。
- 不做 Alembic/SQLAlchemy 迁移，使用版本化 SQL + 轻量 Python 迁移。
- 不做异地备份，一期数据量小且可从采集源重建。

## 3. 编码硬规则

- 优先复用项目已有模式；能用一个函数解决就不新建抽象层。
- 能用标准库或已安装依赖解决，不新增依赖。
- 配置从 `config/*.yaml` 或统一配置模块读取，不在业务函数里直接读环境变量。
- Prompt 从 `prompts/*.md` 加载，不在 Analyzer 内硬编码长 Prompt。
- Analyzer 不直接调用 `openai.AsyncOpenAI`，统一走 `core.llm_client.LLMRegistry.get_client()`。
- 非 `db/` 模块不直接写 SQL，数据库读写走 `src/db/operations.py`。
- API 响应使用统一信封 `envelope()`；`/api/health` 除外。
- 日志走 `logging`，不要用 `print()`。
- 只处理可恢复错误；禁止裸 `except:` 和 `except Exception: pass`。
- 不提交 `.env`、`data/`、`output/`。

## 4. 常用命令

- 安装依赖：`uv sync`
- 本地运行：`uv run uvicorn src.main:app --reload`
- 常规测试：`uv run pytest -m "not integration and not e2e"`
- 全量测试：`uv run pytest`
- 集成测试：`uv run pytest -m integration`
- Prompt 修改后：`uv run pytest tests/test_prompt_regression.py`
- 手动触发采集：`curl -X POST http://localhost:8000/api/pipeline/run`
- 手动构建站点：`curl -X POST http://localhost:8000/api/pipeline/build`

## 5. 改动前读什么

- 改架构、LangGraph pipeline、LLM 管理：读 `docs/architecture.md`。
- 改 API 路由、响应、错误码：读 `docs/api.md`。
- 改数据库 schema、迁移、表关系：读 `docs/data-model.md`。
- 改部署、CI/CD、VPS、备份恢复：读 `docs/operations.md`。
- 找模块入口、职责边界、常见改动点：读 `docs/codemap.md`。
- 处理历史 bug 或类似问题：读 `docs/bug-progress.md`。
- 推进阶段任务或调整优先级：读 `docs/task.md`。
- 了解完整目录结构：读 `docs/structure.md`。
- 追溯历史设计或计划：按需读 `docs/superpowers/`，默认不读。

## 6. 文档写回规则

- 只更新与本次改动直接相关的文档，不顺手整理无关文档。
- 新增或修改 API：同步更新 `docs/api.md`。
- 修改数据模型或迁移：同步更新 `docs/data-model.md`。
- 修改部署、CI/CD、运维流程：同步更新 `docs/operations.md`。
- 新增、移动、删除模块：同步更新 `docs/codemap.md`。
- 修复有复发风险的 bug：记录到 `docs/bug-progress.md`，包含症状、根因、修复和验证命令。
- 推进或调整阶段性任务：同步更新 `docs/task.md`。
- 如果 AGENTS.md 或 docs 与代码冲突，以代码为准，并修正文档。
