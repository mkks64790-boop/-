from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.short_chain_manifest_service import (
    SCHEMA_VERSION,
    evaluate_short_chain_gate,
    load_manifest,
    rights_gate_allows_entry,
    validate_manifest,
    validate_manifest_structure,
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


def _approved_entry(entry_id: str, rel_path: str, *, license_status: str = "approved") -> dict:
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


def test_rights_gate_blocks_pending_license():
    ok, reason = rights_gate_allows_entry({"license_status": "pending"})
    assert not ok
    assert "license_not_approved" in reason

    ok2, _ = rights_gate_allows_entry({"license_status": "approved"})
    assert ok2


def test_valid_manifest_passes_gate(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    audio = root / "shared_data" / "materials" / "stage59" / "sample.wav"
    _write_wav(audio)

    manifest = _base_manifest()
    manifest["entries"] = [
        _approved_entry("sc59_ok", "shared_data/materials/stage59/sample.wav"),
    ]
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    loaded = load_manifest(manifest_path)
    assert validate_manifest_structure(loaded) == []
    gate = evaluate_short_chain_gate(loaded, project_root=root, check_file_exists=True)
    assert gate.ok
    assert gate.approved_entry_ids == ["sc59_ok"]


def test_pending_license_entry_blocked_for_automation(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    audio = root / "shared_data" / "materials" / "stage59" / "pending.wav"
    _write_wav(audio)

    manifest = _base_manifest()
    manifest["entries"] = [
        _approved_entry("sc59_pending", "shared_data/materials/stage59/pending.wav", license_status="pending"),
    ]
    gate = evaluate_short_chain_gate(manifest, project_root=root, check_file_exists=True)
    assert not gate.ok
    assert gate.blocked_entry_ids == ["sc59_pending"]


def test_duration_outside_window_fails_structure():
    manifest = _base_manifest()
    manifest["entries"] = [
        {
            **_approved_entry("sc59_short", "shared_data/x.wav"),
            "duration_seconds": 5.0,
        }
    ]
    errors = validate_manifest_structure(manifest)
    assert any("duration_below_min" in err for err in errors)


def test_redacted_template_schema_valid(tmp_path: Path):
    redacted = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "agent-md"
        / "evidence"
        / "stage59-short-chain-manifest.redacted.json"
    )
    data = load_manifest(redacted)
    assert validate_manifest_structure(data) == []
    gate = evaluate_short_chain_gate(data, project_root=tmp_path, check_file_exists=False)
    assert gate.approved_entry_ids == ["stage59_redacted_cover_source"]
    assert "stage59_redacted_pending_dry_vocal" in gate.blocked_entry_ids


def test_intended_chain_rejects_unknown_step():
    manifest = _base_manifest()
    manifest["entries"] = [
        {
            **_approved_entry("sc59_bad_chain", "shared_data/x.wav"),
            "intended_chain": ["preflight", "train_full"],
        }
    ]
    errors = validate_manifest_structure(manifest)
    assert any("intended_chain_invalid" in err for err in errors)


def test_verifier_does_not_import_inference_modules():
    source = (Path(__file__).resolve().parents[2] / "backend" / "verify_stage59_short_chain_manifest.py").read_text(
        encoding="utf-8"
    )
    assert "voice_changer" not in source
    assert "vocal_separator" not in source
    assert "model_trainer" not in source
    assert "separation_eval_service" not in source
    assert "short_chain_manifest_service" in source