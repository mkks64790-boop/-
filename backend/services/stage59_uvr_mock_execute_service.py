"""
Stage59C-2 — mock UVR execute bridge (readiness → transient artifacts → listening contract).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from backend.services.short_chain_manifest_service import resolve_safe_manifest_path
from backend.services.short_chain_uvr_service import evaluate_uvr_ab_readiness
from backend.services.stage59_listening_bridge_service import build_listening_contract
from backend.services.stage59_transient_artifact_service import (
    REQUIRES_LATER_DB_INTEGRATION,
    STAGE_LABEL,
    attach_listening_contract,
    register_transient_uvr_artifacts,
)

STAGE59C2_LABEL = STAGE_LABEL


def _blocked_result(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        **readiness,
        "ok": False,
        "blocked": True,
        "stage": STAGE59C2_LABEL,
        "mode": "mock_execute",
        "real_execute_allowed": False,
        "audio_files_written": False,
        "metadata_only": True,
        "blocked_reason": readiness.get("blocked_reason", "readiness_blocked"),
    }


def mock_execute_uvr_ab(
    entry_id: str,
    *,
    manifest_path: Path | str | None = None,
    project_root: Path | None = None,
    clip_seconds: int = 45,
    check_file_exists: bool = True,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Mock execute after Stage59C-1 readiness passes.

    No UVR subprocess, no audio files, no DB rows (in-memory contract only).
    """
    readiness = evaluate_uvr_ab_readiness(
        entry_id,
        manifest_path=manifest_path,
        project_root=project_root,
        clip_seconds=clip_seconds,
        runner_mode="mock",
        check_file_exists=check_file_exists,
    )
    if not readiness.get("ok"):
        return _blocked_result(readiness)

    plan = readiness.get("plan") or {}
    source_path = str(plan.get("source_path") or "")
    safe_run_id = run_id or f"stage59c2_{entry_id}_{uuid.uuid4().hex[:8]}"
    manifest_resolved = resolve_safe_manifest_path(manifest_path, project_root=project_root)
    manifest_str = str(manifest_resolved)

    artifact_records = register_transient_uvr_artifacts(
        run_id=safe_run_id,
        entry_id=entry_id,
        source_path=source_path,
        clip_seconds=clip_seconds,
        manifest_path=manifest_str,
    )
    listening_contract = build_listening_contract(
        run_id=safe_run_id,
        entry_id=entry_id,
        source_path=source_path,
        artifact_records=artifact_records,
        clip_seconds=clip_seconds,
    )

    attach_listening_contract(safe_run_id, listening_contract)

    return {
        "ok": True,
        "blocked": False,
        "stage": STAGE59C2_LABEL,
        "mode": "mock_execute",
        "run_id": safe_run_id,
        "real_execute_allowed": False,
        "audio_files_written": False,
        "metadata_only": True,
        "material_entry_id": entry_id,
        "source_path": source_path,
        "manifest_path": manifest_str,
        "clip_seconds": clip_seconds,
        "artifact_records": artifact_records,
        "listening_contract": listening_contract,
        "readiness": readiness,
        "requires_later_db_integration": REQUIRES_LATER_DB_INTEGRATION,
        "safety": {
            "uvr_subprocess": False,
            "rvc_inference": False,
            "gpu_required": False,
            "audio_files_written": False,
        },
    }