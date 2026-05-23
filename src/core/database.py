# src/core/database.py
import os
from pathlib import Path
import aiosqlite


class Database:
    def __init__(self, db_path: Path | str, migrations_dir: Path | str | None = None):
        self.db_path = str(db_path)
        self.migrations_dir = str(migrations_dir) if migrations_dir else None
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._run_migrations()

    async def _run_migrations(self):
        # Ensure schema_version table exists (minimal bootstrap)
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        await self._conn.commit()
        # Ensure there's at least one row with version 0
        await self._conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (0)"
        )
        await self._conn.commit()
        # Read current version
        row = await self._conn.execute("SELECT MAX(version) as v FROM schema_version")
        result = await row.fetchone()
        current = result["v"] if result and result["v"] is not None else 0

        if not self.migrations_dir:
            return

        mig_dir = Path(self.migrations_dir)
        if not mig_dir.exists():
            return

        migrations = sorted(
            [f for f in os.listdir(str(mig_dir)) if f.endswith(".sql") and f[0].isdigit()],
            key=lambda f: int(f.split("_")[0])
        )

        for filename in migrations:
            num = int(filename.split("_")[0])
            if num > current:
                sql = (mig_dir / filename).read_text()
                await self._conn.executescript(sql)
                await self._conn.commit()
                # Delete all rows and insert new version (handles multiple rows case)
                await self._conn.execute("DELETE FROM schema_version")
                await self._conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (num,)
                )
                await self._conn.commit()
                # Re-read for next iteration
                row = await self._conn.execute("SELECT MAX(version) as v FROM schema_version")
                result = await row.fetchone()
                current = result["v"] if result and result["v"] is not None else 0

    async def fetch_one(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchone()

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchall()

    async def execute(self, sql: str, params: tuple = ()):
        return await self._conn.execute(sql, params)

    async def execute_many(self, sql: str, params_list: list[tuple]):
        return await self._conn.executemany(sql, params_list)

    async def commit(self):
        await self._conn.commit()

    async def backup(self, target_path: Path | str):
        """在线热备份到 target_path（使用 aiosqlite 自带 API，不依赖 sqlite3 CLI）"""
        target = await aiosqlite.connect(str(target_path))
        try:
            await self._conn.backup(target)
        finally:
            await target.close()

    async def close(self):
        if self._conn:
            await self._conn.close()
