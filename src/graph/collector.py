# src/graph/collector.py
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
import httpx
import feedparser

from .state import RawItem, CollectResult
from ..core.config import SourceConfig
from ..db.operations import record_source_health

logger = logging.getLogger("pipeline")


async def collect_github(source: SourceConfig) -> list[RawItem]:
    cfg = source.config
    topics = " OR ".join(cfg.get("topics", ["ai"]))
    lookback_days = cfg.get("lookback_days", 7)
    lookback_type = cfg.get("lookback_type", "created")  # "created" 或 "pushed"
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    # 构建查询：pushed:> 查最近活跃仓库，created:> 查新建仓库
    if lookback_type == "pushed":
        q = f"{topics} pushed:>{since}"
    else:
        q = f"{topics} created:>{since}"
    url = "https://api.github.com/search/repositories"
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": source.max_items}
    headers = {"Accept": "application/vnd.github.v3+json"}
    import os
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    items = []
    now = datetime.now(timezone.utc).isoformat()
    min_stars = cfg.get("min_stars", 0)
    min_forks = cfg.get("min_forks", 0)
    min_watchers = cfg.get("min_watchers", 0)
    for repo in data.get("items", []):
        if repo.get("stargazers_count", 0) < min_stars:
            continue
        if repo.get("forks_count", 0) < min_forks:
            continue
        if repo.get("watchers_count", 0) < min_watchers:
            continue
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
    now = datetime.now(timezone.utc).isoformat()
    keywords = cfg.get("filter_keywords", [])

    feed = feedparser.parse(cfg["url"])
    for entry in feed.entries[:source.max_items]:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        if keywords and not any(kw.lower() in f"{title} {summary}".lower() for kw in keywords):
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
    now = datetime.now(timezone.utc).isoformat()
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
    now = datetime.now(timezone.utc).isoformat()
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
