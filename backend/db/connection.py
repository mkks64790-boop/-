"""
backend/db/connection.py

Stage60 DB Governance Phase 2A: Connection ownership only.

Owns:
- database path resolution (DB file lives at backend/feishark.db)
- get_connection()
- row_factory
- PRAGMA setup (WAL, foreign_keys)

No schema, no CRUD, no backfills.
"""

import os
import sqlite3
from pathlib import Path


# Compute paths relative to this package so DB remains at backend/feishark.db
# even after db.py -> db/ package refactor.
_THIS_DIR = Path(__file__).resolve().parent  # backend/db/
_BACKEND_DIR = _THIS_DIR.parent             # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent         # project root

DB_PATH = str(_BACKEND_DIR / "feishark.db")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """获取数据库连接，启用 WAL 模式和外键约束。

    Single source of truth for DB connections (governance rule).

    db_path: optional override (used by orchestrator wrapper to honor
             test monkeypatches of backend.db.DB_PATH without mutating
             this submodule's globals directly).
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn
