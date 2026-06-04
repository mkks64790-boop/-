"""
Thin TrackRepository facade (Stage60 DB Governance Phase 3).

For tracks + release_batches related.
Thin SQL access; no schema change.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from backend.db import get_connection


class TrackRepository:
    """Data access for tracks (and related masters)."""

    def __init__(self, conn: sqlite3.Connection | None = None):
        self._conn = conn

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

    def get(self, track_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM tracks WHERE track_id = ? LIMIT 1", (track_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def list(self, batch_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            if batch_id:
                rows = conn.execute(
                    "SELECT * FROM tracks WHERE batch_id = ? ORDER BY created_at DESC LIMIT ?",
                    (batch_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tracks ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)

    def upsert_track(
        self,
        track_id: str,
        batch_id: str,
        title: str = "",
        artist: str = "",
        source_type: str = "upload",
        status: str = "draft",
        notes: str = "",
        source_audio_path: str = "",
        current_master_job_id: str = "",
        current_master_artifact_id: str = "",
        metadata: dict | None = None,
    ) -> str:
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO tracks (
                    track_id, batch_id, title, artist, source_type, status, notes,
                    source_audio_path, current_master_job_id, current_master_artifact_id,
                    metadata_json, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_at FROM tracks WHERE track_id = ?), CURRENT_TIMESTAMP),
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    track_id,
                    batch_id,
                    title,
                    artist,
                    source_type,
                    status,
                    notes,
                    source_audio_path,
                    current_master_job_id,
                    current_master_artifact_id,
                    meta_json,
                    track_id,
                ),
            )
            conn.commit()
            return track_id
        finally:
            self._close_conn(conn)

    def set_current_master(self, track_id: str, job_id: str, artifact_id: str = "") -> bool:
        conn = self._get_conn()
        try:
            cur = conn.execute(
                """
                UPDATE tracks
                SET current_master_job_id = ?, current_master_artifact_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE track_id = ?
                """,
                (job_id, artifact_id, track_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            self._close_conn(conn)

    def update_status(self, track_id: str, status: str) -> bool:
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "UPDATE tracks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE track_id = ?",
                (status, track_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            self._close_conn(conn)

    # Cover job marker helpers (thin, logic may live in track_service for now)
    def mark_cover_job_state(
        self, track_id: str, job_id: str, state: str, model_id: str = "", voice_name: str = ""
    ) -> None:
        # For now just touch updated; detailed marker fields may be in job or separate.
        # Keep thin: service can use for status side effects if needed.
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE tracks SET updated_at = CURRENT_TIMESTAMP WHERE track_id = ?",
                (track_id,),
            )
            conn.commit()
        finally:
            self._close_conn(conn)
