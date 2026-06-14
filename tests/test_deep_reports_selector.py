from pathlib import Path

import pytest

from src.core.database import Database
from src.db.operations import save_deep_report
from src.deep_reports import selector
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
            "topics": topics if topics is not None else ["coding-agent", "developer-tools"],
        },
        collected_at="2026-06-03T10:00:00+08:00",
    )


def _analyzed(
    url: str,
    *,
    title: str = "Dev Agent",
    summary: str = "AI coding agent CLI for developer workflow automation",
    tags: list[str] | None = None,
    source_id: str = "github_ai_devtools",
    source_detail: str = "github trending",
) -> AnalyzedItem:
    return AnalyzedItem(
        ref_url=url,
        title=title,
        summary=summary,
        tags=tags if tags is not None else ["coding-agent", "CLI"],
        source="github",
        source_detail=source_detail,
        source_id=source_id,
    )


def _reviewed(url: str, *, score: int = 85, verdict: str = "approved") -> ReviewedItem:
    return ReviewedItem(ref_url=url, total_score=score, dimensions={}, verdict=verdict)


async def _select_one(db, url, *, raw=None, analyzed=None, reviewed=None):
    return await select_deep_report_candidate(
        db,
        raw_items=[raw or _raw(url)],
        analyzed_items=[analyzed or _analyzed(url)],
        reviewed_items=[reviewed or _reviewed(url)],
    )


def test_selector_thresholds_are_fixed_at_85():
    assert getattr(selector, "MIN_REVIEWER_SCORE", None) == 85
    assert selector.MIN_CANDIDATE_SCORE == 85


@pytest.mark.parametrize(
    ("title", "description", "summary"),
    [
        (
            "Developer CLI",
            "Benchmark leaderboard for completion models",
            "Compare completion models",
        ),
        (
            "IDE Extension",
            "Dataset and evaluation suite",
            "Leaderboard for model evaluation",
        ),
        (
            "Code Completion",
            "Paper with downloadable model weights",
            "Research model for code completion",
        ),
        (
            "Code Completion",
            "Testbed comparing models",
            "Evaluation framework for completion models",
        ),
        (
            "Calendar MCP",
            "Calendar integration for managing events",
            "The README mentions a coding agent",
        ),
        (
            "Calendar MCP",
            "Calendar integration for managing events",
            "Documentation guidance for code completion",
        ),
        (
            "Calendar MCP",
            "Calendar integration for managing events",
            "Tutorial walkthrough using a code review assistant",
        ),
        (
            "Calendar MCP",
            "Calendar integration for managing events",
            "Examples include a developer MCP server",
        ),
    ],
)
def test_coding_capabilities_require_explicit_delivery_evidence(
    title,
    description,
    summary,
):
    url = "https://github.com/acme/explicit-evidence"
    raw = _raw(url, title=title, description=description, topics=[])
    analyzed = _analyzed(url, title=title, summary=summary, tags=[])

    assert selector._coding_capabilities(raw, analyzed) == set()


