"""
Stage59C-4a — artifact contract API tests.
"""

from __future__ import annotations

from pathlib import Path

from backend.services.short_chain_uvr_service import STAGE59C0_EXECUTE_BLOCK_REASON
from backend.services.execution_safety_service import REAL_RUNNER_NOT_ENABLED_REASON
from backend.services.artifact_lifecycle_service import clear_transient_store


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


def setup_function() -> None:
    clear_transient_store()


def test_artifact_contract_endpoint(client, isolated_backend):
    manifest_rel = _install_redacted_manifest(isolated_backend)
    mock_resp = client.post(
        "/api/stage59/short-chain/uvr-ab/mock-execute",
        json={
            "entry_id": "stage59_redacted_cover_source",
            "manifest_path": manifest_rel,
            "skip_file_exists": True,
        },
    )
    assert mock_resp.status_code == 200
    body = mock_resp.json()
    assert body.get("artifact_persistence_contract") is not None
    run_id = body["run_id"]

    resp = client.get(
        f"/api/stage59/short-chain/uvr-ab/mock-execute/{run_id}/artifact-contract"
    )
    assert resp.status_code == 200
    contract = resp.json()["artifact_persistence_contract"]
    assert contract["metadata_only"] is True
    assert contract["file_exists"] is False
    assert resp.json()["playback_enabled"] is False


def test_execute_still_403(client):
    resp = client.post("/api/stage59/short-chain/uvr-ab/execute", json={})
    assert resp.status_code == 403
    assert STAGE59C0_EXECUTE_BLOCK_REASON in str(resp.json())


def test_approval_preflight_still_blocks_real_execute(client, isolated_backend):
    manifest_rel = _install_redacted_manifest(isolated_backend)
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
    assert REAL_RUNNER_NOT_ENABLED_REASON in str(resp.json())