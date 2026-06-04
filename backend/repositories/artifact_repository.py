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

    def find_audio_asset(
        self,
        job_id: str,
        asset_role: str,
        file_path: str,
        dataset_id: str = "",
    ) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT asset_id
                FROM audio_assets
                WHERE job_id = ? AND COALESCE(dataset_id, '') = COALESCE(?, '') AND asset_role = ? AND file_path = ?
                LIMIT 1
                """,
                (job_id, dataset_id, asset_role, file_path),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def find_job_artifact(
        self,
        job_id: str,
        stage_name: str,
        artifact_type: str,
        file_path: str,
    ) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT artifact_id, is_final, metadata_json
                FROM job_artifacts
                WHERE job_id = ? AND stage_name = ? AND artifact_type = ? AND file_path = ?
                LIMIT 1
                """,
                (job_id, stage_name, artifact_type, file_path),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def update_artifact_metadata(self, job_id: str, artifact_id: str, metadata_json: str) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                """
                UPDATE job_artifacts
                SET metadata_json = ?
                WHERE job_id = ? AND artifact_id = ?
                """,
                (metadata_json, job_id, artifact_id),
            )
            conn.commit()
        finally:
            self._close_conn(conn)

    def patch_job_artifact(
        self,
        artifact_id: str,
        *,
        file_size: int | None = None,
        is_final: bool | None = None,
        metadata_json: str | None = None,
    ) -> None:
        """Partial update used by asset_service register path."""
        sets: list[str] = []
        params: list[Any] = []
        if file_size is not None:
            sets.append("file_size = ?")
            params.append(file_size)
        if is_final is not None:
            sets.append("is_final = CASE WHEN is_final = 1 OR ? = 1 THEN 1 ELSE 0 END")
            params.append(1 if is_final else 0)
        if metadata_json is not None:
            sets.append("metadata_json = ?")
            params.append(metadata_json)
        if not sets:
            return
        params.append(artifact_id)
        conn = self._get_conn()
        try:
            conn.execute(
                f"UPDATE job_artifacts SET {', '.join(sets)} WHERE artifact_id = ?",
                params,
            )
            conn.commit()
        finally:
            self._close_conn(conn)

    def get_final_job_artifact_prioritized(self, job_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM job_artifacts
                WHERE job_id = ? AND is_final = 1
                ORDER BY
                    CASE
                        WHEN artifact_type IN ('cover_master', 'train_model_pth') THEN 0
                        WHEN artifact_type IN ('cover_model', 'train_model_index') THEN 1
                        ELSE 2
                    END,
                    datetime(created_at) DESC,
                    rowid DESC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def get_final_cover_master(self, job_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM job_artifacts
                WHERE job_id = ? AND is_final = 1 AND artifact_type = 'cover_master'
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def list_studio_versions_for_track(
        self, track_id: str, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT
                    a.*,
                    j.job_id AS version_job_id,
                    j.job_type,
                    j.job_kind,
                    j.status AS job_status,
                    j.track_id AS job_track_id
                FROM job_artifacts a
                JOIN jobs j ON j.job_id = a.job_id
                WHERE COALESCE(j.track_id, '') = ?
                  AND COALESCE(j.job_type, '') = 'cover'
                  AND COALESCE(j.job_kind, j.job_type, '') = 'cover'
                  AND COALESCE(j.status, '') IN ('完成', '已完成', 'completed')
                  AND a.artifact_type IN (
                      'cover_master', 'studio_effect_draft_master', 'studio_effect_render_master'
                  )
                ORDER BY datetime(a.created_at) DESC, a.rowid DESC
                LIMIT ? OFFSET ?
                """,
                (track_id, limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)

    def list_final_cover_master_with_track(self) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT ja.*, j.track_id
                FROM job_artifacts ja
                LEFT JOIN jobs j ON j.job_id = ja.job_id
                WHERE ja.is_final = 1 AND ja.artifact_type = 'cover_master'
                ORDER BY datetime(ja.created_at) DESC, ja.rowid DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)
