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
DEVELOPER_CONTEXT_TERMS = {
    "code",
    "coding",
    "developer",
    "development",
    "software",
    "repo",
    "repository",
    "ide",
    "editor",
    "debugger",
    "debugging",
    "test generator",
    "test generation",
    "code review",
    "lint",
    "build",
    "release",
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
    text = _candidate_text(raw, analyzed)
    capabilities = set()

    if _contains_any(text, {"coding agent", "code agent"}):
        capabilities.add("coding_agent")
    if _contains_any(
        text,
        {
            "code understanding",
            "codebase understanding",
            "repository analysis",
            "repository understanding",
            "repo analysis",
            "repository context",
            "repo context",
        },
    ):
        capabilities.add("repo_understanding")
    if _contains_any(text, {"ide", "editor extension", "vscode extension", "vs code extension"}):
        capabilities.add("developer_interface")
    if _contains_any(text, {"cli", "command line"}) and _contains_any(
        text, DEVELOPER_CONTEXT_TERMS
    ):
        capabilities.add("developer_interface")
    if _contains_any(
        text,
        {
            "test generator",
            "test generation",
            "debugger",
            "debugging tool",
            "code review",
            "lint",
            "linter",
        },
    ):
        capabilities.add("code_quality")
    if _contains_any(text, {"mcp", "model context protocol"}) and _contains_any(
        text, DEVELOPER_CONTEXT_TERMS
    ):
        capabilities.add("developer_mcp")
    if _contains_any(text, {"skill", "skills"}) and _contains_any(
        text, DEVELOPER_CONTEXT_TERMS
    ):
        capabilities.add("coding_skill")
    if _contains_any(
        text,
        {
            "developer workflow",
            "development workflow",
            "build automation",
            "release automation",
            "build and release automation",
        },
    ):
        capabilities.add("developer_automation")

    return capabilities


def _readiness_hits(raw: RawItem, analyzed: AnalyzedItem) -> int:
    text = _candidate_text(raw, analyzed)
    readiness_groups = (
        {"install", "installation", "quick start", "quickstart", "getting started", "安装"},
        {"cli", "command line", "ide", "editor extension", "vscode", "命令行", "插件"},
        {"configure", "configuration", "config example", "example", "配置", "示例"},
        {"docker", "pypi", "npm package", "package release", "包发布"},
        {"tests passing", "test passing", "demo", "playground", "测试通过", "演示"},
    )
    return sum(1 for terms in readiness_groups if _contains_any(text, terms))


def _candidate_text(raw: RawItem, analyzed: AnalyzedItem) -> str:
    topics = _sequence_values(raw.raw_metadata.get("topics"))
    tags = _sequence_values(analyzed.tags)
    return " ".join(
        [
            raw.title,
            raw.description,
            analyzed.summary,
            " ".join(str(tag) for tag in tags),
            " ".join(str(topic) for topic in topics),
        ]
    ).lower().replace("-", " ").replace("_", " ")


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
