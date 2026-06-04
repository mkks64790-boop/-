"""
Thin JobRepository facade (Stage60 DB Governance).

For now: thin wrapper around existing patterns in db.py and job_service.
Goal: centralize access, hide legacy_task_id details over time.
No schema changes. No new backfills here.

Future: move more SQL here, remove direct conn from services.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

# Temporary: use existing connection until full migration
# In later phases, repos will own their conn or use injected.
from backend.db import get_connection, ACTIVE_COMPUTE_STATUSES


class JobRepository:
    """Data access for jobs (and legacy tasks mirror during transition).

    Supports optional injected conn (for tests/shared tx).
    Uses get_connection() per-op if none provided (transition friendly, no leaks).
    Absorbs legacy tasks dual-write logic temporarily; no table shape changes.
    """

    def __init__(self, conn: sqlite3.Connection | None = None):
        self._conn = conn  # if None, fetch per operation

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        return get_connection()

    def _should_close(self) -> bool:
        return self._conn is None

    def _close_conn(self, conn: sqlite3.Connection) -> None:
        if self._should_close():
            try:
                conn.close()
            except Exception:
                pass

    def close(self) -> None:
        """Explicit close only meaningful if conn was provided and caller wants."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Get by job_id or legacy_task_id (flexible lookup for compat)."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ? OR legacy_task_id = ? LIMIT 1",
                (job_id, job_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def get_by_legacy_task(self, legacy_task_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM jobs WHERE legacy_task_id = ? LIMIT 1", (legacy_task_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def list(
        self,
        status: str | None = None,
        limit: int = 100,
        job_type: str | None = None,
        strategy_key: str | None = None,
        voice_name: str | None = None,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM jobs WHERE 1=1"
            params: list[Any] = []
            if job_type:
                query += " AND job_type = ?"
                params.append(job_type)
            if status:
                query += " AND status = ?"
                params.append(status)
            if strategy_key:
                query += " AND strategy_key = ?"
                params.append(strategy_key)
            if voice_name:
                query += " AND voice_name LIKE ?"
                params.append(f"%{voice_name}%")
            query += " ORDER BY datetime(created_at) DESC, rowid DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)

    def upsert(self, **fields: Any) -> str:
        """Insert or replace job row. Absorbs _insert_job logic.
        Also performs legacy tasks mirror for transition compat (dual write).
        """
        job_id = fields.get("job_id")
        if not job_id:
            raise ValueError("job_id required")
        legacy_task_id = fields.get("legacy_task_id") or job_id
        job_type = fields.get("job_type") or "cover"
        job_kind = fields.get("job_kind") or job_type
        strategy_key = fields.get("strategy_key") or ""
        status = fields.get("status") or "pending"
        current_stage = fields.get("current_stage") or ""
        compute_ready = int(fields.get("compute_ready") or 0)
        track_id = fields.get("track_id") or ""
        resource_class = fields.get("resource_class") or "gpu_heavy"
        depends_on = fields.get("depends_on") or []
        voice_model_id = fields.get("voice_model_id") or ""
        voice_name = fields.get("voice_name") or ""
        input_path = fields.get("input_path") or ""
        output_root = fields.get("output_root") or ""
        error_log = fields.get("error_log") or ""
        metadata = fields.get("metadata") or {}

        depends_json = json.dumps(depends_on or [], ensure_ascii=False)
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        conn = self._get_conn()
        try:
            # Canonical jobs upsert (matches job_service._insert_job)
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (
                    job_id, legacy_task_id, job_type, job_kind, strategy_key, status, current_stage,
                    compute_ready, track_id, resource_class, depends_on_json, voice_model_id, voice_name, input_path, output_root,
                    error_log, metadata_json, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_at FROM jobs WHERE job_id = ?), CURRENT_TIMESTAMP),
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    job_id,
                    legacy_task_id,
                    job_type,
                    job_kind,
                    strategy_key,
                    status,
                    current_stage,
                    compute_ready,
                    track_id,
                    resource_class,
                    depends_json,
                    voice_model_id,
                    voice_name,
                    input_path,
                    output_root,
                    error_log,
                    meta_json,
                    job_id,
                ),
            )
            conn.commit()

            # Legacy tasks dual-write (thin absorption for compat; matches create_task/create_train_task partials)
            # Only if not already present, to mimic INSERT OR IGNORE behavior.
            task_type = "train" if job_type == "train" else "cover"
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO tasks (task_id, input_file, task_type, voice_name) VALUES (?, ?, ?, ?)",
                    (job_id, input_path or output_root, task_type, voice_name),
                )
                conn.commit()
            except Exception:
                # tasks table may have minimal cols in some states; ignore to not break canonical
                pass

            return job_id
        finally:
            self._close_conn(conn)

    def create(self, **fields: Any) -> str:
        """Alias for upsert for simple create use cases."""
        return self.upsert(**fields)

    def update_status(self, job_id: str, status: str, error_log: str = "") -> bool:
        """Update status on jobs + legacy tasks mirror. Absorbs update_task_status logic (thin)."""
        conn = self._get_conn()
        try:
            # Simplified mirror of db.update_task_status / job_service logic; keep status as-is for legacy strings
            normalized = (status or "").strip()
            if normalized == "pending":
                sql = """
                    UPDATE jobs
                    SET status = ?, current_stage = 'pending', error_log = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ? OR legacy_task_id = ?
                """
            elif normalized in ("\u5df2\u53d6\u6d88", "cancelled", "canceled"):
                sql = """
                    UPDATE jobs
                    SET status = ?, current_stage = 'cancelled', error_log = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ? OR legacy_task_id = ?
                """
            elif normalized in ("\u5931\u8d25", "failed", "fail", "error"):
                sql = """
                    UPDATE jobs
                    SET status = ?,
                        current_stage = CASE
                            WHEN COALESCE(current_stage, '') IN ('', 'pending', 'job_dispatch', 'job_control')
                            THEN 'failed'
                            ELSE current_stage
                        END,
                        error_log = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ? OR legacy_task_id = ?
                """
            elif normalized in ("\u5df2\u5b8c\u6210", "completed", "complete", "done", "success", "succeeded"):
                sql = """
                    UPDATE jobs
                    SET status = ?,
                        current_stage = CASE
                            WHEN COALESCE(current_stage, '') IN ('', 'pending', 'job_dispatch', 'job_control')
                            THEN CASE WHEN COALESCE(job_type,'') = 'train' THEN 'train_register_model' ELSE 'cover_mix' END
                            ELSE current_stage
                        END,
                        error_log = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ? OR legacy_task_id = ?
                """
            else:
                sql = """
                    UPDATE jobs
                    SET status = ?, error_log = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ? OR legacy_task_id = ?
                """
            cur = conn.execute(sql, (status, error_log, job_id, job_id))
            # mirror to tasks
            tcur = conn.execute(
                "UPDATE tasks SET status = ?, error_log = ? WHERE task_id = ?",
                (status, error_log, job_id),
            )
            conn.commit()
            ok = (cur.rowcount > 0) or (tcur.rowcount > 0)
            return ok
        finally:
            self._close_conn(conn)

    def get_next_pending(self) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM jobs
                WHERE status = 'pending'
                  AND compute_ready = 1
                ORDER BY datetime(created_at) ASC, rowid ASC
                LIMIT 1
                """
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def has_active_compute(self) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT job_id
                FROM jobs
                WHERE status IN ({})
                LIMIT 1
                """.format(",".join("?" for _ in ACTIVE_COMPUTE_STATUSES)),
                tuple(ACTIVE_COMPUTE_STATUSES),
            ).fetchone()
            return row is not None
        finally:
            self._close_conn(conn)

    def activate_cover(self, job_id: str, voice_model_id: str, voice_name: str = "") -> bool:
        """Activate cover job (used by activate_cover_job)."""
        conn = self._get_conn()
        try:
            conn.execute(
                """
                UPDATE jobs
                SET job_type = 'cover', job_kind = 'cover', resource_class = 'gpu_heavy', strategy_key = 'cover_strategy',
                    compute_ready = 1, voice_model_id = ?, voice_name = COALESCE(NULLIF(?, ''), voice_name), updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? OR legacy_task_id = ?
                """,
                (voice_model_id, voice_name, job_id, job_id),
            )
            conn.commit()
            return True
        finally:
            self._close_conn(conn)

    def activate_train(self, job_id: str) -> bool:
        conn = self._get_conn()
        try:
            conn.execute(
                """
                UPDATE jobs
                SET job_type = 'train', job_kind = 'train', resource_class = 'gpu_heavy', compute_ready = 1, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? OR legacy_task_id = ?
                """,
                (job_id, job_id),
            )
            conn.commit()
            return True
        finally:
            self._close_conn(conn)

    def get_row(self, job_id: str) -> dict[str, Any] | None:
        """Compat alias for get with flexible lookup."""
        return self.get(job_id)

    def get_for_track_with_voice_name(self, track_id: str, job_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT
                    j.*,
                    COALESCE(NULLIF(j.voice_name, ''), vm.model_name, '') AS resolved_voice_name
                FROM jobs j
                LEFT JOIN voice_models vm
                    ON j.voice_model_id != ''
                   AND (vm.voice_model_id = j.voice_model_id OR vm.legacy_model_id = j.voice_model_id)
                WHERE COALESCE(j.track_id, '') = ?
                  AND j.job_id = ?
                LIMIT 1
                """,
                (track_id, job_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def list_for_track_with_voice_name(
        self, track_id: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT
                    j.*,
                    COALESCE(NULLIF(j.voice_name, ''), vm.model_name, '') AS resolved_voice_name
                FROM jobs j
                LEFT JOIN voice_models vm
                    ON j.voice_model_id != ''
                   AND (vm.voice_model_id = j.voice_model_id OR vm.legacy_model_id = j.voice_model_id)
                WHERE COALESCE(j.track_id, '') = ?
                ORDER BY datetime(j.created_at) DESC, j.rowid DESC
                LIMIT ? OFFSET ?
                """,
                (track_id, limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)
