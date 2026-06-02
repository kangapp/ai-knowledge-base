# Bug 处理记录

## Bug 1: parse_and_validate tags 超过 max_length 导致整批崩溃

**发现时间**: 2026-05-17
**发现场景**: 本地测试 RSS 采集 + LLM 分析时
**根因**: LLM 返回的 tags 数组超过 Pydantic Field `max_length=3` 限制，validation 失败后异常向上传播

**错误日志**:
```
analyzer.parse_failed, agent=rss_analyzer, url=..., error="1 validation error for AnalyzedItem\ntags\n  List should have at most 3 items after validation, not 5"
```

**处理**: 在 `parse_and_validate` 中对 tags 做容错裁剪
```python
# 容错：tags 超过 3 个时裁剪
if "tags" in data and isinstance(data["tags"], list) and len(data["tags"]) > 3:
    data["tags"] = data["tags"][:3]
```

**相关文件**: `src/graph/analyzers/base.py`

---

## Bug 2: analyze_items 单 item 失败导致整批中断

**发现时间**: 2026-05-17
**发现场景**: 同上，parse 失败后 `raise` 导致后续 item 不处理
**根因**: 重试 2 次后 parse 仍失败，直接 raise 抛出异常，for 循环中断

**错误日志**:
```
src.core.llm_client.AllProvidersUnavailable: No available provider for 'rss_analyzer'
```

**处理**: 
- `get_client` 失败时 log warning + continue 到下一个 item
- `parse` 失败后 log warning + continue 到下一个 item（不是 raise）

**相关文件**: `src/graph/analyzers/base.py`

---

## Bug 3: ReviewedItem.ref_url 为 None 时 print 抛 TypeError

**发现时间**: 2026-05-17
**发现场景**: 测试脚本 print reviewed_items 时
**根因**: `ReviewedItem` 中 `ref_url: Optional[str] = None` 允许为 None，但代码中 `item.ref_url[:60]` 会抛 TypeError

**处理**: 
- reviewer_node 正常路径中 `reviewed_items.append(reviewed)` 应保持 `reviewed.ref_url = item.ref_url`
- 确认 ReviewedItem 定义中 `ref_url: Optional[str] = None` 符合 spec（LLM 输出不含此字段，由调用方补全）
- 测试代码改为 `str(item.ref_url or "")[:60]`

**相关文件**: `src/graph/reviewer.py`, `src/graph/state.py`

---

## 踩坑记录

### 1. 环境变量加载顺序
- `.env` 文件需使用 `set -a; source .env; set +a` 加载（fish shell）
- 直接 `uv run` 不会自动读取 `.env`

### 2. GitHub API 需要 GITHUB_TOKEN
- `.env` 中 `GITHUB_TOKEN=ghp_xxx` 为占位符，需替换为真实 token
- 无 token 时 GitHub API 返回 401，但不影响 RSS 等其他数据源采集

### 3. LangGraph async 节点要用 callable 对象
- `graph.add_node("reviewer", lambda s: reviewer_node(s, registry))` 不可行
- 正确做法：`_AnalyzerNode` / `_ReviewerNode` 封装类实现 `__call__`

### 4. Reviewer prompt 文件缺失时的 fallback
- `_load_reviewer_prompt` 在 prompt 文件不存在时使用内置默认 prompt（符合设计）
- 4 个 analyzer 的 `load_prompt` 在 prompt 文件不存在时直接抛 FileNotFoundError（符合"文件缺失应该报错"原则，prompt 文件需手动创建）

---

## Bug 4: save_article ON CONFLICT RETURNING id 在 aiosqlite 下失效

**发现时间**: 2026-05-17
**发现场景**: 完整 pipeline 测试，入库时 article_id 始终为 None
**根因**: aiosqlite 的 `execute()` 是异步包装，但底层 `conn.execute()` 并不支持 SQLite 的 `INSERT ... RETURNING id` 子句（RETURNING 是同步语法，aiosqlite 无法正确解析）；同时缺少 `await db.commit()` 导致事务未提交

