from __future__ import annotations

import json
import uuid

try:
    from ..db import get_connection
    from .smoke_filter import (
        explain_test_data_filter_reason,
        is_smoke_job_record,
        is_smoke_model_record,
        is_test_data_audit_record,
        is_test_data_batch_record,
        is_test_data_track_record,
    )
except ImportError:
    from db import get_connection
    from services.smoke_filter import (
        explain_test_data_filter_reason,
        is_smoke_job_record,
        is_smoke_model_record,
        is_test_data_audit_record,
        is_test_data_batch_record,
        is_test_data_track_record,
    )


def record_audit_event(entity_type: str, entity_id: str, action: str, detail: dict | None = None) -> str:
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO audit_events (
                event_id, entity_type, entity_id, action, detail_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (event_id, entity_type, entity_id, action, json.dumps(detail or {}, ensure_ascii=False)),
        )
        conn.commit()
        return event_id
    finally:
        conn.close()


def list_audit_events(
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_test_data: bool = False,
) -> list[dict]:
    conn = get_connection()
    try:
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: list[object] = []
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)
        query += " ORDER BY datetime(created_at) DESC, rowid DESC"
        rows = conn.execute(query, tuple(params)).fetchall()
        items = [dict(row) for row in rows]
        if not include_test_data:
            items = [item for item in items if not _audit_event_filter_reason(conn, item)]
        else:
            for item in items:
                reason = _audit_event_filter_reason(conn, item)
                if reason:
                    item["filter_reason"] = reason
        return items[offset: offset + limit]
    finally:
        conn.close()


def _audit_event_filter_reason(conn, item: dict) -> str:
    reason = explain_test_data_filter_reason(item, kind="audit")
    if reason:
        return reason

    entity_type = (item.get("entity_type") or "").strip()
    entity_id = (item.get("entity_id") or "").strip()
    if not entity_type or not entity_id:
        return ""

    if entity_type == "batch":
        row = conn.execute("SELECT * FROM release_batches WHERE batch_id = ? LIMIT 1", (entity_id,)).fetchone()
        if row and is_test_data_batch_record(dict(row)):
            return "entity.batch_test_data"
    if entity_type == "track":
        row = conn.execute("SELECT * FROM tracks WHERE track_id = ? LIMIT 1", (entity_id,)).fetchone()
        if row:
            track = dict(row)
            batch = None
            if track.get("batch_id"):
                batch_row = conn.execute("SELECT * FROM release_batches WHERE batch_id = ? LIMIT 1", (track["batch_id"],)).fetchone()
                batch = dict(batch_row) if batch_row else None
            if is_test_data_track_record(track, batch):
                return "entity.track_test_data"
    if entity_type in {"job", "task"}:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ? OR legacy_task_id = ? LIMIT 1", (entity_id, entity_id)).fetchone()
        if row and is_smoke_job_record(dict(row)):
            return "entity.job_test_data"
    if entity_type in {"model", "voice_model"}:
        row = conn.execute("SELECT * FROM voice_models WHERE voice_model_id = ? OR legacy_model_id = ? LIMIT 1", (entity_id, entity_id)).fetchone()
        if row and is_smoke_model_record(dict(row)):
            return "entity.model_test_data"
    return ""
