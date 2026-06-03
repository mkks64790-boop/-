"""
Stage59C-2 — mock execute API tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.services.short_chain_manifest_service import SCHEMA_VERSION
from backend.services.short_chain_uvr_service import STAGE59C0_EXECUTE_BLOCK_REASON
from backend.services.stage59_transient_artifact_service import clear_transient_store


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


def setup_function() -> None:
    clear_transient_store()


def test_contract_exposes_mock_execute(client):
    resp = client.get("/api/stage59/short-chain/uvr-ab/contract")
    assert resp.status_code == 200
    assert resp.json()["mock_execute_supported"] is True


def test_mock_execute_redacted_manifest(client, isolated_backend):
    manifest_rel = _install_redacted_manifest(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/mock-execute",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["mode"] == "mock_execute"
    assert body["real_execute_allowed"] is False
    assert body["audio_files_written"] is False
    assert len(body["artifact_records"]) == 2
    assert body["listening_contract"]["playback_enabled"] is False

    run_id = body["run_id"]
    contract_resp = client.get(
        f"/api/stage59/short-chain/uvr-ab/mock-execute/{run_id}/listening-contract"
    )
    assert contract_resp.status_code == 200
    assert contract_resp.json()["listening_contract"]["schema"] == "stage59_uvr_listening_bridge_v2"
    art_resp = client.get(
        f"/api/stage59/short-chain/uvr-ab/mock-execute/{run_id}/artifact-contract"
    )
    assert art_resp.status_code == 200
    bundle = art_resp.json()["artifact_persistence_contract"]
    assert bundle["metadata_only"] is True
    assert bundle["file_exists"] is False


def test_mock_execute_pending_blocked(client, isolated_backend):
    root = isolated_backend
    rel = "shared_data/materials/stage59/pending.wav"
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_pending", rel, license_status="pending")]
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/mock-execute",
        json={"entry_id": "sc59_pending", "manifest_path": str(manifest_path)},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["blocked_reason"] == "entry_id_not_whitelisted"


def test_mock_execute_unsafe_manifest_400(client, isolated_backend):
    uploads = isolated_backend / "shared_data" / "uploads" / "evil.json"
    uploads.parent.mkdir(parents=True, exist_ok=True)
    uploads.write_text("{}", encoding="utf-8")
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/mock-execute",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": "shared_data/uploads/evil.json",
        },
    )
    assert resp.status_code == 400


def test_execute_still_403(client):
    resp = client.post("/api/stage59/short-chain/uvr-ab/execute", json={})
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason"] == STAGE59C0_EXECUTE_BLOCK_REASON