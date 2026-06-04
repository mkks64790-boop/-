"""
Legacy thin shim for Stage59C-3 execution policy (Stage60C transition).

All new code must import from the durable facade:
    from backend.services.execution_safety_service import (
        evaluate_execution_policy, ExecutionMode, ...
    )

This file only re-exports for any remaining internal/back-compat references.
Implementation now lives in execution_safety_service.py.
"""

from __future__ import annotations

from .execution_safety_service import (
    API_REQUESTED_MODES,
    ExecutionMode,
    NEXT_ALLOWED_STAGE,
    POLICY_STAGE_LABEL,
    REAL_RUNNER_NOT_ENABLED_REASON,
    SUPPORTED_MODES,
    VALID_APPROVAL_TOKEN_PREFIX,
    evaluate_execution_policy,
)

STAGE_LABEL = POLICY_STAGE_LABEL

__all__ = [
    "STAGE_LABEL",
    "API_REQUESTED_MODES",
    "ExecutionMode",
    "NEXT_ALLOWED_STAGE",
    "REAL_RUNNER_NOT_ENABLED_REASON",
    "SUPPORTED_MODES",
    "VALID_APPROVAL_TOKEN_PREFIX",
    "evaluate_execution_policy",
]