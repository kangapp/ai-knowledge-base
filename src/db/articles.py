import json

from ..core.database import Database
from ..core.time import now_bj_iso
from ..graph.state import AnalyzedItem, ReviewedItem, RawItem
from .common import date_window_modifier, decode_json_field


async def save_article(
    db: Database,
    raw: RawItem,
    analyzed: AnalyzedItem,
    reviewed: ReviewedItem,
    cost: float,
    tokens: int,
) -> int | None:
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
    data = decode_json_field(extra_data or "", {})
    raw_dimensions = data.get("dimensions", {})
    article_definitions = (
        ("ai_relevance", "ai_relevance", 40),
        ("content_depth", "content_depth", 30),
        ("info_density", "info_density", 15),
        ("timeliness", "timeliness", 15),
    )
    github_definitions = (
        ("ai_relevance", "ai_relevance", 35),
        ("developer_utility", "developer_utility", 30),
        ("project_signal", "project_signal", 20),
        ("content_clarity", "content_clarity", 15),
    )
    is_github_review = any(
        key in raw_dimensions
        for key in ("developer_utility", "project_signal", "content_clarity")
    )
    definitions = github_definitions if is_github_review else article_definitions
    dimensions = {}
    for name, key, max_score in definitions:
        value = raw_dimensions.get(key, {})
        if not is_github_review and name == "info_density" and not value:
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
    article["deep_report"] = (
        {**dict(report), "url": f"/deep-report.html?id={report['id']}"}
        if report else None
    )
    return article


async def count_articles(db: Database, query: str = "", source: str = "", days: int = 30) -> int:
    where_sql, params = _article_filters(query, source, days)
    if query:
        sql = f"SELECT COUNT(*) as c FROM articles a JOIN articles_fts fts ON a.rowid = fts.rowid WHERE {where_sql}"
    else:
        sql = f"SELECT COUNT(*) as c FROM articles a WHERE {where_sql}"
    row = await db.fetch_one(sql, tuple(params))
    return row["c"] if row else 0


async def search_articles(
    db: Database,
    query: str,
    source: str = "",
    days: int = 30,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    where_sql, params = _article_filters(query, source, days)
    params.extend([limit, offset])
    if query:
        rows = await db.fetch_all(
            f"SELECT a.* FROM articles a JOIN articles_fts fts ON a.rowid = fts.rowid WHERE {where_sql} ORDER BY a.collected_at DESC, a.id ASC LIMIT ? OFFSET ?",
            tuple(params))
    else:
        rows = await db.fetch_all(
            f"SELECT a.* FROM articles a WHERE {where_sql} ORDER BY a.collected_at DESC, a.id ASC LIMIT ? OFFSET ?",
            tuple(params))

    articles_with_tags = []
    for row in rows:
        article = dict(row)
        article["tags"] = await get_article_tags(db, article["id"])
        articles_with_tags.append(article)
    return articles_with_tags
