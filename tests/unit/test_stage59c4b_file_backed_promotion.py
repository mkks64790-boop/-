"""Stage59C-4b file-backed artifact promotion tests."""

from __future__ import annotations

from pathlib import Path

from backend.services.lifecycle_service import resolve_register_job_artifact_lifecycle
from backend.services.artifact_lifecycle_service import (
    build_file_backed_uvr_artifact_contracts,
    build_run_persistence_bundle,
    safe_runtime_run_id,
)
from backend.services.artifact_lifecycle_service import (
    build_job_artifact_promotion_plan,
)


def _write_stems(root: Path, run_id: str) -> dict[str, str]:
    run_dir = root / "shared_data" / "stage59_runtime" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "uvr_vocal": run_dir / "uvr_vocal.wav",
        "uvr_instrumental": run_dir / "uvr_instrumental.wav",
    }
    for path in paths.values():
        path.write_bytes(b"stem")
    return {key: str(path) for key, path in paths.items()}


def test_file_backed_contract_can_promote_when_files_exist(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    run_id = "stage59c4b_run"
    paths = _write_stems(root, run_id)
    records = build_file_backed_uvr_artifact_contracts(
        run_id=run_id,
        entry_id="sc59",
        file_paths=paths,
        project_root=root,
    )
    bundle = build_run_persistence_bundle(
        run_id=run_id,
        entry_id="sc59",
        artifact_records=records,
    )

    plan = build_job_artifact_promotion_plan(
        job_id="job_sc59",
        artifact_contract=bundle,
    )

    # Top level is gated by the physical file register requirement in this stage
    assert plan["can_promote"] is False
    assert "register_job_artifact_requires_os_path_exists" in plan["blocked_reasons"]
    assert plan["requires_later_db_integration"] is True
    assert plan["register_requires_physical_file"] is True
    assert len(plan["per_artifact"]) == 2
    # But per-artifact items are promotable because real files exist on disk
    assert all(item["can_promote"] is True for item in plan["per_artifact"])
    assert all(item.get("file_exists") for item in plan["per_artifact"])


def test_file_backed_contract_promotes_with_sanitized_run_id(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    run_id = "stage59c4b:run"
    paths = _write_stems(root, safe_runtime_run_id(run_id))
    records = build_file_backed_uvr_artifact_contracts(
        run_id=run_id,
        entry_id="sc59",
        file_paths=paths,
        project_root=root,
    )
    bundle = build_run_persistence_bundle(
        run_id=run_id,
        entry_id="sc59",
        artifact_records=records,
    )

    plan = build_job_artifact_promotion_plan(
        job_id="job_sc59",
        artifact_contract=bundle,
    )

    assert plan["can_promote"] is False
    assert "register_job_artifact_requires_os_path_exists" in plan["blocked_reasons"]


def test_file_backed_contract_rejects_empty_file(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    run_id = "stage59c4b_zero"
    paths = _write_stems(root, run_id)
    Path(paths["uvr_vocal"]).write_bytes(b"")
    records = build_file_backed_uvr_artifact_contracts(
        run_id=run_id,
        entry_id="sc59",
        file_paths=paths,
        project_root=root,
    )
    bundle = build_run_persistence_bundle(
        run_id=run_id,
        entry_id="sc59",
        artifact_records=records,
    )

    plan = build_job_artifact_promotion_plan(
        job_id="job_sc59",
        artifact_contract=bundle,
    )

    vocal = next(item for item in plan["per_artifact"] if item["artifact_type"] == "uvr_vocal")
    assert plan["can_promote"] is False
    assert "register_job_artifact_requires_os_path_exists" in plan.get("blocked_reasons", [])
    assert "file_empty" in vocal["blocked_reasons"]


def test_uvr_stems_register_as_transient_lifecycle():
    assert (
        resolve_register_job_artifact_lifecycle(
            artifact_type="uvr_vocal",
            is_final=False,
            job_row=None,
        )
        == "transient"
    )
    assert (
        resolve_register_job_artifact_lifecycle(
            artifact_type="uvr_instrumental",
            is_final=False,
            job_row=None,
        )
        == "transient"
    )
