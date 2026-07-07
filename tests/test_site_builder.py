import json
import asyncio
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
    assert "listSummary(a.summary || a.description || '')" in app_js


def test_homepage_uses_hn_source_detail_as_label():
    index_html = (ROOT / "src/site/templates/index.html").read_text()
    app_js = (ROOT / "src/site/static/js/app.js").read_text()

    assert "article.source in ['rss', 'hotlist', 'hn']" in index_html
    assert "source === 'hn' && sourceDetail" in app_js


def test_homepage_source_filter_uses_source_id_for_github_subsources():
    app_js = (ROOT / "src/site/static/js/app.js").read_text()

    assert "a.source_id || a.source" in app_js
    assert "github_data_ai" in app_js
    assert "GitHub AI × 数据工程" in app_js
    assert "a.source_id === state.source" in app_js


@pytest.mark.asyncio
async def test_homepage_uses_hotlist_source_detail_as_label(tmp_path, monkeypatch):
    articles = [
        {
            "id": 1,
            "title": "AI 热榜文章",
            "url": "https://example.com/hotlist",
            "description": "description",
            "summary": "summary",
            "source": "hotlist",
            "source_detail": "AIHOT",
            "relevance_score": 90,
            "tags": ["AI"],
            "published_at": "",
            "collected_at": "2026-06-21T10:00:00",
        }
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

    visible_html = (output_dir / "index.html").read_text().split(
        "<script>window.__INIT__", 1
    )[0]
    app_js = (ROOT / "src/site/static/js/app.js").read_text()

    assert '<span class="topic-tag">AIHOT</span>' in visible_html
    assert "source === 'hotlist' && sourceDetail" in app_js
    assert "['rss', 'hotlist', 'hn'].includes(a.source)" in app_js


@pytest.mark.asyncio
async def test_site_builder_publishes_analysis_html_pages(tmp_path, monkeypatch):
    analysis_dir = tmp_path / "docs" / "analysis"
    project_dir = analysis_dir / "architecture"
    project_dir.mkdir(parents=True)
    (project_dir / "index.html").write_text(
        "<!doctype html><title>架构分析</title><h1>架构分析</h1>",
        encoding="utf-8",
    )

    async def fake_search_articles(*args, **kwargs):
        return []

    async def fake_get_stats(*args, **kwargs):
        return {}

    monkeypatch.setattr(builder, "search_articles", fake_search_articles)
    monkeypatch.setattr(builder, "get_stats", fake_get_stats)

    output_dir = tmp_path / "output"
    site_builder = builder.SiteBuilder(
        db=object(),
        output_dir=output_dir,
        template_dir=ROOT / "src/site/templates",
        analysis_dir=analysis_dir,
    )
    await site_builder.build()

    analysis_html = (output_dir / "analysis.html").read_text(encoding="utf-8")
    copied_html = output_dir / "analysis" / "architecture" / "index.html"

    assert 'href="/analysis/architecture/index.html"' in analysis_html
    assert "架构分析" in analysis_html
    assert copied_html.read_text(encoding="utf-8").startswith("<!doctype html>")


@pytest.mark.asyncio
async def test_debounced_builder_tracks_superseded_and_completed_runs():
    class FakeBuilder:
        def __init__(self):
            self.build_count = 0

        async def build(self):
            self.build_count += 1

    statuses = []

    async def on_status(run_id, status, details):
        statuses.append((run_id, status, details))

    fake_builder = FakeBuilder()
    debounced = builder.DebouncedBuilder(
        fake_builder,
        debounce_seconds=0,
        on_status=on_status,
    )

    await debounced.schedule("run_1")
    await debounced.schedule("run_2")
    await debounced._timer

    assert statuses == [
        ("run_1", "queued", "等待 0 秒去抖"),
        ("run_1", "superseded", "被后续流水线 run_2 合并"),
        ("run_2", "queued", "等待 0 秒去抖"),
        ("run_2", "running", "静态站构建中"),
        ("run_2", "completed", "静态站构建完成"),
    ]
    assert fake_builder.build_count == 1


@pytest.mark.asyncio
async def test_debounced_builder_records_failed_build():
    class FailingBuilder:
        async def build(self):
            raise RuntimeError("render failed")

    statuses = []

    async def on_status(run_id, status, details):
        statuses.append((run_id, status, details))

    debounced = builder.DebouncedBuilder(
        FailingBuilder(),
        debounce_seconds=0,
        on_status=on_status,
    )

    await debounced.schedule("run_failed")
    with pytest.raises(RuntimeError, match="render failed"):
        await debounced._timer

    assert statuses[-2:] == [
        ("run_failed", "running", "静态站构建中"),
        ("run_failed", "failed", "render failed"),
    ]


def test_article_detail_uses_shared_safe_renderer():
    base_html = (ROOT / "src/site/templates/base.html").read_text()
    article_html = (ROOT / "src/site/templates/article.html").read_text()
    detail_js = ROOT / "src/site/static/js/article-detail.js"

    assert detail_js.exists()
    assert '/static/js/article-detail.js' in base_html
    assert 'data-article-detail-page' in article_html
    assert "fetch('/api/articles/'" not in article_html
    assert ".innerHTML" not in article_html
    assert "document.createElement" in detail_js.read_text()
    assert ".textContent" in detail_js.read_text()


def test_homepage_contains_article_drawer_and_shareable_links():
    index_html = (ROOT / "src/site/templates/index.html").read_text()
    app_js = (ROOT / "src/site/static/js/app.js").read_text()

    assert 'id="article-detail-drawer"' in index_html
    assert 'data-article-link' in index_html
    assert 'href="/article.html?id={{ article.id }}"' in index_html
    assert "ArticleDetail.openDrawer" in app_js


def test_homepage_supports_local_favorites_view():
    index_html = (ROOT / "src/site/templates/index.html").read_text()
    app_js = (ROOT / "src/site/static/js/app.js").read_text()

    assert 'data-view-filter="all"' in index_html
    assert 'data-view-filter="favorites"' in index_html
    assert "ai_kb_favorite_articles" in app_js
    assert "localStorage" in app_js
    assert "data-favorite-toggle" in app_js
    assert "state.favoritesOnly" in app_js


def test_homepage_supports_pagination_and_hidden_articles():
    index_html = (ROOT / "src/site/templates/index.html").read_text()
    app_js = (ROOT / "src/site/static/js/app.js").read_text()

    assert 'data-view-filter="hidden"' in index_html
    assert 'id="pagination-controls"' in index_html
    assert 'data-page-size' in app_js
    assert "ai_kb_hidden_articles" in app_js
    assert "ai_kb_page_size" in app_js
    assert "hiddenIds" in app_js
    assert "state.page" in app_js
    assert "renderPagination" in app_js


def test_homepage_pagination_is_fixed_bottom_bar():
    index_html = (ROOT / "src/site/templates/index.html").read_text()
    app_js = (ROOT / "src/site/static/js/app.js").read_text()
    css = (ROOT / "src/site/static/css/style.css").read_text()

    assert 'id="page-size-filter"' not in index_html
    assert 'data-page-size' in app_js
    assert "position: fixed" in css
    assert "padding-bottom" in css


def test_homepage_loads_full_article_list_for_filters():
    app_js = (ROOT / "src/site/static/js/app.js").read_text()

    assert "fetch('/data.json')" in app_js
    assert "allArticles" in app_js


def test_homepage_score_tooltip_uses_article_detail_dimensions():
    index_html = (ROOT / "src/site/templates/index.html").read_text()
    app_js = (ROOT / "src/site/static/js/app.js").read_text()
    css = (ROOT / "src/site/static/css/style.css").read_text()

    assert 'id="score-tooltip"' in index_html
    assert "data-score-tooltip" in index_html
    assert "data-score-tooltip" in app_js
    assert "setupScoreTooltip" in app_js
    assert "renderScoreTooltip" in app_js
    assert "developer_utility" in app_js
    assert "项目实用性" in app_js
    assert "`/api/articles/${encodeURIComponent(articleId)}`" in app_js
    assert ".score-tooltip" in css


@pytest.mark.asyncio
async def test_homepage_uses_short_list_summary_without_truncating_data_summary(tmp_path, monkeypatch):
    full_summary = "这是一段用于详情展示的完整中文摘要。" * 12
    articles = [
        {
            "id": 1,
            "title": "长摘要文章",
            "url": "https://example.com/long-summary",
            "description": "Original description",
            "summary": full_summary,
            "source": "rss",
            "source_detail": "测试源",
            "relevance_score": 90,
            "tags": ["AI"],
            "published_at": "",
            "collected_at": "2026-06-20T10:00:00",
        }
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
    data = json.loads((output_dir / "data.json").read_text())

    assert full_summary[:120] in index_html
    assert full_summary[:180] not in index_html.split("<script>window.__INIT__", 1)[0]
    assert data[0]["summary"] == builder.clean_text(full_summary, 200)