**错误日志**:
```
row = await db.fetch_one("""INSERT ... ON CONFLICT(url) DO UPDATE SET ... RETURNING id""", ...)
return row["id"] if row else None  # row 始终为 None
```

**处理**:
- 改用 SELECT + UPDATE/INSERT 分离方案：先 `SELECT id FROM articles WHERE url=?` 检查是否存在
- 存在则 UPDATE + commit，不存在则 INSERT + commit + `SELECT last_insert_rowid()`
- 所有 `db.execute()` 后显式添加 `await db.commit()`

**相关文件**: `src/db/operations.py`, `src/core/database.py`

---

## Bug 5: GitHub API 401 无认证 token 时整个采集失败

**发现时间**: 2026-05-17
**发现场景**: 触发 pipeline 时 GitHub API 返回 401
**根因**: `.env` 中 `GITHUB_TOKEN=ghp_xxx` 为占位符，GitHub Search API 对未认证请求有严格限制（60 req/hr），超过后返回 401；`collect_all` 单源失败会导致整批采集部分失败但不影响其余源

**处理**: GitHub collector 已实现：未配置 token 时使用未认证请求，失败时记录 error_log 不中断其他源

**相关文件**: `src/graph/collector.py`

---

## Bug 6: Dockerfile 注释导致 Docker 构建失败

**发现时间**: 2026-05-17
**发现场景**: `docker compose up --build` 时
**根因**: Dockerfile 中 `COPY` 指令行尾的注释 `# ...` 导致 Docker 构建失败，报错 `"/场景的": not found`

**错误日志**:
```
failed to solve: failed to compute cache key: failed to calculate checksum of ref ...: "/场景的": not found
```

**错误写法**:
```dockerfile
COPY config/ ./config/    # compose volume mount 会覆盖，仅作为非 compose 场景的 fallback
```

**处理**: 删除行尾注释
```dockerfile
COPY config/ ./config/
```

**相关文件**: `Dockerfile`

---

## Bug 7: /api/pipeline/build 接口缺失

**发现时间**: 2026-05-17
**发现场景**: 手动触发站点构建时
**根因**: 实现了 `trigger_build` 函数但未注册到 FastAPI 路由，也未调用 `set_builder()`

**错误日志**: `POST /api/pipeline/build` 返回 404 Not Found

**处理**:
- 在 `src/api/routes.py` 添加 `trigger_build` 端点
- 添加 `set_builder()` 函数将 `_builder` 暴露给 routes
- 在 `src/main.py` lifespan 中 `_builder` 创建后调用 `set_builder(_builder)`

**相关文件**: `src/api/routes.py`, `src/main.py`

---

## Bug 8: volume mount 环境下 rename 导致 "Device or resource busy"

**发现时间**: 2026-05-17
**发现场景**: Docker 部署中 `/api/pipeline/build` 触发站点构建时
**根因**: OrbStack 虚拟机环境下 volume mount 的 `/app/output` 目录无法被 rename/shutil.rmtree

**错误日志**:
```
OSError: [Errno 16] Device or resource busy: PosixPath('/app/output')
```

**处理**:
- 不再尝试 rename/rmtree `/app/output` 目录
- 改用文件覆盖方式：遍历临时目录，直接 `shutil.copy2` 到目标位置
- 临时目录用时间戳命名（`output.tmp.{timestamp}`），避免删除操作

```python
# 直接覆盖文件（不删除目录，避免 volume mount busy 问题）
for item in tmp_dir.rglob("*"):
    if item.is_file():
        dest = self.output_dir / item.relative_to(tmp_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest)
```

**相关文件**: `src/site/builder.py`

---

## Bug 9: search_articles 返回结果缺少 tags 字段

**发现时间**: 2026-05-17
**发现场景**: API 返回文章列表中 tags 为空
**根因**: `search_articles` 只查询 articles 表，未关联查询 article_tags 和 tags 表

