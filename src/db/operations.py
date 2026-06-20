# src/db/operations.py
import json
from pathlib import Path
from datetime import datetime, timedelta
import yaml
from ..core.database import Database
from ..core.time import now_bj, now_bj_iso, today_bj
from ..graph.state import AnalyzedItem, CostRecord, ReviewedItem, RawItem


def date_window_modifier(days: int) -> str:
    return f"-{max(days - 1, 0)} days"


def _trend_window_modifier(trend_window: str) -> str:
    value = trend_window.strip().lower()
    if len(value) < 2 or not value[:-1].isdigit() or value[-1] not in {"d", "w", "m"}:
        return "-13 days"

    amount = max(int(value[:-1]), 1)
    unit = value[-1]
    if unit == "d":
        return date_window_modifier(amount)
    if unit == "w":
        return date_window_modifier(amount * 7)
    return f"-{max(amount - 1, 0)} months"


def _load_monthly_budget(default: float = 10.0) -> float:
    config_path = Path(__file__).resolve().parents[2] / "config" / "agents.yaml"
    try:
        data = yaml.safe_load(config_path.read_text()) or {}
        return float(data.get("budget", {}).get("monthly", default))
    except (OSError, TypeError, ValueError):
        return default


def _decode_json_field(value: str, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _deep_report_row(row) -> dict:
    item = dict(row)
    item["report_json"] = _decode_json_field(item.get("report_json", ""), {})
    item["evidence_json"] = _decode_json_field(item.get("evidence_json", ""), [])
    item["tech_stack_json"] = _decode_json_field(item.get("tech_stack_json", ""), {})
    return item


def _deep_report_list_row(row) -> dict:
    item = dict(row)
    item["report_tech_stack"] = _decode_json_field(item.get("report_tech_stack", ""), [])
    item["tech_stack_json"] = _decode_json_field(item.get("tech_stack_json", ""), {})
    return item


async def save_article(db: Database, raw: RawItem, analyzed: AnalyzedItem, reviewed: ReviewedItem, cost: float, tokens: int) -> int | None:
    """保存文章，返回 article id（新插入或已存在行的 id）"""
    now = now_bj_iso()
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
                analysis_cost=?, analysis_tokens=?, updated_at=?
            WHERE url=?
        """, (analyzed.title, raw.description, analyzed.summary, reviewed.total_score,
              reviewed.verdict, analyzed.retry_count, extra, cost, tokens, now, raw.url))
        await db.commit()
        return existing["id"]
    else:
        await db.execute("""
            INSERT INTO articles
            (title, url, description, summary, source, source_detail,
             relevance_score, status, retry_count, collected_at, published_at, extra_data,
             analysis_cost, analysis_tokens, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*params, now, now))
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
    now = now_bj_iso()
    await db.execute("INSERT INTO pipeline_runs (id, status, started_at, trigger) VALUES (?, 'running', ?, ?)", (run_id, now, trigger))
    await db.commit()


async def end_pipeline_run(db: Database, run_id: str, status: str, summary: str):
    now = now_bj_iso()
    await db.execute("UPDATE pipeline_runs SET ended_at=?, status=?, summary=? WHERE id=?", (now, status, summary, run_id))
    await db.commit()


async def record_pipeline_event(
    db: Database,
    *,
    run_id: str,
    phase: str,
    event: str,
    level: str = "info",
    status: str = "",
    source_id: str = "",
    source: str = "",
    source_detail: str = "",
    ref_url: str = "",
    title: str = "",
    agent: str = "",
    provider: str = "",
    model: str = "",
    attempt_no: int | None = None,
    latency_ms: int | None = None,
    cost: float | None = None,
    tokens: int | None = None,
    message: str = "",
    payload: dict | None = None,
) -> int:
    payload_json = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":"))
    await db.execute(
        """
        INSERT INTO pipeline_events
        (run_id, ts, phase, event, level, status, source_id, source, source_detail,
         ref_url, title, agent, provider, model, attempt_no, latency_ms, cost, tokens,
         message, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            now_bj_iso(),
            phase,
            event,
            level,
            status,
            source_id,
            source,
            source_detail,
            ref_url,
            title,
            agent,
            provider,
            model,
            attempt_no,
            latency_ms,
            cost,
            tokens,
            message,
            payload_json,
        ),
    )
    await db.commit()
    row = await db.fetch_one("SELECT last_insert_rowid() as id")
    return row["id"] if row else 0


async def save_cost_log(db: Database, run_id: str, record: CostRecord):
    await db.execute("""
        INSERT INTO cost_logs
        (run_id, agent, provider, model, tokens_in, tokens_out, cost, ref_url,
         source, source_detail, source_id, status, error, latency_ms, attempt_no,
         prompt_name, prompt_version, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        run_id, record.agent, record.provider, record.model,
        record.tokens_in, record.tokens_out, record.cost, record.ref_url,
        record.source, record.source_detail, record.source_id,
        record.status, record.error, record.latency_ms, record.attempt_no,
        record.prompt_name, record.prompt_version, now_bj_iso(),
    ))
    await db.commit()


