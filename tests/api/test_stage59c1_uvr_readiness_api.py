"""
Stage59C-1 — UVR readiness API tests (metadata-only; execute still blocked).
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


def _install_redacted_manifest(root: Path) -> str:
    rel = "docs/agent-md/evidence/stage59-short-chain-manifest.redacted.json"
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_redacted_manifest().read_text(encoding="utf-8"), encoding="utf-8")
    return rel


def _base_manifest() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-06-03T00:00:00",
        "stage": "stage59",
        "rights_policy": {"require_license_approved": True},
        "blocking_flags": {"allow_blocked_entries_in_manifest": True},
        "entries": [],
    }


def _uvr_entry(entry_id: str, rel_path: str) -> dict:
    return {
        "id": entry_id,
        "material_id": "",
        "source_path": rel_path,
        "material_role": "separation_eval_candidate",
        "lifecycle_state": "active",
        "intended_chain": ["preflight", "uvr_ab"],
        "license_status": "approved",
        "duration_seconds": 45.0,
        "rights_blocked": False,
        "quarantine_recommended": False,
    }


def test_contract_exposes_readiness(client):
    resp = client.get("/api/stage59/short-chain/uvr-ab/contract")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["readiness_supported"] is True
    assert payload["real_execute_allowed"] is False
    assert payload["execute_allowed"] is False


def test_readiness_redacted_manifest(client, isolated_backend):
    manifest_rel = _install_redacted_manifest(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/readiness",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["real_execute_allowed"] is False
    assert body["mode"] == "readiness"
    assert len(body["artifact_contracts"]) == 2


def test_readiness_rejects_unsafe_manifest_path(client, isolated_backend):
    root = isolated_backend
    rel = "shared_data/materials/stage59/uvr.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_uvr", rel)]
    bad_manifest = root / "manifest.json"
    bad_manifest.write_text(json.dumps(manifest), encoding="utf-8")

    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/readiness",
        json={"entry_id": "sc59_uvr", "manifest_path": str(bad_manifest)},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["blocked_reason"] == "manifest_path_not_allowed"


def test_readiness_safe_manifest_under_stage59(client, isolated_backend):
    root = isolated_backend
    rel = "shared_data/materials/stage59/uvr.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_uvr", rel)]
    safe_manifest = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    safe_manifest.parent.mkdir(parents=True, exist_ok=True)
    safe_manifest.write_text(json.dumps(manifest), encoding="utf-8")

    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/readiness",
        json={
            "entry_id": "sc59_uvr",
            "manifest_path": str(safe_manifest),
            "skip_file_exists": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["artifact_contracts"]


def test_readiness_real_runner_blocked(client, isolated_backend):
    manifest_rel = _install_redacted_manifest(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/readiness",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
            "runner_mode": "real",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["real_execute_allowed"] is False


def test_execute_still_403(client):
    resp = client.post("/api/stage59/short-chain/uvr-ab/execute", json={})
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason"] == STAGE59C0_EXECUTE_BLOCK_REASON


def test_plan_rejects_unsafe_manifest(client, isolated_backend):
    uploads = isolated_backend / "shared_data" / "uploads" / "evil.json"
    uploads.parent.mkdir(parents=True, exist_ok=True)
    uploads.write_text("{}", encoding="utf-8")
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/plan",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": "shared_data/uploads/evil.json",
            "skip_file_exists": True,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["blocked_reason"] == "manifest_path_not_allowed"