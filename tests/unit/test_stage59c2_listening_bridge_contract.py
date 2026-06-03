"""
Stage59C-2 — Stage49-compatible listening bridge contract tests.
"""

from __future__ import annotations

from backend.services.stage59_listening_bridge_service import (
    LISTENING_BRIDGE_SCHEMA,
    STAGE49_COMPATIBLE_SCHEMA,
    build_listening_contract,
)


def _sample_records() -> list[dict]:
    entry_id = "sc59_entry"
    return [
        {
            "artifact_id": f"stage59c2_{entry_id}_uvr_vocal",
            "artifact_type": "uvr_vocal",
            "planned_path": f"shared_data/separation_eval/stage59/{entry_id}/uvr_vocal.wav",
        },
        {
            "artifact_id": f"stage59c2_{entry_id}_uvr_instrumental",
            "artifact_type": "uvr_instrumental",
            "planned_path": f"shared_data/separation_eval/stage59/{entry_id}/uvr_instrumental.wav",
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
    assert len(contract["ab_pairs"]) >= 1