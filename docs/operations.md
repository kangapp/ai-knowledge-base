# 运维架构

## 部署拓扑

```
VPS (1C2G)
└── Docker Compose
    ├── pipeline (Python)
    │   ├── FastAPI (:8000)
    │   ├── APScheduler (AsyncIOScheduler, Asia/Shanghai, pipeline lock queue)
    │   ├── LangGraph Pipeline (全链路 async，不阻塞 event loop)
    │   └── Jinja2 Site Builder → output.tmp → rename → /output
    │
    ├── web (Caddy)
    │   ├── / → /srv (静态站)
    │   └── /api/* → pipeline:8000
    │
    └── volumes:
        ├── ./data → SQLite + backup/
        ├── ./output → 静态站点
        └── ./config → 配置文件
```

## CI/CD 流程

```
GitHub Actions (push master):
  pytest -m "not integration and not e2e" (仅单元测试，LLM mock，<30s)
    → 构建并推送 commit SHA + latest 双标签镜像
      → VPS 记录当前 pipeline 镜像作为回滚版本
        → 拉取本次 commit SHA 镜像
          → docker compose up -d --wait
            → POST /api/pipeline/build 强制重建静态站
              → 验证 VPS 内部和公网健康接口、关键页面
```

- 集成测试（真实 API+LLM）手动跑：`pytest -m integration`
- E2E（全 mock 完整流程）部署前本地跑：`pytest -m e2e`
- push 到 `master` 自动部署；Actions 的 `workflow_dispatch` 可指定 Git ref，重新构建该 ref 并部署其真实 commit SHA。
- 正式部署只使用 `ghcr.io/kangapp/ai-knowledge-base:<commit-sha>`；`latest` 仅作为人工调试兼容标签。
- `docker-compose.yml` 通过 `PIPELINE_IMAGE` 接收目标镜像，未传入时才回退 `latest`，便于 VPS 首次初始化。
- 部署任务串行排队，避免两个 SSH 部署同时修改 Compose 状态；不取消进行中的部署，避免在容器替换中途终止。
- 部署任务仅在 pipeline 健康后构建静态站；健康检查、构建请求、关键静态页面或公网验收失败时，恢复部署前镜像和静态输出，deploy job 仍保持失败以便追查。
- pipeline 镜像必须包含 `curl`（健康/构建请求）和 `git`（Deep Reports 临时 clone GitHub 仓库）。
- Dockerfile 先安装稳定系统依赖，再复制业务源码；普通代码发布只生成较小的源码层，减少 VPS 从 GHCR 拉取的数据量。
- SSH 建连上限为 30 秒，远程命令上限为 10 分钟；只拉取 pipeline 镜像，单次最多 3 分钟并重试 2 次，持续网络故障会快速失败。
- GitHub 仓库 Secret `PUBLIC_BASE_URL` 保存公网根地址，例如 `http://8.134.176.187:8090`；部署最后验证 `/api/health`、`/deep.html` 和 `/deep-report.html`。
- Actions 与镜像内 uv 使用固定主版本/精确版本，降低运行时升级导致的不可复现风险。

## VPS 初始化（5 步）

1. 安装 Docker + Docker Compose
2. Clone 仓库
3. 对着 `.env.example` 创建 `.env` 填入密钥
4. `docker compose up -d`
5. 验证：`curl https://<domain>/api/health`

## 手动部署与回滚

在 GitHub Actions 的 `Deploy` 工作流选择 **Run workflow**，输入分支、Tag 或 commit SHA。工作流会解析为完整 commit SHA，重新运行测试、构建对应镜像并部署。

自动回滚只覆盖本次部署造成的容器与静态输出变更，不回滚数据库迁移或其他持久化数据。部署前的 pipeline 镜像会临时标记为 `rollback-<run-id>`，静态输出复制到本次 run 专属目录；新版本完成健康检查、静态构建和公网验收后删除临时备份，失败时恢复旧镜像、旧静态输出并再次等待健康。

## 数据库迁移

