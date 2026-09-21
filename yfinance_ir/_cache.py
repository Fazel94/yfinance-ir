"""SQLite-backed symbol -> instrument cache (``<cache_dir>/symbols.sqlite``)."""

import os
import shutil
import sqlite3
import threading
import time
from typing import Optional

from .config import get_config

__all__ = ["SymbolCache", "get_cache", "clear"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS symbols (
    key TEXT PRIMARY KEY,
    ins_code TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT,
    isin TEXT,
    flow INTEGER,
    kind TEXT,
    source TEXT,
    alt_ins_codes TEXT,
    fetched_at REAL
)
"""


class SymbolCache:
    def __init__(self, path: str):
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT ins_code, symbol, name, isin, flow, kind, source, alt_ins_codes "
                "FROM symbols WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return {
            "ins_code": row[0],
            "symbol": row[1],
            "name": row[2],
            "isin": row[3],
            "flow": row[4],
            "kind": row[5],
            "source": row[6],
            "alt_ins_codes": tuple(c for c in (row[7] or "").split(",") if c),
        }

    def put(self, key: str, instrument) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO symbols "
                "(key, ins_code, symbol, name, isin, flow, kind, source, alt_ins_codes, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    key,
                    instrument.ins_code,
                    instrument.symbol,
                    instrument.name,
                    instrument.isin,
                    instrument.flow,
                    instrument.kind,
                    instrument.source,
                    ",".join(instrument.alt_ins_codes),
                    time.time(),
                ),
            )
            self._conn.commit()

    def get_by_isin(self, isin: str) -> Optional[dict]:
        with self._lock:
            cursor = self._conn.execute("SELECT key FROM symbols WHERE isin = ? LIMIT 1", (isin,))
            row = cursor.fetchone()
        return self.get(row[0]) if row else None

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM symbols")
            self._conn.commit()


_cache: Optional[SymbolCache] = None
_cache_path: Optional[str] = None
_cache_lock = threading.Lock()


def get_cache() -> SymbolCache:
    """Process-wide cache, reopened when ``config.cache_dir`` changes."""
    global _cache, _cache_path
    path = os.path.join(get_config().resolved_cache_dir(), "symbols.sqlite")
    with _cache_lock:
        if _cache is None or _cache_path != path:
            _cache = SymbolCache(path)
            _cache_path = path
        return _cache


def clear() -> None:
    """Drop every cached symbol resolution and every downloaded SCI workbook."""
    get_cache().clear()
    shutil.rmtree(os.path.join(get_config().resolved_cache_dir(), "sci"), ignore_errors=True)
