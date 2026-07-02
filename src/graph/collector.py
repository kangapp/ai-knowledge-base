# src/graph/collector.py
import asyncio
import logging
import re
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
import feedparser

from .state import RawItem, CollectResult
from ..core.config import SourceConfig
from ..core.time import now_bj, now_bj_iso
from ..db.operations import record_source_health

logger = logging.getLogger("pipeline")
HOTLIST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AIKnowledgeBase/1.0)",
    "Accept": "application/json",
}


def _quote_github_term(term: str) -> str:
    term = term.strip()
    if " " in term and not (term.startswith('"') and term.endswith('"')):
        return f'"{term}"'
    return term


def _build_github_queries(cfg: dict, now: datetime | None = None) -> list[str]:
    topics = [f"topic:{topic}" for topic in cfg.get("topics", ["ai"])]
    keywords = [_quote_github_term(keyword) for keyword in cfg.get("keywords", [])]
    include_terms = (topics + keywords)[:5]
    if not include_terms:
        include_terms = ["topic:ai"]

    lookback_days = cfg.get("lookback_days", 7)
    lookback_type = cfg.get("lookback_type", "created")  # "created" 或 "pushed"
    current_time = now or now_bj()
    since = (current_time - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    owner = cfg.get("owner")
    owner_prefix = f"user:{owner} " if owner else ""
    return [f"{owner_prefix}{term} {lookback_type}:>{since}" for term in include_terms]


def _build_github_query(cfg: dict, now: datetime | None = None) -> str:
    return _build_github_queries(cfg, now=now)[0]


def _matches_github_exclude(repo: dict, exclude_terms: list[str]) -> bool:
    text = " ".join(
        str(repo.get(field) or "")
        for field in ("full_name", "name", "description")
    ).lower()
    return any(term.strip().lower() in text for term in exclude_terms if term.strip())


def _contains_ascii(term: str) -> bool:
    return any(ch.isascii() and ch.isalpha() for ch in term)


def _matches_rss_keywords(text: str, keywords: list[str]) -> bool:
    for keyword in keywords:
        term = keyword.strip()
        if not term:
            continue
        if _contains_ascii(term):
            pattern = rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])"
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
            continue
        if term in text:
            return True
    return False


async def collect_github(source: SourceConfig, db=None) -> list[RawItem]:
    cfg = source.config
    url = "https://api.github.com/search/repositories"
    headers = {"Accept": "application/vnd.github.v3+json"}
    import os
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"

    repos_by_url = {}
    candidate_pool_size = min(max(source.max_items * 3, source.max_items), 100)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for q in _build_github_queries(cfg):
            params = {"q": q, "sort": "stars", "order": "desc", "per_page": candidate_pool_size}
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            for repo in resp.json().get("items", []):
                repos_by_url[repo["html_url"]] = repo

    eligible_repos = []
    now = now_bj_iso()
    min_stars = cfg.get("min_stars", 0)
    min_forks = cfg.get("min_forks", 0)
    min_watchers = cfg.get("min_watchers", 0)
    exclude_terms = cfg.get("exclude_terms", [])
    repos = sorted(
        repos_by_url.values(),
        key=lambda repo: repo.get("stargazers_count", 0),
        reverse=True,
    )
    for repo in repos:
        if _matches_github_exclude(repo, exclude_terms):
            continue
        if repo.get("stargazers_count", 0) < min_stars:
            continue
        if repo.get("forks_count", 0) < min_forks:
            continue
        if repo.get("watchers_count", 0) < min_watchers:
            continue
        eligible_repos.append(repo)

    existing_urls = set()
    if db is not None and eligible_repos:
        urls = [repo["html_url"] for repo in eligible_repos]
        placeholders = ",".join("?" * len(urls))
        rows = await db.fetch_all(
            f"SELECT url FROM articles WHERE url IN ({placeholders})",
            tuple(urls),
        )
        existing_urls = {row["url"] for row in rows}

    eligible_repos.sort(
        key=lambda repo: (
            repo["html_url"] in existing_urls,
            -repo.get("stargazers_count", 0),
        )
    )

    items = []
    for repo in eligible_repos[:source.max_items]:
        items.append(RawItem(
            url=repo["html_url"],
            title=repo["name"],
            description=repo.get("description") or "",
            source="github",
            source_detail=repo["full_name"],
            published_at=repo.get("pushed_at", ""),
            raw_metadata={"stars": repo.get("stargazers_count", 0), "forks": repo.get("forks_count", 0), "watchers": repo.get("watchers_count", 0), "language": repo.get("language", ""), "topics": repo.get("topics", []), "source_id": source.id},
            collected_at=now,
        ))
    return items


