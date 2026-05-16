import asyncio, json, shutil
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from ..core.database import Database
from ..db.operations import search_articles, get_stats

class SiteBuilder:
    def __init__(self, db: Database, output_dir: Path, template_dir: Path):
        self.db = db
        self.output_dir = output_dir
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)

    async def build(self):
        tmp_dir = self.output_dir.parent / "output.tmp"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir()
        (tmp_dir / "articles").mkdir()

        all_articles = await search_articles(self.db, "", days=3650, limit=100000)
        stats = await get_stats(self.db, days=30)

        # 首页 — Jinja2 预渲染最近 30 天
        recent = [a for a in all_articles[:100]]  # 实际按 collected_at 排序取前 100
        index_html = self.env.get_template("index.html").render(
            articles=recent, stats=stats, updated=datetime.now().isoformat()
        )
        (tmp_dir / "index.html").write_text(index_html, encoding="utf-8")

        # 仪表盘 — Jinja2 内联 stats.json
        dash_html = self.env.get_template("dashboard.html").render(stats=stats)
        (tmp_dir / "dashboard.html").write_text(dash_html, encoding="utf-8")

        # data.json — 列表字段不含 summary，description 截断到 200 字符（详情页走 API）
        json_articles = []
        for a in all_articles:
            desc = a.get("description", "") or ""
            json_articles.append({
                "id": a["id"], "title": a["title"], "url": a["url"],
                "description": desc[:200],
                "source": a["source"], "source_detail": a.get("source_detail", ""),
                "relevance_score": a["relevance_score"],
                "published_at": a.get("published_at", ""),
                "collected_at": a.get("collected_at", ""),
            })
        (tmp_dir / "data.json").write_text(json.dumps(json_articles, ensure_ascii=False), encoding="utf-8")

        # stats.json
        (tmp_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")

        # 原子 rename 切换
        old_dir = self.output_dir.parent / "output.old"
        if old_dir.exists():
            shutil.rmtree(old_dir)
        if self.output_dir.exists():
            self.output_dir.rename(old_dir)
        tmp_dir.rename(self.output_dir)
        if old_dir.exists():
            shutil.rmtree(old_dir)


class DebouncedBuilder:
    """去抖渲染器：pipeline 完成后 schedule()，5min 无新触发才真正构建"""
    def __init__(self, builder: SiteBuilder, debounce_seconds: int = 300):
        self.builder = builder
        self.debounce_seconds = debounce_seconds
        self._timer: asyncio.Task | None = None

    async def schedule(self):
        if self._timer:
            self._timer.cancel()
        self._timer = asyncio.create_task(self._wait_and_build())

    async def _wait_and_build(self):
        await asyncio.sleep(self.debounce_seconds)
        await self.builder.build()

    async def build_now(self):
        if self._timer:
            self._timer.cancel()
        await self.builder.build()