**处理**: 在 `search_articles` 中遍历每篇文章，查询关联标签
```python
for r in rows:
    article = dict(r)
    tag_rows = await db.fetch_all(
        "SELECT t.name FROM tags t JOIN article_tags at ON t.id=at.tag_id WHERE at.article_id=?",
        (article["id"],))
    article["tags"] = [t["name"] for t in tag_rows]
```

**相关文件**: `src/db/operations.py`

---

## Bug 10: Caddyfile 使用域名导致本地 HTTPS 申请失败

**发现时间**: 2026-05-17
**发现场景**: 本地 Docker 部署后访问 localhost:8080 失败
**根因**: Caddyfile 中使用 `kb.your-domain.com` 域名，Caddy 尝试申请 Let's Encrypt 证书（需要 DNS 解析），本地验证失败导致服务不可用

**错误日志**:
```
challenge failed, identifier="kb.your-domain.com", challenge_type="http-01"
```

**处理**: 改为本地开发配置
```caddyfile
# 本地开发禁用 HTTPS
:8080 {
    root * /srv
    file_server
    ...
}
```

**相关文件**: `Caddyfile`

---

## Bug 11: OrbStack 端口转发 localhost 访问失败

**发现时间**: 2026-05-17
**发现场景**: `curl http://localhost:8080` 返回 "Empty reply from server"
**根因**: OrbStack Docker 虚拟机的端口转发与宿主机网络不通

**处理**: 使用 OrbStack 内部 DNS `web.ai-knowledge-base.orb.local/` 访问

**相关文件**: 无（基础设施问题）

---

## Bug 12: article.html 详情页 API 响应未解包导致 undefined

**发现时间**: 2026-05-17
**发现场景**: Playwright MCP 测试文章详情页
**根因**: API 响应格式为 `{code: 0, data: {...}, message: "ok"}`，详情页 JS 直接用 `a.title` 取值，但实际 title 在 `res.data.title`

**错误日志**: 页面显示 "undefined" 所有字段

**处理**: 解包 API 响应
```javascript
fetch('/api/articles/' + id).then(r => r.json()).then(res => {
    const a = res.data;  // 解包 data 字段
    document.getElementById('article-detail').innerHTML = `...`;
});
```

**相关文件**: `src/site/templates/article.html`

---

## Bug 13: article.html collected_at 未格式化显示 undefined

**发现时间**: 2026-05-17
**发现场景**: 同上
**根因**: `collected_at` 格式为 ISO 字符串 `2026-05-17T07:21:04.612826+00:00`，直接显示会显示完整字符串

**处理**: 截取日期部分
```javascript
${a.collected_at ? a.collected_at.slice(0,10) : ''}
```

**相关文件**: `src/site/templates/article.html`

---

## Bug 14: dashboard.html Chart.js 在脚本加载前执行导致 undefined

**发现时间**: 2026-05-17
**发现场景**: Playwright MCP 测试仪表盘，控制台报错 `ReferenceError: Chart is not defined`
**根因**: `new Chart()` 在 `<script src="chart.js">` 之前执行，Chart 全局变量还不存在

**处理**: 
1. base.html 中 Chart.js 加载添加 `defer` 属性
2. dashboard.html 中 Chart 调用包裹在 `DOMContentLoaded` 事件中

```html
<!-- base.html -->
<script defer src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script defer src="/static/js/app.js"></script>

<!-- dashboard.html -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    const stats = window.__STATS__;
    if (typeof Chart !== 'undefined') {
        new Chart(...);
    }
});
</script>
```

**相关文件**: `src/site/templates/base.html`, `src/site/templates/dashboard.html`

---

## Bug 15: OrbStack 容器残留导致 docker compose up 失败

**发现时间**: 2026-05-17
**发现场景**: `docker compose up -d` 时报错 "container name already in use"
**根因**: 之前的容器未正确删除，残留的 bf6b48d5624c 占用了名称

**处理**: `docker rm -f <残留容器ID>`

**相关文件**: 无（基础设施问题）

---

## Bug 16: GitHub Actions pytest 未找到

