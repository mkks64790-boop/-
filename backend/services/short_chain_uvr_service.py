"""
Stage59C-0 — short-chain UVR A/B planner (dry-run only).

Loads manifest via short_chain_manifest_service; whitelists gate-approved entry ids only.
Does not invoke UVR, subprocess, or write audio artifacts in this stage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from backend.services.short_chain_manifest_service import (
    ALLOWED_CHAIN_STEPS,
    DURATION_MAX_SEC,
    DURATION_MIN_SEC,
    ManifestPathSafetyError,
    build_short_chain_whitelist,
    default_manifest_path,
    evaluate_short_chain_gate,
    load_manifest,
    project_root_from_here,
    resolve_safe_manifest_path,
)

STAGE_LABEL = "stage59c0"
STAGE59C1_LABEL = "stage59c1"
UVR_STAGE = "uvr_ab"
EXECUTE_BLOCKED_REASON = "execute_blocked_by_stage59c0"
STAGE59C0_EXECUTE_BLOCK_REASON = EXECUTE_BLOCKED_REASON
DEFAULT_CLIP_SECONDS = 45
DEFAULT_PLAN_LIMIT = 1
MIN_CLIP_SECONDS = 1
MAX_CLIP_SECONDS = 60


class Stage59UvrBlockedError(RuntimeError):
    """Raised when a short-chain UVR action is blocked (whitelist, execute gate, etc.)."""

    def __init__(self, reason: str, *, details: dict[str, Any] | None = None) -> None:
        self.reason = reason
        self.details = details or {}
        message = reason if not self.details else f"{reason}:{self.details}"
        super().__init__(message)


def _clamp_clip_seconds(value: int | float | None) -> int:
    try:
        seconds = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        seconds = DEFAULT_CLIP_SECONDS
    return max(MIN_CLIP_SECONDS, min(seconds, MAX_CLIP_SECONDS))


def _normalize_entry_ids(entry_ids: str | Sequence[str] | None) -> list[str]:
    if entry_ids is None:
        return []
    if isinstance(entry_ids, str):
        text = entry_ids.strip()
        return [text] if text else []
    return [str(item).strip() for item in entry_ids if str(item).strip()]


def _looks_like_path(value: str) -> bool:
    lowered = value.replace("\\", "/").lower()
    if lowered.startswith("shared_data/"):
        return True
    suffixes = (".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg")
    return any(lowered.endswith(ext) for ext in suffixes) or ":/" in lowered or lowered.startswith("/")


def _entries_by_id(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for entry in data.get("entries") or []:
        if isinstance(entry, dict):
            entry_id = str(entry.get("id") or "").strip()
            if entry_id:
                mapping[entry_id] = entry
    return mapping


def _entry_has_uvr_stage(entry: dict[str, Any]) -> bool:
    chain = entry.get("intended_chain")
    if not isinstance(chain, list):
        return False
    return UVR_STAGE in [str(step) for step in chain]


def _planned_action(
    entry: dict[str, Any],
    *,
    clip_seconds: int,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "entry_id": str(entry.get("id") or ""),
        "source_path": str(entry.get("source_path") or ""),
        "clip_seconds": clip_seconds,
        "stages": [UVR_STAGE],
        "dry_run": dry_run,
    }


def plan_short_chain_uvr(
    entry_ids: str | Sequence[str] | None = None,
    *,
    manifest_path: Path | str | None = None,
    project_root: Path | None = None,
    clip_seconds: int = DEFAULT_CLIP_SECONDS,
    dry_run: bool = True,
    execute: bool = False,
    limit: int = DEFAULT_PLAN_LIMIT,
    check_file_exists: bool = True,
    raise_on_block: bool = True,
) -> dict[str, Any]:
    """
    Plan capped UVR A/B actions for manifest entry ids (default dry-run JSON only).

    When execute=True, UVR is blocked in stage59c0 (raises or returns blocked_reason).
    """
    root = project_root or project_root_from_here()
    try:
        manifest_file = resolve_safe_manifest_path(manifest_path, project_root=root)
    except ManifestPathSafetyError as exc:
        base_pre: dict[str, Any] = {
            "ok": False,
            "stage": STAGE_LABEL,
            "dry_run": bool(dry_run),
            "execute": bool(execute),
            "manifest_path": str(manifest_path or ""),
            "planned_actions": [],
            "blocked": True,
            "blocked_reason": exc.reason,
        }
        if raise_on_block:
            raise Stage59UvrBlockedError(exc.reason) from exc
        return base_pre
    safe_clip = _clamp_clip_seconds(clip_seconds)
    safe_limit = max(1, int(limit or DEFAULT_PLAN_LIMIT))
    requested_ids = _normalize_entry_ids(entry_ids)

    base: dict[str, Any] = {
        "ok": False,
        "stage": STAGE_LABEL,
        "dry_run": bool(dry_run),
        "execute": bool(execute),
        "manifest_path": str(manifest_file),
        "clip_seconds": safe_clip,
        "duration_window_sec": {"min": DURATION_MIN_SEC, "max": DURATION_MAX_SEC},
        "allowed_chain_steps": sorted(ALLOWED_CHAIN_STEPS),
        "planned_actions": [],
        "blocked": False,
        "blocked_reason": "",
    }

    if execute:
        base["blocked"] = True
        base["blocked_reason"] = EXECUTE_BLOCKED_REASON
        if raise_on_block:
            raise Stage59UvrBlockedError(EXECUTE_BLOCKED_REASON, details={"execute": True})
        return base

    if not dry_run:
        base["blocked"] = True
        base["blocked_reason"] = "dry_run_required_in_stage59c0"
        if raise_on_block:
            raise Stage59UvrBlockedError(base["blocked_reason"])
        return base

    if not manifest_file.is_file():
        base["blocked_reason"] = "manifest_missing"
        if raise_on_block:
            raise Stage59UvrBlockedError(base["blocked_reason"], details={"manifest_path": str(manifest_file)})
        return base

    data = load_manifest(manifest_file)
    gate = evaluate_short_chain_gate(data, project_root=root, check_file_exists=check_file_exists)
    whitelist = build_short_chain_whitelist(
        data, project_root=root, check_file_exists=check_file_exists
    )
    by_id = _entries_by_id(data)

    base["gate_ok"] = gate.ok
    base["approved_entry_ids"] = list(gate.approved_entry_ids)
    base["blocked_entry_ids"] = list(gate.blocked_entry_ids)

    for entry_id in requested_ids:
        if _looks_like_path(entry_id):
            _block(
                base,
                reason="entry_id_must_not_be_path",
                raise_on_block=raise_on_block,
                details={"entry_id": entry_id},
            )
            return base
        if entry_id not in by_id:
            _block(
                base,
                reason="entry_id_not_in_manifest",
                raise_on_block=raise_on_block,
                details={"entry_id": entry_id},
            )
            return base
        if entry_id not in whitelist:
            _block(
                base,
                reason="entry_id_not_whitelisted",
                raise_on_block=raise_on_block,
                details={"entry_id": entry_id},
            )
            return base

    candidate_ids: list[str]
    if requested_ids:
        candidate_ids = requested_ids
    else:
        candidate_ids = [
            entry_id
            for entry_id in gate.approved_entry_ids
            if _entry_has_uvr_stage(by_id[entry_id])
        ]

    planned: list[dict[str, Any]] = []
    for entry_id in candidate_ids:
        if len(planned) >= safe_limit:
            break
        entry = by_id.get(entry_id)
        if entry is None:
            continue
        if entry_id not in whitelist:
            _block(
                base,
                reason="entry_id_not_whitelisted",
                raise_on_block=raise_on_block,
                details={"entry_id": entry_id},
            )
            return base
        if not _entry_has_uvr_stage(entry):
            _block(
                base,
                reason="entry_missing_uvr_ab_stage",
                raise_on_block=raise_on_block,
                details={"entry_id": entry_id},
            )
            return base
        planned.append(_planned_action(entry, clip_seconds=safe_clip, dry_run=True))

    if not planned:
        base["blocked"] = True
        base["blocked_reason"] = "no_plannable_uvr_entries"
        if raise_on_block:
            raise Stage59UvrBlockedError(base["blocked_reason"], details={"requested_entry_ids": requested_ids})
        return base

    base["ok"] = True
    base["planned_actions"] = planned
    base["planned_count"] = len(planned)
    return base


def _block(
    payload: dict[str, Any],
    *,
    reason: str,
    raise_on_block: bool,
    details: dict[str, Any] | None = None,
) -> None:
    payload["blocked"] = True
    payload["blocked_reason"] = reason
    if raise_on_block:
        raise Stage59UvrBlockedError(reason, details=details)


def select_uvr_ab_entries(
    data: dict[str, Any],
    *,
    whitelist: frozenset[str] | set[str],
    entry_id_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Gate-approved manifest entries with uvr_ab in intended_chain."""
    by_id = _entries_by_id(data)
    selected: list[dict[str, Any]] = []
    for entry_id in whitelist:
        if entry_id_filter and entry_id != entry_id_filter:
            continue
        entry = by_id.get(entry_id)
        if entry is not None and _entry_has_uvr_stage(entry):
            selected.append(entry)
    return selected


