"""Stage59C-4b real-smoke plan service tests."""

from __future__ import annotations

import json
from pathlib import Path

from backend.services.short_chain_manifest_service import SCHEMA_VERSION
from backend.services.uvr_smoke_service import (
    REAL_SMOKE_NOT_EXECUTED_REASON,
    REAL_SMOKE_REQUIRES_FILE_CHECK_REASON,
    evaluate_real_smoke_plan,
)
from backend.services.execution_safety_service import REAL_RUNNER_NOT_ENABLED_REASON


def _manifest(entry_id: str, rel: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-06-04T00:00:00",
        "stage": "stage59",
        "rights_policy": {"require_license_approved": True},
        "blocking_flags": {"allow_blocked_entries_in_manifest": True},
        "entries": [
            {
                "id": entry_id,
                "material_id": "",
                "source_path": rel,
                "material_role": "cover_source",
                "lifecycle_state": "active",
                "intended_chain": ["preflight", "uvr_ab", "rvc_cover"],
                "license_status": "approved",
                "duration_seconds": 30.0,
                "rights_blocked": False,
                "quarantine_recommended": False,
            }
        ],
    }


def _write_real_manifest(root: Path, *, entry_id: str = "sc59_real") -> Path:
    rel = "shared_data/materials/stage59/source.wav"
    source = root / rel
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"not-a-real-wave-but-present")
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.write_text(json.dumps(_manifest(entry_id, rel)), encoding="utf-8")
    return manifest_path


def test_real_smoke_plan_passes_policy_but_never_executes(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "shared_data").mkdir()
    manifest_path = _write_real_manifest(root)

    result = evaluate_real_smoke_plan(
        "sc59_real",
        manifest_path=manifest_path,
        project_root=root,
        confirm_execute=True,
        approval_token="stage59-local-approval",
    )

    assert result["ok"] is True
    assert result["approval_complete"] is True
    assert result["real_execute_allowed"] is False
    assert REAL_RUNNER_NOT_ENABLED_REASON in result["blocked_reasons"]
    assert REAL_SMOKE_NOT_EXECUTED_REASON in result["blocked_reasons"]
    assert result["safety"]["audio_files_written"] is False
    assert len(result["expected_artifacts"]) == 2
    assert all(item["lifecycle_state"] == "transient" for item in result["expected_artifacts"])


def test_real_smoke_plan_blocks_when_file_check_is_skipped(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "shared_data").mkdir()
    manifest_path = _write_real_manifest(root)

    result = evaluate_real_smoke_plan(
        "sc59_real",
        manifest_path=manifest_path,
        project_root=root,
        check_file_exists=False,
        confirm_execute=True,
        approval_token="stage59-local-approval",
    )

    assert result["ok"] is True
    assert result["real_execute_allowed"] is False
    assert REAL_SMOKE_REQUIRES_FILE_CHECK_REASON in result["blocked_reasons"]
