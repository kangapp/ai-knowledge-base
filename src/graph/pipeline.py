# src/graph/pipeline.py
from datetime import datetime, timezone
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from .state import PipelineState
from .router import router_node as _router_fn
from .aggregator import aggregator_node as _aggregator_fn
from .reviewer import reviewer_node as _reviewer_fn
from .analyzers.github import analyze_github
from .analyzers.rss import analyze_rss
from .analyzers.feishu import analyze_feishu
from .analyzers.arxiv import analyze_arxiv
from ..core.llm_client import LLMRegistry


PHASES = ["collect", "route", "analyze", "aggregate", "review"]

# 模块级 DB 引用，由 main.py 在 lifespan 中注入
_db = None
# 并行 analyzer 计数器 — 第一个启动的 analyzer 记录 phase start，最后一个完成的记录 phase end
_analyzer_count = 0


def set_pipeline_db(db):
    global _db
    _db = db


def get_pipeline_db():
    global _db
    if _db is None:
        raise RuntimeError("Pipeline DB not set")
    return _db


def reset_analyzer_counter():
    global _analyzer_count
    _analyzer_count = 0


async def record_phase_start(db, run_id: str, phase: str):
    await db.execute(
        "INSERT INTO pipeline_phase_logs (run_id, phase, status, started_at) VALUES (?, ?, ?, ?)",
        (run_id, phase, "running", datetime.now(timezone.utc).isoformat())
    )
    await db.commit()


async def record_phase_end(db, run_id: str, phase: str, status: str, details: str = None):
    ended_at = datetime.now(timezone.utc).isoformat()
    row = await db.fetch_one(
        "SELECT started_at FROM pipeline_phase_logs WHERE run_id=? AND phase=? AND status='running' ORDER BY id DESC LIMIT 1",
        (run_id, phase)
    )
    duration_ms = None
    if row and row["started_at"]:
        start_str = row["started_at"].replace("Z", "+00:00")
        start = datetime.fromisoformat(start_str)
        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    await db.execute(
        "UPDATE pipeline_phase_logs SET status=?, ended_at=?, duration_ms=?, details=? WHERE run_id=? AND phase=? AND status='running'",
        (status, ended_at, duration_ms, details, run_id, phase)
    )
    await db.commit()


# 独立函数，供测试 mock 使用
async def github_analyzer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.routed_github:
        return {"analyzed_items": [], "cost_records": []}
    items, costs = await analyze_github(state.routed_github, registry)
    return {"analyzed_items": items, "cost_records": costs}


async def rss_analyzer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.routed_rss:
        return {"analyzed_items": [], "cost_records": []}
    items, costs = await analyze_rss(state.routed_rss, registry)
    return {"analyzed_items": items, "cost_records": costs}


async def feishu_analyzer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.routed_feishu:
        return {"analyzed_items": [], "cost_records": []}
    items, costs = await analyze_feishu(state.routed_feishu, registry)
    return {"analyzed_items": items, "cost_records": costs}


async def arxiv_analyzer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.routed_arxiv:
        return {"analyzed_items": [], "cost_records": []}
    items, costs = await analyze_arxiv(state.routed_arxiv, registry)
    return {"analyzed_items": items, "cost_records": costs}


class _RouterNode:
    def __init__(self, router_fn):
        self._router = router_fn

    async def __call__(self, state: PipelineState) -> dict:
        db = get_pipeline_db()
        await record_phase_start(db, state.run_id, "route")
        result = await self._router(state)
        total = len(state.raw_items)
        # 统计 RSS 子源
        rss_by_source = {}
        for item in state.raw_items:
            if item.source == "rss" and item.source_detail:
                rss_by_source[item.source_detail] = rss_by_source.get(item.source_detail, 0) + 1
        rss_detail = ", ".join(f"{k}:{v}" for k, v in rss_by_source.items()) if rss_by_source else ""
        details = f"total:{total}, github:{len(result['routed_github'])}, rss:{len(result['routed_rss'])}"
        if rss_detail:
            details += f" [{rss_detail}]"
        await record_phase_end(db, state.run_id, "route", "done", details)
        return result


class _AnalyzerNode:
    """封装 analyzer 逻辑，第一个启动的实例记录 phase start，最后一个完成的记录 phase end。"""
    def __init__(self, analyze_fn, routed_key: str, registry: LLMRegistry):
        self._analyze = analyze_fn
        self._routed_key = routed_key
        self._registry = registry

    async def __call__(self, state: PipelineState) -> dict:
        global _analyzer_count
        routed = getattr(state, self._routed_key, [])
        if not routed:
            return {"analyzed_items": [], "cost_records": []}

        _analyzer_count += 1
        db = get_pipeline_db()
        if _analyzer_count == 1:
            await record_phase_start(db, state.run_id, "analyze")

        items, costs = await self._analyze(routed, self._registry)
        if _analyzer_count == 1:
            total_cost = sum(c.cost for c in costs) if costs else 0
            details = f"total:{len(routed)}, succeeded:{len(items)}, failed:{len(routed)-len(items)}, cost:${total_cost:.6f}"
        else:
            details = None
        _analyzer_count -= 1
        if _analyzer_count == 0:
            await record_phase_end(db, state.run_id, "analyze", "done", details)
        return {"analyzed_items": items, "cost_records": costs}


