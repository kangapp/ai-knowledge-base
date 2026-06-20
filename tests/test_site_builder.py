import json
from pathlib import Path

import pytest

from src.site import builder


ROOT = Path(__file__).parent.parent


@pytest.mark.asyncio
async def test_homepage_prefers_summary_and_falls_back_to_description(tmp_path, monkeypatch):
    articles = [
        {
            "id": 1,
            "title": "中文摘要文章",
            "url": "https://example.com/summary",
            "description": "Original English description",
            "summary": "这是 Analyzer 生成的中文简介",
            "source": "rss",
            "source_detail": "测试源",
            "relevance_score": 90,
            "tags": ["AI"],
            "published_at": "",
            "collected_at": "2026-06-20T10:00:00",
        },
        {
            "id": 2,
            "title": "摘要缺失文章",
            "url": "https://example.com/fallback",
            "description": "Fallback original description",
            "summary": "",
            "source": "rss",
            "source_detail": "测试源",
            "relevance_score": 86,
            "tags": [],
            "published_at": "",
            "collected_at": "2026-06-20T09:00:00",
        },
    ]

    async def fake_search_articles(*args, **kwargs):
        return articles

    async def fake_get_stats(*args, **kwargs):
        return {}

    monkeypatch.setattr(builder, "search_articles", fake_search_articles)
    monkeypatch.setattr(builder, "get_stats", fake_get_stats)

    output_dir = tmp_path / "output"
    site_builder = builder.SiteBuilder(
        db=object(),
        output_dir=output_dir,
        template_dir=ROOT / "src/site/templates",
    )
    await site_builder.build()

    index_html = (output_dir / "index.html").read_text()
    visible_list_html = index_html.split("<script>window.__INIT__", 1)[0]
    data = json.loads((output_dir / "data.json").read_text())

    assert "这是 Analyzer 生成的中文简介" in visible_list_html
    assert "Original English description" not in visible_list_html
    assert "Fallback original description" in visible_list_html
    assert data[0]["summary"] == "这是 Analyzer 生成的中文简介"
    assert data[0]["description"] == "Original English description"
    assert data[1]["summary"] == "Fallback original description"


def test_homepage_search_matches_summary_and_original_description():
    app_js = (ROOT / "src/site/static/js/app.js").read_text()

    assert "(a.summary || '').toLowerCase().includes(q)" in app_js
    assert "(a.description || '').toLowerCase().includes(q)" in app_js
