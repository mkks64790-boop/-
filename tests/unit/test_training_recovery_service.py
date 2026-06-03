from __future__ import annotations

import json
from pathlib import Path

from backend.db import get_connection, update_task_status
from backend.services import training_recovery_service
from backend.services.job_service import canonical_current_stage, create_train_job
from backend.services.stage_log_service import list_stage_logs
from backend.services.stage_log_service import log_stage


def _seed_candidate(rvc_root: Path, exp_name: str, *, epoch: int, feature_count: int = 1, has_index: bool = False) -> None:
    exp_dir = rvc_root / "logs" / exp_name
    feature_dir = exp_dir / "3_feature768"
    weights_dir = rvc_root / "assets" / "weights"
    index_dir = rvc_root / "assets" / "indices"
    feature_dir.mkdir(parents=True, exist_ok=True)
    weights_dir.mkdir(parents=True, exist_ok=True)
    for index in range(feature_count):
        (feature_dir / f"{index:04d}.npy").write_bytes(b"feature")
    (weights_dir / f"{exp_name}_e{epoch}_s6300.pth").write_bytes(b"checkpoint")
    if has_index:
        index_dir.mkdir(parents=True, exist_ok=True)
        (index_dir / f"{exp_name}.index").write_bytes(b"index-data-long-enough")


def _seed_recovery_job(job_id: str = "train_recovery_case"):
    job = create_train_job(
        job_id,
        voice_name="Recovery",
        dataset_path=f"shared_data/jobs/{job_id}/dataset",
        output_root=f"shared_data/jobs/{job_id}",
        strategy_key="single_long_preprocess",
        metadata={"smoke": True},
    )
    update_task_status(job_id, "失败", "train_core_timeout")
    return job


def test_recovery_candidates_recommend_highest_epoch(client, tmp_path, monkeypatch):
    rvc_root = tmp_path / "rvc"
    monkeypatch.setenv("FEISHARK_RVC_DIR", str(rvc_root))
    _seed_candidate(rvc_root, "feishark_v_62f76886", epoch=90, feature_count=3)
    _seed_candidate(rvc_root, "feishark_v_2860bda4", epoch=10, feature_count=20)

    job = _seed_recovery_job("train_recovery_rank")
    log_stage(job.job_id, "train_core", "failed", "timeout feishark_v_62f76886", {"exp_name": "feishark_v_62f76886"})
    log_stage(job.job_id, "train_core", "failed", "timeout feishark_v_2860bda4", {"exp_name": "feishark_v_2860bda4"})

    resp = client.get(f"/api/jobs/{job.job_id}/training-recovery")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["can_recover"] is True
    assert payload["recommended_exp_name"] == "feishark_v_62f76886"
    assert payload["candidates"][0]["highest_epoch"] == 90


def test_recovery_dry_run_does_not_write_db(client, tmp_path, monkeypatch):
    rvc_root = tmp_path / "rvc"
    monkeypatch.setenv("FEISHARK_RVC_DIR", str(rvc_root))
    _seed_candidate(rvc_root, "feishark_v_abcdef01", epoch=30, feature_count=1, has_index=True)

    job = _seed_recovery_job("train_recovery_dryrun")
    log_stage(job.job_id, "train_core", "failed", "timeout feishark_v_abcdef01", {"exp_name": "feishark_v_abcdef01"})

    resp = client.post(
        f"/api/jobs/{job.job_id}/training-recovery/register",
        json={
            "exp_name": "feishark_v_abcdef01",
            "model_name": "RecoveredDryRun",
            "build_index_if_missing": True,
            "dry_run": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["dry_run"] is True

    conn = get_connection()
    try:
        model = conn.execute("SELECT * FROM voice_models WHERE model_name = 'RecoveredDryRun'").fetchone()
        artifacts = conn.execute("SELECT * FROM job_artifacts WHERE job_id = ?", (job.job_id,)).fetchall()
        row = conn.execute("SELECT status, metadata_json FROM jobs WHERE job_id = ?", (job.job_id,)).fetchone()
    finally:
        conn.close()
    assert model is None
    assert artifacts == []
    assert row["status"] == "失败"
    assert "recovered_from_checkpoint" not in json.loads(row["metadata_json"] or "{}")


def test_recovery_register_builds_missing_index_and_writes_model(client, tmp_path, monkeypatch):
    rvc_root = tmp_path / "rvc"
    monkeypatch.setenv("FEISHARK_RVC_DIR", str(rvc_root))
    exp_name = "feishark_v_abcdef02"
    _seed_candidate(rvc_root, exp_name, epoch=42, feature_count=2, has_index=False)

    job = _seed_recovery_job("train_recovery_register")
    log_stage(job.job_id, "train_core", "failed", f"timeout {exp_name}", {"exp_name": exp_name})
    called = {"index": False}

    def _fake_run_training_index(received_exp_name: str) -> None:
        called["index"] = received_exp_name == exp_name
        index_dir = rvc_root / "assets" / "indices"
        index_dir.mkdir(parents=True, exist_ok=True)
        (index_dir / f"{received_exp_name}.index").write_bytes(b"index-data-long-enough")

    monkeypatch.setattr(training_recovery_service, "run_training_index", _fake_run_training_index)

    resp = client.post(
        f"/api/jobs/{job.job_id}/training-recovery/register",
        json={
            "exp_name": exp_name,
            "model_name": "RecoveredRegister",
            "build_index_if_missing": True,
            "dry_run": False,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert called["index"] is True
    assert payload["pth_path"].endswith("RecoveredRegister.pth")
    assert payload["index_path"].endswith("RecoveredRegister.index")

    conn = get_connection()
    try:
        model = conn.execute("SELECT * FROM voice_models WHERE model_name = 'RecoveredRegister'").fetchone()
        artifacts = conn.execute(
            "SELECT artifact_type FROM job_artifacts WHERE job_id = ? ORDER BY artifact_type",
            (job.job_id,),
        ).fetchall()
        row = conn.execute("SELECT status, metadata_json FROM jobs WHERE job_id = ?", (job.job_id,)).fetchone()
    finally:
        conn.close()
    metadata = json.loads(row["metadata_json"] or "{}")
    assert model is not None
    assert row["status"] == "完成"
    assert metadata["recovered_from_checkpoint"] is True
    assert metadata["recovered_exp_name"] == exp_name
    assert metadata["recovered_epoch"] == 42
    assert [item["artifact_type"] for item in artifacts] == ["train_model_index", "train_model_pth"]


def test_completed_recovered_train_job_canonical_stage_prefers_register(isolated_backend):
    job = _seed_recovery_job("train_recovery_stage")
    log_stage(job.job_id, "train_register_model", "completed", "model registered")
    log_stage(job.job_id, "train_checkpoint_recover", "completed", "checkpoint recovery completed")
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET status = '完成',
                current_stage = 'train_checkpoint_recover',
                metadata_json = ?
            WHERE job_id = ?
            """,
            (
                json.dumps(
                    {
                        "recovered_from_checkpoint": True,
                        "recovered_model_id": "v_recovered",
                        "recovered_exp_name": "feishark_v_abcdef03",
                    },
                    ensure_ascii=False,
                ),
                job.job_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job.job_id,)).fetchone()
    finally:
        conn.close()

    assert canonical_current_stage(dict(row), list_stage_logs(job.job_id)) == "train_register_model"
