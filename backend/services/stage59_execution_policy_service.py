"""
Stage59C-3 — UVR execution policy, approval gate, and mode routing (no real UVR).
"""

from __future__ import annotations

import uuid
from enum import Enum
from pathlib import Path
from typing import Any

from backend.services.short_chain_manifest_service import (
    ManifestPathSafetyError,
    resolve_safe_manifest_path,
)
from backend.services.short_chain_uvr_service import evaluate_uvr_ab_readiness
from backend.services.stage59_approval_audit_service import record_audit_event
from backend.services.stage59_execution_guard_service import (
    DEFAULT_CLIP_SECONDS,
    evaluate_execution_guards,
)

STAGE_LABEL = "stage59c3"
REAL_RUNNER_NOT_ENABLED_REASON = "real_uvr_runner_not_enabled_stage59c3"
NEXT_ALLOWED_STAGE = "stage59c4_tiny_real_uvr_smoke"
VALID_APPROVAL_TOKEN_PREFIX = "stage59-"


class ExecutionMode(str, Enum):
    DRY_RUN = "dry_run"
    READINESS = "readiness"
    MOCK_EXECUTE = "mock_execute"
    APPROVAL_PREFLIGHT = "approval_preflight"
    REAL_EXECUTE = "real_execute"


SUPPORTED_MODES = frozenset(mode.value for mode in ExecutionMode)
API_REQUESTED_MODES = frozenset(
    {ExecutionMode.APPROVAL_PREFLIGHT.value, ExecutionMode.REAL_EXECUTE.value}
)


def _approval_requirements_template() -> dict[str, Any]:
    return {
        "confirm_execute": False,
        "approval_token_present": False,
        "approval_token_valid": False,
        "entry_id_required": True,
        "manifest_path_safe": False,
        "entry_whitelisted": False,
        "uvr_ab_in_chain": False,
        "max_items_exactly_one": False,
        "clip_seconds_in_range": False,
        "disk_preflight": False,
        "sandbox_preflight": False,
        "timeout_policy_present": False,
        "real_runner_configured": False,
    }


def _is_valid_approval_token(token: str | None) -> bool:
    if not token or not str(token).strip():
        return False
    text = str(token).strip()
    return text.startswith(VALID_APPROVAL_TOKEN_PREFIX) and len(text) >= len(
        "stage59-local-approval"
    )