async def get_today_llm_spend(db: Database) -> tuple[float, dict[str, float]]:
    rows = await db.fetch_all("""
        SELECT provider, COALESCE(SUM(cost), 0) AS cost
        FROM cost_logs
        WHERE date(created_at) = ?
        GROUP BY provider
    """, (today_bj(),))
    provider_spend = {
        row["provider"]: float(row["cost"] or 0)
        for row in rows
        if row["provider"]
    }
    return sum(provider_spend.values()), provider_spend


async def record_collection_item(
    db: Database,
    *,
    run_id: str,
    url: str,
    title: str,
    source: str,
    source_id: str,
    source_detail: str = "",
    status: str,
    reason: str = "",
    raw_metadata: dict | None = None,
    article_id: int | None = None,
):
    metadata_json = json.dumps(raw_metadata or {}, ensure_ascii=False)
    await db.execute("""
        INSERT INTO collection_items
        (run_id, url, title, source, source_id, source_detail, status, reason, raw_metadata, article_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, url) DO UPDATE SET
            title=excluded.title,
            source=excluded.source,
            source_id=excluded.source_id,
            source_detail=excluded.source_detail,
            status=excluded.status,
            reason=excluded.reason,
            raw_metadata=excluded.raw_metadata,
            article_id=COALESCE(excluded.article_id, collection_items.article_id),
            updated_at=datetime('now', '+8 hours')
    """, (
        run_id,
        url,
        title,
        source,
        source_id,
        source_detail,
        status,
        reason,
        metadata_json,
        article_id,
    ))
    await db.commit()


async def save_deep_report(
    db: Database,
    *,
    repo_url: str,
    repo_name: str,
    article_id: int | None,
    run_id: str,
    commit_sha: str,
    status: str,
    candidate_score: int,
    trigger_reason: str,
    report_json: dict,
    report_markdown: str,
    evidence_json: list,
    tech_stack_json: dict,
    file_tree_summary: str,
    analysis_cost: float,
    analysis_tokens: int,
    error: str,
    report_version: int = 2,
) -> int:
    now = now_bj_iso()
    cursor = await db.execute("""
        INSERT INTO deep_reports
        (repo_url, repo_name, article_id, run_id, commit_sha, status, candidate_score,
         trigger_reason, report_json, report_markdown, evidence_json, tech_stack_json,
         file_tree_summary, analysis_cost, analysis_tokens, error, created_at, updated_at,
         report_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo_url, commit_sha, report_version) DO UPDATE SET
            repo_name=excluded.repo_name,
            article_id=excluded.article_id,
            run_id=excluded.run_id,
            status=excluded.status,
            candidate_score=excluded.candidate_score,
            trigger_reason=excluded.trigger_reason,
            report_json=excluded.report_json,
            report_markdown=excluded.report_markdown,
            evidence_json=excluded.evidence_json,
            tech_stack_json=excluded.tech_stack_json,
            file_tree_summary=excluded.file_tree_summary,
            analysis_cost=excluded.analysis_cost,
            analysis_tokens=excluded.analysis_tokens,
            error=excluded.error,
            updated_at=excluded.updated_at
        WHERE NOT (deep_reports.status = 'completed' AND excluded.status = 'failed')
        RETURNING id
    """, (
        repo_url,
        repo_name,
        article_id,
        run_id,
        commit_sha,
        status,
        candidate_score,
        trigger_reason,
        json.dumps(report_json, ensure_ascii=False),
        report_markdown,
        json.dumps(evidence_json, ensure_ascii=False),
        json.dumps(tech_stack_json, ensure_ascii=False),
        file_tree_summary,
        analysis_cost,
        analysis_tokens,
        error,
        now,
        now,
        report_version,
    ))
    row = await cursor.fetchone()
    await db.commit()
    if row:
        return row["id"]
    existing = await db.fetch_one(
        """
        SELECT id FROM deep_reports
        WHERE repo_url = ? AND commit_sha = ? AND report_version = ?
        """,
        (repo_url, commit_sha, report_version),
    )
    return existing["id"] if existing else 0


async def get_deep_report(db: Database, report_id: int) -> dict | None:
    row = await db.fetch_one("SELECT * FROM deep_reports WHERE id = ?", (report_id,))
    return _deep_report_row(row) if row else None


