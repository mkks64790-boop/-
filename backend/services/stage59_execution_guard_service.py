"""
Stage59C-3 — execution caps, sandbox plan, and disk preflight (metadata-only).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

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
    if int(max_items) != MAX_ITEMS:
        errors.append(f"max_items_must_be_{MAX_ITEMS}")
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