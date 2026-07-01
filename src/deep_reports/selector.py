import re
from urllib.parse import urlparse

from src.core.database import Database
from src.deep_reports.models import DeepReportCandidate, DeepReportSelection
from src.graph.state import AnalyzedItem, RawItem, ReviewedItem

PREFERRED_SOURCES = {
    "github_ai_devtools",
    "github_trending_velocity",
    "github_trending_hot",
    "github_trending",
}
MIN_REVIEWER_SCORE = 80
MIN_AI_RELEVANCE_SCORE = 28
MIN_DEVELOPER_UTILITY_SCORE = 20
MIN_ADOPTION_VALUE = 55
MIN_ANALYZABILITY = 40
EXCLUDED_PROJECT_TYPES = {
    "research",
    "dataset",
    "benchmark",
    "resource_collection",
    "other",
}
ADOPTION_TERMS = {
    "agent",
    "coding",
    "claude",
    "codex",
    "context",
    "cursor",
    "devtool",
    "developer",
    "hook",
    "ide",
    "mcp",
    "plugin",
    "skill",
    "vscode",
    "workflow",
    "自动化",
    "上下文",
    "代码",
    "开发",
    "插件",
}
ANALYZABILITY_TERMS = {
    "api",
    "cli",
    "core",
    "extension",
    "hook",
    "mcp",
    "package",
    "plugin",
    "server",
    "service",
    "skill",
    "src",
}
AI_DEVTOOLS_SOURCE_TERMS = {"ai", "devtools", "agent", "rag", "code", "mcp", "developer"}
SOURCE_DETAIL_PHRASES = {
    "github_trending_velocity": "github_trending_velocity",
    "trending velocity": "github_trending_velocity",
    "github_trending_hot": "github_trending_hot",
    "trending hot": "github_trending_hot",
    "github_trending": "github_trending",
    "trending": "github_trending",
}
REJECTION_REASONS = (
    "not_approved",
    "reviewer_score",
    "not_github",
    "invalid_repo_url",
    "project_type",
    "ai_relevance",
    "developer_utility",
    "adoption_value",
    "analyzability",
    "recent_report",
)


class DeepCandidateSelector:
    def __init__(self, db: Database):
        self.db = db

    async def select(
        self,
        raw_items: list[RawItem],
        analyzed_items: list[AnalyzedItem],
        reviewed_items: list[ReviewedItem],
    ) -> DeepReportSelection:
        raw_by_url = {item.url: item for item in raw_items}
        analyzed_by_url = {item.ref_url: item for item in analyzed_items}
        diagnostics = {
            "reviewed_total": len(reviewed_items),
            "approved_github": 0,
            "eligible": 0,
            "rejected": {reason: 0 for reason in REJECTION_REASONS},
        }
        candidates = []

        for reviewed in reviewed_items:
            reason = None
            if reviewed.verdict != "approved":
                reason = "not_approved"
            elif reviewed.total_score < MIN_REVIEWER_SCORE:
                reason = "reviewer_score"

            raw = raw_by_url.get(reviewed.ref_url or "")
            analyzed = analyzed_by_url.get(reviewed.ref_url or "")
            if reason is None and (
                raw is None
                or analyzed is None
                or raw.source != "github"
            ):
                reason = "not_github"

            repo_info = _repo_info(raw.url) if raw is not None else None
            if reason is None and repo_info is None:
                reason = "invalid_repo_url"

            if reason is None:
                diagnostics["approved_github"] += 1
                if analyzed.project_type in EXCLUDED_PROJECT_TYPES:
                    reason = "project_type"

            ai_relevance = _dimension_score(reviewed, "ai_relevance")
            developer_utility = _dimension_score(reviewed, "developer_utility")
            adoption_value = (
                _adoption_value(raw, analyzed, developer_utility)
                if raw is not None and analyzed is not None
                else 0
            )
            analyzability = (
                _analyzability(raw, analyzed)
                if raw is not None and analyzed is not None
                else 0
            )
            if reason is None and ai_relevance < MIN_AI_RELEVANCE_SCORE:
                reason = "ai_relevance"
            if reason is None and developer_utility < MIN_DEVELOPER_UTILITY_SCORE:
                reason = "developer_utility"
            if reason is None and adoption_value < MIN_ADOPTION_VALUE:
                reason = "adoption_value"
            if reason is None and analyzability < MIN_ANALYZABILITY:
                reason = "analyzability"

            if reason is None:
                repo_name, repo_url = repo_info
                if await self._has_recent_report(repo_url):
                    reason = "recent_report"

            if reason is not None:
                diagnostics["rejected"][reason] += 1
                continue

            diagnostics["eligible"] += 1
            candidates.append(
                _build_candidate(
                    raw,
                    analyzed,
                    reviewed,
                    repo_name,
                    repo_url,
                    ai_relevance,
                    developer_utility,
                    adoption_value,
                    analyzability,
                )
            )

        candidate = max(candidates, key=lambda item: item.candidate_score) if candidates else None
        return DeepReportSelection(candidate=candidate, diagnostics=diagnostics)

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
) -> DeepReportSelection:
    return await DeepCandidateSelector(db).select(
        raw_items,
        analyzed_items,
        reviewed_items,
    )


