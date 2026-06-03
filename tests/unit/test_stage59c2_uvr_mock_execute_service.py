"""
Stage59C-2 — mock execute service tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.short_chain_manifest_service import SCHEMA_VERSION
from backend.services.stage59_transient_artifact_service import clear_transient_store
from backend.services.stage59_uvr_mock_execute_service import mock_execute_uvr_ab


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


@pytest.fixture(autouse=True)
def _clear_store():
    clear_transient_store()
    yield
    clear_transient_store()


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    return root


def _write_manifest(root: Path, manifest: dict) -> Path:
    path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_mock_execute_passes_after_readiness(project_root: Path):
    rel = "shared_data/materials/stage59/uvr.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_uvr", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    result = mock_execute_uvr_ab(
        "sc59_uvr",
        manifest_path=manifest_path,
        project_root=project_root,
        check_file_exists=False,
        run_id="stage59c2_deterministic_run",
    )
    assert result["ok"] is True
    assert result["mode"] == "mock_execute"
    assert result["real_execute_allowed"] is False
    assert result["audio_files_written"] is False
    assert len(result["artifact_records"]) == 2
    assert result["listening_contract"]["playback_enabled"] is False
    assert not (project_root / result["artifact_records"][0]["planned_path"]).exists()


def test_mock_execute_blocked_when_not_whitelisted(project_root: Path):
    rel = "shared_data/materials/stage59/pending.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_pending", rel, license_status="pending")]
    manifest_path = _write_manifest(project_root, manifest)

    result = mock_execute_uvr_ab(
        "sc59_pending",
        manifest_path=manifest_path,
        project_root=project_root,
        check_file_exists=False,
    )
    assert result["ok"] is False
    assert result["blocked_reason"] == "entry_id_not_whitelisted"


def test_mock_execute_service_has_no_forbidden_imports():
    source = (
        Path(__file__).resolve().parents[2]
        / "backend"
        / "services"
        / "stage59_uvr_mock_execute_service.py"
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