import re
from urllib.parse import urlparse

from src.core.database import Database
from src.deep_reports.models import DeepReportCandidate
from src.graph.state import AnalyzedItem, RawItem, ReviewedItem

PREFERRED_SOURCES = {
    "github_ai_devtools",
    "github_trending_velocity",
    "github_trending_hot",
    "github_trending",
}
MIN_REVIEWER_SCORE = 85
MIN_CANDIDATE_SCORE = 85
AI_DEVTOOLS_SOURCE_TERMS = {"ai", "devtools", "agent", "rag", "code", "mcp", "developer"}
SOURCE_DETAIL_PHRASES = {
    "github_trending_velocity": "github_trending_velocity",
    "trending velocity": "github_trending_velocity",
    "github_trending_hot": "github_trending_hot",
    "trending hot": "github_trending_hot",
    "github_trending": "github_trending",
    "trending": "github_trending",
}
CAPABILITY_PHRASES = {
    "coding_agent": {
        "coding agent",
        "code agent",
    },
    "repo_understanding": {
        "code understanding",
        "codebase understanding",
        "repository analysis",
        "repository understanding",
        "repo analysis",
        "repository context",
        "repo context",
    },
    "developer_interface": {
        "ide",
        "ide extension",
        "ide plugin",
        "editor extension",
        "vscode extension",
        "vs code extension",
        "developer cli",
        "coding cli",
        "code cli",
        "cli for developer",
        "cli for developers",
        "cli for coding",
    },
    "code_quality": {
        "test generator",
        "test generation",
        "testing tool",
        "testing assistant",
        "test tool",
        "debugger",
        "debugging assistant",
        "debugging tool",
        "code review",
        "lint",
        "linter",
    },
    "developer_mcp": {
        "developer mcp",
        "coding mcp",
        "code mcp",
        "mcp server for developer tools",
        "mcp server exposing developer tools",
    },
    "coding_skill": {
        "coding skill",
        "developer skill",
        "developer skills",
        "code skill",
        "code skills",
    },
    "code_generation": {
        "code generation",
        "code generator",
        "code completion",
        "code autocomplete",
        "generates source code",
        "modifies source code",
        "code editing",
        "code modification",
        "code modifying",
        "source code modification",
        "source modification",
    },
    "developer_automation": {
        "developer workflow",
        "development workflow",
        "developer automation",
        "development automation",
        "build automation",
        "release automation",
        "build and release automation",
        "documentation automation",
        "documentation automation for developer",
        "documentation automation for developers",
        "documentation automation for software developer",
        "documentation automation for software developers",
        "developer documentation automation",
    },
}
DELIVERY_TERMS = {
    "tool",
    "assistant",
    "agent",
    "extension",
    "plugin",
    "server",
    "cli",
    "service",
    "platform",
    "provides",
    "offers",
    "enables",
    "supports",
    "automates",
    "generates",
    "modifies",
    "reviews",
    "debugs",
    "analyzes",
}
TITLE_CAPABILITY_NAMES = {
    "release automation",
    "documentation automation for developers",
    "documentation automation for software developers",
}
EVALUATION_POSITIONING_TERMS = {
    "paper",
    "model weights",
    "dataset",
    "benchmark",
    "evaluation",
    "leaderboard",
    "testbed",
    "comparing models",
}
GENERIC_INTERFACE_PHRASES = {
    "developer cli",
    "ide",
    "ide extension",
    "ide plugin",
    "editor extension",
    "vscode extension",
    "vs code extension",
}