@pytest.mark.parametrize(
    ("title", "description", "summary", "expected_capability"),
    [
        (
            "Completion Bench",
            "Code completion tool with benchmark results",
            "Install, configure, and run the demo",
            "code_generation",
        ),
        (
            "Review Bench",
            "Code review assistant with evaluation dataset",
            "Install, configure, and run the demo",
            "code_quality",
        ),
        (
            "Release Bench",
            "Release automation tool with benchmark results",
            "Install, configure, and run the demo",
            "developer_automation",
        ),
        (
            "Completion Bench",
            "IDE plugin for code completion with benchmark results",
            "Install, configure, and run the demo",
            "developer_interface",
        ),
        (
            "Documentation Automation",
            "Documentation automation service for software developers",
            "Install, configure, and run the demo",
            "developer_automation",
        ),
        (
            "Documentation Automation for Developers",
            "Automated developer documentation",
            "Install, configure, and run the demo",
            "developer_automation",
        ),
        (
            "Coding Agent",
            "Autonomous coding agent",
            "Install, configure, and run the demo",
            "coding_agent",
        ),
        (
            "Repository Understanding Tool",
            "Understands source repositories",
            "Install, configure, and run the demo",
            "repo_understanding",
        ),
        (
            "Developer MCP Server",
            "MCP server for developer tools",
            "Install, configure, and run the demo",
            "developer_mcp",
        ),
        (
            "Coding Skill",
            "Coding skill for software developers",
            "Install, configure, and run the demo",
            "coding_skill",
        ),
    ],
)
def test_coding_capabilities_accept_explicit_capability_delivery(
    title,
    description,
    summary,
    expected_capability,
):
    url = "https://github.com/acme/explicit-delivery"
    raw = _raw(url, title=title, description=description, topics=[])
    analyzed = _analyzed(url, title=title, summary=summary, tags=[])

    assert expected_capability in selector._coding_capabilities(raw, analyzed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("verdict", "score"),
    [
        ("retry", 100),
        ("approved", 84),
    ],
)
async def test_selector_requires_approved_verdict_and_reviewer_score_85(tmp_path, verdict, score):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/dev-agent"
        candidate = await _select_one(db, url, reviewed=_reviewed(url, score=score, verdict=verdict))

        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "description"),
    [
        ("rag", "General RAG system over documents"),
        ("knowledge-base", "Universal knowledge base for documents"),
        ("chatbot", "General purpose chatbot"),
        ("model-weights", "Collection of open model weights"),
        ("dataset", "Large language model dataset"),
        ("benchmark", "Benchmark suite for language models"),
    ],
)
async def test_selector_rejects_popular_non_coding_projects(tmp_path, name, description):
    db = await _init_db(tmp_path)
    try:
        url = f"https://github.com/acme/{name}"
        candidate = await _select_one(
            db,
            url,
            raw=_raw(
                url,
                title=name,
                description=description,
                stars=50000,
                topics=[name],
            ),
            analyzed=_analyzed(
                url,
                title=name,
                summary=description,
                tags=[name],
            ),
            reviewed=_reviewed(url, score=95),
        )

        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_rejects_software_agent_benchmark_without_developer_context(tmp_path):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/software-agent-benchmark"
        candidate = await _select_one(
            db,
            url,
            raw=_raw(
                url,
                title="Software Agent Benchmark",
                description="A benchmark for general autonomous software agents",
                stars=50000,
                topics=["software-agent", "benchmark"],
            ),
            analyzed=_analyzed(
                url,
                title="Software Agent Benchmark",
                summary="Dataset and leaderboard for general software agents",
                tags=["software-agent", "benchmark"],
            ),
            reviewed=_reviewed(url, score=95),
        )

        assert candidate is None
        assert selector._coding_capabilities(
            _raw(
                url,
                title="Software Agent Benchmark",
                description="A benchmark for general autonomous software agents",
                stars=50000,
                topics=["software-agent", "benchmark"],
            ),
            _analyzed(
                url,
                title="Software Agent Benchmark",
                summary="Dataset and leaderboard for general software agents",
                tags=["software-agent", "benchmark"],
            ),
        ) == set()
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_rejects_software_agent_benchmark_cli(tmp_path):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/software-agent-cli"
        raw = _raw(
            url,
            title="Software Agent Benchmark CLI",
            description="Command line benchmark for autonomous software agents",
            stars=50000,
            topics=["software-agent", "benchmark", "cli"],
        )
        analyzed = _analyzed(
            url,
            title="Software Agent Benchmark CLI",
            summary="Run benchmark datasets from the command line",
            tags=["software-agent", "benchmark", "cli"],
        )

        candidate = await _select_one(
            db,
            url,
            raw=raw,
            analyzed=analyzed,
            reviewed=_reviewed(url, score=95),
        )

        assert candidate is None
        assert selector._coding_capabilities(raw, analyzed) == set()
    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "title", "description", "summary", "tags", "topics"),
    [
        (
            "cross-field-code-agent",
            "Code",
            "Agent benchmark",
            "Leaderboard for general autonomous agents",
            ["benchmark"],
            ["agent-evaluation"],
        ),
        (
            "code-completion-benchmark",
            "Code Completion Benchmark",
            "Evaluation suite for completion models",
            "Leaderboard and dataset for model evaluation",
            ["benchmark"],
            ["evaluation"],
        ),
        (
            "ide-benchmark",
            "IDE Benchmark",
            "Evaluation suite for integrated development environments",
            "Leaderboard for IDE performance",
            ["benchmark"],
            ["evaluation"],
        ),
        (
            "code-review-dataset",
            "Code Review Dataset",
            "Dataset of historical review comments",
            "Evaluation data for review models",
            ["dataset"],
            ["evaluation"],
        ),
        (
            "calendar-readme",
            "Calendar MCP Server",
            "Calendar integration for managing events",
            "The README includes release automation workflows. Install, configure, and run the demo",
            ["mcp", "calendar"],
            ["calendar"],
        ),
        (
            "calendar-automation-examples",
            "Calendar MCP Server",
            "Calendar integration for managing events",
            "Includes software release automation examples. Install, configure, and run the demo",
            ["mcp", "calendar"],
            ["calendar"],
        ),
        (
            "calendar-documentation",
            "Calendar MCP Server",
            "Calendar integration for managing events",
            "The documentation provides a release automation walkthrough",
            ["mcp", "calendar"],
            ["calendar"],
        ),
        (
            "code-completion-examples",
            "Calendar MCP Server",
            "Calendar integration for managing events",
            "Code completion examples",
            ["mcp", "calendar"],
            ["calendar"],
        ),
        (
            "coding-agent-example",
            "Calendar MCP Server",
            "Calendar integration for managing events",
            "Coding agent example",
            ["mcp", "calendar"],
            ["calendar"],
        ),
        (
            "example-code-review",
            "Calendar MCP Server",
            "Calendar integration for managing events",
            "Example of code review",
            ["mcp", "calendar"],
            ["calendar"],
        ),
        (
            "software-release-automation-examples",
            "Calendar MCP Server",
            "Calendar integration for managing events",
            "Includes examples of software release automation",
            ["mcp", "calendar"],
            ["calendar"],
        ),
        (
            "readme-developer-documentation-automation",
            "Calendar MCP Server",
            "Calendar integration for managing events",
            "The README includes developer documentation automation workflows",
            ["mcp", "calendar"],
            ["calendar"],
        ),
        (
            "docs-developer-documentation-automation",
            "Calendar MCP Server",
            "Calendar integration for managing events",
            "The docs show developer documentation automation workflow",
            ["mcp", "calendar"],
            ["calendar"],
        ),
    ],
)
async def test_selector_rejects_incidental_coding_mentions(
    tmp_path,
    name,
    title,
    description,
    summary,
    tags,
    topics,
):
    db = await _init_db(tmp_path)
    try:
        url = f"https://github.com/acme/{name}"
        raw = _raw(
            url,
            title=title,
            description=description,
            stars=50000,
            topics=topics,
        )
        analyzed = _analyzed(
            url,
            title=title,
            summary=summary,
            tags=tags,
        )

        candidate = await _select_one(
            db,
            url,
            raw=raw,
            analyzed=analyzed,
            reviewed=_reviewed(url, score=95),
        )

        assert selector._coding_capabilities(raw, analyzed) == set()
        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_rejects_code_completion_project_positioned_as_evaluation(tmp_path):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/code-completion-evaluation"
        raw = _raw(
            url,
            title="Code Completion",
            description="Benchmark and dataset for model evaluation",
            topics=["evaluation"],
        )
        analyzed = _analyzed(
            url,
            title="Code Completion",
            summary="Leaderboard for completion model evaluation",
            tags=["benchmark", "dataset"],
        )

        candidate = await _select_one(
            db,
            url,
            raw=raw,
            analyzed=analyzed,
            reviewed=_reviewed(url, score=95),
        )

        assert selector._coding_capabilities(raw, analyzed) == set()
        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_rejects_capability_only_mentioned_in_configuration_examples(tmp_path):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/calendar-mcp"
        raw = _raw(
            url,
            title="Calendar MCP",
            description="Calendar integration for managing events",
            topics=["calendar"],
        )
        analyzed = _analyzed(
            url,
            title="Calendar MCP",
            summary="Configuration examples include code completion for illustration",
            tags=["mcp", "calendar"],
        )

        candidate = await _select_one(
            db,
            url,
            raw=raw,
            analyzed=analyzed,
            reviewed=_reviewed(url, score=95),
        )

        assert selector._coding_capabilities(raw, analyzed) == set()
        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_accepts_tool_clause_alongside_evaluation_clause(tmp_path):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/completion-extension"
        raw = _raw(
            url,
            title="Completion Extension",
            description="IDE extension for code completion with benchmark results",
            topics=[],
        )
        analyzed = _analyzed(
            url,
            title="Completion Extension",
            summary="Run the demo",
            tags=[],
        )

        candidate = await _select_one(db, url, raw=raw, analyzed=analyzed)

        assert candidate is not None
        assert candidate.metadata["coding_capabilities"] == [
            "code_generation",
            "developer_interface",
        ]
    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "description", "should_accept"),
    [
        (
            "documentation-automation",
            "Provides documentation automation for software developers",
            True,
        ),
        (
            "readme-documentation-automation",
            "README includes developer documentation automation",
            False,
        ),
    ],
)
async def test_selector_distinguishes_documentation_capability_from_readme_report(
    tmp_path,
    name,
    description,
    should_accept,
):
    db = await _init_db(tmp_path)
    try:
        url = f"https://github.com/acme/{name}"
        candidate = await _select_one(
            db,
            url,
            raw=_raw(url, title="Calendar MCP", description=description, topics=[]),
            analyzed=_analyzed(
                url,
                title="Calendar MCP",
                summary="Install, configure, and run the demo",
                tags=[],
            ),
        )

        assert (candidate is not None) is should_accept
    finally:
        await db.close()


