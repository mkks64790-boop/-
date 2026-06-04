"""
Legacy thin shim for Stage59C-3 audit (Stage60C transition).

All new code must import from the durable facade:
    from backend.services.execution_safety_service import (
        record_audit_event, list_audit_events, clear_audit_store, ...
    )

This file only re-exports for any remaining internal/back-compat references.
Implementation now lives in execution_safety_service.py.
"""

from __future__ import annotations

from .execution_safety_service import (
    AUDIT_REQUIRES_LATER_DB_INTEGRATION,
    AUDIT_STAGE_LABEL,
    clear_audit_store,
    list_audit_events,
    record_audit_event,
)

# Re-export constants under old names for compat if any code still reads them
STAGE_LABEL = AUDIT_STAGE_LABEL
REQUIRES_LATER_DB_INTEGRATION = AUDIT_REQUIRES_LATER_DB_INTEGRATION

__all__ = [
    "STAGE_LABEL",
    "REQUIRES_LATER_DB_INTEGRATION",
    "clear_audit_store",
    "list_audit_events",
    "record_audit_event",
]