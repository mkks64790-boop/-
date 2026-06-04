"""
Thin VoiceModelRepository facade (Stage60 DB Governance).

Wraps voice_models + legacy voice_assets during transition.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.db import get_connection


class VoiceModelRepository:
    """Data access for voice models (legacy voice_assets mirror)."""

    def __init__(self, conn: sqlite3.Connection | None = None):
        self._conn = conn or get_connection()

    def get(self, voice_model_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM voice_models WHERE voice_model_id = ?", (voice_model_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_by_legacy(self, legacy_model_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM voice_models WHERE legacy_model_id = ?", (legacy_model_id,)
        ).fetchone()
        return dict(row) if row else None

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM voice_models ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # TODO: create, etc. Migrate dual-write logic here gradually.

    def close(self):
        pass