def test_readiness_signals_do_not_span_fields():
    url = "https://github.com/acme/split-readiness"
    raw = _raw(
        url,
        title="Calendar MCP",
        description="getting",
        topics=[],
    )
    analyzed = _analyzed(
        url,
        title="Calendar MCP",
        summary="started",
        tags=[],
    )

    assert selector._readiness_hits(raw, analyzed) == 0


@pytest.mark.asyncio
async def test_stars_cannot_push_candidate_over_threshold(tmp_path):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/repo-context"
        raw = _raw(
            url,
            title="Repo Context Builder",
            description="Understands source repositories",
            source_id="github_trending",
            stars=100000,
            topics=["repository-analysis"],
        )
        analyzed = _analyzed(
            url,
            title="Repo Context Builder",
            summary="Builds repository context for source code understanding",
            tags=["repo-context"],
            source_id="github_trending",
        )

        candidate = await _select_one(db, url, raw=raw, analyzed=analyzed)

        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("title", "description", "summary", "tags", "topics", "expected_capability"),
    [
        (
            "Coding Agent",
            "Autonomous software agent",
            "Install, configure, and run a coding agent demo",
            ["coding-agent"],
            [],
            "coding_agent",
        ),
        (
            "IDE Review Assistant",
            "VS Code extension for code review",
            "Install the editor extension and try the demo",
            ["IDE", "code-review"],
            [],
            "code_quality",
        ),
        (
            "Debug Test CLI",
            "Developer CLI debugger and test generator",
            "Install the package and run the CLI demo",
            ["debugger", "test-generation"],
            [],
            "code_quality",
        ),
        (
            "Developer MCP Server",
            "MCP server exposing developer tools",
            "Install with Docker and configure the developer MCP server",
            ["MCP", "developer-tools"],
            [],
            "developer_mcp",
        ),
        (
            "Coding Skill",
            "Coding skill for software developers",
            "Install the package, configure it, and run the demo",
            ["coding-skill"],
            [],
            "coding_skill",
        ),
        (
            "Repo Context Builder",
            "Repository analysis and code understanding tool",
            "Install the package, configure it, and run the demo",
            ["repo-context"],
            ["repository-analysis"],
            "repo_understanding",
        ),
        (
            "Context Builder",
            "Repository understanding tool and context builder",
            "Install, configure, and run its demo",
            [],
            [],
            "repo_understanding",
        ),
        (
            "Code Completion",
            "Code completion that generates and modifies source code",
            "Install, configure, and run the code autocomplete demo",
            ["code-completion"],
            [],
            "code_generation",
        ),
        (
            "Release Automation",
            "Release automation for developers",
            "Install, configure, and run the release automation demo",
            ["release-automation"],
            [],
            "developer_automation",
        ),
        (
            "Completion Evaluation Tool",
            "Code completion benchmark",
            "Developer CLI for code completion. Install, configure, and run the demo",
            [],
            [],
            "code_generation",
        ),
        (
            "Code Modification",
            "Code modification tool for developers",
            "Install, configure, and run the demo",
            [],
            [],
            "code_generation",
        ),
        (
            "Code Modifying",
            "Code modifying assistant for developers",
            "Install, configure, and run the demo",
            [],
            [],
            "code_generation",
        ),
        (
            "Source Modification",
            "Source code modification tool for developers",
            "Install, configure, and run the demo",
            [],
            [],
            "code_generation",
        ),
        (
            "Testing Tool",
            "Testing tool for software developers",
            "Install, configure, and run the demo",
            [],
            [],
            "code_quality",
        ),
        (
            "Testing Assistant",
            "Testing assistant for software developers",
            "Install, configure, and run the demo",
            [],
            [],
            "code_quality",
        ),
        (
            "Test Tool",
            "Test tool for software developers",
            "Install, configure, and run the demo",
            [],
            [],
            "code_quality",
        ),
        (
            "Debugging Assistant",
            "Debugging assistant for software developers",
            "Install, configure, and run the demo",
            [],
            [],
            "code_quality",
        ),
        (
            "Debugging Tool",
            "Debugging tool for software developers",
            "Install, configure, and run the demo",
            [],
            [],
            "code_quality",
        ),
        (
            "Developer Automation",
            "Developer automation platform for release workflows",
            "Install, configure, and run the demo",
            [],
            [],
            "developer_automation",
        ),
        (
            "Development Automation",
            "Development automation service for release workflows",
            "Install, configure, and run the demo",
            [],
            [],
            "developer_automation",
        ),
        (
            "Documentation Automation",
            "Documentation automation service for software developers",
            "Install, configure, and run the demo",
            [],
            [],
            "developer_automation",
        ),
        (
            "Documentation Automation Provider",
            "Provides documentation automation for software developers",
            "Install, configure, and run the demo",
            [],
            [],
            "developer_automation",
        ),
        (
            "Developer Documentation Automation",
            "Developer documentation automation service",
            "Install, configure, and run the demo",
            [],
            [],
            "developer_automation",
        ),
    ],
)
async def test_selector_accepts_coding_capabilities(
    tmp_path,
    title,
    description,
    summary,
    tags,
    topics,
    expected_capability,
):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/coding-tool"
        candidate = await _select_one(
            db,
            url,
            raw=_raw(url, title=title, description=description, topics=topics),
            analyzed=_analyzed(url, title=title, summary=summary, tags=tags),
        )

        assert candidate is not None
        assert expected_capability in candidate.metadata["coding_capabilities"]
        assert candidate.candidate_score >= 85
    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("title", "description", "tags"),
    [
        ("Universal MCP Server", "MCP server for calendars and documents", ["MCP"]),
        ("Reusable Skills", "A collection of general productivity skills", ["skills"]),
    ],
)
async def test_selector_rejects_generic_mcp_and_skills_without_developer_context(
    tmp_path, title, description, tags
):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/general-tool"
        candidate = await _select_one(
            db,
            url,
            raw=_raw(url, title=title, description=description, topics=[]),
            analyzed=_analyzed(
                url,
                title=title,
                summary="Install the package, configure it, and run the demo",
                tags=tags,
            ),
            reviewed=_reviewed(url, score=100),
        )

        assert candidate is None
    finally:
        await db.close()