async def get_completed_deep_report(db: Database, report_id: int) -> dict | None:
    row = await db.fetch_one(
        """
        SELECT * FROM deep_reports
        WHERE id = ?
          AND status = 'completed'
          AND report_version = (
              SELECT public_version FROM deep_report_settings WHERE id = 1
          )
        """,
        (report_id,),
    )
    return _deep_report_row(row) if row else None


async def get_latest_deep_report(db: Database) -> dict | None:
    row = await db.fetch_one(
        """
        SELECT * FROM deep_reports
        WHERE status = 'completed'
          AND report_version = (
              SELECT public_version FROM deep_report_settings WHERE id = 1
          )
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """
    )
    return _deep_report_row(row) if row else None


async def get_public_deep_report_version(db: Database) -> int:
    row = await db.fetch_one(
        "SELECT public_version FROM deep_report_settings WHERE id = 1"
    )
    return int(row["public_version"])


async def set_public_deep_report_version(db: Database, version: int) -> None:
    await db.execute(
        "UPDATE deep_report_settings SET public_version = ? WHERE id = 1",
        (version,),
    )
    await db.commit()


async def list_deep_reports_for_rebuild(
    db: Database,
    *,
    repo_url: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    params: list = []
    if repo_url:
        sql = """
            SELECT * FROM deep_reports
            WHERE repo_url = ?
              AND (
                  (report_version = 1 AND status = 'completed')
                  OR (report_version = 2 AND status = 'failed')
              )
            ORDER BY report_version DESC, id DESC
            LIMIT 1
        """
        params.append(repo_url)
    else:
        sql = """
            SELECT * FROM deep_reports
            WHERE report_version = 1 AND status = 'completed'
            ORDER BY id
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

    rows = await db.fetch_all(sql, tuple(params))
    return [_deep_report_row(row) for row in rows]


async def delete_deep_reports_by_version(db: Database, version: int) -> None:
    await db.execute(
        "DELETE FROM deep_reports WHERE report_version = ?",
        (version,),
    )
    await db.commit()


async def delete_failed_deep_reports_for_repo(
    db: Database,
    repo_url: str,
    *,
    keep_report_id: int,
) -> None:
    await db.execute(
        """
        DELETE FROM deep_reports
        WHERE repo_url = ?
          AND report_version = 2
          AND status = 'failed'
          AND id != ?
        """,
        (repo_url, keep_report_id),
    )
    await db.commit()


async def switch_public_deep_reports_to_v2(db: Database) -> None:
    await db._conn.execute("BEGIN")
    try:
        await db._conn.execute(
            "UPDATE deep_report_settings SET public_version = 2 WHERE id = 1"
        )
        await db._conn.execute(
            "DELETE FROM deep_reports WHERE report_version = 1"
        )
        await db._conn.commit()
    except Exception:
        await db._conn.rollback()
        raise


async def list_deep_reports(db: Database, page: int = 1, page_size: int = 20) -> dict:
    page = max(page, 1)
    page_size = max(page_size, 1)
    offset = (page - 1) * page_size

    total = await db.fetch_one("SELECT COUNT(*) as c FROM deep_reports")
    rows = await db.fetch_all(
        "SELECT * FROM deep_reports ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    )
    return {
        "items": [_deep_report_row(row) for row in rows],
        "total": total["c"] if total else 0,
        "page": page,
        "page_size": page_size,
    }


async def list_completed_deep_reports(db: Database, page: int = 1, page_size: int = 20) -> dict:
    page = max(page, 1)
    page_size = max(page_size, 1)
    offset = (page - 1) * page_size

    total = await db.fetch_one(
        """
        SELECT COUNT(*) as c
        FROM deep_reports
        WHERE status = 'completed'
          AND report_version = (
              SELECT public_version FROM deep_report_settings WHERE id = 1
          )
        """
    )
    rows = await db.fetch_all(
        """
        SELECT id, repo_url, repo_name, status, candidate_score, trigger_reason,
               commit_sha, created_at, updated_at, tech_stack_json, report_version,
               CASE
                   WHEN json_valid(report_json)
                   THEN json_extract(report_json, '$.summary')
                   ELSE ''
               END AS report_summary,
               CASE
                   WHEN json_valid(report_json)
                   THEN json_extract(report_json, '$.tech_stack')
                   ELSE '[]'
               END AS report_tech_stack
        FROM deep_reports
        WHERE status = 'completed'
          AND report_version = (
              SELECT public_version FROM deep_report_settings WHERE id = 1
          )
        ORDER BY updated_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )
    return {
        "items": [_deep_report_list_row(row) for row in rows],
        "total": total["c"] if total else 0,
        "page": page,
        "page_size": page_size,
    }


