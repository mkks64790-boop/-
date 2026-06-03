"""
Stage59C-3 — metadata-only approval/execute audit records (in-memory).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

STAGE_LABEL = "stage59c3"
REQUIRES_LATER_DB_INTEGRATION = True

_AUDIT_STORE: list[dict[str, Any]] = []


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_audit_event(
    *,
    event_type: str,
    entry_id: str,
    mode: str,
    decision: str,
    blocked_reasons: list[str] | None = None,
    real_execute_allowed: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "audit_id": f"audit_{uuid.uuid4().hex[:12]}",
        "stage": STAGE_LABEL,
        "event_type": event_type,
        "entry_id": entry_id,
        "mode": mode,
        "decision": decision,
        "blocked_reasons": list(blocked_reasons or []),
        "real_execute_allowed": bool(real_execute_allowed),
        "timestamp": _utc_now(),
        "requires_later_db_integration": REQUIRES_LATER_DB_INTEGRATION,
    }
    if extra:
        record.update(extra)
    _AUDIT_STORE.append(record)
    return record


def list_audit_events(*, entry_id: str | None = None) -> list[dict[str, Any]]:
    if entry_id is None:
        return list(_AUDIT_STORE)
    return [item for item in _AUDIT_STORE if item.get("entry_id") == entry_id]


def clear_audit_store() -> None:
    _AUDIT_STORE.clear()