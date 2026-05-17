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
    await db.execute("INSERT INTO cost_logs (run_id, agent, provider, model, tokens_in, tokens_out, cost) VALUES (?,?,?,?,?,?,?)",
        (run_id, record.agent, record.provider, record.model, record.tokens_in, record.tokens_out, record.cost))
    await db.commit()


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

    # 查询标签
    articles_with_tags = []
    for r in rows:
        article = dict(r)
        tag_rows = await db.fetch_all(
            "SELECT t.name FROM tags t JOIN article_tags at ON t.id=at.tag_id WHERE at.article_id=?",
            (article["id"],))
        article["tags"] = [t["name"] for t in tag_rows]
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