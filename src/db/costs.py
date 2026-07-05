from ..core.database import Database
from ..core.time import now_bj_iso, today_bj
from ..graph.state import CostRecord


async def save_cost_log(db: Database, run_id: str, record: CostRecord):
    await db.execute("""
        INSERT INTO cost_logs
        (run_id, agent, provider, model, tokens_in, tokens_out, cost, ref_url,
         source, source_detail, source_id, status, error, latency_ms, attempt_no,
         prompt_name, prompt_version, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        run_id, record.agent, record.provider, record.model,
        record.tokens_in, record.tokens_out, record.cost, record.ref_url,
        record.source, record.source_detail, record.source_id,
        record.status, record.error, record.latency_ms, record.attempt_no,
        record.prompt_name, record.prompt_version, now_bj_iso(),
    ))
    await db.commit()


async def get_today_llm_spend(db: Database) -> tuple[float, dict[str, float]]:
    rows = await db.fetch_all("""
        SELECT provider, COALESCE(SUM(cost), 0) AS cost
        FROM cost_logs
        WHERE date(created_at) = ?
        GROUP BY provider
    """, (today_bj(),))
    provider_spend = {
        row["provider"]: float(row["cost"] or 0)
        for row in rows
        if row["provider"]
    }
    return sum(provider_spend.values()), provider_spend