class DeepCandidateSelector:
    def __init__(self, db: Database):
        self.db = db

    async def select(
        self,
        raw_items: list[RawItem],
        analyzed_items: list[AnalyzedItem],
        reviewed_items: list[ReviewedItem],
    ) -> DeepReportCandidate | None:
        raw_by_url = {item.url: item for item in raw_items}
        analyzed_by_url = {item.ref_url: item for item in analyzed_items}

        candidates = []
        for reviewed in reviewed_items:
            if reviewed.verdict != "approved":
                continue
            if reviewed.total_score < MIN_REVIEWER_SCORE:
                continue
            if not reviewed.ref_url:
                continue

            raw = raw_by_url.get(reviewed.ref_url)
            analyzed = analyzed_by_url.get(reviewed.ref_url)
            if not raw or not analyzed:
                continue
            if raw.source != "github":
                continue

            repo_info = _repo_info(raw.url)
            if not repo_info:
                continue
            repo_name, repo_url = repo_info
            capabilities = _coding_capabilities(raw, analyzed)
            if not capabilities:
                continue
            if await self._has_recent_report(repo_url):
                continue

            candidate = _build_candidate(
                raw,
                analyzed,
                reviewed,
                repo_name,
                repo_url,
                capabilities,
            )
            if candidate.candidate_score < MIN_CANDIDATE_SCORE:
                continue
            candidates.append(candidate)

        if not candidates:
            return None
        return max(candidates, key=lambda item: item.candidate_score)

    async def _has_recent_report(self, repo_url: str) -> bool:
        row = await self.db.fetch_one(
            """
            SELECT id FROM deep_reports
            WHERE repo_url = ?
              AND status = 'completed'
              AND datetime(updated_at) >= datetime('now', '+8 hours', '-7 days')
            LIMIT 1
            """,
            (repo_url,),
        )
        return row is not None


async def select_deep_report_candidate(
    db: Database,
    raw_items: list[RawItem],
    analyzed_items: list[AnalyzedItem],
    reviewed_items: list[ReviewedItem],
) -> DeepReportCandidate | None:
    selector = DeepCandidateSelector(db)
    return await selector.select(raw_items, analyzed_items, reviewed_items)


def _build_candidate(
    raw: RawItem,
    analyzed: AnalyzedItem,
    reviewed: ReviewedItem,
    repo_name: str,
    repo_url: str,
    capabilities: set[str],
) -> DeepReportCandidate:
    source_id = analyzed.source_id or str(raw.raw_metadata.get("source_id") or "")
    source_detail = _effective_source_detail(raw, analyzed)
    source_key = _source_key(source_id, source_detail)
    score_parts = {
        "coding": min(40 + max(len(capabilities) - 1, 0) * 5, 45),
        "reviewer": int(reviewed.total_score * 0.35),
        "source": 10 if source_key == "github_ai_devtools" else 5,
        "readiness": min(_readiness_hits(raw, analyzed) * 2, 10),
    }
    candidate_score = sum(score_parts.values())
    capability_names = sorted(capabilities)
    trigger_reason = (
        f"Coding capabilities: {', '.join(capability_names)}; "
        f"reviewer score: {reviewed.total_score}"
    )
    return DeepReportCandidate(
        repo_url=repo_url,
        repo_name=repo_name,
        article_id=_article_id(raw.raw_metadata),
        source_id=source_id,
        source_detail=source_detail,
        title=analyzed.title or raw.title,
        summary=analyzed.summary,
        reviewer_score=reviewed.total_score,
        candidate_score=candidate_score,
        trigger_reason=trigger_reason,
        metadata={
            "coding_capabilities": capability_names,
            "score_parts": score_parts,
            "source_key": source_key,
            "raw_metadata": raw.raw_metadata,
        },
    )