async def upsert_pipeline_source_run(db: Database, stats: dict):
    await db.execute("""
        INSERT INTO pipeline_source_runs
        (run_id, source_id, source, source_detail, collected, new_items, dedup_skipped,
         analyzed, analysis_failed, approved, retry, discarded, inserted, failed, cost, tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, source_id) DO UPDATE SET
            source=excluded.source,
            source_detail=excluded.source_detail,
            collected=excluded.collected,
            new_items=excluded.new_items,
            dedup_skipped=excluded.dedup_skipped,
            analyzed=excluded.analyzed,
            analysis_failed=excluded.analysis_failed,
            approved=excluded.approved,
            retry=excluded.retry,
            discarded=excluded.discarded,
            inserted=excluded.inserted,
            failed=excluded.failed,
            cost=excluded.cost,
            tokens=excluded.tokens,
            updated_at=datetime('now', '+8 hours')
    """, (
        stats["run_id"],
        stats["source_id"],
        stats["source"],
        stats.get("source_detail", ""),
        stats.get("collected", 0),
        stats.get("new_items", 0),
        stats.get("dedup_skipped", 0),
        stats.get("analyzed", 0),
        stats.get("analysis_failed", 0),
        stats.get("approved", 0),
        stats.get("retry", 0),
        stats.get("discarded", 0),
        stats.get("inserted", 0),
        stats.get("failed", 0),
        stats.get("cost", 0.0),
        stats.get("tokens", 0),
    ))


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
        where.append("a.collected_at >= date('now', '+8 hours', ?)")
        params.append(date_window_modifier(days))
    return " AND ".join(where), params


async def get_article_tags(db: Database, article_id: int) -> list[str]:
    rows = await db.fetch_all(
        "SELECT t.name FROM tags t JOIN article_tags at ON t.id=at.tag_id WHERE at.article_id=? ORDER BY t.name",
        (article_id,),
    )
    return [r["name"] for r in rows]


def _article_dimensions(extra_data: str | None) -> dict:
    data = _decode_json_field(extra_data or "", {})
    raw_dimensions = data.get("dimensions", {})
    definitions = (
        ("ai_relevance", "ai_relevance", 40),
        ("content_depth", "content_depth", 30),
        ("info_density", "info_density", 15),
        ("timeliness", "timeliness", 15),
    )
    dimensions = {}
    for name, key, max_score in definitions:
        value = raw_dimensions.get(key, {})
        if name == "info_density" and not value:
            value = raw_dimensions.get("information_density", {})
        if not isinstance(value, dict) or not value:
            continue
        dimensions[name] = {
            "score": value.get("score", 0),
            "max_score": max_score,
            "reason": value.get("reason", ""),
        }
    return dimensions


