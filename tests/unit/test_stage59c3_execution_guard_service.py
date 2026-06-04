"""Stage59C-3 execution guard tests."""

from __future__ import annotations

from pathlib import Path

from backend.services.execution_safety_service import (
    MAX_ITEMS,
    evaluate_execution_guards,
    plan_sandbox,
    validate_caps,
)


def test_validate_caps_rejects_max_items_gt_one():
    result = validate_caps(max_items=2, clip_seconds=45)
    assert result["caps_ok"] is False
    assert f"max_items_must_be_{MAX_ITEMS}" in result["errors"][0]


def test_validate_caps_rejects_invalid_max_items_without_exception():
    result = validate_caps(max_items="not-a-number", clip_seconds=45)
    assert result["caps_ok"] is False
    assert "max_items_invalid" in result["errors"]


def test_validate_caps_rejects_clip_out_of_range():
    low = validate_caps(max_items=1, clip_seconds=10)
    high = validate_caps(max_items=1, clip_seconds=99)
    assert low["caps_ok"] is False
    assert high["caps_ok"] is False


def test_sandbox_under_stage59_runtime(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    plan = plan_sandbox(run_id="run_abc", project_root=root)
    assert plan["sandbox_ok"] is True
    assert plan["planned_temp_root"].startswith("shared_data/stage59_runtime/run_abc")
    assert plan["files_created"] is False


def test_guards_metadata_only_no_files(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    result = evaluate_execution_guards(
        run_id="run_x",
        project_root=root,
        max_items=1,
        clip_seconds=45,
    )
    assert result["files_created"] is False
    assert "stage59_runtime" in result["sandbox"]["planned_temp_root"]
