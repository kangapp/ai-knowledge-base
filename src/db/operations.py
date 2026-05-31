# src/db/operations.py
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from ..core.database import Database
from ..graph.state import AnalyzedItem, CostRecord, ReviewedItem, RawItem


async def save_article(db: Database, raw: RawItem, analyzed: AnalyzedItem, reviewed: ReviewedItem, cost: float, tokens: int) -> int | None:
    """保存文章，返回 article id（新插入或已存在行的 id）"""
    extra = json.dumps({
        "dimensions": reviewed.dimensions,
        "language": analyzed.language,
        "raw": raw.raw_metadata,
    }, ensure_ascii=False)
    params = (
        analyzed.title, raw.url, raw.description, analyzed.summary,
        raw.source, raw.source_detail, reviewed.total_score,
        reviewed.verdict, analyzed.retry_count,
        raw.collected_at, raw.published_at,
        extra,
        cost, tokens,
    )
    # 事务：先 SELECT 检查是否存在，存在则 UPDATE，否则 INSERT
    existing = await db.fetch_one("SELECT id FROM articles WHERE url=?", (raw.url,))
    if existing:
        await db.execute("""
            UPDATE articles SET
                title=?, description=?, summary=?, relevance_score=?,
                status=?, retry_count=?, extra_data=?,
                analysis_cost=?, analysis_tokens=?, updated_at=datetime('now')
            WHERE url=?
        """, (analyzed.title, raw.description, analyzed.summary, reviewed.total_score,
              reviewed.verdict, analyzed.retry_count, extra, cost, tokens, raw.url))
        await db.commit()
        return existing["id"]
    else:
        await db.execute("""
            INSERT INTO articles
            (title, url, description, summary, source, source_detail,
             relevance_score, status, retry_count, collected_at, published_at, extra_data, analysis_cost, analysis_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, params)
        await db.commit()
        row = await db.fetch_one("SELECT last_insert_rowid() as id")
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
    await db.execute("INSERT INTO pipeline_runs (id, status, started_at, trigger) VALUES (?, 'running', ?, ?)", (run_id, now, trigger))
    await db.commit()


async def end_pipeline_run(db: Database, run_id: str, status: str, summary: str):
    now = datetime.now(timezone.utc).isoformat()
    await db.execute("UPDATE pipeline_runs SET ended_at=?, status=?, summary=? WHERE id=?", (now, status, summary, run_id))
    await db.commit()


async def save_cost_log(db: Database, run_id: str, record: CostRecord):
    await db.execute("INSERT INTO cost_logs (run_id, agent, provider, model, tokens_in, tokens_out, cost, ref_url) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, record.agent, record.provider, record.model, record.tokens_in, record.tokens_out, record.cost, record.ref_url))
    await db.commit()


async def batch_check_existing_urls(db: Database, urls: list[str]) -> set[str]:
    """Collector 后批量查重"""
    if not urls:
        return set()
    placeholders = ",".join("?" * len(urls))
    rows = await db.fetch_all(f"SELECT url FROM articles WHERE url IN ({placeholders})", tuple(urls))
    return {r["url"] for r in rows}


def _article_filters(query: str = "", source: str = "", days: int = 30) -> tuple[str, list]:
    where = ["a.status = 'approved'"]
    params = []
    if query:
        where.append("articles_fts MATCH ?")
        params.append(query)
    if source:
        where.append("a.source = ?")
        params.append(source)
    if days:
        where.append("a.collected_at >= date('now', ?)")
        params.append(f"-{days} days")
    return " AND ".join(where), params


async def get_article_tags(db: Database, article_id: int) -> list[str]:
    rows = await db.fetch_all(
        "SELECT t.name FROM tags t JOIN article_tags at ON t.id=at.tag_id WHERE at.article_id=? ORDER BY t.name",
        (article_id,),
    )
    return [r["name"] for r in rows]


async def count_articles(db: Database, query: str = "", source: str = "", days: int = 30) -> int:
    where_sql, params = _article_filters(query, source, days)
    if query:
        sql = f"SELECT COUNT(*) as c FROM articles a JOIN articles_fts fts ON a.rowid = fts.rowid WHERE {where_sql}"
    else:
        sql = f"SELECT COUNT(*) as c FROM articles a WHERE {where_sql}"
    row = await db.fetch_one(sql, tuple(params))
    return row["c"] if row else 0


async def search_articles(db: Database, query: str, source: str = "", days: int = 30, limit: int = 20, offset: int = 0) -> list[dict]:
    where_sql, params = _article_filters(query, source, days)
    params.extend([limit, offset])
    if query:
        rows = await db.fetch_all(
            f"SELECT a.* FROM articles a JOIN articles_fts fts ON a.rowid = fts.rowid WHERE {where_sql} ORDER BY a.collected_at DESC LIMIT ? OFFSET ?",
            tuple(params))
    else:
        rows = await db.fetch_all(
            f"SELECT a.* FROM articles a WHERE {where_sql} ORDER BY a.collected_at DESC LIMIT ? OFFSET ?",
            tuple(params))

    # 查询标签
    articles_with_tags = []
    for r in rows:
        article = dict(r)
        article["tags"] = await get_article_tags(db, article["id"])
        articles_with_tags.append(article)
    return articles_with_tags


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


async def get_quality_stats(db: Database, days: int = 30) -> dict:
    """数据质量 Tab 查询"""
    # 评分分布
    score_buckets = await db.fetch_all("""
        SELECT
            CASE
                WHEN relevance_score <= 20 THEN '0-20'
                WHEN relevance_score <= 40 THEN '20-40'
                WHEN relevance_score <= 60 THEN '40-60'
                WHEN relevance_score <= 80 THEN '60-80'
                ELSE '80-100'
            END as bucket,
            COUNT(*) as count
        FROM articles
        WHERE status='approved' AND collected_at >= date('now', ?)
        GROUP BY bucket
    """, (f"-{days} days",))

    # 来源细分评分
    source_scores = await db.fetch_all("""
        SELECT source, source_detail,
               COUNT(*) as article_count,
               AVG(relevance_score) as avg_score
        FROM articles
        WHERE status='approved' AND collected_at >= date('now', ?)
        GROUP BY source, source_detail
        ORDER BY avg_score DESC
    """, (f"-{days} days",))

    # 标签云
    top_tags = await db.fetch_all("""
        SELECT t.name, COUNT(*) as count
        FROM tags t JOIN article_tags at ON t.id=at.tag_id
        JOIN articles a ON a.id=at.article_id
        WHERE a.status='approved' AND a.collected_at >= date('now', ?)
        GROUP BY t.id
        ORDER BY count DESC LIMIT 20
    """, (f"-{days} days",))

    # 本周 vs 上月同期
    this_week = await db.fetch_one("""
        SELECT COUNT(*) as c FROM articles
        WHERE status='approved' AND collected_at >= date('now', '-7 days')
    """)
    last_week = await db.fetch_one("""
        SELECT COUNT(*) as c FROM articles
        WHERE collected_at >= date('now', '-14 days') AND collected_at < date('now', '-7 days')
    """)

    return {
        "score_distribution": [{"bucket": r["bucket"], "count": r["count"]} for r in score_buckets],
        "source_scores": [{"source": r["source"], "source_detail": r["source_detail"],
                            "article_count": r["article_count"], "avg_score": round(r["avg_score"], 1)} for r in source_scores],
        "top_tags": [{"name": r["name"], "count": r["count"]} for r in top_tags],
        "freshness": {
            "this_week": this_week["c"] if this_week else 0,
            "last_week": last_week["c"] if last_week else 0,
        }
    }


async def get_runtime_stats(db: Database, days: int = 7) -> dict:
    """运行状态 Tab 查询"""
    # 最新一次 pipeline run
    last_run = await db.fetch_one(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
    )

    if not last_run:
        return {"run": None, "phases": [], "failures": [], "providers": []}

    run_id = last_run["id"]

    # Phase logs
    phases = await db.fetch_all("""
        SELECT phase, status, started_at, ended_at, duration_ms, details
        FROM pipeline_phase_logs WHERE run_id=? ORDER BY id
    """, (run_id,))

    # 失败日志（通过 ref_url JOIN articles 获取标题）
    failures = await db.fetch_all("""
        SELECT cl.created_at, cl.agent, cl.provider, cl.ref_url,
               cl.cost, cl.tokens_in, cl.tokens_out,
               a.title as article_title
        FROM cost_logs cl
        LEFT JOIN articles a ON a.url = cl.ref_url
        WHERE cl.run_id=? AND cl.cost = 0
        ORDER BY cl.created_at DESC LIMIT 50
    """, (run_id,))

    # Provider 健康状态（从 circuit_events 最近）
    provider_events = await db.fetch_all("""
        SELECT provider, event, reason, created_at
        FROM circuit_events ORDER BY created_at DESC LIMIT 20
    """)

    provider_latest = {}
    for e in provider_events:
        p = e["provider"]
        if p not in provider_latest:
            provider_latest[p] = e

    return {
        "run": dict(last_run) if last_run else None,
        "phases": [dict(p) for p in phases],
        "failures": [{
            "time": f["created_at"][11:19] if f["created_at"] else "",
            "stage": f["agent"],
            "provider": f["provider"],
            "url": f["ref_url"] or "",
            "title": f["article_title"] or "",
        } for f in failures],
        "providers": [{
            "name": p,
            "last_event": e["event"],
            "last_reason": e["reason"] or "",
            "last_time": e["created_at"] or "",
        } for p, e in provider_latest.items()]
    }


async def get_consumption_stats(db: Database, days: int = 30) -> dict:
    """资源消耗 Tab 查询"""
    # Provider 费用分解（按日）
    provider_daily = await db.fetch_all("""
        SELECT date(created_at) as date, provider,
               SUM(cost) as cost, SUM(tokens_in+tokens_out) as tokens
        FROM cost_logs
        WHERE created_at >= date('now', ?)
        GROUP BY date(created_at), provider
        ORDER BY date
    """, (f"-{days} days",))

    # Agent 费用分解（按日）
    agent_daily = await db.fetch_all("""
        SELECT date(created_at) as date, agent,
               SUM(cost) as cost, SUM(tokens_in+tokens_out) as tokens
        FROM cost_logs
        WHERE created_at >= date('now', ?)
        GROUP BY date(created_at), agent
        ORDER BY date
    """, (f"-{days} days",))

    # 周期总花费
    period_cost = await db.fetch_one("""
        SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs
        WHERE created_at >= date('now', ?)
    """, (f"-{days} days",))

    # 周期总 token
    period_tokens = await db.fetch_one("""
        SELECT COALESCE(SUM(tokens_in + tokens_out), 0) as total FROM cost_logs
        WHERE created_at >= date('now', ?)
    """, (f"-{days} days",))

    # per-provider 汇总
    provider_summary = await db.fetch_all("""
        SELECT provider, SUM(cost) as total_cost,
               SUM(tokens_in) as total_in, SUM(tokens_out) as total_out
        FROM cost_logs WHERE created_at >= date('now', ?)
        GROUP BY provider
    """, (f"-{days} days",))

    return {
        "provider_daily": [dict(r) for r in provider_daily],
        "agent_daily": [dict(r) for r in agent_daily],
        "period_cost": round(period_cost["total"], 4) if period_cost else 0,
        "period_tokens": period_tokens["total"] if period_tokens else 0,
        "provider_summary": [{
            "provider": r["provider"],
            "total_cost": round(r["total_cost"], 4),
            "total_in": r["total_in"],
            "total_out": r["total_out"],
        } for r in provider_summary],
    }


async def get_consumption_detail_stats(db: Database, period: str = "week") -> dict:
    """
    资源消耗详细统计（Phase 2）
    period 表示趋势粒度：
    day = 近 7 天按天；week = 近 12 周按周；month = 近 12 个月按月。
    """
    window_map = {"day": "-7 days", "week": "-84 days", "month": "-12 months"}
    window = window_map.get(period, "-84 days")

    # 1. 周期总花费和日均
    period_cost = await db.fetch_one("""
        SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs
        WHERE created_at >= date('now', ?)
    """, (window,))

    period_days = await db.fetch_one("""
        SELECT COUNT(DISTINCT date(created_at)) as days FROM cost_logs
        WHERE created_at >= date('now', ?)
    """, (window,))

    # 2. Token 效率
    period_tokens = await db.fetch_one("""
        SELECT COALESCE(SUM(tokens_in + tokens_out), 0) as total FROM cost_logs
        WHERE created_at >= date('now', ?)
    """, (window,))

    # 3. 花费趋势（按周，支持日/月切换）
    if period == "day":
        trend_sql = """
            SELECT date(created_at) as label,
                   SUM(cost) as cost, COUNT(*) as articles
            FROM cost_logs WHERE created_at >= date('now', ?)
            GROUP BY date(created_at) ORDER BY label
        """
    elif period == "week":
        trend_sql = """
            SELECT strftime('%Y-W%W', created_at) as label,
                   SUM(cost) as cost, COUNT(*) as articles
            FROM cost_logs WHERE created_at >= date('now', ?)
            GROUP BY label ORDER BY label
        """
    else:  # month
        trend_sql = """
            SELECT strftime('%Y-%m', created_at) as label,
                   SUM(cost) as cost, COUNT(*) as articles
            FROM cost_logs WHERE created_at >= date('now', ?)
            GROUP BY label ORDER BY label
        """

    trend = await db.fetch_all(trend_sql, (window,))

    # 4. 来源费用趋势（分析 + 审核）
    if period == "day":
        source_trend = await db.fetch_all("""
            SELECT
                CASE
                    WHEN agent LIKE '%_analyzer' THEN SUBSTR(agent, 1, LENGTH(agent) - 8)
                    WHEN agent = 'reviewer' THEN 'review'
                    ELSE agent
                END as source,
                CASE WHEN agent LIKE '%_analyzer' THEN 'analyze' ELSE 'review' END as type,
                date(created_at) as label,
                SUM(cost) as cost
            FROM cost_logs
            WHERE created_at >= date('now', ?)
            GROUP BY source, type, date(created_at)
            ORDER BY label
        """, (window,))
    elif period == "week":
        source_trend = await db.fetch_all("""
            SELECT
                CASE
                    WHEN agent LIKE '%_analyzer' THEN SUBSTR(agent, 1, LENGTH(agent) - 8)
                    WHEN agent = 'reviewer' THEN 'review'
                    ELSE agent
                END as source,
                CASE WHEN agent LIKE '%_analyzer' THEN 'analyze' ELSE 'review' END as type,
                strftime('%Y-W%W', created_at) as label,
                SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', ?)
            GROUP BY source, type, label ORDER BY label
        """, (window,))
    else:
        source_trend = await db.fetch_all("""
            SELECT
                CASE
                    WHEN agent LIKE '%_analyzer' THEN SUBSTR(agent, 1, LENGTH(agent) - 8)
                    WHEN agent = 'reviewer' THEN 'review'
                    ELSE agent
                END as source,
                CASE WHEN agent LIKE '%_analyzer' THEN 'analyze' ELSE 'review' END as type,
                strftime('%Y-%m', created_at) as label,
                SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', ?)
            GROUP BY source, type, label ORDER BY label
        """, (window,))

    # 5. Provider 费用趋势
    if period == "day":
        provider_trend = await db.fetch_all("""
            SELECT date(created_at) as label, provider, SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', ?)
            GROUP BY provider, date(created_at) ORDER BY label
        """, (window,))
    elif period == "week":
        provider_trend = await db.fetch_all("""
            SELECT strftime('%Y-W%W', created_at) as label, provider, SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', ?)
            GROUP BY provider, label ORDER BY label
        """, (window,))
    else:
        provider_trend = await db.fetch_all("""
            SELECT strftime('%Y-%m', created_at) as label, provider, SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', ?)
            GROUP BY provider, label ORDER BY label
        """, (window,))

    # 6. 预算进度（硬编码月度预算 $10，与 config/agents.yaml budget.monthly: 10.0 一致）
    budget = 10.0
    monthly_cost = await db.fetch_one("""
        SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs
        WHERE created_at >= date('now', '-30 days')
    """)

    return {
        "period_cost": round(period_cost["total"] if period_cost else 0, 4),
        "period_days": period_days["days"] if period_days else 0,
        "period_tokens": period_tokens["total"] if period_tokens else 0,
        "daily_avg": round((period_cost["total"] or 0) / max(period_days["days"] if period_days else 1, 1), 4),
        "cost_per_million_tokens": round((period_cost["total"] or 0) / max(period_tokens["total"] if period_tokens else 1, 1) * 1e6, 2),
        "budget_progress": round((monthly_cost["total"] or 0) / budget, 3),
        "budget_remaining": round(budget - (monthly_cost["total"] or 0), 2),
        "trend": [{"label": r["label"], "cost": r["cost"], "articles": r["articles"]} for r in trend] if trend else [],
        "source_trend": [{"source": r["source"], "type": r["type"], "label": r["label"], "cost": r["cost"]} for r in source_trend] if source_trend else [],
        "provider_trend": [{"provider": r["provider"], "label": r["label"], "cost": r["cost"]} for r in provider_trend] if provider_trend else [],
    }


async def record_source_health(db: Database, record: "CollectResult"):
    """记录数据源健康数据"""
    from ..graph.state import CollectResult as CR
    today = datetime.now().strftime("%Y-%m-%d")
    await db.execute("""
        INSERT INTO source_health (source_id, date, total_collected, approved, rejected, failed, avg_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, date) DO UPDATE SET
            total_collected=excluded.total_collected,
            approved=excluded.approved,
            rejected=excluded.rejected,
            failed=excluded.failed,
            avg_score=excluded.avg_score,
            recorded_at=datetime('now')
    """, (record.source_id, today, record.total, record.approved, record.rejected, record.failed, record.avg_score))
    await db.commit()


async def batch_save_github_snapshots(db: Database, items: list[RawItem]):
    """批量写入 GitHub repo 快照（同一 repo_url + date 唯一）"""
    today = datetime.now().strftime("%Y-%m-%d")
    for item in items:
        if item.source != "github":
            continue
        meta = item.raw_metadata
        await db.execute("""
            INSERT OR REPLACE INTO github_repo_snapshots
            (repo_url, repo_name, stars, forks, watchers, snapshot_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (item.url, item.source_detail, meta.get("stars", 0),
              meta.get("forks", 0), meta.get("watchers", 0), today))
    await db.commit()


async def get_trending_repo_urls(db: Database, min_velocity: float, days: int = 7) -> set[str]:
    """计算 repos 在过去 N 天内的 star 增速，返回增速 >= min_velocity 的 repo_url 集合"""
    rows = await db.fetch_all("""
        SELECT s1.repo_url,
               (s1.stars - s0.stars) / (:days * 1.0) AS velocity
        FROM github_repo_snapshots s1
        JOIN github_repo_snapshots s0
          ON s0.repo_url = s1.repo_url
         AND s0.snapshot_date = date(s1.snapshot_date, '-' || :days || ' days')
        WHERE (s1.stars - s0.stars) / (:days * 1.0) >= :min_velocity
    """, {"days": days, "min_velocity": min_velocity})
    return {r["repo_url"] for r in rows}


async def get_quality_detail_stats(db: Database, period: str = "week") -> dict:
    """
    数据质量详细统计（Phase 1）
    period: day(1) / week(7) / month(30)
    """
    days_map = {"day": 1, "week": 7, "month": 30}
    days = days_map.get(period, 7)
    cutoff = f"-{days} days"

    total_articles = await db.fetch_one(
        "SELECT COUNT(*) as c FROM articles WHERE status='approved'"
    )
    period_status = await db.fetch_one("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved,
            AVG(CASE WHEN status='approved' THEN relevance_score END) as avg_score
        FROM articles
        WHERE collected_at >= date('now', ?)
    """, (cutoff,))
    period_total = period_status["total"] if period_status else 0
    period_approved = period_status["approved"] if period_status and period_status["approved"] else 0
    avg_score = period_status["avg_score"] if period_status and period_status["avg_score"] else 0

    # 1. 内容完整性指标
    summary_coverage = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE status='approved' AND collected_at >= date('now', ?)) as rate
        FROM articles WHERE status='approved' AND summary IS NOT NULL AND summary != '' AND collected_at >= date('now', ?)
    """, (cutoff, cutoff))

    desc_len = await db.fetch_one("""
        SELECT AVG(LENGTH(description)) as avg_len FROM articles WHERE status='approved' AND collected_at >= date('now', ?)
    """, (cutoff,))

    summary_len = await db.fetch_one("""
        SELECT AVG(LENGTH(summary)) as avg_len FROM articles WHERE status='approved' AND summary IS NOT NULL AND collected_at >= date('now', ?)
    """, (cutoff,))

    # 2. 审核效率指标
    one_pass = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE status='approved' AND collected_at >= date('now', ?)) as rate
        FROM articles WHERE status='approved' AND retry_count = 0 AND collected_at >= date('now', ?)
    """, (cutoff, cutoff))

    retry_rate = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE collected_at >= date('now', ?)) as rate
        FROM articles WHERE status='retry' AND collected_at >= date('now', ?)
    """, (cutoff, cutoff))

    exhausted_rate = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE collected_at >= date('now', ?)) as rate
        FROM articles WHERE retry_count >= 2 AND collected_at >= date('now', ?)
    """, (cutoff, cutoff))

    # 3. 标签覆盖指标
    tagged_rate = await db.fetch_one("""
        SELECT COUNT(DISTINCT at.article_id) * 1.0 / (SELECT COUNT(*) FROM articles WHERE status='approved' AND collected_at >= date('now', ?)) as rate
        FROM article_tags at
        JOIN articles a ON a.id = at.article_id
        WHERE a.collected_at >= date('now', ?)
    """, (cutoff, cutoff))

    avg_tags = await db.fetch_one("""
        SELECT AVG(tag_count) as avg FROM (
            SELECT COUNT(*) as tag_count FROM article_tags at
            JOIN articles a ON a.id = at.article_id
            WHERE a.collected_at >= date('now', ?)
            GROUP BY at.article_id
        )
    """, (cutoff,))

    # 4. 来源质量分布
    source_rows = await db.fetch_all("""
        SELECT source, source_detail, COUNT(*) as article_count, AVG(relevance_score) as avg_score
        FROM articles
        WHERE status='approved' AND collected_at >= date('now', ?)
        GROUP BY source, source_detail
        ORDER BY avg_score DESC, article_count DESC
        LIMIT 12
    """, (cutoff,))

    # 5. 四维评分统计（从 extra_data JSON 解析）
    dimensions = [
        ("ai_relevance", "ai_relevance", 40),
        ("content_depth", "content_depth", 30),
        ("info_density", "info_density", 15),
        ("timeliness", "timeliness", 15),
    ]
    dimension_stats = {}
    for name, json_key, max_score in dimensions:
        high_threshold = max_score * 0.8
        mid_threshold = max_score * 0.5
        stats = await db.fetch_one(f"""
            SELECT
                AVG(JSON_EXTRACT(extra_data, '$.dimensions.{json_key}.score')) as avg_score,
                COUNT(CASE WHEN JSON_EXTRACT(extra_data, '$.dimensions.{json_key}.score') >= ? THEN 1 END) * 1.0 / NULLIF(COUNT(JSON_EXTRACT(extra_data, '$.dimensions.{json_key}.score')), 0) as high_rate,
                COUNT(CASE WHEN JSON_EXTRACT(extra_data, '$.dimensions.{json_key}.score') >= ? AND JSON_EXTRACT(extra_data, '$.dimensions.{json_key}.score') < ? THEN 1 END) * 1.0 / NULLIF(COUNT(JSON_EXTRACT(extra_data, '$.dimensions.{json_key}.score')), 0) as mid_rate,
                COUNT(CASE WHEN JSON_EXTRACT(extra_data, '$.dimensions.{json_key}.score') < ? THEN 1 END) * 1.0 / NULLIF(COUNT(JSON_EXTRACT(extra_data, '$.dimensions.{json_key}.score')), 0) as low_rate
            FROM articles
            WHERE status='approved' AND extra_data IS NOT NULL AND collected_at >= date('now', ?)
        """, (high_threshold, mid_threshold, high_threshold, mid_threshold, cutoff))
        dimension_stats[name] = {
            "avg_score": round(stats["avg_score"] or 0, 1),
            "high_rate": round(stats["high_rate"] or 0, 3),
            "mid_rate": round(stats["mid_rate"] or 0, 3),
            "low_rate": round(stats["low_rate"] or 0, 3),
            "max_score": max_score,
        }

    # 6. Reason 关键词
    reason_rows = await db.fetch_all("""
        SELECT JSON_EXTRACT(extra_data, '$.dimensions.ai_relevance.reason') as reason
        FROM articles WHERE status='approved' AND extra_data IS NOT NULL AND collected_at >= date('now', ?)
    """, (cutoff,))

    keyword_count = {}
    import re
    for row in reason_rows:
        if row["reason"]:
            words = re.findall(r'[一-龥]+', row["reason"])
            for w in words:
                keyword_count[w] = keyword_count.get(w, 0) + 1

    top_keywords = sorted(keyword_count.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "summary": {
            "total_articles": total_articles["c"] if total_articles else 0,
            "period_articles": period_approved,
            "period_total_collected": period_total,
            "pass_rate": round(period_approved / period_total, 3) if period_total else 0,
            "avg_score": round(avg_score, 1),
        },
        "content_quality": {
            "summary_coverage": round(summary_coverage["rate"] if summary_coverage and summary_coverage["rate"] else 0, 3),
            "avg_desc_length": round(desc_len["avg_len"] if desc_len and desc_len["avg_len"] else 0, 1),
            "avg_summary_length": round(summary_len["avg_len"] if summary_len and summary_len["avg_len"] else 0, 1),
        },
        "audit_efficiency": {
            "one_pass_rate": round(one_pass["rate"] if one_pass and one_pass["rate"] else 0, 3),
            "retry_rate": round(retry_rate["rate"] if retry_rate and retry_rate["rate"] else 0, 3),
            "exhausted_rate": round(exhausted_rate["rate"] if exhausted_rate and exhausted_rate["rate"] else 0, 3),
        },
        "tag_coverage": {
            "tagged_rate": round(tagged_rate["rate"] if tagged_rate and tagged_rate["rate"] else 0, 3),
            "avg_tags": round(avg_tags["avg"] if avg_tags and avg_tags["avg"] else 0, 1),
        },
        "source_quality": [
            {
                "source": r["source"],
                "source_detail": r["source_detail"] or r["source"],
                "article_count": r["article_count"],
                "avg_score": round(r["avg_score"] or 0, 1),
            }
            for r in source_rows
        ],
        "dimensions": dimension_stats,
        "reason_keywords": [{"word": w, "count": c} for w, c in top_keywords],
    }
