from __future__ import annotations

from backend import db as backend_db
from backend.services.job_service import create_train_job
from backend.services.model_service import upsert_voice_model
from backend.services.stage_log_service import log_stage


def test_training_observer_reports_running_core_without_model(client, isolated_backend):
    job_id = "train_observer_running"
    create_train_job(
        job_id,
        voice_name="ObserverRunning",
        dataset_path=f"shared_data/jobs/{job_id}/dataset",
        output_root=f"shared_data/jobs/{job_id}",
        strategy_key="single_long_preprocess",
        metadata={"training_config": {"preset_key": "balanced"}},
    )
    backend_db.update_task_status(job_id, "训练中", "")
    log_stage(job_id, "train_upload", "completed", "upload completed")
    log_stage(job_id, "train_preflight", "completed", "preflight completed")
    log_stage(job_id, "train_core", "started", "core training started", {"exp_name": "feishark_v_observer"})

    resp = client.get(f"/api/jobs/{job_id}/training-observer")

    assert resp.status_code == 200
    observer = resp.json()["observer"]
    assert observer["job_id"] == job_id
    assert observer["normalized_status"] == "processing"
    assert observer["current_stage"] == "train_core"
    assert observer["model_registration_status"] == "not_registered"
    assert observer["generated_model_usable"] is False
    assert observer["stage_progress"]["total"] == 9
    assert "核心训练" in observer["next_step"]


def test_training_observer_reports_registered_usable_model(client, isolated_backend):
    job_id = "train_observer_done"
    create_train_job(
        job_id,
        voice_name="ObserverDone",
        dataset_path=f"shared_data/jobs/{job_id}/dataset",
        output_root=f"shared_data/jobs/{job_id}",
        strategy_key="single_long_preprocess",
        metadata={"training_config": {"preset_key": "quality"}},
    )
    log_stage(job_id, "train_register_model", "completed", "model registered")
    backend_db.update_task_status(job_id, "完成", "")

    weights = isolated_backend / "shared_data" / "weights"
    weights.mkdir(parents=True, exist_ok=True)
    (weights / "ObserverDone.pth").write_bytes(b"fake-pth")
    (weights / "ObserverDone.index").write_bytes(b"fake-index")
    upsert_voice_model(
        "v_observer_done",
        "ObserverDone",
        "shared_data/weights/ObserverDone.pth",
        "shared_data/weights/ObserverDone.index",
        source_job_id=job_id,
        metadata={"origin_kind": "trained_local", "source_job_id": job_id},
    )

    resp = client.get(f"/api/jobs/{job_id}/training-observer")
    latest = client.get("/api/training/observer/latest")

    assert resp.status_code == 200
    observer = resp.json()["observer"]
    assert observer["normalized_status"] == "completed"
    assert observer["model_registration_status"] == "model_usable"
    assert observer["generated_model_id"] == "v_observer_done"
    assert observer["generated_model_usable"] is True
    assert observer["stage_progress"]["label"] == "9/9"

    assert latest.status_code == 200
    assert latest.json()["observer"]["job_id"] == job_id
