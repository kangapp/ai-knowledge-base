# src/core/source_health.py
import logging
from pathlib import Path
from datetime import datetime, timezone
import yaml
from .config import SourcesConfig, load_sources_config, SourceConfig

logger = logging.getLogger("pipeline")

APPROVED_RATE_THRESHOLD = 0.30
CONSECUTIVE_FAILURES = 3
PROTECTION_CYCLES = 3


class SourceHealthTracker:
    """跟踪数据源健康状态，判断是否需要淘汰"""

    def __init__(self, db):
        self._db = db

    async def get_recent_records(self, source_id: str, limit: int = 3) -> list[dict]:
        """获取最近 N 次采集的健康记录"""
        rows = await self._db.fetch_all("""
            SELECT * FROM source_health
            WHERE source_id = ?
            ORDER BY date DESC
            LIMIT ?
        """, (source_id, limit))
        return [dict(r) for r in rows]

    async def get_source_collection_count(self, source_id: str) -> int:
        """获取数据源累计采集次数（用于判断保护期）"""
        row = await self._db.fetch_one(
            "SELECT COUNT(*) as c FROM source_health WHERE source_id = ?",
            (source_id,)
        )
        return row["c"] if row else 0

    async def should_evict(self, source_id: str) -> tuple[bool, str]:
        """
        判断数据源是否应该被淘汰。
        返回 (should_evict, reason)

        保护期（< 3 次记录）：跳过淘汰判断
        超过保护期后：只看最近 3 次计算 approved 率
        """
        records = await self.get_recent_records(source_id, limit=CONSECUTIVE_FAILURES + PROTECTION_CYCLES)

        if len(records) < PROTECTION_CYCLES:
            return False, f"保护期内（已采集 {len(records)} 次，< {PROTECTION_CYCLES} 次）"

        # 超过保护期后，只看最近 3 次
        recent = records[:CONSECUTIVE_FAILURES]
        if len(recent) < CONSECUTIVE_FAILURES:
            return False, "记录不足"

        total = sum(r["total_collected"] for r in recent)
        if total == 0:
            return False, "无采集数据"

        approved = sum(r["approved"] for r in recent)
        rate = approved / total

        if rate < APPROVED_RATE_THRESHOLD:
            return True, f"连续{CONSECUTIVE_FAILURES}次 approved 率 {rate:.1%} < {APPROVED_RATE_THRESHOLD:.1%}"
        return False, f"approved 率 {rate:.1%} 正常"

    async def check_and_evict(self, sources: list[SourceConfig]) -> list[dict]:
        """
        检查所有数据源，执行淘汰。
        返回淘汰记录列表。
        """
        # Import here to avoid circular import
        from .source_manager import SourceManager

        evicted = []
        for source in sources:
            should, reason = await self.should_evict(source.id)
            if should:
                SourceManager.remove(source.id)
                logger.info("source.evicted", extra={"source_id": source.id, "reason": reason})
                evicted.append({"source_id": source.id, "reason": reason})
        return evicted

    async def get_all_sources_health(self, limit: int = 7) -> list[dict]:
        """获取所有数据源的最近健康数据"""
        rows = await self._db.fetch_all("""
            SELECT DISTINCT source_id FROM source_health
        """)
        result = []
        for row in rows:
            source_id = row["source_id"]
            records = await self.get_recent_records(source_id, limit=limit)
            total_collected = sum(r["total_collected"] for r in records)
            total_approved = sum(r["approved"] for r in records)
            approved_rate = total_approved / total_collected if total_collected > 0 else 0
            avg_score = sum(r["avg_score"] or 0 for r in records) / len(records) if records else None
            result.append({
                "source_id": source_id,
                "recent_approved_rate": round(approved_rate, 3),
                "recent_total": total_collected,
                "avg_score": round(avg_score, 1) if avg_score else None,
                "records": records,
            })
        return result