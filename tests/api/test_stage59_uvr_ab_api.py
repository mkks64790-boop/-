"""
Stage59C-0 — UVR A/B dry-run API contract (no UVR/RVC/GPU).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.short_chain_manifest_service import SCHEMA_VERSION
from backend.services.short_chain_uvr_service import STAGE59C0_EXECUTE_BLOCK_REASON


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _redacted_manifest() -> Path:
    return (
        _repo_root()
        / "docs"
        / "agent-md"
        / "evidence"
        / "stage59-short-chain-manifest.redacted.json"
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


def _uvr_entry(entry_id: str, rel_path: str, *, license_status: str = "approved") -> dict:
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


def test_uvr_ab_contract_endpoint(client):
    resp = client.get("/api/stage59/short-chain/uvr-ab/contract")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["stage"] == "stage59c3"
    assert payload["readiness_supported"] is True
    assert payload["mock_execute_supported"] is True
    assert payload["execute_allowed"] is False
    assert payload["execute_block_reason"] == STAGE59C0_EXECUTE_BLOCK_REASON
    assert payload["safety"]["uvr_subprocess"] is False
    assert payload["safety"]["rvc_inference"] is False
    assert payload["safety"]["gpu_required"] is False


def _install_redacted_manifest(root: Path) -> str:
    rel = "docs/agent-md/evidence/stage59-short-chain-manifest.redacted.json"
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_redacted_manifest().read_text(encoding="utf-8"), encoding="utf-8")
    return rel


def test_uvr_ab_plan_redacted_manifest(client, isolated_backend):
    manifest_rel = _install_redacted_manifest(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/plan",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
        },
    )
    assert resp.status_code == 200
    plan = resp.json()
    assert plan["ok"] is True
    assert plan["dry_run"] is True
    assert plan["planned_count"] == 1
    assert plan["planned_actions"][0]["entry_id"] == "stage59_redacted_cover_source"
    assert plan["planned_actions"][0]["dry_run"] is True


def test_uvr_ab_plan_pending_entry_blocked(client, isolated_backend):
    root = isolated_backend
    rel = "shared_data/materials/stage59/pending.wav"
    _write_wav(root / rel)
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_pending", rel, license_status="pending")]
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/plan",
        json={"entry_id": "sc59_pending", "manifest_path": str(manifest_path)},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["blocked_reason"] == "entry_id_not_whitelisted"


def test_uvr_ab_plan_rejects_path_like_entry_id(client, isolated_backend):
    root = isolated_backend
    rel = "shared_data/materials/stage59/uvr.wav"
    _write_wav(root / rel)
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_uvr", rel)]
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/plan",
        json={"entry_id": rel, "manifest_path": str(manifest_path)},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["blocked_reason"] == "entry_id_must_not_be_path"


def test_uvr_ab_execute_always_blocked(client):
    resp = client.post("/api/stage59/short-chain/uvr-ab/execute", json={})
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["reason"] == STAGE59C0_EXECUTE_BLOCK_REASON


def test_main_uvr_ab_routes_do_not_import_separation_runner():
    source = (_repo_root() / "backend" / "main.py").read_text(encoding="utf-8")
    start = source.index('"/api/stage59/short-chain/uvr-ab/contract"')
    end = source.index('"/api/training/presets"', start)
    block = source[start:end]
    assert "separation_eval_service" not in block
    assert "import subprocess" not in block
    assert "plan_short_chain_uvr" in source