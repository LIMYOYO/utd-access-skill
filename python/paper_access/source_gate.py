"""Local cross-process request serialization for sources with strict limits."""
import asyncio
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path


class SourceGate:
    def __init__(self, path: Path, *, now=time.time, sleep=asyncio.sleep):
        self.path, self.now, self.sleep = path, now, sleep

    def defer(self, source: str, seconds: float) -> None:
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("INSERT INTO limits VALUES(?,?) ON CONFLICT(source) DO UPDATE SET next_at=MAX(limits.next_at,excluded.next_at)",
                       (source, self.now() + seconds))

    @asynccontextmanager
    async def slot(self, source: str, interval: float):
        from .http import RateLimited
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=0)
        acquired = False
        try:
            try:
                db.execute("CREATE TABLE IF NOT EXISTS limits (source TEXT PRIMARY KEY, next_at REAL NOT NULL)")
                db.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as error:
                if "locked" in str(error).lower():
                    raise RateLimited(interval) from None
                raise
            acquired = True
            row = db.execute("SELECT next_at FROM limits WHERE source=?", (source,)).fetchone()
            delay = max(0, row[0] - self.now()) if row else 0
            if delay > 5:
                raise RateLimited(delay)
            if delay:
                await self.sleep(delay)
            yield
        finally:
            if acquired:
                db.execute("INSERT INTO limits VALUES(?,?) ON CONFLICT(source) DO UPDATE SET next_at=MAX(limits.next_at,excluded.next_at)",
                           (source, self.now() + interval))
                db.commit()
            db.close()