async def get_article_detail(db: Database, article_id: int) -> dict | None:
    row = await db.fetch_one("SELECT * FROM articles WHERE id = ?", (article_id,))
    if not row:
        return None

    article = dict(row)
    article["tags"] = await get_article_tags(db, article_id)
    article["dimensions"] = _article_dimensions(article.pop("extra_data", None))

    report = await db.fetch_one(
        """
        SELECT id, repo_name, candidate_score, trigger_reason
        FROM deep_reports
        WHERE article_id = ?
          AND status = 'completed'
          AND report_version = (
              SELECT public_version FROM deep_report_settings WHERE id = 1
          )
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (article_id,),
    )
    if report:
        article["deep_report"] = {
            **dict(report),
            "url": f"/deep-report.html?id={report['id']}",
        }
    else:
        article["deep_report"] = None
    return article


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
    period = await db.fetch_one("SELECT COUNT(*) as c FROM articles WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)", (date_window_modifier(days),))
    source_dist = await db.fetch_all("SELECT source, COUNT(*) as c FROM articles WHERE status='approved' GROUP BY source ORDER BY c DESC")
    cost_period = await db.fetch_one("SELECT COALESCE(SUM(cost),0) as t FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?)", (date_window_modifier(days),))
    cost_total = await db.fetch_one("SELECT COALESCE(SUM(cost),0) as t FROM cost_logs")
    daily_cost = await db.fetch_all("SELECT date(created_at) as date, SUM(cost) as cost, COUNT(*) as articles FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?) GROUP BY date(created_at) ORDER BY date", (date_window_modifier(days),))
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
    today = now_bj().strftime("%Y%m%d")
    backup_file = Path(backup_dir) / f"knowledge-{today}.db"
    await db.backup(str(backup_file))

    # 清理 7 天前
    cutoff = now_bj().replace(tzinfo=None) - timedelta(days=7)
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
        WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)
        GROUP BY bucket
    """, (date_window_modifier(days),))

    # 来源细分评分
    source_scores = await db.fetch_all("""
        SELECT source, source_detail,
               COUNT(*) as article_count,
               AVG(relevance_score) as avg_score
        FROM articles
        WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)
        GROUP BY source, source_detail
        ORDER BY avg_score DESC
    """, (date_window_modifier(days),))

    # 标签云
    top_tags = await db.fetch_all("""
        SELECT t.name, COUNT(*) as count
        FROM tags t JOIN article_tags at ON t.id=at.tag_id
        JOIN articles a ON a.id=at.article_id
        WHERE a.status='approved' AND a.collected_at >= date('now', '+8 hours', ?)
        GROUP BY t.id
        ORDER BY count DESC LIMIT 20
    """, (date_window_modifier(days),))

    # 近 7 个自然日 vs 前 7 个自然日
    this_week = await db.fetch_one("""
        SELECT COUNT(*) as c FROM articles
        WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)
    """, (date_window_modifier(7),))
    last_week = await db.fetch_one("""
        SELECT COUNT(*) as c FROM articles
        WHERE collected_at >= date('now', '+8 hours', ?) AND collected_at < date('now', '+8 hours', ?)
    """, (date_window_modifier(14), date_window_modifier(7)))

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
    cutoff = date_window_modifier(days)

    # 最新一次 pipeline run
    last_run = await db.fetch_one(
        "SELECT * FROM pipeline_runs WHERE started_at >= date('now', '+8 hours', ?) ORDER BY started_at DESC LIMIT 1",
        (cutoff,),
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
        FROM circuit_events
        WHERE created_at >= date('now', '+8 hours', ?)
        ORDER BY created_at DESC LIMIT 20
    """, (cutoff,))

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
        WHERE created_at >= date('now', '+8 hours', ?)
        GROUP BY date(created_at), provider
        ORDER BY date
    """, (date_window_modifier(days),))

    # Agent 费用分解（按日）
    agent_daily = await db.fetch_all("""
        SELECT date(created_at) as date, agent,
               SUM(cost) as cost, SUM(tokens_in+tokens_out) as tokens
        FROM cost_logs
        WHERE created_at >= date('now', '+8 hours', ?)
        GROUP BY date(created_at), agent
        ORDER BY date
    """, (date_window_modifier(days),))

    # 周期总花费
    period_cost = await db.fetch_one("""
        SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs
        WHERE created_at >= date('now', '+8 hours', ?)
    """, (date_window_modifier(days),))

    # 周期总 token
    period_tokens = await db.fetch_one("""
        SELECT COALESCE(SUM(tokens_in + tokens_out), 0) as total FROM cost_logs
        WHERE created_at >= date('now', '+8 hours', ?)
    """, (date_window_modifier(days),))

    # per-provider 汇总
    provider_summary = await db.fetch_all("""
        SELECT provider, SUM(cost) as total_cost,
               SUM(tokens_in) as total_in, SUM(tokens_out) as total_out
        FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?)
        GROUP BY provider
    """, (date_window_modifier(days),))

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


