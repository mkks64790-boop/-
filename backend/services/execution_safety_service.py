from __future__ import annotations

# Stage60 durable facade for safety gates, approval policy, sandbox checks, and audit.
# This facade intentionally delegates to existing Stage59 modules for zero behavior change.

from .stage59_approval_audit_service import (
    clear_audit_store,
    list_audit_events,
    record_audit_event,
)
from .stage59_execution_guard_service import (
    CLIP_SECONDS_MAX,
    CLIP_SECONDS_MIN,
    DEFAULT_CLIP_SECONDS,
    DEFAULT_TIMEOUT_SEC,
    MAX_ITEMS,
    evaluate_execution_guards,
    plan_sandbox,
    validate_caps,
    validate_disk_preflight,
)
from .stage59_execution_policy_service import (
    REAL_RUNNER_NOT_ENABLED_REASON,
    VALID_APPROVAL_TOKEN_PREFIX,
    ExecutionMode,
    evaluate_execution_policy,
)


__all__ = [
    "CLIP_SECONDS_MAX",
    "CLIP_SECONDS_MIN",
    "DEFAULT_CLIP_SECONDS",
    "DEFAULT_TIMEOUT_SEC",
    "ExecutionMode",
    "MAX_ITEMS",
    "REAL_RUNNER_NOT_ENABLED_REASON",
    "VALID_APPROVAL_TOKEN_PREFIX",
    "clear_audit_store",
    "evaluate_execution_guards",
    "evaluate_execution_policy",
    "list_audit_events",
    "plan_sandbox",
    "record_audit_event",
    "validate_caps",
    "validate_disk_preflight",
]

# Lazy import to break circular with thin shims
def __getattr__(name):
    if name in {
        "clear_audit_store",
        "list_audit_events",
        "record_audit_event",
    }:
        from .stage59_approval_audit_service import (
            clear_audit_store,
            list_audit_events,
            record_audit_event,
        )
        return locals().get(name) or globals().get(name)
    if name in {
        "CLIP_SECONDS_MAX",
        "CLIP_SECONDS_MIN",
        "DEFAULT_CLIP_SECONDS",
        "DEFAULT_TIMEOUT_SEC",
        "MAX_ITEMS",
        "evaluate_execution_guards",
        "plan_sandbox",
        "validate_caps",
        "validate_disk_preflight",
    }:
        from .stage59_execution_guard_service import (
            CLIP_SECONDS_MAX,
            CLIP_SECONDS_MIN,
            DEFAULT_CLIP_SECONDS,
            DEFAULT_TIMEOUT_SEC,
            MAX_ITEMS,
            evaluate_execution_guards,
            plan_sandbox,
            validate_caps,
            validate_disk_preflight,
        )
        return locals().get(name) or globals().get(name)
    if name in {
        "REAL_RUNNER_NOT_ENABLED_REASON",
        "VALID_APPROVAL_TOKEN_PREFIX",
        "ExecutionMode",
        "evaluate_execution_policy",
    }:
        from .stage59_execution_policy_service import (
            REAL_RUNNER_NOT_ENABLED_REASON,
            VALID_APPROVAL_TOKEN_PREFIX,
            ExecutionMode,
            evaluate_execution_policy,
        )
        return locals().get(name) or globals().get(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

