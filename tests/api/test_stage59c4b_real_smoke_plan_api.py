"""Stage59C-4b real-smoke plan API tests."""

from __future__ import annotations

import json
from pathlib import Path

from backend.services.short_chain_manifest_service import SCHEMA_VERSION
from backend.services.execution_safety_service import REAL_RUNNER_NOT_ENABLED_REASON


def _install_manifest(root: Path) -> str:
    rel = "shared_data/materials/stage59/source.wav"
    source = root / rel
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"present")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-06-04T00:00:00",
        "stage": "stage59",
        "rights_policy": {"require_license_approved": True},
        "blocking_flags": {"allow_blocked_entries_in_manifest": True},
        "entries": [
            {
                "id": "stage59_real_source",
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
    manifest_rel = "shared_data/materials/stage59/short_chain_manifest.json"
    path = root / manifest_rel
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_rel


def test_contract_exposes_real_smoke_plan(client):
    resp = client.get("/api/stage59/short-chain/uvr-ab/contract")
    assert resp.status_code == 200
    body = resp.json()
    assert body["real_smoke_plan_supported"] is True
    assert "real_smoke_plan" in body["supported_modes"]


def test_real_smoke_plan_never_executes(client, isolated_backend):
    manifest_rel = _install_manifest(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/real-smoke-plan",
        json={
            "entry_id": "stage59_real_source",
            "manifest_path": manifest_rel,
            "confirm_execute": True,
            "approval_token": "stage59-local-approval",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["real_execute_allowed"] is False
    assert body["safety"]["audio_files_written"] is False
    assert REAL_RUNNER_NOT_ENABLED_REASON in body["blocked_reasons"]


def test_real_smoke_plan_requires_real_file_check(client, isolated_backend):
    manifest_rel = _install_manifest(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/real-smoke-plan",
        json={
            "entry_id": "stage59_real_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
            "confirm_execute": True,
            "approval_token": "stage59-local-approval",
        },
    )
    assert resp.status_code == 200
    assert "real_smoke_requires_file_exists_check" in resp.json()["blocked_reasons"]
