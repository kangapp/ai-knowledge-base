import asyncio, json, re, shutil
from pathlib import Path
from html import unescape
from jinja2 import Environment, FileSystemLoader
from ..core.database import Database
from ..core.time import now_bj, now_bj_iso
from ..db.operations import search_articles, get_stats


def clean_text(raw: str, length: int = 200) -> str:
    """去掉 HTML 标签，解码 HTML 实体，截断到 length 字符（按单词边界）"""
    if not raw:
        return ""
    # 去掉 HTML 标签
    text = re.sub(r"<[^>]+>", " ", raw)
    # 解码 HTML 实体
    text = unescape(text)
    # 合并多余空白
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= length:
        return text
    # 按单词边界截断
    truncated = text[:length]
    last_space = truncated.rfind(" ")
    if last_space > length * 0.7:
        truncated = truncated[:last_space]
    return truncated + "..."

class SiteBuilder:
    def __init__(self, db: Database, output_dir: Path, template_dir: Path):
        self.db = db
        self.output_dir = output_dir
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)

    async def build(self):
        # 用时间戳生成临时目录，避免删除 volume mount 的 /app/output
        tmp_dir = self.output_dir.parent / f"output.tmp.{now_bj().strftime('%Y%m%d%H%M%S')}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        (tmp_dir / "articles").mkdir()

        # 复制静态资源 (css, js)
        static_src = Path(__file__).parent / "static"
        if static_src.exists():
            shutil.copytree(static_src, tmp_dir / "static", dirs_exist_ok=True)

        all_articles = await search_articles(self.db, "", days=3650, limit=100000)
        stats = await get_stats(self.db, days=30)

        # 首页 — 优先展示 Analyzer 中文摘要，缺失时回退原始 description
        recent = [dict(a) for a in all_articles[:100]]  # 实际按 collected_at 排序取前 100
        for a in recent:
            description = clean_text(a.get("description", "") or "", 200)
            a["description"] = description
            a["summary"] = clean_text(a.get("summary", "") or description, 200)
            a["list_summary"] = clean_text(a["summary"], 120)
        index_html = self.env.get_template("index.html").render(
            articles=recent, stats=stats, updated=now_bj_iso()
        )
        (tmp_dir / "index.html").write_text(index_html, encoding="utf-8")

        # 仪表盘 — Jinja2 内联 stats.json
        dash_html = self.env.get_template("dashboard.html").render(stats=stats)
        (tmp_dir / "dashboard.html").write_text(dash_html, encoding="utf-8")

        # data.json — summary 用于列表展示，description 保留给原文关键词搜索
        json_articles = []
        for a in all_articles:
            description = clean_text(a.get("description", "") or "", 200)
            json_articles.append({
                "id": a["id"], "title": a["title"], "url": a["url"],
                "summary": clean_text(a.get("summary", "") or description, 200),
                "description": description,
                "source": a["source"], "source_detail": a.get("source_detail", ""),
                "relevance_score": a["relevance_score"],
                "tags": a.get("tags", []),
                "published_at": a.get("published_at", ""),
                "collected_at": a.get("collected_at", ""),
            })
        (tmp_dir / "data.json").write_text(json.dumps(json_articles, ensure_ascii=False), encoding="utf-8")

        # article.html — 静态外壳，详情内容由 JS 通过 /api/articles/{id} 渲染
        article_html = self.env.get_template("article.html").render()
        (tmp_dir / "article.html").write_text(article_html, encoding="utf-8")

        # stats.json
        (tmp_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")

        # 新增页面：配置查看页、DAG 状态页、深度报告页（需要 API 数据，由浏览器 JS 渲染）
        # base.html 需先复制，然后 config/dag.html 用 Jinja2 渲染
        base_src = self.template_dir / "base.html"
        if base_src.exists():
            shutil.copy2(base_src, tmp_dir / "base.html")
        for tmpl in ("config.html", "dag.html", "deep.html", "deep-report.html"):
            src = self.template_dir / tmpl
            if src.exists():
                rendered = self.env.get_template(tmpl).render()
                (tmp_dir / tmpl).write_text(rendered, encoding="utf-8")

        # 直接覆盖文件（不删除目录，避免 volume mount busy 问题）
        for item in tmp_dir.rglob("*"):
            if item.is_file():
                dest = self.output_dir / item.relative_to(tmp_dir)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)


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
