"""Stage59C-3 execution policy tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.short_chain_manifest_service import SCHEMA_VERSION
from backend.services.execution_safety_service import clear_audit_store
from backend.services.execution_safety_service import (
    REAL_RUNNER_NOT_ENABLED_REASON,
    evaluate_execution_policy,
)


def _base_manifest() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-06-03T00:00:00",
        "stage": "stage59",
        "rights_policy": {"require_license_approved": True},
        "blocking_flags": {"allow_blocked_entries_in_manifest": True},
        "entries": [],
    }


def _entry(entry_id: str, rel: str, *, license_status: str = "approved") -> dict:
    return {
        "id": entry_id,
        "material_id": "",
        "source_path": rel,
        "material_role": "separation_eval_candidate",
        "lifecycle_state": "active",
        "intended_chain": ["preflight", "uvr_ab"],
        "license_status": license_status,
        "duration_seconds": 45.0,
        "rights_blocked": False,
        "quarantine_recommended": False,
    }


@pytest.fixture(autouse=True)
def _clear_audit():
    clear_audit_store()
    yield
    clear_audit_store()


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "shared_data").mkdir(parents=True, exist_ok=True)
    return root


def _write_manifest(root: Path, manifest: dict) -> Path:
    path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_preflight_missing_confirmation_passes_with_warnings(project_root: Path):
    rel = "shared_data/materials/stage59/x.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    result = evaluate_execution_policy(
        "sc59",
        manifest_path=manifest_path,
        project_root=project_root,
        check_file_exists=False,
        confirm_execute=False,
    )
    assert result["ok"] is True
    assert result["real_execute_allowed"] is False
    assert "confirm_execute_missing" in result["blocked_reasons"]


def test_preflight_with_token_still_blocks_real_execute(project_root: Path):
    rel = "shared_data/materials/stage59/x.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    result = evaluate_execution_policy(
        "sc59",
        manifest_path=manifest_path,
        project_root=project_root,
        check_file_exists=False,
        confirm_execute=True,
        approval_token="stage59-local-approval",
    )
    assert result["ok"] is True
    assert result["approval_complete"] is True
    assert result["real_execute_allowed"] is False


def test_requested_real_execute_blocked(project_root: Path):
    rel = "shared_data/materials/stage59/x.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    result = evaluate_execution_policy(
        "sc59",
        manifest_path=manifest_path,
        project_root=project_root,
        check_file_exists=False,
        confirm_execute=True,
        approval_token="stage59-local-approval",
        requested_mode="real_execute",
    )
    assert result["ok"] is False
    assert REAL_RUNNER_NOT_ENABLED_REASON in result["blocked_reasons"]


def test_pending_entry_blocked(project_root: Path):
    rel = "shared_data/materials/stage59/p.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_p", rel, license_status="pending")]
    manifest_path = _write_manifest(project_root, manifest)

    result = evaluate_execution_policy(
        "sc59_p",
        manifest_path=manifest_path,
        project_root=project_root,
        check_file_exists=False,
    )
    assert result["ok"] is False


def test_invalid_requested_mode(project_root: Path):
    result = evaluate_execution_policy(
        "sc59",
        manifest_path=None,
        project_root=project_root,
        requested_mode="dry_run",
    )
    assert result["ok"] is False
    assert "invalid_requested_mode" in result["blocked_reasons"]


def test_policy_module_no_forbidden_imports():
    source = (
        Path(__file__).resolve().parents[2]
        / "backend"
        / "services"
        / "stage59_execution_policy_service.py"
    ).read_text(encoding="utf-8")
    assert "voice_changer" not in source
    assert "import subprocess" not in source