def plan_dry_run(
    entry_ids: list[str],
    manifest_path: str | Path,
    *,
    project_root: Path | None = None,
    check_file_exists: bool = True,
    clip_seconds: int = DEFAULT_CLIP_SECONDS,
    limit: int | None = None,
) -> dict[str, Any]:
    """59C-0 CLI adapter: dry-run plan for explicit whitelisted entry ids."""
    safe_limit = max(len(entry_ids), 1) if limit is None else limit
    result = plan_short_chain_uvr(
        entry_ids,
        manifest_path=manifest_path,
        project_root=project_root,
        clip_seconds=clip_seconds,
        dry_run=True,
        execute=False,
        limit=safe_limit,
        check_file_exists=check_file_exists,
        raise_on_block=False,
    )
    result["execute_allowed"] = False
    result["execute_block_reason"] = EXECUTE_BLOCKED_REASON
    result["safety"] = {
        "uvr_subprocess": False,
        "rvc_inference": False,
        "gpu_required": False,
    }
    return result


def evaluate_uvr_ab_readiness(
    entry_id: str,
    *,
    manifest_path: Path | str | None = None,
    project_root: Path | None = None,
    clip_seconds: int = DEFAULT_CLIP_SECONDS,
    runner_mode: str = "mock",
    check_file_exists: bool = True,
) -> dict[str, Any]:
    """Stage59C-1 readiness harness — mock metadata plan; real runner blocked."""
    from backend.services.stage59_uvr_runner_contract import (
        STAGE59C1_REAL_EXECUTE_BLOCKED,
        evaluate_runner_readiness_from_paths,
    )

    payload = evaluate_runner_readiness_from_paths(
        entry_id,
        manifest_path,
        project_root=project_root,
        clip_seconds=clip_seconds,
        runner_mode=runner_mode,
        check_file_exists=check_file_exists,
    )
    payload["stage"] = STAGE59C1_LABEL
    payload["mode"] = "readiness"
    payload.setdefault("real_execute_allowed", False)
    payload.setdefault("execute_block_reason", STAGE59C0_EXECUTE_BLOCK_REASON)
    if runner_mode == "real":
        payload["real_execute_allowed"] = False
        payload["execute_block_reason"] = STAGE59C1_REAL_EXECUTE_BLOCKED
    return payload