def evaluate_execution_policy(
    entry_id: str,
    *,
    manifest_path: Path | str | None = None,
    project_root: Path | None = None,
    clip_seconds: int = DEFAULT_CLIP_SECONDS,
    check_file_exists: bool = True,
    confirm_execute: bool = False,
    approval_token: str | None = None,
    requested_mode: str = ExecutionMode.APPROVAL_PREFLIGHT.value,
    max_items: int = 1,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Evaluate approval preflight / real-execute request policy.

    Stage59C-3: real execute remains blocked even when all approval fields are valid.
    """
    from backend.services.short_chain_manifest_service import project_root_from_here

    root = project_root or project_root_from_here()
    mode = str(requested_mode or ExecutionMode.APPROVAL_PREFLIGHT.value).strip().lower()
    safe_entry_id = str(entry_id or "").strip()
    safe_run_id = run_id or f"stage59c3_{safe_entry_id}_{uuid.uuid4().hex[:8]}"

    blocked_reasons: list[str] = []
    requirements = _approval_requirements_template()

    base: dict[str, Any] = {
        "ok": False,
        "stage": STAGE_LABEL,
        "mode": mode,
        "real_execute_allowed": False,
        "blocked": True,
        "blocked_reasons": blocked_reasons,
        "approval_requirements": requirements,
        "run_id": safe_run_id,
        "entry_id": safe_entry_id,
        "next_allowed_stage": NEXT_ALLOWED_STAGE,
        "safety": {
            "uvr_subprocess": False,
            "rvc_inference": False,
            "gpu_required": False,
            "audio_files_written": False,
            "real_runner_enabled": False,
        },
    }

    if mode not in API_REQUESTED_MODES:
        blocked_reasons.append("invalid_requested_mode")
        base["blocked_reasons"] = blocked_reasons
        record_audit_event(
            event_type="invalid_mode_rejected",
            entry_id=safe_entry_id,
            mode=mode,
            decision="blocked",
            blocked_reasons=blocked_reasons,
        )
        return base

    if not safe_entry_id:
        blocked_reasons.append("entry_id_required")
        base["blocked_reasons"] = blocked_reasons
        return base

    try:
        manifest_resolved = resolve_safe_manifest_path(manifest_path, project_root=root)
        requirements["manifest_path_safe"] = True
        base["manifest_path"] = str(manifest_resolved)
    except ManifestPathSafetyError as exc:
        blocked_reasons.append(exc.reason)
        base["blocked_reasons"] = blocked_reasons
        record_audit_event(
            event_type="unsafe_manifest_rejected",
            entry_id=safe_entry_id,
            mode=mode,
            decision="blocked",
            blocked_reasons=blocked_reasons,
        )
        return base

    guards = evaluate_execution_guards(
        run_id=safe_run_id,
        project_root=root,
        max_items=max_items,
        clip_seconds=clip_seconds,
    )
    base["caps"] = guards["caps"]["caps"]
    base["sandbox"] = guards["sandbox"]
    base["disk"] = guards["disk"]
    requirements["max_items_exactly_one"] = guards["caps"]["caps_ok"]
    requirements["clip_seconds_in_range"] = guards["caps"]["caps_ok"]
    requirements["disk_preflight"] = guards["disk"]["disk_ok"]
    requirements["sandbox_preflight"] = guards["sandbox"]["sandbox_ok"]
    requirements["timeout_policy_present"] = True
    requirements["real_runner_configured"] = False
    blocked_reasons.extend(guards.get("errors") or [])

    readiness = evaluate_uvr_ab_readiness(
        safe_entry_id,
        manifest_path=manifest_resolved,
        project_root=root,
        clip_seconds=clip_seconds,
        check_file_exists=check_file_exists,
        runner_mode="mock",
    )
    base["readiness"] = readiness
    if readiness.get("ok"):
        requirements["entry_whitelisted"] = True
        requirements["uvr_ab_in_chain"] = True
    else:
        reason = readiness.get("blocked_reason", "readiness_blocked")
        blocked_reasons.append(str(reason))
        record_audit_event(
            event_type="entry_rejected",
            entry_id=safe_entry_id,
            mode=mode,
            decision="blocked",
            blocked_reasons=blocked_reasons,
        )
        base["blocked_reasons"] = blocked_reasons
        return base

    requirements["confirm_execute"] = bool(confirm_execute)
    token_present = bool(approval_token and str(approval_token).strip())
    requirements["approval_token_present"] = token_present
    token_valid = _is_valid_approval_token(approval_token)
    requirements["approval_token_valid"] = token_valid

    if not confirm_execute:
        blocked_reasons.append("confirm_execute_missing")
    if not token_present:
        blocked_reasons.append("approval_token_missing")
    elif not token_valid:
        blocked_reasons.append("approval_token_invalid")

    approval_fields_complete = (
        confirm_execute and token_valid and not blocked_reasons
    )

    if mode == ExecutionMode.REAL_EXECUTE.value:
        blocked_reasons.append(REAL_RUNNER_NOT_ENABLED_REASON)
        base["blocked"] = True
        base["ok"] = False
        base["blocked_reasons"] = list(dict.fromkeys(blocked_reasons))
        record_audit_event(
            event_type="real_execute_blocked",
            entry_id=safe_entry_id,
            mode=mode,
            decision="blocked",
            blocked_reasons=base["blocked_reasons"],
        )
        return base

    # approval_preflight: framework may PASS without full approval fields
    framework_ok = guards["guards_ok"] and readiness.get("ok")
    if not framework_ok:
        base["blocked_reasons"] = list(dict.fromkeys(blocked_reasons))
        return base

    base["blocked"] = not approval_fields_complete
    base["ok"] = True
    base["approval_complete"] = approval_fields_complete
    base["blocked_reasons"] = (
        list(dict.fromkeys(blocked_reasons)) if not approval_fields_complete else []
    )
    base["real_execute_allowed"] = False
    base["real_execute_block_reason"] = REAL_RUNNER_NOT_ENABLED_REASON

    record_audit_event(
        event_type="approval_preflight_accepted"
        if approval_fields_complete
        else "approval_preflight_incomplete",
        entry_id=safe_entry_id,
        mode=mode,
        decision="pass" if approval_fields_complete else "pass_with_warnings",
        blocked_reasons=base["blocked_reasons"],
        real_execute_allowed=False,
        extra={"run_id": safe_run_id},
    )
    return base