"""
Stage59C-2 — Stage49-compatible listening bridge contract tests.
"""

from __future__ import annotations

from backend.services.artifact_lifecycle_service import (
    LISTENING_BRIDGE_SCHEMA,
    STAGE49_COMPATIBLE_SCHEMA,
    build_listening_contract,
)


def _sample_records() -> list[dict]:
    entry_id = "sc59_entry"
    run_id = "stage59c2_test_run"
    base = f"shared_data/stage59_runtime/{run_id}"
    return [
        {
            "artifact_id": f"stage59_{entry_id}_uvr_vocal",
            "artifact_type": "uvr_vocal",
            "planned_path": f"{base}/uvr_vocal.wav",
            "lifecycle_state": "transient",
            "file_exists": False,
            "metadata_only": True,
            "promotable_to_job_artifact": False,
        },
        {
            "artifact_id": f"stage59_{entry_id}_uvr_instrumental",
            "artifact_type": "uvr_instrumental",
            "planned_path": f"{base}/uvr_instrumental.wav",
            "lifecycle_state": "transient",
            "file_exists": False,
            "metadata_only": True,
            "promotable_to_job_artifact": False,
        },
    ]


def test_listening_contract_stage49_compatible_shape():
    contract = build_listening_contract(
        run_id="stage59c2_test_run",
        entry_id="sc59_entry",
        source_path="shared_data/materials/stage59/source.wav",
        artifact_records=_sample_records(),
        clip_seconds=45,
    )
    assert contract["schema"] == LISTENING_BRIDGE_SCHEMA
    assert contract["compatible_with"] == STAGE49_COMPATIBLE_SCHEMA
    assert contract["playback_enabled"] is False
    assert contract["real_execute_required"] is True
    assert contract["next_action"] == "requires_real_uvr_execute"
    assert "a_source" in contract["sides"]
    assert "b_uvr_vocal" in contract["sides"]
    assert contract["sides"]["b_uvr_vocal"]["file_exists"] is False
    assert contract["sides"]["b_uvr_vocal"]["can_play"] is False
    assert contract["sides"]["b_uvr_vocal"]["reason"] == "metadata_only_artifact"
    assert "artifact_ref" in contract["sides"]["b_uvr_vocal"]
    assert contract["sides"]["b_uvr_vocal"]["artifact_ref"]["artifact_id"].startswith("stage59_")
    assert len(contract["ab_pairs"]) >= 1