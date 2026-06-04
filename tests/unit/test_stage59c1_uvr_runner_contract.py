"""
Stage59C-1 — UVR runner contract and mock harness tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.short_chain_manifest_service import SCHEMA_VERSION
from backend.services.uvr_smoke_service import (
    INVALID_RUNNER_MODE_REASON,
    REAL_RUNNER_BLOCKED_REASON,
    MockUvrAbRunner,
    RealUvrAbRunnerAdapter,
    RunnerMode,
    UvrAbRunnerRequest,
    build_runner_request,
    evaluate_runner_readiness,
    evaluate_runner_readiness_from_paths,
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


def _entry(entry_id: str, rel_path: str, *, license_status: str = "approved") -> dict:
    return {
        "id": entry_id,
        "material_id": "",
        "source_path": rel_path,
        "material_role": "separation_eval_candidate",
        "lifecycle_state": "active",
        "intended_chain": ["preflight", "uvr_ab"],
        "license_status": license_status,
        "duration_seconds": 45.0,
        "rights_blocked": False,
        "quarantine_recommended": False,
    }


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    rel_dir = root / "shared_data" / "materials" / "stage59"
    rel_dir.mkdir(parents=True)
    return root


def _write_manifest(root: Path, manifest: dict) -> Path:
    path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_mock_runner_returns_metadata_contracts(project_root: Path):
    rel = "shared_data/materials/stage59/source.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_uvr", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    result = evaluate_runner_readiness_from_paths(
        "sc59_uvr",
        manifest_path,
        project_root=project_root,
        check_file_exists=False,
    )
    assert result["ok"] is True
    assert result["real_execute_allowed"] is False
    assert result["runner_mode"] == RunnerMode.MOCK.value
    contracts = result["artifact_contracts"]
    assert len(contracts) == 2
    assert {item["artifact_type"] for item in contracts} == {
        "uvr_vocal",
        "uvr_instrumental",
    }
    assert all(item["metadata_only"] is True for item in contracts)


def test_real_runner_always_blocked(project_root: Path):
    rel = "shared_data/materials/stage59/source.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_uvr", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    result = evaluate_runner_readiness_from_paths(
        "sc59_uvr",
        manifest_path,
        project_root=project_root,
        runner_mode=RunnerMode.REAL,
        check_file_exists=False,
    )
    assert result["ok"] is False
    assert result["blocked_reason"] == REAL_RUNNER_BLOCKED_REASON
    assert result["requires_manual_approval"] is True


def test_invalid_runner_mode_blocked(project_root: Path):
    rel = "shared_data/materials/stage59/source.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_uvr", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    result = evaluate_runner_readiness_from_paths(
        "sc59_uvr",
        manifest_path,
        project_root=project_root,
        runner_mode="bad",
        check_file_exists=False,
    )
    assert result["ok"] is False
    assert result["blocked_reason"] == INVALID_RUNNER_MODE_REASON


def test_non_whitelisted_entry_blocked(project_root: Path):
    rel = "shared_data/materials/stage59/pending.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_pending", rel, license_status="pending")]
    manifest_path = _write_manifest(project_root, manifest)

    result = evaluate_runner_readiness_from_paths(
        "sc59_pending",
        manifest_path,
        project_root=project_root,
        check_file_exists=False,
    )
    assert result["blocked_reason"] == "entry_id_not_whitelisted"


def test_missing_uvr_stage_blocked(project_root: Path):
    rel = "shared_data/materials/stage59/source.wav"
    manifest = _base_manifest()
    manifest["entries"] = [
        {**_entry("sc59_no_uvr", rel), "intended_chain": ["preflight"]},
    ]
    manifest_path = _write_manifest(project_root, manifest)

    result = evaluate_runner_readiness_from_paths(
        "sc59_no_uvr",
        manifest_path,
        project_root=project_root,
        check_file_exists=False,
    )
    assert result["blocked_reason"] == "entry_missing_uvr_ab_stage"


def test_unsafe_manifest_path_blocked(project_root: Path):
    bad = project_root / "backend" / "evil.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{}", encoding="utf-8")
    result = evaluate_runner_readiness_from_paths(
        "sc59_uvr",
        bad,
        project_root=project_root,
        check_file_exists=False,
    )
    assert result["blocked_reason"] == "manifest_path_not_allowed"


def test_runner_contract_module_has_no_forbidden_imports():
    source = (
        Path(__file__).resolve().parents[2]
        / "backend"
        / "services"
        / "stage59_uvr_runner_contract.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "voice_changer",
        "model_trainer",
        "vocal_separator",
        "audio_mixer",
        "ffmpeg",
        "gradio_client",
    ):
        assert forbidden not in source
    assert "import subprocess" not in source


def test_mock_runner_class_does_not_write_files(project_root: Path, tmp_path: Path):
    rel = "shared_data/materials/stage59/source.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_uvr", rel)]
    manifest_path = _write_manifest(project_root, manifest)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    request = build_runner_request(
        "sc59_uvr",
        manifest_path,
        project_root=project_root,
        check_file_exists=False,
    )
    before = list(tmp_path.rglob("*.wav"))
    result = MockUvrAbRunner().run(
        request,
        data=data,
        entry=manifest["entries"][0],
        whitelist=frozenset({"sc59_uvr"}),
    )
    after = list(tmp_path.rglob("*.wav"))
    assert result["ok"] is True
    assert before == after


def test_real_adapter_blocked():
    request = UvrAbRunnerRequest(
        entry_id="x",
        manifest_path=Path("shared_data/materials/stage59/short_chain_manifest.json"),
    )
    result = RealUvrAbRunnerAdapter().run(request)
    assert result["blocked_reason"] == REAL_RUNNER_BLOCKED_REASON