async def collect_rss(source: SourceConfig) -> list[RawItem]:
    cfg = source.config
    items = []
    now = now_bj_iso()
    keywords = cfg.get("filter_keywords", [])
    filter_scope = cfg.get("filter_scope", "title_summary")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(cfg["url"])
        resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        match_text = title if filter_scope == "title" else f"{title} {summary}"
        if keywords and not _matches_rss_keywords(match_text, keywords):
            continue
        items.append(RawItem(
            url=entry.get("link", ""),
            title=title,
            description=(summary or "")[:500],
            source="rss",
            source_detail=source.name,
            published_at=entry.get("published", ""),
            raw_metadata={"feed": cfg["url"], "source_id": source.id},
            collected_at=now,
        ))
        if len(items) >= source.max_items:
            break
    return items


def _is_safe_hotlist_url(url: str, expected_domain: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    if not expected_domain:
        return True

    hostname = parsed.hostname.lower()
    expected = expected_domain.strip().lower()
    return hostname == expected or hostname.endswith(f".{expected}")


async def collect_hotlist(source: SourceConfig) -> list[RawItem]:
    cfg = source.config
    platform_id = cfg["platform_id"]
    expected_domain = cfg.get("expected_domain", "")
    keywords = cfg.get("filter_keywords", [])
    filter_scope = cfg.get("filter_scope", "title_summary")

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers=HOTLIST_HEADERS,
    ) as client:
        resp = await client.get(
            cfg["api_url"],
            params={"id": platform_id, "latest": ""},
        )
        resp.raise_for_status()
        payload = resp.json()

    status = payload.get("status")
    if status not in {"success", "cache"}:
        raise ValueError(f"NewsNow 响应状态异常: {status}")

    items = []
    now = now_bj_iso()
    for rank, entry in enumerate(payload.get("items", []), start=1):
        title = entry.get("title")
        url = entry.get("url", "")
        if not isinstance(title, str) or not title.strip():
            continue
        if not _is_safe_hotlist_url(url, expected_domain):
            continue

        extra = entry.get("extra") or {}
        description = extra.get("hover", "") if isinstance(extra, dict) else ""
        info = extra.get("info", "") if isinstance(extra, dict) else ""
        match_text = title if filter_scope == "title" else f"{title} {description}"
        if keywords and not _matches_rss_keywords(match_text, keywords):
            continue

        items.append(RawItem(
            url=url,
            title=title.strip(),
            description=str(description or "")[:500],
            source="hotlist",
            source_detail=source.name,
            published_at=str(entry.get("pubDate") or ""),
            raw_metadata={
                "item_id": str(entry.get("id") or ""),
                "rank": rank,
                "info": str(info or ""),
                "platform_id": platform_id,
                "updated_time": payload.get("updatedTime"),
                "source_id": source.id,
            },
            collected_at=now,
        ))
        if len(items) >= source.max_items:
            break
    return items


async def collect_hn(source: SourceConfig) -> list[RawItem]:
    cfg = source.config
    items = []
    now = now_bj_iso()
    keywords = cfg.get("filter_keywords", [])

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(
            cfg["api_url"],
            params={
                "tags": "story",
                "query": cfg.get("query", ""),
                "hitsPerPage": min(source.max_items * 3, 100),
            },
        )
        resp.raise_for_status()
        payload = resp.json()

    for hit in payload.get("hits", []):
        object_id = str(hit.get("objectID") or "")
        title = hit.get("title") or hit.get("story_title") or ""
        if not title or not object_id:
            continue
        if keywords and not _matches_rss_keywords(title, keywords):
            continue
        url = hit.get("url") or hit.get("story_url") or f"https://news.ycombinator.com/item?id={object_id}"
        points = hit.get("points") or 0
        comments = hit.get("num_comments") or 0
        items.append(RawItem(
            url=url,
            title=title,
            description=f"points={points} comments={comments}",
            source="hn",
            source_detail=source.name,
            published_at=str(hit.get("created_at") or ""),
            raw_metadata={
                "object_id": object_id,
                "points": points,
                "num_comments": comments,
                "source_id": source.id,
            },
            collected_at=now,
        ))
        if len(items) >= source.max_items:
            break
    return items


