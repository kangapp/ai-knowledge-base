import json

from ..core.database import Database
from ..core.time import now_bj_iso
from .common import decode_json_field


def _deep_report_row(row) -> dict:
    item = dict(row)
    item["report_json"] = decode_json_field(item.get("report_json", ""), {})
    item["evidence_json"] = decode_json_field(item.get("evidence_json", ""), [])
    item["tech_stack_json"] = decode_json_field(item.get("tech_stack_json", ""), {})
    return item


def _deep_report_list_row(row) -> dict:
    item = dict(row)
    item["report_tech_stack"] = decode_json_field(item.get("report_tech_stack", ""), [])
    item["tech_stack_json"] = decode_json_field(item.get("tech_stack_json", ""), {})
    return item


async def save_deep_report(
    db: Database,
    *,
    repo_url: str,
    repo_name: str,
    article_id: int | None,
    run_id: str,
    commit_sha: str,
    status: str,
    candidate_score: int,
    trigger_reason: str,
    report_json: dict,
    report_markdown: str,
    evidence_json: list,
    tech_stack_json: dict,
    file_tree_summary: str,
    analysis_cost: float,
    analysis_tokens: int,
    error: str,
    report_version: int = 2,
) -> int:
    now = now_bj_iso()
    cursor = await db.execute("""
        INSERT INTO deep_reports
        (repo_url, repo_name, article_id, run_id, commit_sha, status, candidate_score,
         trigger_reason, report_json, report_markdown, evidence_json, tech_stack_json,
         file_tree_summary, analysis_cost, analysis_tokens, error, created_at, updated_at,
         report_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo_url, commit_sha, report_version) DO UPDATE SET
            repo_name=excluded.repo_name,
            article_id=excluded.article_id,
            run_id=excluded.run_id,
            status=excluded.status,
            candidate_score=excluded.candidate_score,
            trigger_reason=excluded.trigger_reason,
            report_json=excluded.report_json,
            report_markdown=excluded.report_markdown,
            evidence_json=excluded.evidence_json,
            tech_stack_json=excluded.tech_stack_json,
            file_tree_summary=excluded.file_tree_summary,
            analysis_cost=excluded.analysis_cost,
            analysis_tokens=excluded.analysis_tokens,
            error=excluded.error,
            updated_at=excluded.updated_at
        WHERE NOT (deep_reports.status = 'completed' AND excluded.status = 'failed')
        RETURNING id
    """, (
        repo_url,
        repo_name,
        article_id,
        run_id,
        commit_sha,
        status,
        candidate_score,
        trigger_reason,
        json.dumps(report_json, ensure_ascii=False),
        report_markdown,
        json.dumps(evidence_json, ensure_ascii=False),
        json.dumps(tech_stack_json, ensure_ascii=False),
        file_tree_summary,
        analysis_cost,
        analysis_tokens,
        error,
        now,
        now,
        report_version,
    ))
    row = await cursor.fetchone()
    await db.commit()
    if row:
        return row["id"]
    existing = await db.fetch_one(
        """
        SELECT id FROM deep_reports
        WHERE repo_url = ? AND commit_sha = ? AND report_version = ?
        """,
        (repo_url, commit_sha, report_version),
    )
    return existing["id"] if existing else 0


async def get_deep_report(db: Database, report_id: int) -> dict | None:
    row = await db.fetch_one("SELECT * FROM deep_reports WHERE id = ?", (report_id,))
    return _deep_report_row(row) if row else None


async def get_completed_deep_report(db: Database, report_id: int) -> dict | None:
    row = await db.fetch_one(
        """
        SELECT * FROM deep_reports
        WHERE id = ?
          AND status = 'completed'
          AND report_version = (
              SELECT public_version FROM deep_report_settings WHERE id = 1
          )
        """,
        (report_id,),
    )
    return _deep_report_row(row) if row else None


async def get_latest_deep_report(db: Database) -> dict | None:
    row = await db.fetch_one(
        """
        SELECT * FROM deep_reports
        WHERE status = 'completed'
          AND report_version = (
              SELECT public_version FROM deep_report_settings WHERE id = 1
          )
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """
    )
    return _deep_report_row(row) if row else None


