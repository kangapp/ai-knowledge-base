from pathlib import Path

import pytest

from src.core.database import Database
from src.db.operations import save_deep_report
from src.deep_reports.selector import select_deep_report_candidate
from src.graph.state import AnalyzedItem, RawItem, ReviewedItem

_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


async def _init_db(tmp_path) -> Database:
    db = Database(tmp_path / "deep_reports_selector.db", migrations_dir=_MIGRATIONS_DIR)
    await db.initialize()
    await db.execute(
        "INSERT INTO articles (id, title, url, source, collected_at) VALUES (?, ?, ?, ?, ?)",
        (12, "Tool", "https://github.com/acme/dev-agent", "github", "2026-06-03T10:00:00+08:00"),
    )
    await db.execute(
        "INSERT INTO pipeline_runs (id, started_at, status, trigger) VALUES (?, datetime('now', '+8 hours'), ?, ?)",
        ("run_1", "completed", "test"),
    )
    await db.commit()
    return db


def _raw(
    url: str,
    *,
    title: str = "Dev Agent",
    description: str = "AI coding agent CLI for developer workflow automation",
    source: str = "github",
    source_id: str = "github_ai_devtools",
    source_detail: str = "github trending",
    stars: int = 1800,
    topics=None,
) -> RawItem:
    return RawItem(
        url=url,
        title=title,
        description=description,
        source=source,
        source_detail=source_detail,
        raw_metadata={
            "source_id": source_id,
            "stars": stars,
            "topics": topics if topics is not None else ["agent", "developer-tools"],
        },
        collected_at="2026-06-03T10:00:00+08:00",
    )


def _analyzed(
    url: str,
    *,
    summary: str = "实用的 AI agent developer tool，支持 CLI workflow automation",
    tags: list[str] | None = None,
    source_id: str = "github_ai_devtools",
) -> AnalyzedItem:
    return AnalyzedItem(
        ref_url=url,
        title="Dev Agent",
        summary=summary,
        tags=tags if tags is not None else ["AI", "Agent", "CLI"],
        source="github",
        source_detail="github trending",
        source_id=source_id,
    )


def _reviewed(url: str, *, score: int = 85, verdict: str = "approved") -> ReviewedItem:
    return ReviewedItem(ref_url=url, total_score=score, dimensions={}, verdict=verdict)