# ===== 飞书认证 =====
class FeishuAuth:
    """惰性 token 管理"""
    def __init__(self):
        import os
        self.app_id = os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        self._token = ""
        self._expires_at = 0.0

    async def get_token(self) -> str:
        if self._token and time.time() < self._expires_at - 180:
            return self._token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        self._token = data["tenant_access_token"]
        self._expires_at = time.time() + data.get("expire", 7200)
        return self._token


_feishu_auth = FeishuAuth()


async def collect_feishu(source: SourceConfig) -> list[RawItem]:
    """采集飞书知识库文档"""
    if not _feishu_auth.app_id or _feishu_auth.app_id.startswith("cli_"):
        return []
    cfg = source.config
    items = []
    now = now_bj_iso()
    token = await _feishu_auth.get_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for space_id in cfg.get("space_ids", []):
            # 获取知识库空间下的节点列表
            resp = await client.get(
                f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes",
                headers=headers,
                params={"page_size": source.max_items},
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            nodes = data.get("data", {}).get("nodes", [])
            for node in nodes:
                node_id = node.get("node_id", "")
                node_type = node.get("node_type", "")
                if node_type == "origin_page":
                    # 获取页面详情
                    page_resp = await client.get(
                        f"https://open.feishu.cn/open-apis/wiki/v2/pages/{node_id}",
                        headers=headers,
                    )
                    if page_resp.status_code == 200:
                        page = page_resp.json().get("data", {}).get("page", {})
                        title = page.get("title", "")
                        url = page.get("url", "")
                        if title and url:
                            items.append(RawItem(
                                url=url,
                                title=title,
                                description="",
                                source="feishu",
                                source_detail=space_id,
                                published_at=node.get("create_time", ""),
                                raw_metadata={"node_id": node_id, "space_id": space_id, "source_id": source.id},
                                collected_at=now,
                            ))
    return items


async def collect_arxiv(source: SourceConfig) -> list[RawItem]:
    cfg = source.config
    items = []
    now = now_bj_iso()
    for cat in cfg.get("categories", []):
        url = f"http://export.arxiv.org/api/query?search_query=cat:{cat}&start=0&max_results={source.max_items}&sortBy=submittedDate&sortOrder=descending"
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        keywords = cfg.get("keywords", [])
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "").strip()
            if keywords and not any(kw.lower() in f"{title} {summary}".lower() for kw in keywords):
                continue
            items.append(RawItem(
                url=entry.get("id", ""),
                title=title,
                description=summary[:500],
                source="arxiv",
                source_detail=cat,
                published_at=entry.get("published", ""),
                raw_metadata={"categories": [t.get("term", "") for t in entry.get("tags", [])], "source_id": source.id},
                collected_at=now,
            ))
    return items


COLLECTOR_MAP = {
    "github": collect_github,
    "rss": collect_rss,
    "hotlist": collect_hotlist,
    "hn": collect_hn,
    "feishu": collect_feishu,
    "arxiv": collect_arxiv,
}


async def _record_health_failure(db, src_id: str):
    await record_source_health(db, CollectResult(source_id=src_id, failed=1))


async def _record_health_success(db, src_id: str, count: int):
    await record_source_health(db, CollectResult(source_id=src_id, total=count))


async def collect_all(db, sources: list[SourceConfig], collectors: dict | None = None) -> tuple[list[RawItem], list[dict]]:
    """并行采集所有启用的源，单个源失败不影响其余。返回 (all_items, error_log)。"""
    cmap = collectors or COLLECTOR_MAP
    tasks = {}
    for src in sources:
        if not src.enabled:
            continue
        fn = cmap.get(src.type)
        if fn:
            if collectors is None and src.type == "github":
                tasks[src.id] = asyncio.ensure_future(fn(src, db=db))
            else:
                tasks[src.id] = asyncio.ensure_future(fn(src))

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    all_items = []
    error_log = []
    for (src_id, src), result in zip(tasks.items(), results):
        if isinstance(result, Exception):
            logger.warning("collector.error", extra={"source": src_id, "error": str(result)})
            error_log.append({"source": src_id, "error": str(result), "retry_in": "next cron"})
            await _record_health_failure(db, src_id)
        elif isinstance(result, list):
            all_items.extend(result)
            await _record_health_success(db, src_id, len(result))

    return all_items, error_log