async def get_consumption_detail_stats(
    db: Database,
    period: str = "week",
    trend_window: str | None = None,
    monthly_budget: float | None = None,
) -> dict:
    """
    资源消耗详细统计（Phase 2）
    period 表示日期窗口：
    day = 今天；week = 近 7 个自然日；month = 近 30 个自然日。
    trend_window 表示趋势回看窗口：day 默认 14d，week 默认 12w，month 默认 12m。
    """
    window_map = {"day": "-0 days", "week": "-6 days", "month": "-29 days"}
    window = window_map.get(period, "-6 days")
    trend_window = trend_window or {"day": "14d", "week": "12w", "month": "12m"}.get(period, "12w")
    trend_cutoff = _trend_window_modifier(trend_window)

    # 1. 周期总花费和日均
    period_cost = await db.fetch_one("""
        SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs
        WHERE created_at >= date('now', '+8 hours', ?)
    """, (window,))

    period_days = await db.fetch_one("""
        SELECT COUNT(DISTINCT date(created_at)) as days FROM cost_logs
        WHERE created_at >= date('now', '+8 hours', ?)
    """, (window,))

    # 2. Token 效率
    period_tokens = await db.fetch_one("""
        SELECT COALESCE(SUM(tokens_in + tokens_out), 0) as total FROM cost_logs
        WHERE created_at >= date('now', '+8 hours', ?)
    """, (window,))

    # 3. 花费趋势（按周，支持日/月切换）
    if period == "day":
        trend_sql = """
            SELECT date(created_at) as label,
                   SUM(cost) as cost, COUNT(*) as llm_calls
            FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?)
            GROUP BY date(created_at) ORDER BY label
        """
    elif period == "week":
        trend_sql = """
            SELECT strftime('%Y-W%W', created_at) as label,
                   SUM(cost) as cost, COUNT(*) as llm_calls
            FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?)
            GROUP BY label ORDER BY label
        """
    else:  # month
        trend_sql = """
            SELECT strftime('%Y-%m', created_at) as label,
                   SUM(cost) as cost, COUNT(*) as llm_calls
            FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?)
            GROUP BY label ORDER BY label
        """

    trend = await db.fetch_all(trend_sql, (trend_cutoff,))

    # 4. 来源费用构成（按文章真实来源归因，历史数据回退到 agent 推断）
    source_expr = """
        CASE
            WHEN cl.source = 'rss' AND NULLIF(TRIM(cl.source_detail), '') IS NOT NULL THEN cl.source_detail
            WHEN NULLIF(TRIM(cl.source), '') IS NOT NULL THEN cl.source
            WHEN a.source = 'rss' AND NULLIF(TRIM(a.source_detail), '') IS NOT NULL THEN a.source_detail
            WHEN NULLIF(TRIM(a.source), '') IS NOT NULL THEN a.source
            WHEN cl.ref_url LIKE 'https://36kr.com/%' OR cl.ref_url LIKE 'http://36kr.com/%' THEN '36氪'
            WHEN cl.ref_url LIKE 'https://www.huxiu.com/%' OR cl.ref_url LIKE 'http://www.huxiu.com/%' THEN '虎嗅'
            WHEN cl.ref_url LIKE 'https://juejin.cn/%' OR cl.ref_url LIKE 'https://api.juejin.cn/%' THEN '稀土掘金'
            WHEN cl.ref_url LIKE 'https://www.ithome.com/%' OR cl.ref_url LIKE 'http://www.ithome.com/%' THEN 'IT之家'
            WHEN cl.ref_url LIKE 'https://techcrunch.com/%' OR cl.ref_url LIKE 'http://techcrunch.com/%' THEN 'TechCrunch AI'
            WHEN cl.ref_url LIKE 'https://www.theverge.com/%' OR cl.ref_url LIKE 'http://www.theverge.com/%' THEN 'The Verge AI'
            WHEN cl.ref_url LIKE 'https://arstechnica.com/%' OR cl.ref_url LIKE 'http://arstechnica.com/%' THEN 'Ars Technica'
            WHEN cl.ref_url LIKE 'https://www.reuters.com/%' OR cl.ref_url LIKE 'http://www.reuters.com/%' THEN 'Reuters Science'
            WHEN cl.ref_url LIKE 'https://www.producthunt.com/%' OR cl.ref_url LIKE 'http://www.producthunt.com/%' THEN 'Product Hunt'
            WHEN cl.ref_url LIKE 'https://github.com/%' OR cl.ref_url LIKE 'http://github.com/%' THEN 'github'
            WHEN cl.ref_url LIKE 'https://arxiv.org/%' OR cl.ref_url LIKE 'http://arxiv.org/%' THEN 'arxiv'
            WHEN cl.agent LIKE '%_analyzer' THEN SUBSTR(cl.agent, 1, LENGTH(cl.agent) - 9)
            WHEN cl.agent = 'reviewer' THEN 'review'
            ELSE cl.agent
        END
    """
    if period == "day":
        source_trend = await db.fetch_all(f"""
            SELECT
                {source_expr} as source,
                CASE WHEN cl.agent LIKE '%_analyzer' THEN 'analyze' ELSE 'review' END as type,
                date(cl.created_at) as label,
                SUM(cl.cost) as cost
            FROM cost_logs cl
            LEFT JOIN articles a ON a.url = cl.ref_url
            WHERE cl.created_at >= date('now', '+8 hours', ?)
            GROUP BY 1, 2, 3
            ORDER BY label
        """, (trend_cutoff,))
    elif period == "week":
        source_trend = await db.fetch_all(f"""
            SELECT
                {source_expr} as source,
                CASE WHEN cl.agent LIKE '%_analyzer' THEN 'analyze' ELSE 'review' END as type,
                strftime('%Y-W%W', cl.created_at) as label,
                SUM(cl.cost) as cost
            FROM cost_logs cl
            LEFT JOIN articles a ON a.url = cl.ref_url
            WHERE cl.created_at >= date('now', '+8 hours', ?)
            GROUP BY 1, 2, 3 ORDER BY label
        """, (trend_cutoff,))
    else:
        source_trend = await db.fetch_all(f"""
            SELECT
                {source_expr} as source,
                CASE WHEN cl.agent LIKE '%_analyzer' THEN 'analyze' ELSE 'review' END as type,
                strftime('%Y-%m', cl.created_at) as label,
                SUM(cl.cost) as cost
            FROM cost_logs cl
            LEFT JOIN articles a ON a.url = cl.ref_url
            WHERE cl.created_at >= date('now', '+8 hours', ?)
            GROUP BY 1, 2, 3 ORDER BY label
        """, (trend_cutoff,))

    # 5. Provider 费用趋势
    if period == "day":
        provider_trend = await db.fetch_all("""
            SELECT date(created_at) as label, provider, SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?)
            GROUP BY provider, date(created_at) ORDER BY label
        """, (trend_cutoff,))
    elif period == "week":
        provider_trend = await db.fetch_all("""
            SELECT strftime('%Y-W%W', created_at) as label, provider, SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?)
            GROUP BY provider, label ORDER BY label
        """, (trend_cutoff,))
    else:
        provider_trend = await db.fetch_all("""
            SELECT strftime('%Y-%m', created_at) as label, provider, SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?)
            GROUP BY provider, label ORDER BY label
        """, (trend_cutoff,))

    # 6. 预算进度
    budget = monthly_budget if monthly_budget is not None else _load_monthly_budget()
    budget = max(float(budget), 0.01)
    monthly_cost = await db.fetch_one("""
        SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs
        WHERE created_at >= date('now', '+8 hours', '-29 days')
    """)

    return {
        "period_cost": round(period_cost["total"] if period_cost else 0, 4),
        "period_days": period_days["days"] if period_days else 0,
        "period_tokens": period_tokens["total"] if period_tokens else 0,
        "daily_avg": round((period_cost["total"] or 0) / max(period_days["days"] if period_days else 1, 1), 4),
        "cost_per_million_tokens": round((period_cost["total"] or 0) / max(period_tokens["total"] if period_tokens else 1, 1) * 1e6, 2),
        "budget_progress": round((monthly_cost["total"] or 0) / budget, 3),
        "budget_remaining": round(budget - (monthly_cost["total"] or 0), 2),
        "monthly_budget": round(budget, 2),
        "trend_window": trend_window,
        "trend": [
            {
                "label": r["label"],
                "cost": r["cost"],
                "llm_calls": r["llm_calls"],
                "articles": r["llm_calls"],
            }
            for r in trend
        ] if trend else [],
        "source_trend": [{"source": r["source"], "type": r["type"], "label": r["label"], "cost": r["cost"]} for r in source_trend] if source_trend else [],
        "provider_trend": [{"provider": r["provider"], "label": r["label"], "cost": r["cost"]} for r in provider_trend] if provider_trend else [],
    }


