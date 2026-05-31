from __future__ import annotations

import json
import uuid

try:
    from ..db import get_connection
except ImportError:
    from db import get_connection


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
        query += " ORDER BY datetime(created_at) DESC, rowid DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
