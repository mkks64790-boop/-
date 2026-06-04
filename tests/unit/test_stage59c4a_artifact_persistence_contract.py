"""
Stage59C-4a — artifact persistence contract unit tests.
"""

from __future__ import annotations

from backend.services.artifact_lifecycle_service import (
    build_artifact_contract_record,
    build_mock_uvr_artifact_contracts,
    clear_persistence_store,
    stable_artifact_id,
    validate_artifact_contract_record,
)


def setup_function() -> None:
    clear_persistence_store()


def test_stable_artifact_id_for_entry_and_type():
    a = stable_artifact_id("sc59_entry", "uvr_vocal")
    b = stable_artifact_id("sc59_entry", "uvr_vocal")
    assert a == b
    assert a == "stage59_sc59_entry_uvr_vocal"


def test_mock_contract_metadata_only_under_sandbox():
    run_id = "stage59_sc59_entry_ab12cd34"
    records = build_mock_uvr_artifact_contracts(run_id=run_id, entry_id="sc59_entry")
    assert len(records) == 2
    for item in records:
        assert item["lifecycle_state"] == "transient"
        assert item["metadata_only"] is True
        assert item["file_exists"] is False
        assert item["playback_enabled"] is False
        assert item["download_enabled"] is False
        assert item["promotable_to_job_artifact"] is False
        assert item["planned_path"].startswith(f"shared_data/stage59_runtime/{run_id}/")
        assert not validate_artifact_contract_record(item)


def test_validator_rejects_active_lifecycle():
    record = build_mock_uvr_artifact_contracts(run_id="r1", entry_id="e1")[0]
    record["lifecycle_state"] = "active"
    errors = validate_artifact_contract_record(record)
    assert "mock_smoke_must_not_be_active" in errors


def test_validator_requires_exact_run_id_directory_segment():
    record = build_artifact_contract_record(
        run_id="run",
        entry_id="entry",
        artifact_type="uvr_vocal",
    )
    record["planned_path"] = "shared_data/stage59_runtime/run_evil/uvr_vocal.wav"

    errors = validate_artifact_contract_record(record)

    assert "path_run_id_mismatch" in errors
