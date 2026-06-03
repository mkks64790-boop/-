from __future__ import annotations

from backend.services.lifecycle_service import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_TEST_DATA,
    LIFECYCLE_TRANSIENT,
    infer_job_artifact_lifecycle,
    infer_voice_model_lifecycle,
    is_valid_lifecycle_transition,
    lifecycle_allows_file_delete,
    retention_status_to_lifecycle,
    resolve_register_job_artifact_lifecycle,
    should_default_hide_lifecycle,
)


def test_cover_intermediate_is_transient():
    state = resolve_register_job_artifact_lifecycle(
        artifact_type="cover_vocal",
        is_final=False,
        job_row={"job_id": "real_job", "metadata_json": '{"source":"stage47_real"}'},
    )
    assert state == LIFECYCLE_TRANSIENT
    assert lifecycle_allows_file_delete(state)


def test_cover_master_is_active():
    state = resolve_register_job_artifact_lifecycle(
        artifact_type="cover_master",
        is_final=True,
        job_row={"job_id": "real_job", "metadata_json": "{}"},
    )
    assert state == LIFECYCLE_ACTIVE
    assert not lifecycle_allows_file_delete(state)


def test_smoke_job_artifacts_are_test_data():
    job_row = {"job_id": "smoke_cover_001", "metadata_json": '{"smoke": true}'}
    state = infer_job_artifact_lifecycle(
        {"artifact_type": "cover_vocal", "is_final": 0, "file_path": "shared_data/outputs/x/vocal.wav"},
        job_row=job_row,
    )
    assert state == LIFECYCLE_TEST_DATA


def test_retention_maps_to_lifecycle():
    assert retention_status_to_lifecycle("quarantined") == "archived"
    assert retention_status_to_lifecycle("active") == LIFECYCLE_ACTIVE


def test_should_default_hide_test_data_and_purged():
    assert should_default_hide_lifecycle("test_data")
    assert should_default_hide_lifecycle("purged")
    assert not should_default_hide_lifecycle("active")


def test_lifecycle_transition_guard():
    assert is_valid_lifecycle_transition("transient", "archived")
    assert not is_valid_lifecycle_transition("purged", "active")


def test_smoke_model_is_test_data():
    state = infer_voice_model_lifecycle(
        {"model_name": "smoke_voice", "metadata_json": '{"test_scope":"smoke"}', "status": "ready"}
    )
    assert state == LIFECYCLE_TEST_DATA