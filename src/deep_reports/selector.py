import re
from urllib.parse import urlparse

from src.core.database import Database
from src.deep_reports.models import DeepReportCandidate
from src.graph.state import AnalyzedItem, RawItem, ReviewedItem

PREFERRED_SOURCES = {
    "github_ai_devtools": 25,
    "github_trending_velocity": 18,
    "github_trending_hot": 14,
    "github_trending": 8,
}
PRACTICAL_TERMS = {
    "tool",
    "agent",
    "code",
    "developer",
    "rag",
    "mcp",
    "cli",
    "knowledge",
    "graph",
    "automation",
    "workflow",
    "copilot",
}
MIN_CANDIDATE_SCORE = 70
AI_DEVTOOLS_SOURCE_TERMS = {"ai", "devtools", "agent", "rag", "code", "mcp", "developer"}
SOURCE_DETAIL_PHRASES = {
    "github_trending_velocity": "github_trending_velocity",
    "trending velocity": "github_trending_velocity",
    "github_trending_hot": "github_trending_hot",
    "trending hot": "github_trending_hot",
    "github_trending": "github_trending",
    "trending": "github_trending",
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
            if reviewed.verdict not in {"approved", "retry"}:
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
            if await self._has_recent_report(repo_url):
                continue

            candidate = _build_candidate(raw, analyzed, reviewed, repo_name, repo_url)
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
) -> DeepReportCandidate:
    source_id = analyzed.source_id or str(raw.raw_metadata.get("source_id") or "")
    source_detail = _effective_source_detail(raw, analyzed)
    source_key = _source_key(source_id, source_detail)
    practical_hits = _practical_hits(raw, analyzed)
    score_parts = {
        "source": PREFERRED_SOURCES.get(source_key, 0),
        "practical": min(practical_hits * 6, 30),
        "reviewer": int(reviewed.total_score * 0.15),
        "stars": min(_int_metadata(raw.raw_metadata, "stars") // 500, 10),
        "source_detail": 5 if source_detail else 0,
    }
    candidate_score = sum(score_parts.values())
    trigger_reason = (
        f"{source_id or 'github'} source + {practical_hits} practical hits "
        f"+ reviewer {reviewed.total_score}"
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


def _practical_hits(raw: RawItem, analyzed: AnalyzedItem) -> int:
    topics = _sequence_values(raw.raw_metadata.get("topics"))
    tags = _sequence_values(analyzed.tags)
    text = " ".join(
        [
            raw.title,
            raw.description,
            analyzed.summary,
            " ".join(str(tag) for tag in tags),
            " ".join(str(topic) for topic in topics),
        ]
    ).lower()
    return sum(1 for term in PRACTICAL_TERMS if term in text)


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


def _int_metadata(metadata: dict, key: str) -> int:
    value = metadata.get(key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _article_id(metadata: dict) -> int | None:
    value = metadata.get("article_id") or metadata.get("id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