def _repo_info(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return None
    if parsed.netloc.lower() != "github.com":
        return None
    if parsed.params or parsed.query or parsed.fragment:
        return None
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        return None
    owner, repo = parts
    if not owner or not repo:
        return None
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not repo:
        return None
    repo_name = f"{owner}/{repo}"
    return repo_name, f"https://github.com/{repo_name}"


def _coding_capabilities(raw: RawItem, analyzed: AnalyzedItem) -> set[str]:
    capabilities = set()
    has_specific_direct_evidence = False
    title_segment_count = len(_text_segments([raw.title]))
    primary_segments = _text_segments([raw.title, raw.description, analyzed.summary])
    for index, segment in enumerate(_capability_segments(raw, analyzed)):
        segment_capabilities, has_specific_delivery = _segment_capabilities(
            segment,
            is_title=index < title_segment_count,
        )
        capabilities.update(segment_capabilities)
        if index < len(primary_segments):
            has_specific_direct_evidence |= has_specific_delivery

    has_evaluation_positioning = _segments_contain_any(
        primary_segments,
        EVALUATION_POSITIONING_TERMS,
    )
    if has_evaluation_positioning and not has_specific_direct_evidence:
        return set()
    return capabilities


def _capability_segments(raw: RawItem, analyzed: AnalyzedItem) -> list[str]:
    topics = _sequence_values(raw.raw_metadata.get("topics"))
    tags = _sequence_values(analyzed.tags)
    values = [raw.title, raw.description, analyzed.summary, *tags, *topics]
    return _text_segments(values)


def _text_segments(values: list) -> list[str]:
    segments = []
    for value in values:
        normalized = str(value).lower().replace("-", " ").replace("_", " ")
        segments.extend(
            segment.strip()
            for segment in re.split(r"[.?!\n]+", normalized)
            if segment.strip()
        )
    return segments


def _segment_capabilities(segment: str, *, is_title: bool) -> tuple[set[str], bool]:
    if _is_supporting_documentation(segment, is_title=is_title):
        return set(), False
    if is_title and _contains_any(segment, EVALUATION_POSITIONING_TERMS):
        return set(), False

    capabilities = {
        capability
        for capability, phrases in CAPABILITY_PHRASES.items()
        if _contains_any(segment, phrases)
    }
    has_delivery = _contains_any(segment, DELIVERY_TERMS)
    has_implicit_delivery = bool(capabilities & {"developer_mcp", "coding_skill"})
    has_title_name = is_title and _contains_any(segment, TITLE_CAPABILITY_NAMES)
    if not (has_delivery or has_implicit_delivery or has_title_name):
        return set(), False

    concrete_phrases = set().union(*CAPABILITY_PHRASES.values()) - GENERIC_INTERFACE_PHRASES
    has_specific_delivery = bool(capabilities) and _contains_any(segment, concrete_phrases)
    return capabilities, has_specific_delivery


def _is_supporting_documentation(segment: str, *, is_title: bool) -> bool:
    supporting_terms = {
        "example",
        "examples",
        "tutorial",
        "walkthrough",
        "guidance",
    }
    if _contains_any(segment, supporting_terms):
        return True

    documentation_terms = {"docs", "readme", "documentation"}
    if not _contains_any(segment, documentation_terms):
        return False
    if is_title and _contains_any(segment, TITLE_CAPABILITY_NAMES):
        return False

    documentation_automation_terms = {
        "documentation automation",
        "documentation automation for developer",
        "documentation automation for developers",
        "documentation automation for software developer",
        "documentation automation for software developers",
        "developer documentation automation",
    }
    return not (
        _contains_any(segment, documentation_automation_terms)
        and _contains_any(segment, DELIVERY_TERMS)
    )


def _segments_contain_any(segments: list[str], terms: set[str]) -> bool:
    return any(_contains_any(segment, terms) for segment in segments)


def _readiness_hits(raw: RawItem, analyzed: AnalyzedItem) -> int:
    segments = _capability_segments(raw, analyzed)
    readiness_groups = (
        {"install", "installation", "quick start", "quickstart", "getting started", "安装"},
        {"cli", "command line", "ide", "editor extension", "vscode", "命令行", "插件"},
        {
            "configure",
            "configuration",
            "configuration example",
            "config example",
            "example config",
            "配置",
            "示例",
        },
        {"docker", "pypi", "npm package", "package release", "包发布"},
        {"tests passing", "test passing", "demo", "playground", "测试通过", "演示"},
    )
    return sum(1 for terms in readiness_groups if _segments_contain_any(segments, terms))


def _contains_any(text: str, terms: set[str]) -> bool:
    for term in terms:
        escaped_term = re.escape(term)
        if re.search(rf"(?<![a-z0-9]){escaped_term}(?![a-z0-9])", text):
            return True
    return False


def _effective_source_detail(raw: RawItem, analyzed: AnalyzedItem) -> str:
    return analyzed.source_detail or raw.source_detail


def _source_key(source_id: str, source_detail: str) -> str:
    if source_id in PREFERRED_SOURCES:
        return source_id

    detail = source_detail.lower()
    detail_terms = set(re.findall(r"[a-z0-9]+", detail))
    if detail_terms & AI_DEVTOOLS_SOURCE_TERMS:
        return "github_ai_devtools"

    for phrase, preferred_source in SOURCE_DETAIL_PHRASES.items():
        if phrase in detail:
            return preferred_source
    return source_id


def _sequence_values(value) -> list:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _article_id(metadata: dict) -> int | None:
    value = metadata.get("article_id") or metadata.get("id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
