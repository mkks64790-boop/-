"""
Thin ArtifactRepository facade (Stage60 DB Governance Phase 3).

Covers job_artifacts + audio_assets hotspots.
Thin wrappers over SQL; no table changes.
Optional conn support.
Dual/legacy not applicable here (newer tables).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from backend.db import get_connection


class ArtifactRepository:
    """Data access for job_artifacts (and audio_assets during transition)."""

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

    def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM job_artifacts WHERE job_id = ? ORDER BY datetime(created_at), rowid",
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)

    def get(self, job_id: str, artifact_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM job_artifacts
                WHERE job_id = ? AND artifact_id = ?
                LIMIT 1
                """,
                (job_id, artifact_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def get_final_for_job(self, job_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM job_artifacts
                WHERE job_id = ? AND is_final = 1
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def upsert_artifact(
        self,
        artifact_id: str,
        job_id: str,
        stage_name: str,
        artifact_type: str,
        file_path: str,
        file_size: int = 0,
        is_final: bool = False,
        lifecycle_state: str = "active",
        metadata: dict | None = None,
    ) -> str:
        """Basic INSERT/UPDATE for job_artifacts. File mirroring stays in services."""
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        is_final_int = 1 if is_final else 0
        conn = self._get_conn()
        try:
            # check exists for update path (simple)
            existing = conn.execute(
                "SELECT artifact_id FROM job_artifacts WHERE artifact_id = ? LIMIT 1",
                (artifact_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE job_artifacts
                    SET file_size = ?, is_final = CASE WHEN is_final=1 OR ? =1 THEN 1 ELSE 0 END,
                        lifecycle_state = ?, metadata_json = ?
                    WHERE artifact_id = ?
                    """,
                    (file_size, is_final_int, lifecycle_state, meta_json, artifact_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO job_artifacts (
                        artifact_id, job_id, stage_name, artifact_type,
                        file_path, file_size, is_final, lifecycle_state, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        job_id,
                        stage_name,
                        artifact_type,
                        file_path,
                        file_size,
                        is_final_int,
                        lifecycle_state,
                        meta_json,
                    ),
                )
            conn.commit()
            return artifact_id
        finally:
            self._close_conn(conn)

    def register_audio_asset(
        self,
        asset_id: str,
        job_id: str,
        asset_role: str,
        file_name: str,
        file_path: str,
        file_ext: str = "",
        file_size: int = 0,
        duration_sec: float = 0.0,
        dataset_id: str = "",
        lifecycle_state: str = "active",
        metadata: dict | None = None,
    ) -> str:
        """Thin access for audio_assets (used by asset_service hotspots)."""
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO audio_assets (
                    asset_id, dataset_id, job_id, asset_role, file_name, file_ext,
                    file_path, file_size, duration_sec, lifecycle_state, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    dataset_id,
                    job_id,
                    asset_role,
                    file_name,
                    file_ext,
                    file_path,
                    file_size,
                    duration_sec,
                    lifecycle_state,
                    meta_json,
                ),
            )
            conn.commit()
            return asset_id
        finally:
            self._close_conn(conn)

    def list_audio_for_job(self, job_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM audio_assets WHERE job_id = ? ORDER BY datetime(created_at), rowid",
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)
