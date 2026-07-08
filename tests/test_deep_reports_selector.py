from pathlib import Path

import pytest
import pytest_asyncio

from src.core.database import Database
from src.db.operations import save_deep_report
from src.deep_reports.selector import select_deep_report_candidate
from src.graph.state import AnalyzedItem, RawItem, ReviewedItem

_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(
        tmp_path / "deep_reports_selector.db",
        migrations_dir=_MIGRATIONS_DIR,
    )
    await database.initialize()
    try:
        yield database
    finally:
        await database.close()


def _raw(
    url: str,
    *,
    source: str = "github",
    source_id: str = "github_trending_hot",
) -> RawItem:
    return RawItem(
        url=url,
        title=url.rsplit("/", 1)[-1],
        description="GitHub project",
        source=source,
        source_detail=url.removeprefix("https://github.com/"),
        raw_metadata={"source_id": source_id},
    )


def _analyzed(
    url: str,
    *,
    project_type: str | None = "coding_tool",
    source_id: str = "github_trending_hot",
) -> AnalyzedItem:
    return AnalyzedItem(
        ref_url=url,
        title=url.rsplit("/", 1)[-1],
        summary="面向开发者的 Coding 工具",
        source="github",
        source_detail=url.removeprefix("https://github.com/"),
        source_id=source_id,
        project_type=project_type,
    )


def _reviewed(
    url: str,
    *,
    score: int = 90,
    verdict: str = "approved",
    ai_score=32,
    utility_score=26,
) -> ReviewedItem:
    return ReviewedItem(
        ref_url=url,
        total_score=score,
        verdict=verdict,
        dimensions={
            "ai_relevance": {"score": ai_score},
            "developer_utility": {"score": utility_score},
        },
    )


async def _select(
    db,
    url: str,
    *,
    raw=None,
    analyzed=None,
    reviewed=None,
):
    return await select_deep_report_candidate(
        db,
        [raw or _raw(url)],
        [analyzed or _analyzed(url)],
        [reviewed or _reviewed(url)],
    )


@pytest.mark.parametrize(
    ("repo", "reviewer_score", "ai_score", "utility_score"),
    [
        ("aaif-goose/goose", 93, 33, 27),
        ("upstash/context7", 95, 34, 28),
        ("rtk-ai/rtk", 92, 33, 27),
        ("DietrichGebert/ponytail", 87, 32, 24),
    ],
)
async def test_selector_accepts_production_coding_tools(
    db,
    repo,
    reviewer_score,
    ai_score,
    utility_score,
):
    url = f"https://github.com/{repo}"

    result = await _select(
        db,
        url,
        reviewed=_reviewed(
            url,
            score=reviewer_score,
            ai_score=ai_score,
            utility_score=utility_score,
        ),
    )

    assert result.candidate is not None
    assert result.candidate.repo_name == repo
    assert result.diagnostics["eligible"] == 1
    assert sum(result.diagnostics["rejected"].values()) == 0


@pytest.mark.parametrize(
    "project_type",
    [
        "research",
        "dataset",
        "benchmark",
        "resource_collection",
        "other",
    ],
)
async def test_selector_rejects_non_coding_project_types(db, project_type):
    url = "https://github.com/acme/project"

    result = await _select(
        db,
        url,
        analyzed=_analyzed(url, project_type=project_type),
    )

    assert result.candidate is None
    assert result.diagnostics["rejected"]["project_type"] == 1


@pytest.mark.parametrize("project_type", [None, "", "unknown"])
async def test_selector_accepts_missing_project_type_when_adoption_value_is_high(db, project_type):
    url = "https://github.com/acme/project"

    result = await _select(
        db,
        url,
        analyzed=_analyzed(url, project_type=project_type),
    )

    assert result.candidate is not None
    assert result.diagnostics["eligible"] == 1


@pytest.mark.parametrize(
    ("reviewed", "reason"),
    [
        (_reviewed("https://github.com/acme/project", verdict="retry"), "not_approved"),
        (_reviewed("https://github.com/acme/project", score=79), "reviewer_score"),
        (_reviewed("https://github.com/acme/project", ai_score=27), "ai_relevance"),
        (
            _reviewed(
                "https://github.com/acme/project",
                ai_score="invalid",
                utility_score=26,
            ),
            "ai_relevance",
        ),
    ],
)
async def test_selector_rejects_first_failed_review_rule(db, reviewed, reason):
    url = "https://github.com/acme/project"
    reviewed.ref_url = url

    result = await _select(db, url, reviewed=reviewed)

    assert result.candidate is None
    assert result.diagnostics["rejected"][reason] == 1
    assert sum(result.diagnostics["rejected"].values()) == 1


async def test_selector_rejects_non_github_source(db):
    url = "https://example.com/article"

    result = await _select(
        db,
        url,
        raw=_raw(url, source="rss", source_id="rss_example"),
        analyzed=_analyzed(url),
        reviewed=_reviewed(url),
    )

    assert result.candidate is None
    assert result.diagnostics["rejected"]["not_github"] == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/acme/project",
        "https://gitlab.com/acme/project",
        "https://github.com/acme",
        "https://github.com/acme/project/issues",
        "https://github.com/acme/project?tab=readme",
    ],
)
async def test_selector_rejects_invalid_repo_url(db, url):
    result = await _select(db, url)

    assert result.candidate is None
    assert result.diagnostics["rejected"]["invalid_repo_url"] == 1


