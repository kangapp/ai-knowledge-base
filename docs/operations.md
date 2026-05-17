# 运维架构

## 部署拓扑

```
VPS (1C2G)
└── Docker Compose
    ├── pipeline (Python)
    │   ├── FastAPI (:8000)
    │   ├── APScheduler (AsyncIOScheduler, skip_if_running)
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
GitHub Actions (push main):
  pytest -m "not integration and not e2e" (仅单元测试，LLM mock，<30s)
    → docker build
      → docker save → scp → docker load
        → docker compose up -d
```

- 集成测试（真实 API+LLM）手动跑：`pytest -m integration`
- E2E（全 mock 完整流程）部署前本地跑：`pytest -m e2e`

## VPS 初始化（5 步）

1. 安装 Docker + Docker Compose
2. Clone 仓库
3. 对着 `.env.example` 创建 `.env` 填入密钥
4. `docker compose up -d`
5. 验证：`curl https://<domain>/api/health`

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
- **调度重叠**：`skip_if_running` — 上一轮未完成时跳过本轮，下轮 cron 兜底

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