def _build_candidate(
    raw: RawItem,
    analyzed: AnalyzedItem,
    reviewed: ReviewedItem,
    repo_name: str,
    repo_url: str,
    ai_relevance: int,
    developer_utility: int,
    adoption_value: int,
    analyzability: int,
) -> DeepReportCandidate:
    source_id = analyzed.source_id or str(raw.raw_metadata.get("source_id") or "")
    source_detail = analyzed.source_detail or raw.source_detail
    source_key = _source_key(source_id, source_detail)
    source_bonus = 5 if source_key == "github_ai_devtools" else 0
    score_parts = {
        "ai_relevance": _normalize_score(ai_relevance, 35) * 0.30,
        "developer_utility": _normalize_score(developer_utility, 30) * 0.30,
        "adoption_value": adoption_value * 0.25,
        "analyzability": analyzability * 0.15,
        "source": source_bonus,
    }
    candidate_score = round(sum(score_parts.values()))
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
        trigger_reason=(
            f"reviewer={reviewed.total_score}; ai_relevance={ai_relevance}; "
            f"developer_utility={developer_utility}; adoption_value={adoption_value}; "
            f"analyzability={analyzability}"
        ),
        metadata={
            "project_type": analyzed.project_type,
            "ai_relevance": ai_relevance,
            "developer_utility": developer_utility,
            "adoption_value": adoption_value,
            "analyzability": analyzability,
            "score_parts": score_parts,
            "source_key": source_key,
            "raw_metadata": raw.raw_metadata,
        },
    )


def _dimension_score(reviewed: ReviewedItem, name: str) -> int:
    value = reviewed.dimensions.get(name, {})
    if not isinstance(value, dict):
        return 0
    try:
        return int(value.get("score", 0))
    except (TypeError, ValueError):
        return 0


def _normalize_score(value: int, maximum: int) -> float:
    return min(max(value, 0), maximum) / maximum * 100


def _term_hits(raw: RawItem, analyzed: AnalyzedItem, terms: set[str]) -> int:
    metadata = raw.raw_metadata or {}
    topics = " ".join(str(topic) for topic in metadata.get("topics", []))
    text = " ".join(
        [
            raw.title,
            raw.description,
            raw.source_detail,
            analyzed.title,
            analyzed.summary,
            " ".join(analyzed.tags),
            topics,
        ]
    ).lower()
    return sum(1 for term in terms if term.lower() in text)


def _adoption_value(raw: RawItem, analyzed: AnalyzedItem, developer_utility: int) -> int:
    utility = _normalize_score(developer_utility, 30)
    term_bonus = min(_term_hits(raw, analyzed, ADOPTION_TERMS) * 6, 30)
    type_bonus = 10 if analyzed.project_type in {"coding_tool", "ai_infrastructure", "framework"} else 0
    return round(min(100, utility * 0.65 + term_bonus + type_bonus))


def _analyzability(raw: RawItem, analyzed: AnalyzedItem) -> int:
    score = 35
    if raw.description or analyzed.summary:
        score += 20
    if "/" in raw.source_detail:
        score += 20
    score += min(_term_hits(raw, analyzed, ANALYZABILITY_TERMS) * 5, 25)
    return min(score, 100)


def _repo_info(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        return None
    if parsed.params or parsed.query or parsed.fragment:
        return None
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        return None
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    repo_name = f"{owner}/{repo}"
    return repo_name, f"https://github.com/{repo_name}"


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


def _article_id(metadata: dict) -> int | None:
    value = metadata.get("article_id") or metadata.get("id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
