"""
Legacy thin shim for Stage59C-3 execution guards (Stage60C transition).

All new code must import from the durable facade:
    from backend.services.execution_safety_service import (
        validate_caps, plan_sandbox, validate_disk_preflight,
        evaluate_execution_guards, ...
    )

This file only re-exports for any remaining internal/back-compat references.
Implementation now lives in execution_safety_service.py.
"""

from __future__ import annotations

from .execution_safety_service import (
    CLIP_SECONDS_MAX,
    CLIP_SECONDS_MIN,
    DEFAULT_CLIP_SECONDS,
    DEFAULT_TIMEOUT_SEC,
    MAX_ITEMS,
    STAGE_RUNTIME_REL,
    evaluate_execution_guards,
    plan_sandbox,
    validate_caps,
    validate_disk_preflight,
)

__all__ = [
    "CLIP_SECONDS_MAX",
    "CLIP_SECONDS_MIN",
    "DEFAULT_CLIP_SECONDS",
    "DEFAULT_TIMEOUT_SEC",
    "MAX_ITEMS",
    "STAGE_RUNTIME_REL",
    "evaluate_execution_guards",
    "plan_sandbox",
    "validate_caps",
    "validate_disk_preflight",
]