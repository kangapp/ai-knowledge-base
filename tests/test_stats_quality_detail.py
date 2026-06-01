import json
from pathlib import Path

import pytest

from src.core.database import Database
from src.db.operations import get_quality_detail_stats


_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


async def _insert_article(
    db: Database,
    *,
    title: str,
    url: str,
    source: str,
    source_detail: str,
    score: int,
    retry_count: int,
    dimensions: dict,
):
    await db.execute(
        """
        INSERT INTO articles
        (title, url, description, summary, source, source_detail, relevance_score,
         status, retry_count, collected_at, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'approved', ?, datetime('now', '+8 hours'), ?)
        """,
        (
            title,
            url,
            "description",
            "summary",
            source,
            source_detail,
            score,
            retry_count,
            json.dumps({"dimensions": dimensions}, ensure_ascii=False),
        ),
    )


@pytest.mark.asyncio
async def test_quality_detail_supports_dashboard_contract(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()

        await _insert_article(
            db,
            title="A",
            url="https://example.com/a",
            source="rss",
            source_detail="anthropic",
            score=90,
            retry_count=0,
            dimensions={
                "ai_relevance": {"score": 36, "reason": "核心 LLM"},
                "content_depth": {"score": 25, "reason": "深度原创"},
                "info_density": {"score": 13, "reason": "信息密集"},
                "timeliness": {"score": 12, "reason": "本周"},
            },
        )
        await _insert_article(
            db,
            title="B",
            url="https://example.com/b",
            source="rss",
            source_detail="openai_blog",
            score=60,
            retry_count=1,
            dimensions={
                "ai_relevance": {"score": 20, "reason": "AI 基础设施"},
                "content_depth": {"score": 10, "reason": "简要"},
                "info_density": {"score": 5, "reason": "一般"},
                "timeliness": {"score": 5, "reason": "较早"},
            },
        )
        await db.execute("INSERT INTO tags (name) VALUES ('AI')")
        tag = await db.fetch_one("SELECT id FROM tags WHERE name='AI'")
        article = await db.fetch_one("SELECT id FROM articles WHERE url='https://example.com/a'")
        await db.execute(
            "INSERT INTO article_tags (article_id, tag_id) VALUES (?, ?)",
            (article["id"], tag["id"]),
        )
        await db.commit()

        data = await get_quality_detail_stats(db, "week")

        assert data["summary"]["total_articles"] == 2
        assert data["summary"]["period_articles"] == 2
        assert data["summary"]["avg_score"] == 75.0
        assert data["summary"]["pass_rate"] == 1.0
        assert data["content_quality"]["summary_coverage"] == 1.0
        assert data["tag_coverage"]["tagged_rate"] == 0.5
        assert data["audit_efficiency"]["one_pass_rate"] == 0.5

        assert data["source_quality"][0]["source_detail"] == "anthropic"
        assert data["source_quality"][0]["avg_score"] == 90.0
        assert data["source_quality"][1]["source_detail"] == "openai_blog"

        assert data["dimensions"]["ai_relevance"]["avg_score"] == 28.0
        assert data["dimensions"]["content_depth"]["avg_score"] == 17.5
        assert data["dimensions"]["info_density"]["avg_score"] == 9.0
        assert data["dimensions"]["timeliness"]["avg_score"] == 8.5
        assert data["dimensions"]["ai_relevance"]["high_rate"] == 0.5
        assert data["dimensions"]["ai_relevance"]["mid_rate"] == 0.5
        assert data["dimensions"]["ai_relevance"]["low_rate"] == 0.0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_quality_detail_accepts_legacy_information_density_key(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()

        await _insert_article(
            db,
            title="legacy",
            url="https://example.com/legacy",
            source="github",
            source_detail="org/repo",
            score=80,
            retry_count=0,
            dimensions={
                "ai_relevance": {"score": 35, "reason": "核心 AI"},
                "content_depth": {"score": 20, "reason": "有细节"},
                "information_density": {"score": 11, "reason": "历史 key"},
                "timeliness": {"score": 14, "reason": "本周"},
            },
        )
        await db.commit()

        data = await get_quality_detail_stats(db, "week")

        assert data["dimensions"]["info_density"]["avg_score"] == 11.0
        assert data["dimensions"]["info_density"]["high_rate"] == 0.0
        assert data["dimensions"]["info_density"]["mid_rate"] == 1.0
    finally:
        await db.close()