**发现时间**: 2026-05-17
**发现场景**: CI/CD 流水线 test job 运行 `uv run pytest` 报错
**根因**: `uv sync --frozen` 只安装生产依赖，`dev` 依赖未安装，pytest 不存在

**错误日志**:
```
error: Failed to spawn: `pytest`
Caused by: No such file or directory (os error 2)
```

**处理**: 添加 `--dev` 安装开发依赖（含 pytest）
```yaml
# 原写法
- run: uv sync --frozen
- run: uv run pytest -m "not integration and not e2e"

# 修复后
- run: uv sync --frozen --dev
- run: uv run pytest -m "not integration and not e2e"
```

**相关文件**: `.github/workflows/deploy.yml`

---

## Bug 17: CI/CD deploy job 未生效（条件仍是 main 分支）

**发现时间**: 2026-05-17
**发现场景**: 修改 workflow 后 deploy job 未触发
**根因**: deploy job 的 `if` 条件中仍引用 `refs/heads/main`，未同步修改为 `refs/heads/master`

**处理**:
```yaml
# 原写法
if: github.ref == 'refs/heads/main'

# 修复后
if: github.ref == 'refs/heads/master'
```

**相关文件**: `.github/workflows/deploy.yml`

---

## Bug 18: CI/CD deploy 超时（VPS docker build 太慢）

**发现时间**: 2026-05-17
**发现场景**: CI/CD deploy job 每次都报 "Run Command Timeout"
**根因**: VPS 上执行 `docker compose up -d --build`，在 1C2G VPS 上构建镜像耗时过长（约 10+ 分钟），SSH 命令超时

**错误日志**:
```
2026/05/17 10:51:16 Run Command Timeout
Error: Process completed with exit code 1.
```

**处理**: 拆分为 CI 构建 + VPS 部署两阶段
1. CI 使用 `docker/build-push-action@v6` 构建镜像并推送到 ghcr.io
2. VPS 只执行 `docker pull` + `docker compose up -d`（不构建）

```yaml
# CI 构建 job
build-image:
  needs: test
  steps:
    - uses: docker/build-push-action@v6
      with:
        context: .
        push: true
        tags: ghcr.io/${{ github.repository_owner }}/ai-knowledge-base:latest
        cache-from: type=gha
        cache-to: type=gha,mode=max

# VPS 部署 job（只 pull + up）
deploy:
  needs: build-image
  script: |
    docker pull ghcr.io/kangapp/ai-knowledge-base:latest
    docker compose up -d
```

同时改用 `image: ghcr.io/...` 替代 `build: .` 在 docker-compose.yml

**相关文件**: `.github/workflows/deploy.yml`, `docker-compose.yml`

---

## Bug 19: CI/CD VPS 部署 git pull 报 local changes 冲突

**发现时间**: 2026-05-17
**发现场景**: CI/CD SSH 脚本执行 `git pull origin master` 时 VPS 报错
**根因**: VPS 上 docker-compose.yml 和 .github/workflows/deploy.yml 有本地修改（之前调试时变更），与远程冲突

**错误日志**:
```
error: Your local changes to the following files would be overwritten by merge:
  .github/workflows/deploy.yml
  docker-compose.yml
Please commit your changes or stash them before you merge.
Aborting: fatal: Cannot fast-forward your working tree.
```

**处理**: 使用 `git fetch` + `git reset --hard origin/master` 替代 `git pull`
```bash
git fetch origin master
git reset --hard origin/master
docker compose up -d
```

**相关文件**: `.github/workflows/deploy.yml`

---

## Bug 20: CI/CD deploy script 仍有 docker build 残留

**发现时间**: 2026-05-17
**发现场景**: 检查 VPS docker-compose.yml 发现还是 `build: .` 而非 `image: ghcr.io/...`
**根因**: 修改 docker-compose.yml 后未同步到 VPS

**处理**: 
1. 本地修改 docker-compose.yml 将 `build: .` 改为 `image: ghcr.io/kangapp/ai-knowledge-base:latest`
2. 在 VPS 上手动 `git reset --hard origin/master` 拉取最新配置
3. CI/CD deploy script 确保每次都 reset 到 origin/master

