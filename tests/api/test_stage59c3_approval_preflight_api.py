"""Stage59C-3 approval preflight API tests."""

from __future__ import annotations

import json
from pathlib import Path

from backend.services.short_chain_manifest_service import SCHEMA_VERSION
from backend.services.short_chain_uvr_service import STAGE59C0_EXECUTE_BLOCK_REASON
from backend.services.stage59_approval_audit_service import clear_audit_store
from backend.services.stage59_execution_policy_service import REAL_RUNNER_NOT_ENABLED_REASON


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _install_redacted(root: Path) -> str:
    rel = "docs/agent-md/evidence/stage59-short-chain-manifest.redacted.json"
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        (
            _repo_root()
            / "docs"
            / "agent-md"
            / "evidence"
            / "stage59-short-chain-manifest.redacted.json"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
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


def setup_function() -> None:
    clear_audit_store()


def test_contract_approval_preflight_supported(client):
    resp = client.get("/api/stage59/short-chain/uvr-ab/contract")
    assert resp.status_code == 200
    body = resp.json()
    assert body["approval_preflight_supported"] is True
    assert "approval_preflight" in body["supported_modes"]


def test_approval_preflight_without_confirm(client, isolated_backend):
    manifest_rel = _install_redacted(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/approval-preflight",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["real_execute_allowed"] is False
    assert "confirm_execute_missing" in resp.json()["blocked_reasons"]


def test_approval_preflight_with_token(client, isolated_backend):
    manifest_rel = _install_redacted(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/approval-preflight",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
            "confirm_execute": True,
            "approval_token": "stage59-local-approval",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["approval_complete"] is True
    assert resp.json()["real_execute_allowed"] is False


def test_real_execute_requested_mode_403(client, isolated_backend):
    manifest_rel = _install_redacted(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/approval-preflight",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
            "confirm_execute": True,
            "approval_token": "stage59-local-approval",
            "requested_mode": "real_execute",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason"] == REAL_RUNNER_NOT_ENABLED_REASON


def test_invalid_requested_mode_422(client, isolated_backend):
    manifest_rel = _install_redacted(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/approval-preflight",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
            "requested_mode": "dry_run",
        },
    )
    assert resp.status_code == 422


def test_unsafe_manifest_400(client, isolated_backend):
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/approval-preflight",
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


def test_max_items_gt_one_422(client, isolated_backend):
    manifest_rel = _install_redacted(isolated_backend)
    resp = client.post(
        "/api/stage59/short-chain/uvr-ab/approval-preflight",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
            "max_items": 2,
        },
    )
    assert resp.status_code == 422