class _AggregatorNode:
    def __init__(self, aggregator_fn):
        self._aggregator = aggregator_fn

    async def __call__(self, state: PipelineState) -> dict:
        db = get_pipeline_db()
        await record_phase_start(db, state.run_id, "aggregate")
        result = await self._aggregator(state)
        details = f"total:{len(state.analyzed_items)}"
        await record_phase_end(db, state.run_id, "aggregate", "done", details)
        return result


class _ReviewerNode:
    def __init__(self, registry: LLMRegistry):
        self._registry = registry
        self._reviewer = _reviewer_fn

    async def __call__(self, state: PipelineState) -> dict:
        db = get_pipeline_db()
        await record_phase_start(db, state.run_id, "review")
        result = await self._reviewer(state, self._registry)
        reviewed = result.get("reviewed_items", [])
        total_cost = sum(c.cost for c in result.get("cost_records", []))
        approved = sum(1 for r in reviewed if r.verdict == "approved")
        retry = sum(1 for r in reviewed if r.verdict == "retry")
        discarded = sum(1 for r in reviewed if r.verdict == "discarded")
        details = f"approved:{approved}, retry:{retry}, discarded:{discarded}, cost:${total_cost:.6f}"
        await record_phase_end(db, state.run_id, "review", "done", details)

        # 写入各数据源健康记录（含 approved/rejected/avg_score）
        from .state import CollectResult
        from ..db.operations import record_source_health

        # 建立 ref_url -> (source, source_detail) 映射，同时统计每个 source 的数量
        ref_source_map = {}
        routed_counts = {}  # src_id -> count of items entering review
        for key in ("routed_github", "routed_rss", "routed_feishu", "routed_arxiv"):
            routed_items = getattr(state, key, [])
            for item in routed_items:
                # RSS 子源用 source_detail 作为 src_id，其余用 source
                src_id = item.source_detail if item.source == "rss" else item.source
                routed_counts[src_id] = routed_counts.get(src_id, 0) + 1
                ref_source_map[item.url] = (item.source, item.source_detail)

        # 按 source_id 汇总 verdicts（src_id 与 routed_counts 一致）
        source_stats = {}  # src_id -> {approved, rejected, failed, scores}
        for r in reviewed:
            mapping = ref_source_map.get(r.ref_url)
            if not mapping:
                continue
            source, source_detail = mapping
            # RSS 子源用 source_detail 作为 src_id，其余用 source
            src_id = source_detail if source == "rss" else source
            if src_id not in source_stats:
                source_stats[src_id] = {"approved": 0, "rejected": 0, "failed": 0, "scores": []}
            if r.verdict == "approved":
                source_stats[src_id]["approved"] += 1
                source_stats[src_id]["scores"].append(r.total_score)
            elif r.verdict in ("retry", "discarded"):
                source_stats[src_id]["rejected"] += 1

        # 写入健康记录
        for src_id, stats in source_stats.items():
            scores = stats["scores"]
            avg_score = round(sum(scores) / len(scores), 1) if scores else None
            await record_source_health(db, CollectResult(
                source_id=src_id,
                total=routed_counts.get(src_id, 0),  # ← 修复：使用进入 review 的数量
                approved=stats["approved"],
                rejected=stats["rejected"],
                failed=0,
                avg_score=avg_score,
            ))

        return result


def continue_to_analyzers(state: PipelineState):
    sends = []
    if state.routed_github:
        sends.append(Send("github_analyzer", state))
    if state.routed_rss:
        sends.append(Send("rss_analyzer", state))
    if state.routed_feishu:
        sends.append(Send("feishu_analyzer", state))
    if state.routed_arxiv:
        sends.append(Send("arxiv_analyzer", state))
    return sends


def build_pipeline(registry: LLMRegistry):
    """构建并编译 LangGraph pipeline。

    Collector 和 DB 查重在图外执行（需要 DB 连接），
    图内编排：Router → Fan-out(4×Analyzer) → Aggregator → Reviewer。

    每个图内节点自动记录 phase 起止时间（路由/分析/汇总/审核）。
    analyzed_items 和 cost_records 使用 operator.add reducer，
    fan-out 并行分支的结果自动合并。
    """
    graph = StateGraph(PipelineState)

    graph.add_node("router", _RouterNode(_router_fn))
    graph.add_node("github_analyzer", _AnalyzerNode(analyze_github, "routed_github", registry))
    graph.add_node("rss_analyzer", _AnalyzerNode(analyze_rss, "routed_rss", registry))
    graph.add_node("feishu_analyzer", _AnalyzerNode(analyze_feishu, "routed_feishu", registry))
    graph.add_node("arxiv_analyzer", _AnalyzerNode(analyze_arxiv, "routed_arxiv", registry))
    graph.add_node("aggregator", _AggregatorNode(_aggregator_fn))
    graph.add_node("reviewer", _ReviewerNode(registry))

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", continue_to_analyzers)
    graph.add_edge("github_analyzer", "aggregator")
    graph.add_edge("rss_analyzer", "aggregator")
    graph.add_edge("feishu_analyzer", "aggregator")
    graph.add_edge("arxiv_analyzer", "aggregator")
    graph.add_edge("aggregator", "reviewer")
    graph.add_edge("reviewer", END)

    return graph.compile()


__all__ = ["build_pipeline", "record_phase_start", "record_phase_end", "PHASES", "set_pipeline_db", "reset_analyzer_counter"]