**相关文件**: `docker-compose.yml`

---

## Bug 21: docker-compose.yml 中 build 模式下 .dockerignore 未排除 output 目录导致构建上下文过大

**发现时间**: 2026-05-17
**发现场景**: 本地 docker build 传输了 2.27k context
**根因**: .dockerignore 缺失，未排除 output/、data/、.git 等大目录

**处理**: 创建 .dockerignore 文件：
```
__pycache__/
*.pyc
.git/
output/
data/
.gitignore
.env
*.md
tests/
docs/
```

**相关文件**: `.dockerignore`

---

## Bug 22: APScheduler 重复添加 job（调试日志可见多条相同 job）

**发现时间**: 2026-05-17
**发现场景**: 启动日志中出现多条 "Added job 'partial'" 而非每个 source 一个 job
**根因**: 调试期间多次 reload 导致 APScheduler 未正确清理旧 job

**处理**: 保持单次部署正常，已在 lifespan shutdown 时正确调用 `_scheduler.shutdown()`

**相关文件**: `src/main.py`

---

## Bug 23: healthcheck curl 命令未安装

**发现时间**: 2026-05-17
**发现场景**: 容器 healthcheck 失败，docker compose ps 显示 unhealthy
**根因**: python:3.12-slim 镜像默认无 curl，而 healthcheck 配置了 `curl -f http://localhost:8000/api/health`

**处理**: 在 Dockerfile 中安装 curl：
```dockerfile
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
```

**相关文件**: `Dockerfile`

---

## Bug 24: VPS 外部无法访问服务（端口未开放）

**发现时间**: 2026-05-17
**发现场景**: 从本地 curl http://8.134.176.187:8090 失败
**根因**: 
1. Caddy web 服务端口 8090 映射到主机，但需检查防火墙
2. 内部 curl localhost:8000 在容器内正常，外部访问需确认端口映射

**处理**: 
1. 确认 docker-compose.yml 中 `ports: "8090:80"` 正确映射
2. 如需外部访问，需在 VPS 防火墙开放 8090 端口

**相关文件**: `docker-compose.yml`

---

## Bug 25: 新增 config.html/dag.html 页面部署后返回 404

