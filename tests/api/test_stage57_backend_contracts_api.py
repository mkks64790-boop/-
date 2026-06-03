from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from backend import db as backend_db
from backend import main as backend_main
from backend.services.asset_service import (
    get_final_job_artifact,
    get_job_artifact,
    register_job_artifact,
    update_job_artifact_review,
)
from backend.services.job_service import create_cover_job, create_train_job, get_job_row


def _task_row(task_id: str) -> dict:
    conn = backend_db.get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        assert row is not None
        return dict(row)
    finally:
        conn.close()


def _set_job_track(job_id: str, track_id: str) -> None:
    conn = backend_db.get_connection()
    try:
        conn.execute("UPDATE jobs SET track_id = ? WHERE job_id = ?", (track_id, job_id))
        conn.commit()
    finally:
        conn.close()


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _create_completed_cover_job(job_id: str) -> None:
    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "stage57_backend_contract_test"},
        voice_model_id="v_stage57",
        voice_name="Stage57 Voice",
    )
    backend_db.update_task_status(job_id, "completed", "")


def test_health_and_diagnostics_expose_runtime_source_contract(client, monkeypatch):
    monkeypatch.setattr(backend_main, "get_engine_summary", lambda: {"ok": True})
    monkeypatch.setattr(
        backend_main,
        "run_train_preflight",
        lambda strategy_key: {"ok": True, "checks": [], "errors": []},
    )
    monkeypatch.setattr(
        backend_main,
        "run_cover_preflight",
        lambda model_id: {"ok": True, "checks": [], "errors": []},
    )
    monkeypatch.setattr(backend_main, "list_models", lambda *args, **kwargs: [{"usable": True}])

    health = client.get("/api/health")
    diagnostics = client.get("/api/diagnostics/summary")

    assert health.status_code == 200
    assert diagnostics.status_code == 200
    for runtime in (health.json()["api_runtime"], diagnostics.json()["api_runtime"]):
        assert runtime["loaded_source"]["path"].endswith("main.py")
        assert runtime["loaded_source"]["sha256_12"]
        assert runtime["current_source"]["sha256_12"]
        assert runtime["route_signature"]["route_count"] > 20
        assert runtime["needs_restart"] is False
        assert "restart_hint" in runtime


def test_status_filters_and_controls_are_normalized_without_dispatch(client, monkeypatch):
    calls: list[str] = []

    def forbidden_run(*args, **kwargs):
        calls.append("run")
        raise AssertionError("job control contract test must not run compute")

    monkeypatch.setattr(backend_main, "_safe_dispatch_pending_compute_task", lambda: False)
    monkeypatch.setattr(backend_main, "_run_job", forbidden_run)

    failed_train_id = "stage57_failed_train"
    create_train_job(
        failed_train_id,
        voice_name="Stage57Failed",
        dataset_path=f"shared_data/jobs/{failed_train_id}/dataset",
        output_root=f"shared_data/jobs/{failed_train_id}",
        strategy_key="single_long_preprocess",
        metadata={"source": "stage57_backend_contract_test"},
    )
    backend_db.update_task_status(failed_train_id, "failed", "synthetic failure")

    failed_cover_id = "stage57_failed_cover"
    create_cover_job(
        failed_cover_id,
        input_path=f"shared_data/jobs/{failed_cover_id}/input/source.wav",
        output_root=f"shared_data/jobs/{failed_cover_id}",
        metadata={"source": "stage57_backend_contract_test"},
    )
    backend_db.update_task_status(failed_cover_id, "\u5931\u8d25", "synthetic failure")

    cancel_id = "stage57_cancel_queued"
    create_cover_job(
        cancel_id,
        input_path=f"shared_data/jobs/{cancel_id}/input/source.wav",
        output_root=f"shared_data/jobs/{cancel_id}",
        metadata={"source": "stage57_backend_contract_test"},
    )
    backend_db.update_task_status(cancel_id, "queued", "")

    failed_items = client.get("/api/jobs?status=failed&include_smoke=true").json()["items"]
    failed_items_cn = client.get("/api/jobs?status=%E5%A4%B1%E8%B4%A5&include_smoke=true").json()["items"]
    failed_ids = {item["job_id"] for item in failed_items}
    failed_ids_cn = {item["job_id"] for item in failed_items_cn}

    assert failed_train_id in failed_ids
    assert failed_cover_id in failed_ids
    assert failed_train_id in failed_ids_cn
    assert client.get(f"/api/jobs/{failed_train_id}").json()["current_stage"] == "failed"
    assert client.get("/api/jobs/summary?include_smoke=true").json()["failed_count"] >= 2

    retry = client.post(f"/api/jobs/{failed_train_id}/retry")
    requeue = client.post(f"/api/jobs/{failed_cover_id}/requeue")
    cancel = client.post(f"/api/jobs/{cancel_id}/cancel")

    assert retry.status_code == 200
    assert retry.json()["status"] == "pending"
    assert retry.json()["current_stage"] == "pending"
    assert retry.json()["dispatch_triggered"] is False
    assert _task_row(failed_train_id)["status"] == "pending"
    assert get_job_row(failed_train_id)["status"] == "pending"

    assert requeue.status_code == 200
    assert requeue.json()["status"] == "pending"
    assert requeue.json()["current_stage"] == "pending"
    assert _task_row(failed_cover_id)["status"] == "pending"
    assert get_job_row(failed_cover_id)["status"] == "pending"

    assert cancel.status_code == 200
    assert cancel.json()["status"] == "\u5df2\u53d6\u6d88"
    assert cancel.json()["current_stage"] == "cancelled"
    assert _task_row(cancel_id)["status"] == "\u5df2\u53d6\u6d88"
    assert get_job_row(cancel_id)["current_stage"] == "cancelled"
    assert calls == []


