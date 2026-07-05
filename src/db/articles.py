import json

from ..core.database import Database
from ..core.time import now_bj_iso
from ..graph.state import AnalyzedItem, ReviewedItem, RawItem
from .common import date_window_modifier, decode_json_field

CATEGORIES = (
    "模型与基础设施",
    "Agent 与自动化",
    "RAG 与知识系统",
    "开发工具与框架",
    "研究与评测",
    "产品与行业应用",
    "商业与市场",
    "安全与治理",
)

TAG_CATEGORY = {
    "LLM": "模型与基础设施",
    "多模态": "模型与基础设施",
    "AI芯片": "模型与基础设施",
    "Agent": "Agent 与自动化",
    "Coding Agent": "Agent 与自动化",
    "自动化": "Agent 与自动化",
    "RAG": "RAG 与知识系统",
    "知识库": "RAG 与知识系统",
    "数据治理": "RAG 与知识系统",
    "MCP": "开发工具与框架",
    "Tool": "开发工具与框架",
    "Framework": "开发工具与框架",
    "Open Source": "开发工具与框架",
    "Claude Code": "开发工具与框架",
    "Codex": "开发工具与框架",
    "研究": "研究与评测",
    "Benchmark": "研究与评测",
    "Dataset": "研究与评测",
    "医疗AI": "产品与行业应用",
    "具身智能": "产品与行业应用",
    "XR": "产品与行业应用",
    "融资": "商业与市场",
    "产业趋势": "商业与市场",
    "监管": "安全与治理",
    "安全": "安全与治理",
}

TAG_ALIASES = {
    "AI": "模型与基础设施",
    "人工智能": "模型与基础设施",
    "大模型": "LLM",
    "OpenAI": "LLM",
    "ChatGPT": "LLM",
    "ChatGPT Plus": "LLM",
    "Claude": "LLM",
    "GPT-5.5": "LLM",
    "Cerebras": "AI芯片",
    "AI硬件": "AI芯片",
    "摩尔线程": "AI芯片",
    "Tokenmaxxing": "LLM",
    "AI Agent": "Agent",
    "AI/Agent": "Agent",
    "企业代理": "Agent",
    "Agentic Coding": "Coding Agent",
    "AI Editor": "Coding Agent",
    "Codex Skill": "Codex",
    "Linter": "Tool",
    "Markdown": "Tool",
    "Prompt Engineering": "Tool",
    "Programming Language": "Framework",
    "开源": "Open Source",
    "论文解读": "研究",
    "论文写作": "研究",
    "学术诚信": "研究",
    "ArXiv": "研究",
    "计算机视觉": "多模态",
    "AI医疗": "医疗AI",
    "AI智能影像": "医疗AI",
    "百度健康": "医疗AI",
    "大健康": "医疗AI",
    "物理AI": "具身智能",
    "机器人芯片": "AI芯片",
    "低功耗芯片": "AI芯片",
    "VR眼镜": "XR",
    "VITURE": "XR",
    "AI产品": "产品与行业应用",
    "AI人才": "产品与行业应用",
    "AI浓度": "产品与行业应用",
    "AI营销": "产品与行业应用",
    "AI职场趋势": "产品与行业应用",
    "HR科技": "产品与行业应用",
    "人力资源": "产品与行业应用",
    "人才培养": "产品与行业应用",
    "人机共生": "产品与行业应用",
    "业务运营": "产品与行业应用",
    "企业数字化转型": "产品与行业应用",
    "场景落地": "产品与行业应用",
    "工业应用": "产品与行业应用",
    "转化率优化": "产品与行业应用",
    "AI投资": "融资",
    "创业": "融资",
    "产业转型": "产业趋势",
    "产品战略": "产业趋势",
    "科技行业": "产业趋势",
    "预测市场": "商业与市场",
    "数字资产": "商业与市场",
    "内幕交易": "商业与市场",
    "AI监管": "监管",
}


def normalize_tags(tags: list[str]) -> list[str]:
    normalized = []
    seen = set()
    canonical = [TAG_ALIASES.get(tag.strip(), tag.strip()) for tag in tags if tag.strip()]
    has_specific_tag = any(tag in TAG_CATEGORY for tag in canonical)
    has_category = False

    def add(tag: str):
        if tag and tag not in seen:
            seen.add(tag)
            normalized.append(tag)

    for tag in canonical:
        if tag in CATEGORIES:
            if has_specific_tag:
                continue
            add(tag)
            continue
        category = TAG_CATEGORY.get(tag)
        if not category:
            continue
        if not has_category:
            add(category)
            has_category = True
        add(tag)
    return normalized[:3]


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
    for tag_name in normalize_tags(tags):
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
        """
        SELECT t.name
        FROM tags t
        JOIN article_tags at ON t.id=at.tag_id
        WHERE at.article_id=?
        ORDER BY CASE t.name
            WHEN '模型与基础设施' THEN 0
            WHEN 'Agent 与自动化' THEN 1
            WHEN 'RAG 与知识系统' THEN 2
            WHEN '开发工具与框架' THEN 3
            WHEN '研究与评测' THEN 4
            WHEN '产品与行业应用' THEN 5
            WHEN '商业与市场' THEN 6
            WHEN '安全与治理' THEN 7
            ELSE 99
        END, t.name
        """,
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
