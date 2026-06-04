"""
Thin JobRepository facade (Stage60 DB Governance).

For now: thin wrapper around existing patterns in db.py and job_service.
Goal: centralize access, hide legacy_task_id details over time.
No schema changes. No new backfills here.

Future: move more SQL here, remove direct conn from services.
"""

from __future__ import annotations

import sqlite3
from typing import Any

# Temporary: use existing connection until full migration
# In later phases, repos will own their conn or use injected.
from backend.db import get_connection


class JobRepository:
    """Data access for jobs (and legacy tasks mirror during transition)."""

    def __init__(self, conn: sqlite3.Connection | None = None):
        self._conn = conn or get_connection()

    def get(self, job_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_by_legacy_task(self, legacy_task_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE legacy_task_id = ?", (legacy_task_id,)
        ).fetchone()
        return dict(row) if row else None

    def list(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def create(self, **fields: Any) -> str:
        # Minimal for now; in practice call existing db helpers or expand
        # This is placeholder to establish the boundary.
        # Real create logic remains in job_service/db for this phase.
        job_id = fields.get("job_id")
        if not job_id:
            raise ValueError("job_id required")
        # TODO in next phase: move INSERT here, remove from services
        return job_id

    # TODO: add update_status, etc. as we migrate call sites.

    def close(self):
        # If we own the conn in future
        pass
