"""
Stage59C-4a — job artifact promotion dry plan tests.
"""

from __future__ import annotations

from backend.services.stage59_artifact_persistence_service import (
    build_mock_uvr_artifact_contracts,
    build_run_persistence_bundle,
)
from backend.services.stage59_job_artifact_promotion_service import (
    build_job_artifact_promotion_plan,
)


def test_promotion_blocked_without_files():
    run_id = "stage59_test_run"
    records = build_mock_uvr_artifact_contracts(run_id=run_id, entry_id="entry_a")
    bundle = build_run_persistence_bundle(
        run_id=run_id,
        entry_id="entry_a",
        artifact_records=records,
    )
    plan = build_job_artifact_promotion_plan(job_id="job_123", artifact_contract=bundle)
    assert plan["can_promote"] is False
    assert plan["db_write_performed"] is False
    assert "register_job_artifact_requires_os_path_exists" in plan["blocked_reasons"]
    for item in plan["per_artifact"]:
        assert item["can_promote"] is False
        assert "file_missing_at_planned_path" in item["blocked_reasons"]


def test_promotion_plan_allows_future_when_file_exists(monkeypatch):
    run_id = "stage59_test_run2"
    records = build_mock_uvr_artifact_contracts(run_id=run_id, entry_id="entry_b")
    vocal_path = "shared_data/stage59_runtime/stage59_test_run2/uvr_vocal.wav"
    monkeypatch.setattr(
        "backend.services.stage59_job_artifact_promotion_service.os.path.exists",
        lambda path: path == vocal_path,
    )
    bundle = build_run_persistence_bundle(
        run_id=run_id,
        entry_id="entry_b",
        artifact_records=records,
    )
    plan = build_job_artifact_promotion_plan(
        job_id="job_456",
        artifact_contract=bundle,
        file_paths={"uvr_vocal": vocal_path},
    )
    vocal_item = next(i for i in plan["per_artifact"] if i["artifact_type"] == "uvr_vocal")
    assert vocal_item["file_exists"] is True
    assert vocal_item["can_promote"] is False
    assert "metadata_only_not_promotable" in vocal_item["blocked_reasons"]