- 版本化 SQL 文件：`src/db/migrations/001_init.sql`, `002_xxx.sql`, ... 按编号递增
- `schema_version` 表记录当前版本
- 启动时 `database.py` 自动检测 → 执行未应用迁移 → 按序往前滚
- 回滚：恢复 `.backup` 文件后重新跑迁移

## 密钥管理

`.env` 不入 Git，VPS 手动维护。`.env.example` 在 Git 中作为密钥清单模板。

- **轮换现有密钥**：`vim /app/.env` → `docker compose restart pipeline`
- **新增 Provider/密钥字段**：本地更新 `.env.example` 模板 → SSH 同步 `.env` → `docker compose up -d`

## 备份与恢复

- **备份**：每次 pipeline 完成后 `Database.backup()` 调用 `aiosqlite` 的 `.backup()` API 在线热备份到 `data/backup/knowledge-YYYYMMDD.db`
- **保留**：VPS 本地保留最近 7 天，每天滚动覆盖
- **异地**：一期不做。SQLite 仅 ~20MB/年，机器故障后重建 + 重跑采集即可恢复
- **恢复**：`docker compose stop pipeline` → `cp data/backup/knowledge-YYYYMMDD.db data/knowledge.db` → `docker compose start pipeline`

## 应急处理

- **LLM Provider 全挂**：`TrackedClient` 遍历 fallback[] 链，全失败则当天文章以 `pending_review` 状态入库
- **单源 API 故障**：try/except 隔离，返回空列表 + 记录 error_log，其余源继续
- **SQLite 损坏**：`cp data/backup/knowledge-YYYYMMDD.db data/knowledge.db` + restart pipeline
- **调度重叠**：采集任务按 cron 分组注册并使用北京时间；若上一轮仍未完成，新任务记录 `pipeline.queued` 后等待进程内锁，上一轮结束后继续执行，不再跳过整组。
- **连续零采集**：先查 `/api/sources/stats` 的 `health_status/last_error/last_run_at`。`failed` 是请求失败，`success_zero` 是请求成功但关键词零命中，`dedup_only` 是本轮全部重复，`analysis_failed` 是已采集但分析阶段失败。
- **RSS 地址失效**：优先切换到来源官方 Feed；不存在稳定官方 Feed 时在 `config/sources.yaml` 设为 `enabled: false`，不要用不稳定代理伪装成可用源。
- **部署在 6-10 分钟内失败**：查看 `2/6 Pull immutable image` 阶段。GHCR 拉取单次 3 分钟、最多 2 次；网络持续过慢时快速失败，不继续占用 runner。
- **部署后自动回滚**：查看 `Deployment failed; collecting diagnostics` 和 `Restoring previous pipeline image`。CI 仍显示失败是预期行为，线上应继续运行旧镜像。
- **回滚也失败**：按日志中的镜像 ID 登录 VPS，执行 `PIPELINE_IMAGE=<旧镜像标签> docker compose up -d --wait --wait-timeout 90`，并检查数据库迁移是否需要单独恢复。

## 日志与排查

结构化 JSON 日志 → stdout → `docker logs` 收集：

```bash
# 排查昨天的 pipeline
docker logs pipeline --since 24h | grep '"event"' | jq .

# 看错误
docker logs pipeline --since 24h | grep '"error"'

# 看某次 pipeline 全链路
docker logs pipeline --since 24h | grep '"run_id": "20260516-0900"'
```

Log 事件命名：`{module}.{action}` — `collector.start`, `collector.done`, `collector.error`, `router.done`, `analyzer.done`, `reviewer.done`, `pipeline.done`。

`pipeline_runs` 表提供结构化快照，快速判断当天是否有产出：

```sql
SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 5;
```

当前源配置决策（2026-06-10）：

- Product Hunt 使用官方 `https://www.producthunt.com/feed`。
- 虎嗅、掘金、Reuters 因原地址 404 或持续超时暂时禁用。
- Ars Technica 保持启用，由北京时间调度和排队机制保证执行。