async def test_selector_rejects_recent_completed_report(db):
    url = "https://github.com/acme/project"
    await db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES (?, datetime('now', '+8 hours'), 'completed', 'test')
        """,
        ("old_run",),
    )
    await db.commit()
    await save_deep_report(
        db,
        repo_url=url,
        repo_name="acme/project",
        article_id=None,
        run_id="old_run",
        commit_sha="abc",
        status="completed",
        candidate_score=90,
        trigger_reason="test",
        report_json={},
        report_markdown="",
        evidence_json=[],
        tech_stack_json={},
        file_tree_summary="",
        analysis_cost=0,
        analysis_tokens=0,
        error="",
    )

    result = await _select(db, url)

    assert result.candidate is None
    assert result.diagnostics["rejected"]["recent_report"] == 1


async def test_selector_skips_when_weekly_completed_quota_is_full(db):
    await db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES (?, datetime('now', '+8 hours'), 'completed', 'test')
        """,
        ("weekly_quota_run",),
    )
    await db.commit()
    for index in range(2):
        await save_deep_report(
            db,
            repo_url=f"https://github.com/acme/reported-{index}",
            repo_name=f"acme/reported-{index}",
            article_id=None,
            run_id="weekly_quota_run",
            commit_sha="abc",
            status="completed",
            candidate_score=90,
            trigger_reason="test",
            report_json={},
            report_markdown="",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0,
            analysis_tokens=0,
            error="",
        )

    result = await _select(db, "https://github.com/acme/new-tool")

    assert result.candidate is None
    assert result.diagnostics["rejected"]["weekly_quota"] == 1
    assert result.diagnostics["eligible"] == 0


async def test_candidate_score_is_ranking_only_and_uses_source_bonus(db):
    first_url = "https://github.com/acme/first"
    second_url = "https://github.com/acme/second"

    result = await select_deep_report_candidate(
        db,
        [
            _raw(first_url, source_id="github_ai_devtools"),
            _raw(second_url, source_id="github_trending_hot"),
        ],
        [
            _analyzed(first_url, source_id="github_ai_devtools"),
            _analyzed(second_url, source_id="github_trending_hot"),
        ],
        [
            _reviewed(first_url, score=85, utility_score=24),
            _reviewed(second_url, score=90, utility_score=24),
        ],
    )

    assert result.candidate is not None
    assert result.candidate.repo_url == first_url
    assert result.candidate.candidate_score == 86
    assert result.diagnostics["eligible"] == 2


async def test_selector_uses_adoption_value_for_ranking(db):
    utility_url = "https://github.com/acme/context-tool"
    generic_url = "https://github.com/acme/generic-ai"

    result = await select_deep_report_candidate(
        db,
        [
            _raw(utility_url, source_id="github_ai_devtools"),
            _raw(generic_url, source_id="github_trending_hot"),
        ],
        [
            _analyzed(
                utility_url,
                project_type=None,
                source_id="github_ai_devtools",
            ).model_copy(update={
                "title": "Context Tool",
                "summary": "MCP hooks CLI for Claude Code and Cursor context optimization",
                "tags": ["MCP", "CLI", "Coding Agent"],
            }),
            _analyzed(
                generic_url,
                project_type="framework",
                source_id="github_trending_hot",
            ).model_copy(update={
                "title": "Generic AI Framework",
                "summary": "General AI framework",
                "tags": ["AI"],
            }),
        ],
        [
            _reviewed(utility_url, score=88, ai_score=32, utility_score=26),
            _reviewed(generic_url, score=92, ai_score=32, utility_score=24),
        ],
    )

    assert result.candidate is not None
    assert result.candidate.repo_url == utility_url
    assert result.candidate.metadata["score_parts"]["adoption_value"] > result.candidate.metadata["score_parts"]["analyzability"]


async def test_selector_preserves_input_order_for_equal_scores(db):
    first_url = "https://github.com/acme/first"
    second_url = "https://github.com/acme/second"

    result = await select_deep_report_candidate(
        db,
        [_raw(first_url), _raw(second_url)],
        [_analyzed(first_url), _analyzed(second_url)],
        [_reviewed(first_url), _reviewed(second_url)],
    )

    assert result.candidate is not None
    assert result.candidate.repo_url == first_url


async def test_selector_diagnostics_count_each_review_once(db):
    urls = {
        "retry": "https://github.com/acme/retry",
        "low": "https://github.com/acme/low",
        "rss": "https://example.com/article",
        "research": "https://github.com/acme/research",
        "eligible": "https://github.com/acme/tool",
    }

    result = await select_deep_report_candidate(
        db,
        [
            _raw(urls["retry"]),
            _raw(urls["low"]),
            _raw(urls["rss"], source="rss"),
            _raw(urls["research"]),
            _raw(urls["eligible"]),
        ],
        [
            _analyzed(urls["retry"]),
            _analyzed(urls["low"]),
            _analyzed(urls["rss"]),
            _analyzed(urls["research"], project_type="research"),
            _analyzed(urls["eligible"]),
        ],
        [
            _reviewed(urls["retry"], verdict="retry"),
            _reviewed(urls["low"], score=79),
            _reviewed(urls["rss"]),
            _reviewed(urls["research"]),
            _reviewed(urls["eligible"]),
        ],
    )

    assert result.diagnostics == {
        "reviewed_total": 5,
        "approved_github": 2,
        "eligible": 1,
        "rejected": {
            "not_approved": 1,
            "reviewer_score": 1,
            "not_github": 1,
            "invalid_repo_url": 0,
            "project_type": 1,
            "ai_relevance": 0,
            "developer_utility": 0,
            "adoption_value": 0,
            "analyzability": 0,
            "recent_report": 0,
            "weekly_quota": 0,
        },
    }
