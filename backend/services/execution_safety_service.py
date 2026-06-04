from __future__ import annotations

# Stage60 durable facade for safety gates, approval policy, sandbox checks, and audit.
# Implementation moved here from the stage59_* modules to complete Stage60C.
# Old stage59_*_service.py files are now thin shims re-exporting from this facade
# for backward compatibility during final transition. All new code should import
# from this facade.

# --- Inlined from stage59_approval_audit_service.py (Stage59C-3 audit) ---
import uuid
from datetime import datetime, timezone
from typing import Any

AUDIT_STAGE_LABEL = "stage59c3"
AUDIT_REQUIRES_LATER_DB_INTEGRATION = True

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
        "stage": AUDIT_STAGE_LABEL,
        "event_type": event_type,
        "entry_id": entry_id,
        "mode": mode,
        "decision": decision,
        "blocked_reasons": list(blocked_reasons or []),
        "real_execute_allowed": bool(real_execute_allowed),
        "timestamp": _utc_now(),
        "requires_later_db_integration": AUDIT_REQUIRES_LATER_DB_INTEGRATION,
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


# --- Inlined from stage59_execution_guard_service.py (Stage59C-3 guards) ---
import shutil
from pathlib import Path

STAGE_RUNTIME_REL = Path("shared_data") / "stage59_runtime"

MAX_ITEMS = 1
CLIP_SECONDS_MIN = 20
CLIP_SECONDS_MAX = 60
DEFAULT_CLIP_SECONDS = 45
DEFAULT_TIMEOUT_SEC = 300


def _normalize_run_id(run_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run_id)
    return safe[:128] or "stage59_run"


def validate_caps(*, max_items: int, clip_seconds: int) -> dict[str, Any]:
    errors: list[str] = []
    try:
        if int(max_items) != MAX_ITEMS:
            errors.append(f"max_items_must_be_{MAX_ITEMS}")
    except (TypeError, ValueError):
        errors.append("max_items_invalid")
    try:
        clip = int(clip_seconds)
    except (TypeError, ValueError):
        errors.append("clip_seconds_invalid")
        clip = DEFAULT_CLIP_SECONDS
    else:
        if clip < CLIP_SECONDS_MIN:
            errors.append(f"clip_seconds_below_min:{CLIP_SECONDS_MIN}")
        if clip > CLIP_SECONDS_MAX:
            errors.append(f"clip_seconds_above_max:{CLIP_SECONDS_MAX}")

    return {
        "caps_ok": not errors,
        "errors": errors,
        "caps": {
            "max_items": MAX_ITEMS,
            "clip_seconds_min": CLIP_SECONDS_MIN,
            "clip_seconds_max": CLIP_SECONDS_MAX,
            "default_clip_seconds": DEFAULT_CLIP_SECONDS,
            "requested_max_items": max_items,
            "requested_clip_seconds": clip_seconds,
            "timeout_sec": DEFAULT_TIMEOUT_SEC,
            "batch_execution": False,
        },
    }


def plan_sandbox(*, run_id: str, project_root: Path) -> dict[str, Any]:
    """Planned sandbox under shared_data/stage59_runtime/<run_id>/ — no files created."""
    safe_id = _normalize_run_id(run_id)
    rel_root = (STAGE_RUNTIME_REL / safe_id).as_posix()
    abs_root = (project_root / STAGE_RUNTIME_REL / safe_id).resolve()
    try:
        abs_root.relative_to(project_root.resolve())
    except ValueError:
        return {
            "sandbox_ok": False,
            "errors": ["sandbox_path_outside_project"],
            "planned_temp_root": "",
        }

    if ".." in rel_root:
        return {
            "sandbox_ok": False,
            "errors": ["sandbox_path_traversal"],
            "planned_temp_root": rel_root,
        }

    return {
        "sandbox_ok": True,
        "errors": [],
        "planned_temp_root": rel_root,
        "absolute_planned_root": str(abs_root),
        "cleanup_required": True,
        "files_created": False,
        "cleanup_plan": [
            f"remove_tree:{rel_root}",
            "on_failure:remove_tree",
            "on_success:archive_or_promote_later",
        ],
    }


def validate_disk_preflight(*, project_root: Path, min_free_mb: int = 256) -> dict[str, Any]:
    """Cheap disk check; never creates probe files in 59C-3."""
    target = project_root / "shared_data"
    try:
        usage = shutil.disk_usage(str(target))
        free_mb = usage.free // (1024 * 1024)
        total_mb = usage.total // (1024 * 1024)
        disk_ok = free_mb >= min_free_mb
        return {
            "disk_ok": disk_ok,
            "disk_check_mode": "shutil_disk_usage",
            "free_mb": free_mb,
            "total_mb": total_mb,
            "min_free_mb_required": min_free_mb,
            "errors": [] if disk_ok else [f"insufficient_free_space_mb:{free_mb}"],
        }
    except OSError as exc:
        return {
            "disk_ok": True,
            "disk_check_mode": "metadata_only",
            "errors": [],
            "warning": f"disk_usage_unavailable:{exc}",
        }


def evaluate_execution_guards(
    *,
    run_id: str,
    project_root: Path,
    max_items: int,
    clip_seconds: int,
) -> dict[str, Any]:
    caps = validate_caps(max_items=max_items, clip_seconds=clip_seconds)
    sandbox = plan_sandbox(run_id=run_id, project_root=project_root)
    disk = validate_disk_preflight(project_root=project_root)
    errors = list(caps.get("errors") or [])
    errors.extend(sandbox.get("errors") or [])
    errors.extend(disk.get("errors") or [])
    return {
        "guards_ok": not errors,
        "errors": errors,
        "caps": caps,
        "sandbox": sandbox,
        "disk": disk,
        "cleanup_required": True,
        "files_created": False,
    }


# --- Inlined from stage59_execution_policy_service.py (Stage59C-3 policy) ---
import uuid
from enum import Enum
from pathlib import Path

from backend.services.short_chain_manifest_service import (
    ManifestPathSafetyError,
    resolve_safe_manifest_path,
)
from backend.services.short_chain_uvr_service import evaluate_uvr_ab_readiness

POLICY_STAGE_LABEL = "stage59c3"
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
        "stage": POLICY_STAGE_LABEL,
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


# --- Public exports (all symbols now defined directly in this module) ---
__all__ = [
    "AUDIT_STAGE_LABEL",
    "AUDIT_REQUIRES_LATER_DB_INTEGRATION",
    "API_REQUESTED_MODES",
    "CLIP_SECONDS_MAX",
    "CLIP_SECONDS_MIN",
    "DEFAULT_CLIP_SECONDS",
    "DEFAULT_TIMEOUT_SEC",
    "ExecutionMode",
    "MAX_ITEMS",
    "NEXT_ALLOWED_STAGE",
    "POLICY_STAGE_LABEL",
    "REAL_RUNNER_NOT_ENABLED_REASON",
    "STAGE_RUNTIME_REL",
    "SUPPORTED_MODES",
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

# No more delegation to old shims for core symbols.
# Lazy kept only if needed for very late imports, but definitions are here now.
def __getattr__(name):
    # Fallback for any edge cases during transition
    if name in __all__:
        return globals().get(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