def test_test_generation_capability_is_not_a_readiness_signal():
    url = "https://github.com/acme/test-generator"
    raw = _raw(
        url,
        title="Test Generator",
        description="Generates unit tests for source code",
        topics=["test-generation"],
    )
    analyzed = _analyzed(
        url,
        title="Test Generator",
        summary="Test generation for Python code",
        tags=["test-generation"],
    )

    assert selector._readiness_hits(raw, analyzed) == 0


def test_example_project_is_not_a_readiness_signal():
    url = "https://github.com/acme/example-project"
    raw = _raw(
        url,
        title="Example Project",
        description="An example project for learning patterns",
        topics=[],
    )
    analyzed = _analyzed(
        url,
        title="Example Project",
        summary="Reference example project",
        tags=[],
    )

    assert selector._readiness_hits(raw, analyzed) == 0


@pytest.mark.asyncio
async def test_candidate_metadata_contains_capabilities_and_score_parts(tmp_path):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/review-cli"
        candidate = await _select_one(
            db,
            url,
            raw=_raw(
                url,
                title="IDE Code Review CLI",
                description="VS Code extension and developer CLI for code review",
                stars=99999,
                topics=["code-review", "developer-tools"],
            ),
            analyzed=_analyzed(
                url,
                title="IDE Code Review CLI",
                summary="Install the package, configure the CLI, and run tests and a demo",
                tags=["IDE", "code-review", "CLI"],
            ),
        )

        assert candidate is not None
        assert candidate.metadata["coding_capabilities"] == [
            "code_quality",
            "developer_interface",
        ]
        assert candidate.metadata["score_parts"] == {
            "coding": 45,
            "reviewer": 29,
            "source": 10,
            "readiness": 8,
        }
        assert candidate.candidate_score == 92
        assert "50000" not in candidate.trigger_reason
        assert "85" in candidate.trigger_reason
        assert candidate.metadata["raw_metadata"]["stars"] == 99999
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_candidate_score_threshold_accepts_exactly_85(tmp_path):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/coding-skill"
        candidate = await _select_one(
            db,
            url,
            raw=_raw(
                url,
                title="Coding Skill",
                description="Coding skill for developers",
                topics=[],
            ),
            analyzed=_analyzed(
                url,
                title="Coding Skill",
                summary="Install the package, configure it, and run a demo",
                tags=["coding-skill"],
            ),
        )

        assert candidate is not None
        assert candidate.candidate_score == 85
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_keeps_source_priority(tmp_path):
    db = await _init_db(tmp_path)
    try:
        preferred_url = "https://github.com/acme/preferred"
        trending_url = "https://github.com/acme/trending"
        candidate = await select_deep_report_candidate(
            db,
            raw_items=[
                _raw(
                    preferred_url,
                    title="Coding Agent CLI",
                    source_id="",
                    source_detail="GitHub AI devtools source",
                ),
                _raw(
                    trending_url,
                    title="Coding Agent CLI",
                    source_id="github_trending",
                ),
            ],
            analyzed_items=[
                _analyzed(
                    preferred_url,
                    title="Coding Agent CLI",
                    source_id="",
                    source_detail="",
                ),
                _analyzed(
                    trending_url,
                    title="Coding Agent CLI",
                    source_id="github_trending",
                ),
            ],
            reviewed_items=[
                _reviewed(preferred_url, score=100),
                _reviewed(trending_url, score=100),
            ],
        )

        assert candidate is not None
        assert candidate.repo_url == preferred_url
        assert candidate.metadata["score_parts"]["source"] == 10
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_skips_recently_reported_repo(tmp_path):
    db = await _init_db(tmp_path)
    try:
        recent_url = "https://github.com/acme/dev-agent"
        fallback_url = "https://github.com/acme/test-generator"
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
            raw_items=[
                _raw(recent_url),
                _raw(
                    fallback_url,
                    title="Test Generator CLI",
                    description="CLI test generator for developers",
                ),
            ],
            analyzed_items=[
                _analyzed(recent_url),
                _analyzed(
                    fallback_url,
                    title="Test Generator CLI",
                    summary="Install the package, configure the CLI, and run a demo",
                    tags=["test-generation", "CLI"],
                ),
            ],
            reviewed_items=[_reviewed(recent_url, score=95), _reviewed(fallback_url)],
        )

        assert candidate is not None
        assert candidate.repo_url == fallback_url
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
            """
            UPDATE deep_reports
            SET updated_at = strftime(
                '%Y-%m-%dT%H:%M:%S',
                'now',
                '+8 hours',
                '-7 days',
                '-1 hour'
            )
            WHERE repo_url = ?
            """,
            (repo_url,),
        )
        await db.commit()

        candidate = await _select_one(db, repo_url)

        assert candidate is not None
        assert candidate.repo_url == repo_url
    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["failed", "pending", "report"])