async def record_source_health(db: Database, record: "CollectResult"):
    """记录数据源健康数据"""
    from ..graph.state import CollectResult as CR
    today = today_bj()
    has_review_stats = record.approved > 0 or record.rejected > 0 or record.avg_score is not None
    total_collected = 0 if has_review_stats else record.total
    await db.execute("""
        INSERT INTO source_health (source_id, date, total_collected, approved, rejected, failed, avg_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, date) DO UPDATE SET
            total_collected=source_health.total_collected + excluded.total_collected,
            approved=source_health.approved + excluded.approved,
            rejected=source_health.rejected + excluded.rejected,
            failed=source_health.failed + excluded.failed,
            avg_score=CASE
                WHEN excluded.avg_score IS NULL OR excluded.approved = 0 THEN source_health.avg_score
                WHEN source_health.avg_score IS NULL OR source_health.approved = 0 THEN excluded.avg_score
                ELSE ROUND(
                    (source_health.avg_score * source_health.approved + excluded.avg_score * excluded.approved)
                    / (source_health.approved + excluded.approved),
                    1
                )
            END,
            recorded_at=datetime('now', '+8 hours')
    """, (record.source_id, today, total_collected, record.approved, record.rejected, record.failed, record.avg_score))
    await db.commit()


async def batch_save_github_snapshots(db: Database, items: list[RawItem]):
    """批量写入 GitHub repo 快照（同一 repo_url + date 唯一）"""
    today = today_bj()
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
    """计算 repos 在过去 N 天内的 star 增速，返回增速 >= min_velocity 的 repo_url 集合。"""
    rows = await db.fetch_all("""
        WITH latest AS (
            SELECT repo_url, MAX(snapshot_date) AS latest_date
            FROM github_repo_snapshots
            GROUP BY repo_url
        ),
        baseline AS (
            SELECT s.repo_url, MAX(s.snapshot_date) AS baseline_date
            FROM github_repo_snapshots s
            JOIN latest l ON l.repo_url = s.repo_url
            WHERE s.snapshot_date <= date(l.latest_date, '-' || :days || ' days')
            GROUP BY s.repo_url
        )
        SELECT s1.repo_url,
               (s1.stars - s0.stars) / (:days * 1.0) AS velocity
        FROM latest l
        JOIN baseline b ON b.repo_url = l.repo_url
        JOIN github_repo_snapshots s1
          ON s1.repo_url = l.repo_url
         AND s1.snapshot_date = l.latest_date
        JOIN github_repo_snapshots s0
          ON s0.repo_url = b.repo_url
         AND s0.snapshot_date = b.baseline_date
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
    cutoff = date_window_modifier(days)

    total_articles = await db.fetch_one(
        "SELECT COUNT(*) as c FROM articles WHERE status='approved'"
    )
    period_status = await db.fetch_one("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved,
            AVG(CASE WHEN status='approved' THEN relevance_score END) as avg_score
        FROM articles
        WHERE collected_at >= date('now', '+8 hours', ?)
    """, (cutoff,))
    period_total = period_status["total"] if period_status else 0
    period_approved = period_status["approved"] if period_status and period_status["approved"] else 0
    avg_score = period_status["avg_score"] if period_status and period_status["avg_score"] else 0

    # 1. 内容完整性指标
    summary_coverage = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)) as rate
        FROM articles WHERE status='approved' AND summary IS NOT NULL AND summary != '' AND collected_at >= date('now', '+8 hours', ?)
    """, (cutoff, cutoff))

    desc_len = await db.fetch_one("""
        SELECT AVG(LENGTH(description)) as avg_len FROM articles WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)
    """, (cutoff,))

    summary_len = await db.fetch_one("""
        SELECT AVG(LENGTH(summary)) as avg_len FROM articles WHERE status='approved' AND summary IS NOT NULL AND collected_at >= date('now', '+8 hours', ?)
    """, (cutoff,))

    # 2. 审核效率指标
    one_pass = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)) as rate
        FROM articles WHERE status='approved' AND retry_count = 0 AND collected_at >= date('now', '+8 hours', ?)
    """, (cutoff, cutoff))

    retry_rate = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE collected_at >= date('now', '+8 hours', ?)) as rate
        FROM articles WHERE status='retry' AND collected_at >= date('now', '+8 hours', ?)
    """, (cutoff, cutoff))

    exhausted_rate = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE collected_at >= date('now', '+8 hours', ?)) as rate
        FROM articles WHERE retry_count >= 2 AND collected_at >= date('now', '+8 hours', ?)
    """, (cutoff, cutoff))

    # 3. 标签覆盖指标
    tagged_rate = await db.fetch_one("""
        SELECT COUNT(DISTINCT at.article_id) * 1.0 / (SELECT COUNT(*) FROM articles WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)) as rate
        FROM article_tags at
        JOIN articles a ON a.id = at.article_id
        WHERE a.collected_at >= date('now', '+8 hours', ?)
    """, (cutoff, cutoff))

    avg_tags = await db.fetch_one("""
        SELECT AVG(tag_count) as avg FROM (
            SELECT COUNT(*) as tag_count FROM article_tags at
            JOIN articles a ON a.id = at.article_id
            WHERE a.collected_at >= date('now', '+8 hours', ?)
            GROUP BY at.article_id
        )
    """, (cutoff,))

    # 4. 来源质量分布
    source_rows = await db.fetch_all("""
        SELECT source, source_detail, COUNT(*) as article_count, AVG(relevance_score) as avg_score
        FROM articles
        WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)
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
        score_expr = f"JSON_EXTRACT(extra_data, '$.dimensions.{json_key}.score')"
        if name == "info_density":
            score_expr = (
                "COALESCE("
                "JSON_EXTRACT(extra_data, '$.dimensions.info_density.score'), "
                "JSON_EXTRACT(extra_data, '$.dimensions.information_density.score')"
                ")"
            )
        stats = await db.fetch_one(f"""
            SELECT
                AVG({score_expr}) as avg_score,
                COUNT(CASE WHEN {score_expr} >= ? THEN 1 END) * 1.0 / NULLIF(COUNT({score_expr}), 0) as high_rate,
                COUNT(CASE WHEN {score_expr} >= ? AND {score_expr} < ? THEN 1 END) * 1.0 / NULLIF(COUNT({score_expr}), 0) as mid_rate,
                COUNT(CASE WHEN {score_expr} < ? THEN 1 END) * 1.0 / NULLIF(COUNT({score_expr}), 0) as low_rate
            FROM articles
            WHERE status='approved' AND extra_data IS NOT NULL AND collected_at >= date('now', '+8 hours', ?)
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
        FROM articles WHERE status='approved' AND extra_data IS NOT NULL AND collected_at >= date('now', '+8 hours', ?)
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
