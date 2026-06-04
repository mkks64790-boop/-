"""
Legacy shim/impl holder for Stage59C-4b real-smoke plan (Stage60C transition).

The durable facade (uvr_smoke_service) re-exports.
All new code should import from the facade.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .short_chain_manifest_service import load_manifest
from .artifact_lifecycle_service import (
    build_mock_uvr_artifact_contracts,
    safe_runtime_run_id,
)
from .execution_safety_service import (
    REAL_RUNNER_NOT_ENABLED_REASON,
    evaluate_execution_guards,
    evaluate_execution_policy,
)

REAL_SMOKE_NOT_EXECUTED_REASON = "real_uvr_smoke_plan_never_executes"
REAL_SMOKE_REQUIRES_FILE_CHECK_REASON = "real_smoke_requires_file_exists_check"
REAL_SMOKE_PLAN_MODE = "real_smoke_plan"


def build_expected_real_smoke_artifacts(
    *, run_id: str, entry_id: str
) -> list[dict[str, Any]]:
    """Build the two expected UVR stem contracts for a real-smoke plan (metadata-only)."""
    return build_mock_uvr_artifact_contracts(run_id=run_id, entry_id=entry_id)


def evaluate_real_smoke_plan(
    entry_id: str,
    *,
    manifest_path: str | Path,
    project_root: str | Path | None = None,
    clip_seconds: int | None = 45,
    check_file_exists: bool = True,
    confirm_execute: bool = False,
    approval_token: str | None = None,
    max_items: int | None = 1,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Plan-only evaluation for a would-be real UVR A/B separation on an approved short-chain entry.

    Always forces real_execute_allowed=false and includes runner-not-enabled + smoke-never-executes.
    Optionally validates that the source material file referenced by the manifest entry exists on disk.
    Composes guards + policy results.
    """
    root = Path(project_root) if project_root else Path.cwd()
    mpath = Path(manifest_path)

    if run_id is None:
        run_id = f"stage59_real_{entry_id}"
    safe_run = safe_runtime_run_id(run_id)

    blocked_reasons: list[str] = []
    source_file_ok = True

    if check_file_exists:
        try:
            manifest: dict[str, Any] = {}
            if mpath.exists():
                manifest = load_manifest(mpath)
            entries = manifest.get("entries", []) if isinstance(manifest, dict) else []
            ent = next(
                (e for e in entries if str(e.get("id", "")) == str(entry_id)), None
            )
            if ent:
                src_rel = ent.get("source_path") or ent.get("rel_path") or ""
                if src_rel:
                    sp = Path(src_rel)
                    if not sp.is_absolute():
                        sp = root / sp
                    if not (sp.exists() and sp.stat().st_size > 0):
                        source_file_ok = False
            else:
                blocked_reasons.append("entry_not_in_manifest")
        except Exception as ex:
            blocked_reasons.append(f"manifest_load_or_file_check_failed:{ex}")
            source_file_ok = False

        if not source_file_ok:
            blocked_reasons.append(REAL_SMOKE_REQUIRES_FILE_CHECK_REASON)
    else:
        # Explicitly skipping the file existence check for this plan request.
        # The plan must still declare that a real run would require the on-disk check.
        blocked_reasons.append(REAL_SMOKE_REQUIRES_FILE_CHECK_REASON)

    # Guards (sandbox, caps, disk)
    guards = evaluate_execution_guards(
        run_id=safe_run,
        clip_seconds=clip_seconds or 45,
        max_items=max_items or 1,
        project_root=root,
    )

    # Policy (approval fields, preflight vs execute decision)
    # Use approval_preflight so that complete token+confirm yields approval_complete=True
    policy = evaluate_execution_policy(
        entry_id=entry_id,
        manifest_path=mpath if mpath.exists() else None,
        project_root=root,
        clip_seconds=clip_seconds or 45,
        check_file_exists=check_file_exists,
        confirm_execute=confirm_execute,
        approval_token=approval_token,
        requested_mode="approval_preflight",
        max_items=max_items or 1,
        run_id=safe_run,
    )

    for br in policy.get("blocked_reasons", []) or []:
        if br not in blocked_reasons:
            blocked_reasons.append(br)

    # Smoke plan is never allowed to execute
    if REAL_RUNNER_NOT_ENABLED_REASON not in blocked_reasons:
        blocked_reasons.append(REAL_RUNNER_NOT_ENABLED_REASON)
    if REAL_SMOKE_NOT_EXECUTED_REASON not in blocked_reasons:
        blocked_reasons.append(REAL_SMOKE_NOT_EXECUTED_REASON)

    blocked_reasons = list(dict.fromkeys(blocked_reasons))

    expected_artifacts = build_expected_real_smoke_artifacts(
        run_id=safe_run, entry_id=entry_id
    )

    safety = {
        "audio_files_written": False,
        "uvr_subprocess": False,
        "rvc_inference": False,
        "guards_ok": guards.get("guards_ok", False),
        "files_created": False,
    }

    # approval_complete: trust the preflight policy result (which checks token+confirm+guards)
    # The smoke plan always adds its own never-executes blocks on top.
    approval_complete = bool(policy.get("approval_complete"))

    # ok means "we could produce a plan", not "execute allowed"
    guards_ok = guards.get("guards_ok", True)
    ok = guards_ok and "entry_not_in_manifest" not in blocked_reasons

    result: dict[str, Any] = {
        "ok": ok,
        "mode": REAL_SMOKE_PLAN_MODE,
        "entry_id": entry_id,
        "run_id": safe_run,
        "approval_complete": approval_complete,
        "real_execute_allowed": False,
        "blocked_reasons": blocked_reasons,
        "safety": safety,
        "expected_artifacts": expected_artifacts,
        "planned_sandbox": f"shared_data/stage59_runtime/{safe_run}",
        "clip_seconds": clip_seconds,
        "max_items": max_items,
        "guards": guards,
    }

    # carry over useful fields from policy if present
    for carry in ("planned_sandbox", "real_execute_block_reason"):
        if carry in policy and carry not in result:
            result[carry] = policy[carry]

    return result


__all__ = [
    "REAL_RUNNER_NOT_ENABLED_REASON",
    "REAL_SMOKE_NOT_EXECUTED_REASON",
    "REAL_SMOKE_PLAN_MODE",
    "REAL_SMOKE_REQUIRES_FILE_CHECK_REASON",
    "build_expected_real_smoke_artifacts",
    "evaluate_real_smoke_plan",
]
