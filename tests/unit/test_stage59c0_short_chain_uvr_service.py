"""
Stage59C-0 — short_chain_uvr_service dry-run planner tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.short_chain_manifest_service import SCHEMA_VERSION
from backend.services.short_chain_uvr_service import (
    EXECUTE_BLOCKED_REASON,
    Stage59UvrBlockedError,
    plan_short_chain_uvr,
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


def _write_wav(path: Path, *, seconds: float = 1.0, sample_rate: int = 44100) -> None:
    import struct
    import wave

    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, int(sample_rate * seconds))
    silent = struct.pack("<h", 0) * frame_count
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(silent)


def _entry(entry_id: str, rel_path: str, *, license_status: str = "approved") -> dict:
    return {
        "id": entry_id,
        "material_id": "",
        "source_path": rel_path,
        "material_role": "cover_source",
        "lifecycle_state": "active",
        "intended_chain": ["preflight", "uvr_ab", "rvc_cover"],
        "license_status": license_status,
        "duration_seconds": 45.0,
        "rights_blocked": False,
        "quarantine_recommended": False,
    }


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    rel = "shared_data/materials/stage59"
    _write_wav(root / rel / "approved.wav")
    _write_wav(root / rel / "pending.wav")
    return root


def _write_manifest(root: Path, manifest: dict) -> Path:
    path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_dry_run_plans_whitelisted_entry(project_root: Path):
    rel = "shared_data/materials/stage59/approved.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_ok", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    result = plan_short_chain_uvr(
        "sc59_ok",
        manifest_path=manifest_path,
        project_root=project_root,
        check_file_exists=True,
        raise_on_block=False,
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["execute"] is False
    assert result["blocked"] is False
    assert len(result["planned_actions"]) == 1
    action = result["planned_actions"][0]
    assert action == {
        "entry_id": "sc59_ok",
        "source_path": rel,
        "clip_seconds": 45,
        "stages": ["uvr_ab"],
        "dry_run": True,
    }


def test_pending_entry_not_whitelisted(project_root: Path):
    rel = "shared_data/materials/stage59/pending.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_pending", rel, license_status="pending")]
    manifest_path = _write_manifest(project_root, manifest)

    with pytest.raises(Stage59UvrBlockedError) as exc:
        plan_short_chain_uvr(
            "sc59_pending",
            manifest_path=manifest_path,
            project_root=project_root,
            check_file_exists=True,
        )
    assert exc.value.reason == "entry_id_not_whitelisted"


def test_execute_blocked_by_stage59c0(project_root: Path):
    rel = "shared_data/materials/stage59/approved.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_ok", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    with pytest.raises(Stage59UvrBlockedError) as exc:
        plan_short_chain_uvr(
            "sc59_ok",
            manifest_path=manifest_path,
            project_root=project_root,
            execute=True,
            check_file_exists=True,
        )
    assert exc.value.reason == EXECUTE_BLOCKED_REASON

    blocked = plan_short_chain_uvr(
        "sc59_ok",
        manifest_path=manifest_path,
        project_root=project_root,
        execute=True,
        check_file_exists=True,
        raise_on_block=False,
    )
    assert blocked["blocked"] is True
    assert blocked["blocked_reason"] == EXECUTE_BLOCKED_REASON
    assert blocked["planned_actions"] == []


def test_rejects_path_like_entry_id(project_root: Path):
    rel = "shared_data/materials/stage59/approved.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_ok", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    with pytest.raises(Stage59UvrBlockedError) as exc:
        plan_short_chain_uvr(
            rel,
            manifest_path=manifest_path,
            project_root=project_root,
            check_file_exists=True,
        )
    assert exc.value.reason == "entry_id_must_not_be_path"


def test_unknown_entry_id_blocked(project_root: Path):
    rel = "shared_data/materials/stage59/approved.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_ok", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    with pytest.raises(Stage59UvrBlockedError) as exc:
        plan_short_chain_uvr(
            "sc59_missing",
            manifest_path=manifest_path,
            project_root=project_root,
            check_file_exists=True,
        )
    assert exc.value.reason == "entry_id_not_in_manifest"


def test_entry_without_uvr_ab_stage_blocked(project_root: Path):
    rel = "shared_data/materials/stage59/approved.wav"
    manifest = _base_manifest()
    manifest["entries"] = [
        {
            **_entry("sc59_preflight_only", rel),
            "intended_chain": ["preflight"],
        }
    ]
    manifest_path = _write_manifest(project_root, manifest)

    with pytest.raises(Stage59UvrBlockedError) as exc:
        plan_short_chain_uvr(
            "sc59_preflight_only",
            manifest_path=manifest_path,
            project_root=project_root,
            check_file_exists=True,
        )
    assert exc.value.reason == "entry_missing_uvr_ab_stage"


def test_clip_seconds_clamped(project_root: Path):
    rel = "shared_data/materials/stage59/approved.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_entry("sc59_ok", rel)]
    manifest_path = _write_manifest(project_root, manifest)

    result = plan_short_chain_uvr(
        "sc59_ok",
        manifest_path=manifest_path,
        project_root=project_root,
        clip_seconds=120,
        check_file_exists=True,
        raise_on_block=False,
    )
    assert result["planned_actions"][0]["clip_seconds"] == 60


def test_service_does_not_import_forbidden_modules():
    source = (
        Path(__file__).resolve().parents[2]
        / "backend"
        / "services"
        / "short_chain_uvr_service.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "voice_changer",
        "model_trainer",
        "vocal_separator",
        "separation_eval_service",
    ):
        assert forbidden not in source
    assert "short_chain_manifest_service" in source
    assert "import subprocess" not in source


def test_redacted_template_dry_run_without_files(tmp_path: Path):
    repo = Path(__file__).resolve().parents[2]
    redacted_src = (
        repo
        / "docs"
        / "agent-md"
        / "evidence"
        / "stage59-short-chain-manifest.redacted.json"
    )
    rel = "docs/agent-md/evidence/stage59-short-chain-manifest.redacted.json"
    redacted = tmp_path / rel
    redacted.parent.mkdir(parents=True, exist_ok=True)
    redacted.write_text(redacted_src.read_text(encoding="utf-8"), encoding="utf-8")
    result = plan_short_chain_uvr(
        "stage59_redacted_cover_source",
        manifest_path=rel,
        project_root=tmp_path,
        check_file_exists=False,
        raise_on_block=False,
    )
    assert result["ok"] is True
    assert result["planned_actions"][0]["entry_id"] == "stage59_redacted_cover_source"