async def get_public_deep_report_version(db: Database) -> int:
    row = await db.fetch_one(
        "SELECT public_version FROM deep_report_settings WHERE id = 1"
    )
    return int(row["public_version"])


async def set_public_deep_report_version(db: Database, version: int) -> None:
    await db.execute(
        "UPDATE deep_report_settings SET public_version = ? WHERE id = 1",
        (version,),
    )
    await db.commit()


async def list_deep_reports_for_rebuild(
    db: Database,
    *,
    repo_url: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    params: list = []
    if repo_url:
        sql = """
            SELECT * FROM deep_reports
            WHERE repo_url = ?
              AND (
                  (report_version = 1 AND status = 'completed')
                  OR (report_version = 2 AND status = 'failed')
              )
            ORDER BY report_version DESC, id DESC
            LIMIT 1
        """
        params.append(repo_url)
    else:
        sql = """
            SELECT * FROM deep_reports
            WHERE report_version = 1 AND status = 'completed'
            ORDER BY id
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

    rows = await db.fetch_all(sql, tuple(params))
    return [_deep_report_row(row) for row in rows]


async def delete_deep_reports_by_version(db: Database, version: int) -> None:
    await db.execute(
        "DELETE FROM deep_reports WHERE report_version = ?",
        (version,),
    )
    await db.commit()


async def delete_failed_deep_reports_for_repo(
    db: Database,
    repo_url: str,
    *,
    keep_report_id: int,
) -> None:
    await db.execute(
        """
        DELETE FROM deep_reports
        WHERE repo_url = ?
          AND report_version = 2
          AND status = 'failed'
          AND id != ?
        """,
        (repo_url, keep_report_id),
    )
    await db.commit()


async def switch_public_deep_reports_to_v2(db: Database) -> None:
    await db._conn.execute("BEGIN")
    try:
        await db._conn.execute(
            "UPDATE deep_report_settings SET public_version = 2 WHERE id = 1"
        )
        await db._conn.execute(
            "DELETE FROM deep_reports WHERE report_version = 1"
        )
        await db._conn.commit()
    except Exception:
        await db._conn.rollback()
        raise


async def list_deep_reports(db: Database, page: int = 1, page_size: int = 20) -> dict:
    page = max(page, 1)
    page_size = max(page_size, 1)
    offset = (page - 1) * page_size

    total = await db.fetch_one("SELECT COUNT(*) as c FROM deep_reports")
    rows = await db.fetch_all(
        "SELECT * FROM deep_reports ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    )
    return {
        "items": [_deep_report_row(row) for row in rows],
        "total": total["c"] if total else 0,
        "page": page,
        "page_size": page_size,
    }


async def list_completed_deep_reports(db: Database, page: int = 1, page_size: int = 20) -> dict:
    page = max(page, 1)
    page_size = max(page_size, 1)
    offset = (page - 1) * page_size

    total = await db.fetch_one(
        """
        SELECT COUNT(*) as c
        FROM deep_reports
        WHERE status = 'completed'
          AND report_version = (
              SELECT public_version FROM deep_report_settings WHERE id = 1
          )
        """
    )
    rows = await db.fetch_all(
        """
        SELECT id, repo_url, repo_name, status, candidate_score, trigger_reason,
               commit_sha, created_at, updated_at, tech_stack_json, report_version,
               CASE
                   WHEN json_valid(report_json)
                   THEN json_extract(report_json, '$.summary')
                   ELSE ''
               END AS report_summary,
               CASE
                   WHEN json_valid(report_json)
                   THEN json_extract(report_json, '$.tech_stack')
                   ELSE '[]'
               END AS report_tech_stack
        FROM deep_reports
        WHERE status = 'completed'
          AND report_version = (
              SELECT public_version FROM deep_report_settings WHERE id = 1
          )
        ORDER BY updated_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )
    return {
        "items": [_deep_report_list_row(row) for row in rows],
        "total": total["c"] if total else 0,
        "page": page,
        "page_size": page_size,
    }
