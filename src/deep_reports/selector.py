import re
from urllib.parse import urlparse

from src.core.database import Database
from src.deep_reports.models import DeepReportCandidate, DeepReportSelection
from src.graph.state import PROJECT_TYPES, AnalyzedItem, RawItem, ReviewedItem

PREFERRED_SOURCES = {
    "github_ai_devtools",
    "github_trending_velocity",
    "github_trending_hot",
    "github_trending",
}
MIN_REVIEWER_SCORE = 85
MIN_AI_RELEVANCE_SCORE = 28
MIN_DEVELOPER_UTILITY_SCORE = 24
VALID_PROJECT_TYPES = set(PROJECT_TYPES)
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
    "project_type_missing",
    "project_type",
    "ai_relevance",
    "developer_utility",
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
                if analyzed.project_type not in VALID_PROJECT_TYPES:
                    reason = "project_type_missing"
                elif analyzed.project_type != "coding_tool":
                    reason = "project_type"

            ai_relevance = _dimension_score(reviewed, "ai_relevance")
            developer_utility = _dimension_score(reviewed, "developer_utility")
            if reason is None and ai_relevance < MIN_AI_RELEVANCE_SCORE:
                reason = "ai_relevance"
            if reason is None and developer_utility < MIN_DEVELOPER_UTILITY_SCORE:
                reason = "developer_utility"

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
) -> DeepReportCandidate:
    source_id = analyzed.source_id or str(raw.raw_metadata.get("source_id") or "")
    source_detail = analyzed.source_detail or raw.source_detail
    source_key = _source_key(source_id, source_detail)
    source_bonus = 5 if source_key == "github_ai_devtools" else 0
    score_parts = {
        "reviewer": reviewed.total_score * 0.7,
        "developer_utility": developer_utility * 0.6,
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
            f"project_type=coding_tool; reviewer={reviewed.total_score}; "
            f"ai_relevance={ai_relevance}; developer_utility={developer_utility}"
        ),
        metadata={
            "project_type": analyzed.project_type,
            "ai_relevance": ai_relevance,
            "developer_utility": developer_utility,
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
