from __future__ import annotations

import json
import os
import uuid
from typing import Iterable

from fastapi import UploadFile

try:
    from ..db import BATCHES_ROOT, PROJECT_ROOT, get_connection
    from .audit_service import record_audit_event
    from .smoke_filter import explain_test_data_filter_reason, is_test_data_batch_record
except ImportError:
    from db import BATCHES_ROOT, PROJECT_ROOT, get_connection
    from services.audit_service import record_audit_event
    from services.smoke_filter import explain_test_data_filter_reason, is_test_data_batch_record


def get_batch_root(batch_id: str) -> str:
    return os.path.join(BATCHES_ROOT, batch_id)


def ensure_batch_dirs(batch_id: str) -> dict[str, str]:
    root = get_batch_root(batch_id)
    paths = {
        "root": root,
        "tracks": os.path.join(root, "tracks"),
        "exports": os.path.join(root, "exports"),
    }
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
    return paths


def _normalize_root_path(path: str) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.join(PROJECT_ROOT, path)


def _maybe_relpath(path: str) -> str:
    try:
        common = os.path.commonpath([os.path.abspath(path), os.path.abspath(PROJECT_ROOT)])
    except ValueError:
        return path
    if common == os.path.abspath(PROJECT_ROOT):
        return os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")
    return path


def create_batch(batch_name: str, target_platforms: list[str] | None = None, output_root: str = "", metadata: dict | None = None) -> dict:
    batch_id = f"batch_{uuid.uuid4().hex[:10]}"
    dirs = ensure_batch_dirs(batch_id)
    stored_output_root = _normalize_root_path(output_root) or dirs["exports"]
    os.makedirs(stored_output_root, exist_ok=True)

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO release_batches (
                batch_id, batch_name, status, target_platforms_json, output_root, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                batch_name.strip() or batch_id,
                "draft",
                json.dumps(target_platforms or [], ensure_ascii=False),
                os.path.relpath(stored_output_root, PROJECT_ROOT).replace("\\", "/")
                if _maybe_relpath(stored_output_root) != stored_output_root
                else stored_output_root,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    record_audit_event("batch", batch_id, "create", {"batch_name": batch_name, "target_platforms": target_platforms or []})
    return get_batch(batch_id) or {}


def list_batches(
    limit: int = 50,
    offset: int = 0,
    *,
    include_smoke: bool = False,
    include_test_data: bool = False,
) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                b.*,
                COALESCE(t.track_count, 0) AS track_count,
                COALESCE(t.completed_track_count, 0) AS completed_track_count
            FROM release_batches b
            LEFT JOIN (
                SELECT
                    batch_id,
                    COUNT(*) AS track_count,
                    SUM(CASE WHEN status IN ('completed', 'ready', 'published') THEN 1 ELSE 0 END) AS completed_track_count
                FROM tracks
                GROUP BY batch_id
            ) t ON t.batch_id = b.batch_id
            ORDER BY datetime(b.created_at) DESC, b.rowid DESC
            """
        ).fetchall()
        items = [dict(row) for row in rows]
        include_filtered = bool(include_smoke or include_test_data)
        if not include_filtered:
            items = [item for item in items if not is_test_data_batch_record(item)]
        else:
            for item in items:
                reason = explain_test_data_filter_reason(item, kind="batch")
                if reason:
                    item["filter_reason"] = reason
        return items[offset: offset + limit]
    finally:
        conn.close()


def hidden_test_batch_count() -> int:
    conn = get_connection()
    try:
        rows = [dict(row) for row in conn.execute("SELECT * FROM release_batches").fetchall()]
        return sum(1 for row in rows if is_test_data_batch_record(row))
    finally:
        conn.close()


def get_batch(batch_id: str, *, include_test_data: bool = True) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM release_batches WHERE batch_id = ? LIMIT 1", (batch_id,)).fetchone()
        if not row:
            return None
        payload = dict(row)
        reason = explain_test_data_filter_reason(payload, kind="batch")
        if reason:
            payload["filter_reason"] = reason
        track_rows = conn.execute(
            "SELECT * FROM tracks WHERE batch_id = ? ORDER BY datetime(created_at) DESC, rowid DESC",
            (batch_id,),
        ).fetchall()
        tracks = [dict(track) for track in track_rows]
        if not include_test_data:
            tracks = [track for track in tracks if not reason and not explain_test_data_filter_reason(track, kind="track")]
        payload["track_count"] = len(tracks)
        payload["hidden_test_track_count"] = len(track_rows) - len(tracks)
        payload["tracks"] = tracks
        payload["audit_events"] = [
            dict(row)
            for row in conn.execute(
                """
                SELECT * FROM audit_events
                WHERE entity_type = 'batch' AND entity_id = ?
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT 20
                """,
                (batch_id,),
            ).fetchall()
        ]
        return payload
    finally:
        conn.close()


async def import_tracks_to_batch(
    batch_id: str,
    files: Iterable[UploadFile],
    *,
    titles: list[str] | None = None,
    artist: str = "",
    source_type: str = "upload",
    notes: str = "",
    metadata: dict | None = None,
) -> list[dict]:
    dirs = ensure_batch_dirs(batch_id)
    track_root = dirs["tracks"]
    batch = get_batch(batch_id)
    if not batch:
        raise ValueError("batch_not_found")

    imported: list[dict] = []
    titles = titles or []
    for index, upload in enumerate(files, start=1):
        track_id = f"trk_{uuid.uuid4().hex[:10]}"
        track_dir = os.path.join(track_root, track_id, "source")
        os.makedirs(track_dir, exist_ok=True)

        original_name = upload.filename or f"track_{index}.wav"
        ext = os.path.splitext(original_name)[1].lower() or ".wav"
        stored_name = f"{index:02d}_{track_id}{ext}"
        abs_path = os.path.join(track_dir, stored_name)

        size = 0
        with open(abs_path, "wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                size += len(chunk)

        rel_path = os.path.relpath(abs_path, PROJECT_ROOT).replace("\\", "/")
        title = (titles[index - 1] if index - 1 < len(titles) else "") or os.path.splitext(original_name)[0] or f"Track {index}"

        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO tracks (
                    track_id, batch_id, title, artist, source_type, status,
                    notes, source_audio_path, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track_id,
                    batch_id,
                    title.strip() or track_id,
                    artist.strip(),
                    source_type,
                    "imported",
                    notes.strip(),
                    rel_path,
                    json.dumps(
                        {
                            **(metadata or {}),
                            "original_filename": original_name,
                            "file_size": size,
                            "source_type": source_type,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        record_audit_event(
            "track",
            track_id,
            "import",
            {"batch_id": batch_id, "original_filename": original_name, "file_size": size},
        )
        imported.append(
            {
                "track_id": track_id,
                "batch_id": batch_id,
                "title": title,
                "artist": artist.strip(),
                "status": "imported",
                "source_audio_path": rel_path,
                "file_size": size,
            }
        )

    return imported
