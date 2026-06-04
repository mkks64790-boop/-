"""
Thin MaterialRepository facade (Stage60 DB Governance Phase 3).

For material_libraries + material_assets (inventory hotspots).
Thin; no shape changes.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from backend.db import get_connection


class MaterialRepository:
    """Data access for material libraries and assets."""

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

    def get_library(self, library_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM material_libraries WHERE library_id = ? OR library_key = ? LIMIT 1",
                (library_id, library_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            self._close_conn(conn)

    def list_libraries(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM material_libraries"
            if enabled_only:
                query += " WHERE enabled = 1"
            query += " ORDER BY display_name"
            rows = conn.execute(query).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)

    def upsert_library(
        self,
        library_id: str,
        library_key: str,
        display_name: str,
        source_group: str = "",
        root_path: str = "",
        license_status: str = "unknown",
        enabled: int = 1,
        metadata: dict | None = None,
    ) -> str:
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO material_libraries (
                    library_id, library_key, display_name, source_group, root_path,
                    license_status, enabled, metadata_json, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_at FROM material_libraries WHERE library_id = ?), CURRENT_TIMESTAMP),
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    library_id,
                    library_key,
                    display_name,
                    source_group,
                    root_path,
                    license_status,
                    enabled,
                    meta_json,
                    library_id,
                ),
            )
            conn.commit()
            return library_id
        finally:
            self._close_conn(conn)

    def list_assets(
        self,
        library_id: str | None = None,
        limit: int = 200,
        quality_state: str | None = None,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            query = "SELECT * FROM material_assets WHERE 1=1"
            params: list[Any] = []
            if library_id:
                query += " AND library_id = ?"
                params.append(library_id)
            if quality_state:
                query += " AND quality_state = ?"
                params.append(quality_state)
            query += " ORDER BY datetime(created_at) DESC, rowid DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_conn(conn)

    def upsert_asset(
        self,
        material_id: str,
        library_id: str,
        file_name: str,
        file_path: str,
        source_group: str = "",
        file_ext: str = "",
        relative_path: str = "",
        file_size: int = 0,
        duration_sec: float | None = None,
        sample_rate: int | None = None,
        material_profile: str = "",
        material_role: str = "",
        quality_state: str = "unknown",
        retention_status: str = "keep",
        lifecycle_state: str = "active",
        metadata: dict | None = None,
    ) -> str:
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO material_assets (
                    material_id, library_id, source_group, file_name, file_ext,
                    file_path, relative_path, file_size, duration_sec, sample_rate,
                    material_profile, material_role, quality_state, retention_status,
                    lifecycle_state, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    material_id,
                    library_id,
                    source_group,
                    file_name,
                    file_ext,
                    file_path,
                    relative_path,
                    file_size,
                    duration_sec,
                    sample_rate,
                    material_profile,
                    material_role,
                    quality_state,
                    retention_status,
                    lifecycle_state,
                    meta_json,
                ),
            )
            conn.commit()
            return material_id
        finally:
            self._close_conn(conn)

    def delete_assets_for_library(self, library_id: str) -> int:
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "DELETE FROM material_assets WHERE library_id = ?", (library_id,)
            )
            conn.commit()
            return cur.rowcount or 0
        finally:
            self._close_conn(conn)
