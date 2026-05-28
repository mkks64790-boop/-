from __future__ import annotations

import sqlite3
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.main as main_mod  # noqa: E402
from backend.db import DB_PATH, init_db, update_task_status  # noqa: E402
from backend.services.job_service import create_cover_job, create_train_job, get_job, release_job, reserve_job  # noqa: E402
from backend.services.stage_log_service import log_stage  # noqa: E402


class VerifyError(RuntimeError):
    pass


def step(message: str) -> None:
    print(f"[STAGE13] {message}")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyError(message)


def wait_for(predicate, timeout_seconds: int, message: str) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.2)
    raise VerifyError(message)


def cleanup_synthetic_jobs() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT job_id, status
            FROM jobs
            WHERE job_id LIKE 'smoke_busy_%'
               OR job_id LIKE 'stage13_busy_%'
               OR job_id LIKE 'stage13_retry_%'
               OR job_id LIKE 'stage13_cancel_%'
               OR job_id LIKE 'stage13_queue_%'
            """
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        if row["status"] in {"pending", "processing", "分离中", "修音中", "变声中", "混音中", "切片中", "训练中"}:
            update_task_status(row["job_id"], "失败", "stage13 synthetic cleanup")


def assert_status_views(client: TestClient, job_id: str, expected_status: str, expected_stage: str) -> None:
    job = client.get(f"/api/jobs/{job_id}").json()
    task = client.get(f"/api/task_status/{job_id}").json()
    logs = client.get(f"/api/jobs/{job_id}/stage-logs").json()["stage_logs"]
    expect(job.get("status") == expected_status, f"job status mismatch for {job_id}: {job}")
    expect(task.get("status") == expected_status, f"task status mismatch for {job_id}: {task}")
    expect(job.get("current_stage") == expected_stage, f"job current_stage mismatch for {job_id}: {job}")
    expect(task.get("current_stage") == expected_stage, f"task current_stage mismatch for {job_id}: {task}")
    expect(bool(logs), f"missing stage logs for {job_id}")


def main() -> int:
    init_db()
    cleanup_synthetic_jobs()

    busy_job_id = f"stage13_busy_{uuid.uuid4().hex[:8]}"
    retry_job_id = f"stage13_retry_{uuid.uuid4().hex[:8]}"
    cancel_job_id = f"stage13_cancel_{uuid.uuid4().hex[:8]}"
    queue_job_id = f"stage13_queue_{uuid.uuid4().hex[:8]}"

    busy_job = create_train_job(
        busy_job_id,
        voice_name=busy_job_id,
        dataset_path=f"shared_data/jobs/{busy_job_id}/dataset",
        output_root=f"shared_data/jobs/{busy_job_id}",
        strategy_key="single_long_preprocess",
        metadata={"smoke": True, "test_scope": "verify_stage13"},
    )
    expect(reserve_job(busy_job, main_mod.TRAIN_START_STATUS), "unable to reserve synthetic busy compute slot")

    create_cover_job(
        retry_job_id,
        input_path=f"shared_data/jobs/{retry_job_id}/input/retry.wav",
        output_root=f"shared_data/jobs/{retry_job_id}",
        metadata={"smoke": True, "test_scope": "verify_stage13"},
    )
    update_task_status(retry_job_id, "失败", "stage13 synthetic failure")

    create_cover_job(
        cancel_job_id,
        input_path=f"shared_data/jobs/{cancel_job_id}/input/cancel.wav",
        output_root=f"shared_data/jobs/{cancel_job_id}",
        metadata={"smoke": True, "test_scope": "verify_stage13"},
    )

    create_train_job(
        queue_job_id,
        voice_name=queue_job_id,
        dataset_path=f"shared_data/jobs/{queue_job_id}/dataset",
        output_root=f"shared_data/jobs/{queue_job_id}",
        strategy_key="single_long_preprocess",
        metadata={"smoke": True, "test_scope": "verify_stage13"},
    )

    original_execute_job = main_mod.execute_job
    original_get_next_pending_job = main_mod.get_next_pending_job
    dispatch_event = threading.Event()

    def synthetic_execute_job(job_id: str) -> dict:
        expect(job_id == queue_job_id, f"unexpected dispatched job: {job_id}")
        log_stage(job_id, "train_register_model", "completed", "stage13 synthetic dispatch")
        update_task_status(job_id, "完成", "")
        dispatch_event.set()
        return {"success": True, "synthetic": True, "job_id": job_id}

    def synthetic_get_next_pending_job():
        job = get_job(queue_job_id)
        if job and job.status == "pending" and job.compute_ready == 1:
            return job
        return None

    try:
        with TestClient(main_mod.app) as client:
            retry_resp = client.post(f"/api/jobs/{retry_job_id}/retry")
            expect(retry_resp.status_code == 200, f"retry failed: {retry_resp.status_code} {retry_resp.text}")
            retry_data = retry_resp.json()
            expect(retry_data.get("status") == "pending", f"retry status mismatch: {retry_data}")
            expect(retry_data.get("current_stage") == "pending", f"retry current_stage mismatch: {retry_data}")
            expect(retry_data.get("queue_state") == "waiting_for_compute_slot", f"retry queue_state mismatch: {retry_data}")
            assert_status_views(client, retry_job_id, "pending", "pending")

            requeue_resp = client.post(f"/api/jobs/{queue_job_id}/requeue")
            expect(requeue_resp.status_code == 200, f"requeue failed: {requeue_resp.status_code} {requeue_resp.text}")
            requeue_data = requeue_resp.json()
            expect(requeue_data.get("status") == "pending", f"requeue status mismatch: {requeue_data}")
            expect(requeue_data.get("current_stage") == "pending", f"requeue current_stage mismatch: {requeue_data}")
            expect(requeue_data.get("queue_state") == "waiting_for_compute_slot", f"requeue queue_state mismatch: {requeue_data}")
            assert_status_views(client, queue_job_id, "pending", "pending")

            cancel_resp = client.post(f"/api/jobs/{cancel_job_id}/cancel")
            expect(cancel_resp.status_code == 200, f"cancel failed: {cancel_resp.status_code} {cancel_resp.text}")
            cancel_data = cancel_resp.json()
            expect(cancel_data.get("status") == "已取消", f"cancel status mismatch: {cancel_data}")
            expect(cancel_data.get("current_stage") == "cancelled", f"cancel current_stage mismatch: {cancel_data}")
            assert_status_views(client, cancel_job_id, "已取消", "cancelled")

            main_mod.execute_job = synthetic_execute_job
            main_mod.get_next_pending_job = synthetic_get_next_pending_job

            main_mod._finalize_compute_task(busy_job_id)

            wait_for(dispatch_event.is_set, 20, "queued job was not dispatched after busy slot release")
            wait_for(
                lambda: client.get(f"/api/jobs/{queue_job_id}").json().get("status") == "完成",
                20,
                "queued job did not reach completed status",
            )
            assert_status_views(client, queue_job_id, "完成", "train_register_model")

            step(f"retry ok -> {retry_job_id}")
            step(f"requeue ok -> {queue_job_id}")
            step(f"cancel ok -> {cancel_job_id}")
            step("busy requeue dispatch ok")
    finally:
        main_mod.execute_job = original_execute_job
        main_mod.get_next_pending_job = original_get_next_pending_job
        try:
            release_job(busy_job_id)
        except Exception:
            pass
        cleanup_synthetic_jobs()

    step("stage13 job control verification PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerifyError as exc:
        print(f"[STAGE13][FAIL] {exc}")
        raise SystemExit(1)
