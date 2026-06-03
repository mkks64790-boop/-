from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backend import model_trainer
from backend.services import job_service
from backend.services.stage_log_service import log_stage
from backend.services.training_runtime_guard import (
    TRAIN_CORE_TIMEOUT_CODE,
    TrainingRuntimeError,
    ensure_training_identity,
    has_unclosed_stage,
    inspect_training_checkpoint,
)


def test_train_timeout_is_six_hours_by_default():
    assert model_trainer.TRAIN_TIMEOUT == 21600


def test_train_core_timeout_becomes_structured_error(tmp_path, monkeypatch):
    rvc_root = tmp_path / "rvc"
    logs_dir = rvc_root / "logs"
    weights_dir = rvc_root / "assets" / "weights"
    exp_name = "feishark_v_timeout"
    weights_dir.mkdir(parents=True)
    (logs_dir / exp_name).mkdir(parents=True)
    (weights_dir / f"{exp_name}_e90_s6300.pth").write_bytes(b"checkpoint")

    monkeypatch.setattr(model_trainer, "RVC_WEBUI_DIR", str(rvc_root))
    monkeypatch.setattr(model_trainer, "RVC_LOGS_DIR", str(logs_dir))
    monkeypatch.setattr(model_trainer, "TRAIN_VERSION", "v2")

    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs.get("args") or args[0], timeout=21600, stderr="torch warning")

    monkeypatch.setattr(model_trainer.subprocess, "run", _raise_timeout)

    with pytest.raises(TrainingRuntimeError) as caught:
        model_trainer._run_rvc_command(
            ["python", "train.py", "-e", exp_name],
            timeout=21600,
            label="train/core",
            exp_name=exp_name,
        )

    summary = caught.value.to_summary()
    assert summary["error_code"] == TRAIN_CORE_TIMEOUT_CODE
    assert "21600" in summary["error_summary"]
    assert summary["exp_name"] == exp_name
    assert "e90" in summary["checkpoint_hint"]


def test_inspect_training_checkpoint_finds_epoch_and_feature_dir(tmp_path):
    rvc_root = tmp_path / "rvc"
    exp_name = "feishark_v_guard"
    exp_dir = rvc_root / "logs" / exp_name
    feature_dir = exp_dir / "3_feature768"
    weights_dir = rvc_root / "assets" / "weights"
    feature_dir.mkdir(parents=True)
    weights_dir.mkdir(parents=True)
    (feature_dir / "0000.npy").write_bytes(b"feature")
    (weights_dir / f"{exp_name}_e20_s1400.pth").write_bytes(b"old")
    (weights_dir / f"{exp_name}_e90_s6300.pth").write_bytes(b"new")
    (exp_dir / "G_2333333.pth").write_bytes(b"g")
    (exp_dir / "D_2333333.pth").write_bytes(b"d")

    result = inspect_training_checkpoint(
        exp_name,
        rvc_logs_dir=str(rvc_root / "logs"),
        rvc_webui_dir=str(rvc_root),
        train_version="v2",
    )

    assert result["exists"] is True
    assert result["highest_epoch"] == 90
    assert result["index_feasible"] is True
    assert result["g_weight"].endswith("G_2333333.pth")
    assert result["d_weight"].endswith("D_2333333.pth")


def test_job_summary_normalizes_mixed_statuses(isolated_backend):
    conn = job_service.get_connection()
    try:
        rows = [
            ("job_done_cn", "cover", "完成"),
            ("job_done_legacy", "cover", "已完成"),
            ("job_done_en", "train", "completed"),
            ("job_failed_cn", "cover", "失败"),
            ("job_failed_en", "train", "failed"),
            ("job_cancelled_cn", "cover", "已取消"),
            ("job_running_cn", "train", "训练中"),
            ("job_running_en", "cover", "running"),
        ]
        for job_id, job_type, status in rows:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, legacy_task_id, job_type, job_kind, strategy_key, status,
                    compute_ready, resource_class, depends_on_json, input_path, output_root, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, 1, 'gpu_heavy', '[]', '', '', '{}')
                """,
                (job_id, job_id, job_type, job_type, job_type, status),
            )
        conn.commit()
    finally:
        conn.close()

    summary = job_service.job_summary(include_smoke=True)
    assert summary["completed_count"] == 3
    assert summary["failed_count"] == 2
    assert summary["cancelled_count"] == 1
    assert summary["processing_count"] == 2


def test_train_job_with_open_core_log_is_not_dispatched(isolated_backend, monkeypatch):
    job = job_service.create_train_job(
        "train_guard_open_core",
        voice_name="Guard",
        dataset_path="shared_data/jobs/train_guard_open_core/dataset",
        output_root="shared_data/jobs/train_guard_open_core",
        strategy_key="single_long_preprocess",
        metadata={"smoke": True},
    )
    log_stage(job.job_id, "train_core", "started", "train core: feishark_v_guard", {"exp_name": "feishark_v_guard"})
    assert has_unclosed_stage(job.job_id, "train_core") is True

    called = {"value": False}

    def _never_run(_job):
        called["value"] = True
        return {"success": True}

    monkeypatch.setattr(job_service, "run_registered_pipeline", _never_run)
    result = job_service.execute_job(job.job_id)

    assert result["success"] is False
    assert called["value"] is False
    assert result["error_summary"]["error_code"] == "duplicate_train_core_blocked"


def test_training_identity_is_reused(isolated_backend):
    job = job_service.create_train_job(
        "train_guard_identity",
        voice_name="Guard",
        dataset_path="shared_data/jobs/train_guard_identity/dataset",
        output_root="shared_data/jobs/train_guard_identity",
        strategy_key="single_long_preprocess",
        metadata={"training_model_id": "v_fixed", "training_exp_name": "feishark_v_fixed"},
    )

    first = ensure_training_identity(job)
    second = ensure_training_identity(job)

    assert first == ("v_fixed", "feishark_v_fixed")
    assert second == first