async def test_selector_does_not_skip_recent_non_completed_report(tmp_path, status):
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
            error="clone failed" if status == "failed" else "",
        )

        candidate = await _select_one(db, repo_url)

        assert candidate is not None
        assert candidate.repo_url == repo_url
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_skips_recent_completed_report_for_normalized_git_url(tmp_path):
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

        candidate = await _select_one(db, variant_url)

        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_accepts_repo_root_url_with_trailing_slash_and_git_suffix(tmp_path):
    db = await _init_db(tmp_path)
    try:
        repo_url = "https://github.com/acme/dev-agent.git/"

        candidate = await _select_one(db, repo_url)

        assert candidate is not None
        assert candidate.repo_url == "https://github.com/acme/dev-agent"
        assert candidate.repo_name == "acme/dev-agent"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_ignores_github_issue_and_tree_urls(tmp_path):
    db = await _init_db(tmp_path)
    try:
        issue_url = "https://github.com/acme/dev-agent/issues/1"
        tree_url = "https://github.com/acme/dev-agent/tree/main"

        candidate = await select_deep_report_candidate(
            db,
            raw_items=[_raw(issue_url), _raw(tree_url)],
            analyzed_items=[_analyzed(issue_url), _analyzed(tree_url)],
            reviewed_items=[_reviewed(issue_url), _reviewed(tree_url)],
        )

        assert candidate is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_selector_handles_non_sequence_topics_and_tags(tmp_path):
    db = await _init_db(tmp_path)
    try:
        url = "https://github.com/acme/dev-agent"
        analyzed = AnalyzedItem.model_construct(
            ref_url=url,
            title="Coding Agent",
            summary="Install and run the coding agent CLI demo",
            tags=123,
            language="zh",
            retry_count=0,
            source="github",
            source_detail="github trending",
            source_id="github_ai_devtools",
            metadata={},
        )

        candidate = await _select_one(
            db,
            url,
            raw=_raw(url, title="Coding Agent", topics="coding-agent"),
            analyzed=analyzed,
        )

        assert candidate is not None
        assert candidate.metadata["coding_capabilities"] == [
            "coding_agent",
            "developer_automation",
            "developer_interface",
        ]
    finally:
        await db.close()
