"""
Stage59C-4a — listening bridge stable artifact ref tests.
"""

from __future__ import annotations

from backend.services.artifact_lifecycle_service import build_mock_uvr_artifact_contracts
from backend.services.artifact_lifecycle_service import build_listening_contract


def test_listening_bridge_uses_artifact_refs_not_only_paths():
    run_id = "stage59_run_refs"
    entry_id = "entry_refs"
    records = build_mock_uvr_artifact_contracts(run_id=run_id, entry_id=entry_id)
    contract = build_listening_contract(
        run_id=run_id,
        entry_id=entry_id,
        source_path="shared_data/materials/stage59/source.wav",
        artifact_records=records,
        clip_seconds=45,
    )
    vocal = contract["sides"]["b_uvr_vocal"]
    assert vocal["artifact_ref"]["artifact_id"] == f"stage59_{entry_id}_uvr_vocal"
    assert vocal["artifact_ref"]["run_id"] == run_id
    assert vocal["job_artifact_ref"]["promotable"] is False
    assert vocal["can_play"] is False
    assert vocal["can_review"] is False