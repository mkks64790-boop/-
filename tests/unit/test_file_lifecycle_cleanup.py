from __future__ import annotations

from pathlib import Path

import pytest

from backend import db as backend_db


def _seed_old_cover_job(
    job_id: str,
    *,
    status: str = "completed",
    created_at: str = "2020-01-01 00:00:00",
    legacy_task_id: str = "",
) -> None:
    conn = backend_db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, legacy_task_id, job_type, job_kind, strategy_key, status,
                input_path, output_root
            ) VALUES (?, ?, 'cover', 'cover', 'cover_strategy', ?, '', '')
            """,
            (job_id, legacy_task_id or None, status),
        )
        conn.execute(
            "UPDATE jobs SET created_at = ? WHERE job_id = ?",
            (created_at, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_old_legacy_task(task_id: str, *, status: str = "完成") -> None:
    conn = backend_db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO tasks (task_id, task_type, input_file, status, created_at)
            VALUES (?, 'cover', 'shared_data/uploads/legacy.wav', ?, '2020-01-01 00:00:00')
            """,
            (task_id, status),
        )
        conn.commit()
    finally:
        conn.close()


def _write_output_artifacts(output_root: Path, job_id: str) -> Path:
    task_dir = output_root / job_id
    task_dir.mkdir(parents=True, exist_ok=True)
    for name in backend_db.LIFECYCLE_DELETE_FILENAMES:
        (task_dir / name).write_bytes(b"mid")
    final_master = task_dir / "final_master.wav"
    final_master.write_bytes(b"keep")
    return task_dir


def test_jobs_only_terminal_cover_job_cleans_intermediates(isolated_backend):
    job_id = "job_only_cover_001"
    _seed_old_cover_job(job_id, status="completed")
    output_root = Path(isolated_backend) / "shared_data" / "outputs"
    task_dir = _write_output_artifacts(output_root, job_id)

    result = backend_db.file_lifecycle_cleanup(days=1)

    assert result["scanned_tasks"] == 1
    assert result["deleted_files"] == len(backend_db.LIFECYCLE_DELETE_FILENAMES)
    for name in backend_db.LIFECYCLE_DELETE_FILENAMES:
        assert not (task_dir / name).exists()
    assert (task_dir / "final_master.wav").exists()


@pytest.mark.parametrize("status", ["failed", "失败", "cancelled", "已取消"])
def test_jobs_terminal_status_variants_are_eligible(isolated_backend, status: str):
    job_id = f"job_status_{status}"
    _seed_old_cover_job(job_id, status=status)
    output_root = Path(isolated_backend) / "shared_data" / "outputs"
    task_dir = _write_output_artifacts(output_root, job_id)

    result = backend_db.file_lifecycle_cleanup(days=1)

    assert result["scanned_tasks"] == 1
    assert result["deleted_files"] == len(backend_db.LIFECYCLE_DELETE_FILENAMES)
    assert not any((task_dir / name).exists() for name in backend_db.LIFECYCLE_DELETE_FILENAMES)


def test_non_terminal_and_recent_jobs_are_skipped(isolated_backend):
    old_active = "job_old_processing"
    recent_done = "job_recent_done"
    _seed_old_cover_job(old_active, status="processing")
    _seed_old_cover_job(recent_done, status="completed", created_at="2099-01-01 00:00:00")
    output_root = Path(isolated_backend) / "shared_data" / "outputs"
    _write_output_artifacts(output_root, old_active)
    _write_output_artifacts(output_root, recent_done)

    result = backend_db.file_lifecycle_cleanup(days=1)

    assert result["scanned_tasks"] == 0
    assert result["deleted_files"] == 0
    assert (output_root / old_active / "vocal.wav").exists()
    assert (output_root / recent_done / "vocal.wav").exists()


def test_deduplicates_shared_id_between_tasks_and_jobs(isolated_backend):
    shared_id = "shared_legacy_cover"
    _seed_old_legacy_task(shared_id)
    _seed_old_cover_job(shared_id, status="completed", legacy_task_id=shared_id)
    output_root = Path(isolated_backend) / "shared_data" / "outputs"
    _write_output_artifacts(output_root, shared_id)

    result = backend_db.file_lifecycle_cleanup(days=1)

    assert result["scanned_tasks"] == 1
    assert result["deleted_files"] == len(backend_db.LIFECYCLE_DELETE_FILENAMES)


def test_legacy_tasks_path_still_cleans_intermediates(isolated_backend):
    task_id = "legacy_task_only"
    _seed_old_legacy_task(task_id)
    output_root = Path(isolated_backend) / "shared_data" / "outputs"
    task_dir = _write_output_artifacts(output_root, task_id)

    result = backend_db.file_lifecycle_cleanup(days=1)

    assert result["scanned_tasks"] == 1
    assert not (task_dir / "vocal.wav").exists()
    assert (task_dir / "final_master.wav").exists()