def test_artifact_dedup_updates_final_contract_and_preserves_review(client, isolated_backend):
    job_id = "stage57_artifact_dedup"
    track_id = "track 57+A"
    _create_completed_cover_job(job_id)
    _set_job_track(job_id, track_id)

    source = isolated_backend / "shared_data" / "outputs" / job_id / "final master +57.wav"
    _write_bytes(source, b"first")
    artifact_id = register_job_artifact(
        job_id,
        "cover_mix",
        "cover_master",
        str(source),
        is_final=False,
        metadata={"marker": "first"},
    )
    assert artifact_id
    assert get_final_job_artifact(job_id) is None

    update_job_artifact_review(job_id, artifact_id, verdict="usable", notes="human review")
    final_payload = b"RIFF-stage57-final-master"
    _write_bytes(source, final_payload)
    second_artifact_id = register_job_artifact(
        job_id,
        "cover_mix",
        "cover_master",
        str(source),
        is_final=True,
        metadata={"marker": "second"},
    )

    assert second_artifact_id == artifact_id
    artifact = get_job_artifact(job_id, artifact_id)
    assert artifact is not None
    assert artifact["is_final"] == 1
    assert artifact["file_size"] == len(final_payload)
    metadata = json.loads(artifact["metadata_json"])
    assert metadata["marker"] == "second"
    assert metadata["listening_review"]["verdict"] == "usable"
    assert get_final_job_artifact(job_id)["artifact_id"] == artifact_id

    conn = backend_db.get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM job_artifacts WHERE job_id = ?",
            (job_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1

    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["can_open_studio"] is True
    assert detail["final_artifact_id"] == artifact_id
    assert detail["final_artifact_download_url"] == f"/api/jobs/{job_id}/artifacts/{artifact_id}/download"
    query = parse_qs(urlparse(detail["studio_url"]).query)
    assert query["job_id"] == [job_id]
    assert query["artifact_id"] == [artifact_id]

    review_items = client.get("/api/reviews/artifacts?limit=20").json()["items"]
    review_item = next(item for item in review_items if item["artifact_id"] == artifact_id)
    review_query = parse_qs(urlparse(review_item["studio_url"]).query)
    assert review_query["track_id"] == [track_id]
    assert review_query["job_id"] == [job_id]
    assert review_query["artifact_id"] == [artifact_id]
