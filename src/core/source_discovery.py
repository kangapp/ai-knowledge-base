import re
import logging
import json
import httpx
import feedparser
import hashlib
from urllib.parse import urlparse
from .source_manager import SourceManager
from .config import SourceConfig

logger = logging.getLogger("pipeline")

GITHUB_TRENDING_URL = "https://github.com/trending"
RSS_NEIGHBOR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SourceDiscoveryBot/1.0)"
}
SKIP_DISCOVERY_DOMAINS = {"github.com", "arxiv.org", "news.ycombinator.com"}


def _stable_rss_id(url: str) -> str:
    """根据 URL 生成稳定的 hash-based ID"""
    slug = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"rss_{slug}"


def _github_owner_id(owner: str) -> str:
    slug = re.sub(r"\W+", "_", owner.lower()).strip("_")
    return f"github_owner_{slug}"


def _discovery_key(source: SourceConfig) -> str:
    return source.config.get("url") or f"{source.type}:{source.id}"


class SourceDiscovery:
    """数据源发现：GitHub Topic 扩展 + RSS 友链扫描"""

    def __init__(self, db=None):
        self._db = db

    async def discover_from_approved_articles(self, limit: int = 100) -> list[SourceConfig]:
        """从已通过内容反推候选源：RSS 域名 + GitHub owner。"""
        if self._db is None:
            return []

        rows = await self._db.fetch_all(
            """
            SELECT url
            FROM articles
            WHERE status = 'approved' AND url IS NOT NULL AND url != ''
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        existing_rows = await self._db.fetch_all("SELECT id, config_json FROM source_registry")
        existing_ids = {row["id"] for row in existing_rows}
        existing_domains = set()
        for row in existing_rows:
            try:
                url = json.loads(row["config_json"] or "{}").get("url", "")
            except json.JSONDecodeError:
                url = ""
            domain = urlparse(url).netloc.lower()
            if domain:
                existing_domains.add(domain)

        discovered: list[SourceConfig] = []
        seen_ids: set[str] = set()
        for row in rows:
            parsed = urlparse(row["url"])
            domain = parsed.netloc.lower()
            if not domain:
                continue

            source: SourceConfig | None = None
            if domain == "github.com":
                parts = [part for part in parsed.path.split("/") if part]
                if len(parts) < 2:
                    continue
                owner = parts[0]
                source_id = _github_owner_id(owner)
                source = SourceConfig(
                    id=source_id,
                    name=f"GitHub {owner}",
                    type="github",
                    enabled=True,
                    priority=2,
                    cron="0 */6 * * *",
                    max_items=10,
                    config={
                        "owner": owner,
                        "keywords": ["AI", "LLM", "agent", "RAG", "MCP"],
                        "lookback_type": "pushed",
                        "lookback_days": 90,
                        "min_stars": 50,
                    },
                )
            elif domain not in SKIP_DISCOVERY_DOMAINS and domain not in existing_domains:
                feed_url = f"{parsed.scheme or 'https'}://{domain}/feed"
                source = SourceConfig(
                    id=_stable_rss_id(feed_url),
                    name=domain[:50],
                    type="rss",
                    enabled=True,
                    priority=2,
                    cron="0 */4 * * *",
                    max_items=10,
                    config={
                        "url": feed_url,
                        "filter_keywords": ["AI", "LLM", "artificial intelligence", "machine learning"],
                    },
                )

            if source is None or source.id in existing_ids or source.id in seen_ids:
                continue
            await self._write_discovered_source(source)
            discovered.append(source)
            seen_ids.add(source.id)

        logger.info("discovery.approved_articles", extra={"found": len(discovered)})
        return discovered

    async def discover_github_topics(self) -> list[SourceConfig]:
        """
        发现 GitHub Trending 中的新 topic。
        策略：解析 trending 页面获取所有仓库的 topics，
        统计频率，发现新出现的 AI 相关 topic。
        """
        discovered = []
        topics_seen = set()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(GITHUB_TRENDING_URL, headers=RSS_NEIGHBOR_HEADERS)
                resp.raise_for_status()
                html = resp.text

            # 解析仓库列表，提取 topics
            repo_pattern = r'/[\w-]+/[\w.-]+\?source=[\w-]+'
            repo_matches = re.findall(r'/([\w-]+)/([\w.-]+)\?', html)

            for owner, repo in repo_matches[:20]:  # 只看前 20 个
                repo_url = f"https://github.com/{owner}/{repo}"
                try:
                    repo_resp = await client.get(repo_url, headers=RSS_NEIGHBOR_HEADERS)
                    repo_html = repo_resp.text
                    topics_match = re.findall(r'topic-link.*?>([\w-]+)<', repo_html)
                    for topic in topics_match:
                        topics_seen.add(topic.lower())
                except Exception:
                    continue

            # 获取现有配置的 topics
            existing_sources = SourceManager.load()
            existing_topics = set()
            for src in existing_sources:
                if src.type == "github":
                    existing_topics.update(src.config.get("topics", []))

            # 发现新 topic（AI 相关）
            ai_keywords = {"ai", "llm", "ml", "machine-learning", "nlp", "deep-learning",
                           "agent", "rag", "mcp", "gpt", "transformer", "neural"}
            new_ai_topics = topics_seen - existing_topics & ai_keywords

            for topic in new_ai_topics:
                source = SourceConfig(
                    id=f"github_topic_{topic}",
                    name=f"GitHub {topic.title()}",
                    type="github",
                    enabled=True,
                    priority=2,
                    cron="0 */6 * * *",
                    max_items=10,
                    config={
                        "topics": [topic],
                        "min_stars": 50,
                        "lookback_days": 7,
                    }
                )
                # 先写入 discovered_sources 表
                await self._write_discovered_source(source)
                discovered.append(source)

            logger.info(f"discovery.github_topics", extra={"found": len(discovered), "topics": list(new_ai_topics)})

        except Exception as e:
            logger.warning(f"discovery.github.error", extra={"error": str(e)})

        return discovered

    async def scan_rss_neighbors(self) -> list[SourceConfig]:
        """
        扫描已配置 RSS 源的友链，发现新 RSS 源。
        策略：抓取 RSS 源的 HTML 首页，解析 <link rel="alternate"> 标签。
        """
        discovered = []
        existing_sources = SourceManager.load()
        existing_urls = {src.config.get("url", "") for src in existing_sources if src.type == "rss"}

        for source in existing_sources:
            if source.type != "rss":
                continue
            url = source.config.get("url", "")
            if not url:
                continue

            try:
                # 从 RSS URL 推导 HTML 首页（如 https://techcrunch.com/feed/ -> https://techcrunch.com/）
                base_url = "/".join(url.split("/")[:3])
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(base_url, headers=RSS_NEIGHBOR_HEADERS)
                    resp.raise_for_status()
                    html = resp.text

                # 解析 <link rel="alternate" type="application/rss+xml">
                rss_links = re.findall(
                    r'<link[^>]+rel=["\']alternate["\'][^>]+type=["\']application/rss\+xml["\'][^>]+href=["\']([^"\']+)["\']',
                    html, re.IGNORECASE
                )
                rss_links += re.findall(
                    r'<link[^>]+type=["\']application/rss\+xml["\'][^>]+href=["\']([^"\']+)["\']',
                    html, re.IGNORECASE
                )

                for rss_url in rss_links:
                    if rss_url in existing_urls:
                        continue
                    # 验证 RSS 可读
                    try:
                        feed = feedparser.parse(rss_url)
                        if feed.get("bozo", True) and not feed.entries:
                            continue
                    except Exception:
                        continue

                    name = feed.feed.get("title", rss_url.split("/")[2] if len(rss_url.split("/")) > 2 else rss_url)
                    source = SourceConfig(
                        id=_stable_rss_id(rss_url),
                        name=name[:50],
                        type="rss",
                        enabled=True,
                        priority=2,
                        cron="0 */4 * * *",
                        max_items=10,
                        config={
                            "url": rss_url,
                            "filter_keywords": ["AI", "LLM", "artificial intelligence", "machine learning"],
                        }
                    )
                    # 先写入 discovered_sources 表
                    await self._write_discovered_source(source)
                    discovered.append(source)
                    existing_urls.add(rss_url)

            except Exception as e:
                logger.warning(f"discovery.rss_scan.error", extra={"source": source.id, "error": str(e)})
                continue

        logger.info(f"discovery.rss_neighbors", extra={"found": len(discovered)})
        return discovered

    async def _write_discovered_source(self, source: SourceConfig):
        """写入 discovered_sources 表（status='candidate'）"""
        if self._db is None:
            return
        try:
            await self._db.execute("""
                INSERT OR IGNORE INTO discovered_sources (url, name, type, status, discovered_at)
                VALUES (?, ?, ?, 'candidate', datetime('now', '+8 hours'))
            """, (_discovery_key(source), source.name, source.type))
            await self._db.execute(
                """
                INSERT INTO source_registry
                (id, name, type, status, enabled, priority, cron, max_items, config_json)
                VALUES (?, ?, ?, 'candidate', 0, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    source.id,
                    source.name,
                    source.type,
                    source.priority,
                    source.cron,
                    source.max_items,
                    json.dumps(source.config, ensure_ascii=False),
                ),
            )
            await self._db.commit()
            logger.info("discovered_source.recorded", extra={"source_id": source.id, "type": source.type})
        except Exception as e:
            logger.warning("discovered_source.write_failed", extra={"source_id": source.id, "error": str(e)})

    async def discover(self) -> list[SourceConfig]:
        """
        执行完整发现流程，返回所有发现的数据源。
        """
        approved_sources = await self.discover_from_approved_articles()
        github_sources = await self.discover_github_topics()
        rss_sources = await self.scan_rss_neighbors()
        return approved_sources + github_sources + rss_sources
