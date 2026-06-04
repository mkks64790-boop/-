"""
Thin VoiceModelRepository facade (Stage60 DB Governance).

Wraps voice_models + legacy voice_assets during transition.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from backend.db import get_connection


class VoiceModelRepository:
    """Data access for voice models (legacy voice_assets mirror during transition).

    Upsert performs dual-write to voice_assets for compat (temporary).
    Flexible lookup by id or legacy.
    Optional conn for injection; per-op get_connection for transition safety.
    No schema changes.
    """

    def __init__(self, conn: sqlite3.Connection | None = None):
        self._conn = conn  # None means fetch per-op

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
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass

    def get(self, voice_model_id: str) -> dict[str, Any] | None:
        """Flexible get by voice_model_id or legacy_model_id."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM voice_models WHERE voice_model_id = ? OR legacy_model_id = ? LIMIT 1",
                (voice_model_id, voice_model_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def get_by_legacy(self, legacy_model_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM voice_models WHERE legacy_model_id = ? LIMIT 1", (legacy_model_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def get_by_source_job(self, source_job_id: str) -> dict[str, Any] | None:
        if not source_job_id:
            return None
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT voice_model_id, legacy_model_id
                FROM voice_models
                WHERE source_job_id = ?
                ORDER BY datetime(updated_at) DESC, rowid DESC
                LIMIT 1
                """,
                (source_job_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def list(
        self,
        limit: int = 100,
        include_inactive: bool = True,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM voice_models"
            if not include_inactive:
                query += " WHERE COALESCE(lifecycle_state, 'active') NOT IN ('test_data', 'purged')"
            query += " ORDER BY datetime(created_at), rowid LIMIT ?"
            rows = conn.execute(query, (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)

    def upsert(
        self,
        voice_model_id: str,
        model_name: str,
        pth_path: str,
        index_path: str,
        default_pitch: int = 0,
        source_job_id: str = "",
        legacy_model_id: str | None = None,
        status: str = "ready",
        metadata: dict | None = None,
        lifecycle_state: str | None = None,
    ) -> str:
        """Central upsert for voice_models. Absorbs dual-write to voice_assets temporarily.
        Matches model_service.upsert_voice_model + _sync_legacy.
        """
        legacy_model_id = legacy_model_id or voice_model_id
        source_job_id = source_job_id or None
        metadata_payload = metadata or {}
        ls = lifecycle_state or "active"  # will be enriched in service layer if needed

        meta_json = json.dumps(metadata_payload, ensure_ascii=False)

        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO voice_models (
                    voice_model_id, legacy_model_id, model_name, source_job_id,
                    pth_path, index_path, default_pitch, status, lifecycle_state, metadata_json,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_at FROM voice_models WHERE voice_model_id = ?), CURRENT_TIMESTAMP),
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    voice_model_id,
                    legacy_model_id,
                    model_name,
                    source_job_id,
                    pth_path,
                    index_path,
                    default_pitch,
                    status,
                    ls,
                    meta_json,
                    voice_model_id,
                ),
            )
            conn.commit()

            # Dual write to legacy voice_assets (temporary compat, as in _sync_legacy_voice_asset)
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO voice_assets (
                        model_id, model_name, pth_path, index_path, default_pitch
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (voice_model_id, model_name, pth_path, index_path, default_pitch),
                )
                conn.commit()
            except Exception:
                # voice_assets may be minimal in some envs; do not fail canonical
                pass

            return voice_model_id
        finally:
            self._close_conn(conn)

    def create(self, **kwargs: Any) -> str:
        """Simple create alias delegating to upsert."""
        # expects same kwargs as upsert
        return self.upsert(**kwargs)

    def update_lifecycle(self, voice_model_id: str, lifecycle_state: str) -> bool:
        """For lifecycle backfills etc, thin."""
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "UPDATE voice_models SET lifecycle_state = ?, updated_at = CURRENT_TIMESTAMP WHERE voice_model_id = ? OR legacy_model_id = ?",
                (lifecycle_state, voice_model_id, voice_model_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            self._close_conn(conn)

    def find_by_name_or_path(self, model_name: str, pth_path: str) -> dict[str, Any] | None:
        """For import dedup checks etc. Returns row or None."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT voice_model_id, legacy_model_id
                FROM voice_models
                WHERE model_name = ? OR pth_path = ?
                LIMIT 1
                """,
                (model_name, pth_path),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)
