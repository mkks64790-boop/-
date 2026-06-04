"""
Stage59C-2 — transient artifact metadata store (no physical files).
"""

from __future__ import annotations

from pathlib import Path

from backend.services.artifact_lifecycle_service import (
    REQUIRES_LATER_DB_INTEGRATION,
    clear_transient_store,
    get_transient_run,
    register_transient_uvr_artifacts,
)


def setup_function() -> None:
    clear_transient_store()


def test_register_transient_artifacts_metadata_only(tmp_path: Path):
    records = register_transient_uvr_artifacts(
        run_id="stage59c2_test_run",
        entry_id="sc59_entry",
        source_path="shared_data/materials/stage59/x.wav",
        clip_seconds=45,
        manifest_path="shared_data/materials/stage59/short_chain_manifest.json",
    )
    assert len(records) == 2
    types = {item["artifact_type"] for item in records}
    assert types == {"uvr_vocal", "uvr_instrumental"}
    for item in records:
        assert item["lifecycle_state"] == "transient"
        assert item["metadata_only"] is True
        assert item["file_exists"] is False
        assert item["playback_enabled"] is False
        assert item["download_enabled"] is False
        assert item["artifact_id"].startswith("stage59_sc59_entry_")
        assert "stage59_runtime" in item["planned_path"]
        assert not (tmp_path / item["planned_path"]).exists()

    run = get_transient_run("stage59c2_test_run")
    assert run is not None
    assert run["audio_files_written"] is False
    assert records[0]["requires_later_db_integration"] is REQUIRES_LATER_DB_INTEGRATION