@pytest.mark.asyncio
async def test_selector_prefers_practical_github_ai_tool(tmp_path):
    db = await _init_db(tmp_path)
    try:
        practical_url = "https://github.com/acme/dev-agent"
        hot_but_less_practical_url = "https://github.com/acme/model-zoo"
        rss_url = "https://example.com/news"

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[
                _raw(
                    hot_but_less_practical_url,
                    title="Model Zoo",
                    description="Collection of benchmark models",
                    source_id="github_trending",
                    stars=12000,
                    topics=["models"],
                ),
                _raw(practical_url),
                _raw(rss_url, title="RSS Item", source="rss", source_id="rss"),
            ],
            analyzed_items=[
                _analyzed(
                    hot_but_less_practical_url,
                    summary="模型集合和榜单",
                    tags=["AI"],
                    source_id="github_trending",
                ),
                _analyzed(practical_url),
                _analyzed(rss_url),
            ],
            reviewed_items=[
                _reviewed(hot_but_less_practical_url, score=88),
                _reviewed(practical_url, score=84),
                _reviewed(rss_url, score=95),
            ],
        )

        assert candidate is not None
        assert candidate.repo_url == practical_url
        assert candidate.repo_name == "acme/dev-agent"
        assert candidate.reviewer_score == 84
        assert candidate.candidate_score >= 70
        assert "github_ai_devtools" in candidate.trigger_reason
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_skips_recently_reported_repo(tmp_path):
    db = await _init_db(tmp_path)
    try:
        recent_url = "https://github.com/acme/dev-agent"
        fallback_url = "https://github.com/acme/rag-workflow"
        await save_deep_report(
            db,
            repo_url=recent_url,
            repo_name="acme/dev-agent",
            article_id=12,
            run_id="run_1",
            commit_sha="abc123",
            status="completed",
            candidate_score=95,
            trigger_reason="recent",
            report_json={},
            report_markdown="",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0,
            analysis_tokens=0,
            error="",
        )

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[_raw(recent_url), _raw(fallback_url, title="RAG Workflow", stars=700)],
            analyzed_items=[_analyzed(recent_url), _analyzed(fallback_url)],
            reviewed_items=[_reviewed(recent_url, score=92), _reviewed(fallback_url, score=82)],
        )

        assert candidate is not None
        assert candidate.repo_url == fallback_url
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_ignores_discarded_and_low_candidate_score(tmp_path):
    db = await _init_db(tmp_path)
    try:
        candidate = await select_deep_report_candidate(
            db,
            raw_items=[
                _raw("https://github.com/acme/discarded"),
                _raw(
                    "https://github.com/acme/low-candidate-score",
                    title="Model Archive",
                    description="Benchmark collection",
                    source_id="unknown",
                    source_detail="",
                    stars=0,
                    topics=["models"],
                ),
            ],
            analyzed_items=[
                _analyzed("https://github.com/acme/discarded"),
                _analyzed(
                    "https://github.com/acme/low-candidate-score",
                    summary="模型归档和榜单",
                    tags=["AI"],
                    source_id="unknown",
                ),
            ],
            reviewed_items=[
                _reviewed("https://github.com/acme/discarded", score=95, verdict="discarded"),
                _reviewed("https://github.com/acme/low-candidate-score", score=100),
            ],
        )

        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_chooses_highest_candidate_score(tmp_path):
    db = await _init_db(tmp_path)
    try:
        lower_url = "https://github.com/acme/plain-ai"
        higher_url = "https://github.com/acme/mcp-copilot"

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[
                _raw(lower_url, source_id="github_trending", stars=200, topics=["ai"]),
                _raw(higher_url, source_id="github_trending_velocity", stars=2500, topics=["mcp", "copilot"]),
            ],
            analyzed_items=[
                _analyzed(lower_url, summary="AI project", tags=["AI"], source_id="github_trending"),
                _analyzed(
                    higher_url,
                    summary="MCP copilot CLI tool for developer workflow",
                    tags=["MCP", "CLI", "Agent"],
                    source_id="github_trending_velocity",
                ),
            ],
            reviewed_items=[
                _reviewed(lower_url, score=88),
                _reviewed(higher_url, score=80),
            ],
        )

        assert candidate is not None
        assert candidate.repo_url == higher_url
        assert candidate.candidate_score >= 70
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_uses_source_detail_for_ai_devtools_priority(tmp_path):
    db = await _init_db(tmp_path)
    try:
        source_detail_url = "https://github.com/acme/detail-agent"
        trending_url = "https://github.com/acme/plain-trending"

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[
                _raw(
                    source_detail_url,
                    source_id="",
                    source_detail="GitHub AI devtools agent source",
                    stars=5000,
                    topics=["ai"],
                ),
                _raw(
                    trending_url,
                    source_id="github_trending",
                    source_detail="github trending",
                    stars=5000,
                    topics=["ai"],
                ),
            ],
            analyzed_items=[
                _analyzed(
                    source_detail_url,
                    summary="AI project",
                    tags=["AI"],
                    source_id="",
                ).model_copy(update={"source_detail": ""}),
                _analyzed(
                    trending_url,
                    summary="AI project",
                    tags=["AI"],
                    source_id="github_trending",
                ),
            ],
            reviewed_items=[
                _reviewed(source_detail_url, score=100),
                _reviewed(trending_url, score=100),
            ],
        )

        assert candidate is not None
        assert candidate.repo_url == source_detail_url
        assert candidate.candidate_score >= 70
        assert candidate.metadata["score_parts"]["source"] == 25
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_uses_analyzed_source_detail_when_raw_source_detail_empty(tmp_path):
    db = await _init_db(tmp_path)
    try:
        repo_url = "https://github.com/acme/analyzed-detail-agent"

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[
                _raw(
                    repo_url,
                    source_id="unknown",
                    source_detail="",
                    stars=5000,
                    topics=["ai"],
                )
            ],
            analyzed_items=[
                _analyzed(
                    repo_url,
                    summary="AI project",
                    tags=["AI"],
                    source_id="unknown",
                ).model_copy(update={"source_detail": "GitHub AI devtools agent source"})
            ],
            reviewed_items=[_reviewed(repo_url, score=100)],
        )

        assert candidate is not None
        assert candidate.repo_url == repo_url
        assert candidate.source_detail == "GitHub AI devtools agent source"
        assert candidate.candidate_score >= 70
        assert candidate.metadata["score_parts"]["source"] == 25
        assert candidate.metadata["score_parts"]["source_detail"] == 5
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_allows_low_reviewer_score_when_candidate_score_meets_threshold(tmp_path):
    db = await _init_db(tmp_path)
    try:
        repo_url = "https://github.com/acme/dev-agent"

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[_raw(repo_url, stars=5000)],
            analyzed_items=[_analyzed(repo_url)],
            reviewed_items=[_reviewed(repo_url, score=60)],
        )

        assert candidate is not None
        assert candidate.reviewer_score == 60
        assert candidate.candidate_score >= 70
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_ignores_github_issue_and_tree_urls(tmp_path):
    db = await _init_db(tmp_path)
    try:
        issue_url = "https://github.com/acme/dev-agent/issues/1"
        tree_url = "https://github.com/acme/dev-agent/tree/main"
        pull_url = "https://github.com/acme/dev-agent/pull/1"
        query_url = "https://github.com/acme/dev-agent?tab=readme"

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[_raw(issue_url), _raw(tree_url), _raw(pull_url), _raw(query_url)],
            analyzed_items=[
                _analyzed(issue_url),
                _analyzed(tree_url),
                _analyzed(pull_url),
                _analyzed(query_url),
            ],
            reviewed_items=[
                _reviewed(issue_url),
                _reviewed(tree_url),
                _reviewed(pull_url),
                _reviewed(query_url),
            ],
        )

        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_accepts_repo_root_url_with_trailing_slash_and_git_suffix(tmp_path):
    db = await _init_db(tmp_path)
    try:
        repo_url = "https://github.com/acme/dev-agent.git/"

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[_raw(repo_url)],
            analyzed_items=[_analyzed(repo_url)],
            reviewed_items=[_reviewed(repo_url)],
        )

        assert candidate is not None
        assert candidate.repo_url == "https://github.com/acme/dev-agent"
        assert candidate.repo_name == "acme/dev-agent"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_skips_recent_completed_report_for_git_suffix_variant(tmp_path):
    db = await _init_db(tmp_path)
    try:
        await save_deep_report(
            db,
            repo_url="https://github.com/acme/dev-agent",
            repo_name="acme/dev-agent",
            article_id=12,
            run_id="run_1",
            commit_sha="abc123",
            status="completed",
            candidate_score=95,
            trigger_reason="recent",
            report_json={},
            report_markdown="",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0,
            analysis_tokens=0,
            error="",
        )
        variant_url = "https://github.com/acme/dev-agent.git/"

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[_raw(variant_url)],
            analyzed_items=[_analyzed(variant_url)],
            reviewed_items=[_reviewed(variant_url)],
        )

        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_does_not_skip_completed_report_outside_recent_window(tmp_path):
    db = await _init_db(tmp_path)
    try:
        repo_url = "https://github.com/acme/dev-agent"
        await save_deep_report(
            db,
            repo_url=repo_url,
            repo_name="acme/dev-agent",
            article_id=12,
            run_id="run_1",
            commit_sha="abc123",
            status="completed",
            candidate_score=95,
            trigger_reason="old",
            report_json={},
            report_markdown="",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0,
            analysis_tokens=0,
            error="",
        )
        await db.execute(
            "UPDATE deep_reports SET updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', '+8 hours', '-7 days', '-1 hour') WHERE repo_url = ?",
            (repo_url,),
        )
        await db.commit()

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[_raw(repo_url)],
            analyzed_items=[_analyzed(repo_url)],
            reviewed_items=[_reviewed(repo_url)],
        )

        assert candidate is not None
        assert candidate.repo_url == repo_url
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_does_not_skip_failed_recent_report(tmp_path):
    db = await _init_db(tmp_path)
    try:
        repo_url = "https://github.com/acme/dev-agent"
        await save_deep_report(
            db,
            repo_url=repo_url,
            repo_name="acme/dev-agent",
            article_id=12,
            run_id="run_1",
            commit_sha="abc123",
            status="failed",
            candidate_score=95,
            trigger_reason="failed",
            report_json={},
            report_markdown="",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0,
            analysis_tokens=0,
            error="clone failed",
        )

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[_raw(repo_url)],
            analyzed_items=[_analyzed(repo_url)],
            reviewed_items=[_reviewed(repo_url)],
        )

        assert candidate is not None
        assert candidate.repo_url == repo_url
    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "report"])