**发现时间**: 2026-05-17
**发现场景**: 部署后访问 http://8.134.176.187:8090/config.html 返回 404
**根因**: 
1. builder.py 中新增页面的构建逻辑正确执行，但容器可能未拉取最新镜像
2. Caddy 配置只做静态文件服务 + /api/* 反向代理，新增页面在 output/ 目录需要先被构建出来

**排查过程**:
- `/dashboard.html` 正常返回（存在）
- `/config.html` 返回 404（不存在）
- `/api/config/llm` 返回 404（新 API 路由未注册）
- 执行 `POST /api/pipeline/build` 后 `/config.html` 仍然 404

**处理**: 
1. 在 builder.py 中添加 config.html 和 dag.html 的构建逻辑（复制 base.html + 渲染模板）
2. 确保 CI/CD deploy job 正确执行 `docker compose up -d`（会 pull 最新镜像）
3. 检查 VPS 容器是否运行最新镜像：`docker compose ps` + `docker image ls`

**相关文件**: `src/site/builder.py`

---

## Bug 26: Playwright MCP 测试时控制台残留历史错误

**发现时间**: 2026-05-17
**发现场景**: Playwright MCP 测试完成后，控制台错误列表包含大量历史错误（如早期测试的 localhost:8888、localhost:8765 等）
**根因**: Playwright 持久化控制台日志，早期测试的 API 404 错误残留

**处理**: 重新刷新页面获取最新错误列表

**相关文件**: 无

---

## Bug 27: 仪表盘 cost-chart canvas 高度失控导致页面无限拉长

**发现时间**: 2026-05-17
**发现场景**: 访问 VPS 仪表盘 http://8.134.176.187:8090/dashboard.html，页面被无限拉长
**根因**: `canvas#cost-chart` 没有固定高度的父容器。Chart.js 配置了 `responsive: true` + `maintainAspectRatio: false`，但 `.chart-card` 无高度约束，导致 canvas 渲染高度达到 ~236,627px，页面总高度 ~25,000px

**Playwright 检测数据**:
```
修复前:
  canvas height: 236,627px
  page height:   24,950px

修复后:
  canvas height: 150px (在 350px wrapper 内)
  page height:   630px
```

**处理**:
1. `dashboard.html`: canvas 外层包裹 `<div class="chart-canvas-wrapper">`
2. `style.css`: 新增 `.chart-canvas-wrapper { position: relative; height: 350px; width: 100%; }`

这是 Chart.js 的已知最佳实践：当 `responsive: true` 且 `maintainAspectRatio: false` 时，必须给 canvas 的容器设置固定高度。

**相关文件**: `src/site/templates/dashboard.html`, `src/site/static/css/style.css`

**关联发现**: Caddy 配置了 `Cache-Control: max-age=3600`，部署后浏览器可能缓存旧 CSS/JS 长达 1 小时，导致修复后仍需强制刷新才能看到效果。后续可考虑给静态资源 URL 添加版本查询参数。

---

## Bug 28: CI/CD deploy job 未执行 docker pull 导致 VPS 镜像不更新

**发现时间**: 2026-05-17
**发现场景**: Bug 27 修复推送到 master 后，CI/CD 显示部署成功，但 VPS 上 dashboard.html 仍是旧版（无 `.chart-canvas-wrapper`）
**根因**: `deploy.yml` 的 SSH 脚本中只执行了 `docker compose up -d`，Docker Compose 不会自动拉取已存在的 `latest` 标签镜像。需要显式 `docker compose pull` 先拉取最新镜像

**处理**:
```yaml
# 修复前
script: |
  set -e
  cd /opt/ai-knowledge-base
  git fetch origin master
  git reset --hard origin/master
  docker compose up -d

# 修复后
script: |
  set -e
  cd /opt/ai-knowledge-base
  git fetch origin master
  git reset --hard origin/master
  docker compose pull          # ← 新增
  docker compose up -d
```

**相关文件**: `.github/workflows/deploy.yml`

---

## Bug 29: lifespan 未初始化 _graph 导致 pipeline.not_initialized

**发现时间**: 2026-05-17
**发现场景**: 手动触发 `POST /api/pipeline/run`，日志显示 `pipeline.not_initialized`，定时任务同样失败
**根因**: `lifespan()` 中 `_graph` 始终为 `None` — `build_pipeline` 已在文件顶部 import，但初始化代码漏掉了 `_graph = build_pipeline(_registry)` 调用

**错误日志**:
```
{"ts": "2026-05-17T14:29:03.449335+00:00", "level": "ERROR", "msg": "pipeline.not_initialized", "taskName": "Task-51"}
{"ts": "2026-05-17T14:43:09.599562+00:00", "level": "ERROR", "msg": "pipeline.not_initialized", "taskName": "Task-83"}
```

**处理**: 在 `lifespan()` 中 `_registry = LLMRegistry(...)` 之后添加一行：
```python
_graph = build_pipeline(_registry)
```

**关联发现**: 修复后测试发现 DAG 状态仍不准确 — `start_pipeline_run`、`end_pipeline_run`、`save_cost_log`、`record_phase_start`、`record_phase_end` 全部缺少 `await db.commit()`。同时 `db.backup()` 在有未提交事务时会卡住，产生 0 字节备份文件并锁死数据库。

**关联修复** (同 commit):
- 所有 DB 写操作添加 `await db.commit()`
- `start_pipeline_run` INSERT 时显式设置 `status='running'`
- 简化 phase 记录：route/analyze/aggregate/review 合并为单个 `process` 阶段
- `save_cost_log` 添加 commit

**相关文件**: `src/main.py`, `src/db/operations.py`, `src/graph/pipeline.py`

---

## Bug 30: MiniMax `abab6.5s-chat` 模型已停用，导致全量分析失败

**发现时间**: 2026-05-22
**发现场景**: VPS 上 pipeline analyze 阶段全量失败，所有 item 返回 `LLM output is not valid JSON`
**根因**: MiniMax API 已弃用 `abab6.5s-chat` 模型，API 返回错误 `"your current token plan not support model, abab6.5s-chat (2061)"`

**错误日志**:
```
analyzer.parse_failed, agent=rss_analyzer, url=..., error="Error code: 500 - {'type': 'error', 'error': {'type': 'server_error', 'message': 'your current token plan not support model, abab6.5s-chat (2061)', 'http_code': '500'}}"
```

**处理**: 当时将 `config/agents.yaml` 中所有 analyzer 和 reviewer 的 `abab6.5s-chat` 替换为 MiniMax 上一代可用模型；2026-06-02 已统一升级为 `MiniMax-M3`。

**相关文件**: `config/agents.yaml`

---

## Bug 31: MiniMax thinking tags 导致 `parse_and_validate` JSON 解析失败

**发现时间**: 2026-05-22
**发现场景**: analyze 阶段全量失败，日志显示 `LLM output is not valid JSON`
**根因**: MiniMax 返回内容包含 `<think> ... 】` 格式的 thinking tags（有时无结束标签），`parse_and_validate` 未处理导致 JSON 解析时包含干扰文本

**处理**: 在 `parse_and_validate` 中添加 thinking tag 剥离逻辑：
```python
for _ in range(10):
    new_raw = re.sub(r'<think>[\s\S]*?】', '', raw).strip()
    if new_raw == raw:
        break
    raw = new_raw
json_start = raw.find('{')
if json_start > 0:
    raw = raw[json_start:]
```

**相关文件**: `src/graph/analyzers/base.py`

---

## Bug 32: `parse_reviewer_output` 缺少 thinking tags 处理

**发现时间**: 2026-05-22
**发现场景**: reviewer 阶段全量失败，日志显示 `Reviewer output is not valid JSON`
**根因**: `parse_reviewer_output` 只处理 markdown ```json 包裹，未处理 MiniMax thinking tags，导致解析失败后触发熔断

**处理**: 添加与 `base.py` 一致的 thinking tag 剥离逻辑：
```python
for _ in range(10):
    new_raw = re.sub(r'<think>[\s\S]*?(】|</think>)', '', raw).strip()
    if new_raw == raw:
        break
    raw = new_raw
```

**相关文件**: `src/graph/reviewer.py`

---

## Bug 33: `parse_reviewer_output` markdown-first 顺序导致 markdown 包裹 JSON 解析失败

**发现时间**: 2026-05-22
**发现场景**: 本地测试 `test_parse_reviewer_output_markdown_wrapped` 失败
**根因**: 原实现先剥离 thinking tag 再用 `find('{')` 截断，但对 `` ```json\n{...}\n``` `` 格式，`find('{')` 找到后 JSON 解析成功但留下尾部 `\n``` ` 导致 `Extra data` 错误

**处理**: 优先用正则剥离 markdown 包裹，再处理 thinking tags：
```python
m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
if m:
    return ReviewedItem.model_validate(json.loads(m.group(1)))
# 然后再处理 thinking tags...
```

**相关文件**: `src/graph/reviewer.py`

---

## Bug 34: 本地 `config/agents.yaml` 模型名未同步

**发现时间**: 2026-05-22
**发现场景**: 本地代码中 `agents.yaml` 仍是 `abab6.5s-chat`，与 VPS 上的已修正版本不一致
**根因**: VPS 上手动修改了 `/opt/ai-knowledge-base/config/agents.yaml`，但本地 git 仓库未同步更新

**处理**: 当时将本地 `config/agents.yaml` 中 5 处 `abab6.5s-chat` 替换为 MiniMax 上一代可用模型；2026-06-02 已统一升级为 `MiniMax-M3`。

**相关文件**: `config/agents.yaml`

---

## Bug 35: 文章卡片右上角标签（AI/Agent 等）丢失

**发现时间**: 2026-05-22
**发现场景**: 首页文章卡片只剩左上角来源标签，右上角文章标签（AI、Agent、LLM）消失
**根因**: `1c7e367` 重构 app.js 时将 `card-header`（含 `source-badge` 来源徽章 + `tags` 标签）替换为只有 `card-top`（来源标签），导致右上角标签丢失

**错误日志**:
```javascript
// 重构后 render() 输出（丢失了标签）
<div class="card-top"><span class="topic-tag">${label}</span></div>
// 之前有右上角标签
<div class="card-header"><span class="source-badge">${a.source}</span><div class="tags">...</div></div>
```

**处理**:
1. `index.html` 模板添加 `article_tags` 变量和 `tags` 渲染逻辑
2. `app.js` render() 用 `card-header` 布局替换 `card-top`（左侧来源 + 右侧标签）
3. `style.css` 补充 `.card-header/.tags/.tag` 样式

**相关文件**: `src/site/templates/index.html`, `src/site/static/js/app.js`, `src/site/static/css/style.css`

---

## Bug 36: GitHub 数据源健康采集量为 0

**发现时间**: 2026-06-02
**发现场景**: 数据源健康 Tab 中 GitHub Trending、持续热门、趋势增速采集量均为 0；DB 中 `source_health.failed=0`，说明不是请求失败。
**根因**: GitHub Search API 不支持对 `topic:` qualifier 使用 `OR`。`topic:llm` 单独可返回数据，但 `(topic:llm OR topic:machine-learning)` 会返回 0，`topic:llm OR topic:machine-learning` 会返回 422。

**处理**: GitHub collector 将 `topics/keywords` 拆成最多 5 个单条件 Search 请求，分别请求后本地按 URL 合并去重、按 stars 排序，再应用 `exclude_terms` 和 stars/forks/watchers 阈值。

**相关文件**: `src/graph/collector.py`, `tests/test_collector.py`

---

## Bug 37: MiniMax-M3 输出尾部解释导致 JSON 解析失败

**发现时间**: 2026-06-02
**发现场景**: VPS 流水线中 analyzer/reviewer 多次出现 `parse_failed`，日志显示 M3 会输出 `<think>`、markdown 包裹、合法 JSON 后追加解释或残留 ```。

**根因**: Analyzer 和 Reviewer 各自维护 JSON 清洗逻辑，只能处理少数固定格式；当合法 JSON 后存在尾部文本时，`json.loads()` 报 `Extra data`。

**处理**:
1. 新增 `src/core/json_utils.py::extract_json_object()`，统一剥离 thinking tags、markdown 包裹，并用 `json.JSONDecoder.raw_decode()` 提取第一个完整 JSON 对象。
2. `src/graph/analyzers/base.py` 和 `src/graph/reviewer.py` 复用同一个解析工具。
3. 增加 analyzer/reviewer 尾部文本回归测试。

**相关文件**: `src/core/json_utils.py`, `src/graph/analyzers/base.py`, `src/graph/reviewer.py`, `tests/test_analyzer.py`, `tests/test_reviewer.py`

---

## Bug 38: retry 轮重复跑 Analyzer 导致流水线耗时和成本放大

**发现时间**: 2026-06-02
**发现场景**: VPS 手动流水线第一轮 review 后有 10 条 retry，后续又进入 route/analyze/aggregate/review；由于 Analyzer prompt 未消费 `retry_feedback`，重跑分析没有带来确定收益。

**根因**: retry 循环复用整张 LangGraph DAG，导致 retry item 重新走 Router 和 Analyzer。

**处理**:
1. 新增 `_prepare_retry_review_items()`，从已有 `AnalyzedItem` 中挑选 retry item 并递增 `retry_count`。
2. retry 轮直接调用 `reviewer_node()`，保留 review phase log，避免重复 Analyzer 调用。
3. 增加 retry 复用已有分析结果的回归测试。

**相关文件**: `src/main.py`, `tests/test_pipeline_observability.py`
