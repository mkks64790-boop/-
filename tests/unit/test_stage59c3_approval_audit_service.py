"""Stage59C-3 approval audit tests."""

from backend.services.stage59_approval_audit_service import (
    clear_audit_store,
    list_audit_events,
    record_audit_event,
)


def setup_function() -> None:
    clear_audit_store()


def test_record_audit_event_metadata_only():
    record = record_audit_event(
        event_type="approval_preflight_accepted",
        entry_id="sc59",
        mode="approval_preflight",
        decision="pass",
        blocked_reasons=[],
    )
    assert record["audit_id"].startswith("audit_")
    assert record["requires_later_db_integration"] is True
    assert list_audit_events(entry_id="sc59")