async def test_selector_does_not_skip_pending_or_report_recent_report(tmp_path, status):
    db = await _init_db(tmp_path)
    try:
        repo_url = "https://github.com/acme/dev-agent"
        await save_deep_report(
            db,
            repo_url=repo_url,
            repo_name="acme/dev-agent",
            article_id=12,
            run_id="run_1",
            commit_sha="abc123",
            status=status,
            candidate_score=95,
            trigger_reason=status,
            report_json={},
            report_markdown="",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0,
            analysis_tokens=0,
            error="",
        )

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[_raw(repo_url)],
            analyzed_items=[_analyzed(repo_url)],
            reviewed_items=[_reviewed(repo_url)],
        )

        assert candidate is not None
        assert candidate.repo_url == repo_url
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_handles_non_sequence_topics(tmp_path):
    db = await _init_db(tmp_path)
    try:
        int_topics_url = "https://github.com/acme/int-topics"
        string_topics_url = "https://github.com/acme/string-topics"

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[
                _raw(int_topics_url, topics=123),
                _raw(
                    string_topics_url,
                    title="Plain Project",
                    description="Reference implementation",
                    source_id="unknown",
                    source_detail="",
                    stars=0,
                    topics="agent cli developer workflow automation tool",
                ),
            ],
            analyzed_items=[
                _analyzed(int_topics_url),
                _analyzed(
                    string_topics_url,
                    summary="参考实现",
                    tags=[],
                    source_id="unknown",
                ),
            ],
            reviewed_items=[
                _reviewed(int_topics_url),
                _reviewed(string_topics_url, score=100),
            ],
        )

        assert candidate is not None
        assert candidate.repo_url == int_topics_url
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_handles_non_sequence_tags(tmp_path):
    db = await _init_db(tmp_path)
    try:
        int_tags_url = "https://github.com/acme/int-tags"
        string_tags_url = "https://github.com/acme/string-tags"

        int_tags = AnalyzedItem.model_construct(
            ref_url=int_tags_url,
            title="Dev Agent",
            summary="实用的 AI agent developer tool，支持 CLI workflow automation",
            tags=123,
            language="zh",
            retry_count=0,
            source="github",
            source_detail="github trending",
            source_id="github_ai_devtools",
            metadata={},
        )
        string_tags = AnalyzedItem.model_construct(
            ref_url=string_tags_url,
            title="Plain Project",
            summary="参考实现",
            tags="agent cli developer workflow automation tool",
            language="zh",
            retry_count=0,
            source="github",
            source_detail="",
            source_id="unknown",
            metadata={},
        )

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[
                _raw(int_tags_url),
                _raw(
                    string_tags_url,
                    title="Plain Project",
                    description="Reference implementation",
                    source_id="unknown",
                    source_detail="",
                    stars=0,
                    topics=[],
                ),
            ],
            analyzed_items=[int_tags, string_tags],
            reviewed_items=[
                _reviewed(int_tags_url),
                _reviewed(string_tags_url, score=100),
            ],
        )

        assert candidate is not None
        assert candidate.repo_url == int_tags_url
    finally:
        await db.close()
