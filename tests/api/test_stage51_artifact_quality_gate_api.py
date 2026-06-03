from __future__ import annotations

import math
import wave
from pathlib import Path

from backend import main as backend_main
from backend.services.asset_service import register_job_artifact
from backend.services.job_service import create_cover_job
from backend import db as backend_db


def _write_pcm_wav(path: Path, *, duration_sec: float, amplitude: int = 8000, sample_rate: int = 8000) -> None:
    frame_count = int(duration_sec * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            value = 0 if amplitude == 0 else int(amplitude * math.sin(2 * math.pi * 220 * index / sample_rate))
            frames.extend(value.to_bytes(2, "little", signed=True))
        handle.writeframes(bytes(frames))


def _seed_cover_job(root: Path, job_id: str) -> None:
    input_path = root / "shared_data" / "jobs" / job_id / "input" / "source.wav"
    _write_pcm_wav(input_path, duration_sec=1.0, amplitude=2000)
    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "stage51_quality_gate_test"},
        voice_model_id="v_stage51",
        voice_name="Stage51 Voice",
    )
    backend_db.update_task_status(job_id, "completed", "")


def _seed_cover_master(root: Path, job_id: str, *, duration_sec: float, amplitude: int = 8000) -> str:
    _seed_cover_job(root, job_id)
    final_path = root / "shared_data" / "outputs" / job_id / "final_master.wav"
    _write_pcm_wav(final_path, duration_sec=duration_sec, amplitude=amplitude)
    artifact_id = register_job_artifact(
        job_id,
        "cover_mix",
        "cover_master",
        str(final_path),
        is_final=True,
        metadata={"source": "stage51_quality_gate_test"},
    )
    assert artifact_id
    return artifact_id


def test_review_artifacts_return_quality_summary_and_counts(client, isolated_backend):
    long_artifact_id = _seed_cover_master(isolated_backend, "task_stage51_long", duration_sec=31.0, amplitude=9000)
    short_artifact_id = _seed_cover_master(isolated_backend, "task_stage51_short", duration_sec=2.0, amplitude=9000)
    silent_artifact_id = _seed_cover_master(isolated_backend, "task_stage51_silent", duration_sec=31.0, amplitude=0)

    resp = client.get("/api/reviews/artifacts?limit=20")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["summary"]["total"] == 3
    assert payload["summary"]["quality_reviewable"] == 1
    assert payload["summary"]["quality_blocked"] == 2

    by_id = {item["artifact_id"]: item for item in payload["items"]}
    assert by_id[long_artifact_id]["quality_verdict"] == "reviewable"
    assert by_id[short_artifact_id]["quality_verdict"] == "blocked_auto"
    assert "too_short_under_10s" in by_id[short_artifact_id]["quality_flags"]
    assert by_id[silent_artifact_id]["quality_verdict"] == "blocked_auto"
    assert "near_silent" in by_id[silent_artifact_id]["quality_flags"]


def test_review_artifacts_quality_filter(client, isolated_backend):
    reviewable_id = _seed_cover_master(isolated_backend, "task_stage51_filter_long", duration_sec=31.0, amplitude=9000)
    _seed_cover_master(isolated_backend, "task_stage51_filter_short", duration_sec=1.0, amplitude=9000)

    reviewable_resp = client.get("/api/reviews/artifacts?quality=reviewable&limit=20")
    blocked_resp = client.get("/api/reviews/artifacts?quality=blocked_auto&limit=20")
    invalid_resp = client.get("/api/reviews/artifacts?quality=made_up&limit=20")

    assert reviewable_resp.status_code == 200
    assert reviewable_resp.json()["summary"]["total"] == 1
    assert reviewable_resp.json()["items"][0]["artifact_id"] == reviewable_id
    assert blocked_resp.status_code == 200
    assert blocked_resp.json()["summary"]["quality_blocked"] == 1
    assert invalid_resp.status_code == 422


def test_job_artifacts_and_detail_include_quality_contract(client, isolated_backend):
    job_id = "task_stage51_job_contract"
    artifact_id = _seed_cover_master(isolated_backend, job_id, duration_sec=2.0, amplitude=9000)

    artifacts_resp = client.get(f"/api/jobs/{job_id}/artifacts")
    detail_resp = client.get(f"/api/jobs/{job_id}")

    assert artifacts_resp.status_code == 200
    artifact = next(item for item in artifacts_resp.json()["artifacts"] if item["artifact_id"] == artifact_id)
    assert artifact["quality_verdict"] == "blocked_auto"
    assert artifact["quality_summary"]["duration_sec"] == 2.0

    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["final_artifact_quality_verdict"] == "blocked_auto"
    assert "too_short_under_10s" in detail["final_artifact_quality_flags"]


def test_quality_gate_read_api_does_not_dispatch_compute(client, isolated_backend, monkeypatch):
    calls: list[str] = []

    def forbidden_dispatch(*args, **kwargs):
        calls.append("dispatch")
        raise AssertionError("quality gate read API must not dispatch compute work")

    def forbidden_run(*args, **kwargs):
        calls.append("run")
        raise AssertionError("quality gate read API must not run jobs")

    monkeypatch.setattr(backend_main, "_dispatch_pending_compute_task", forbidden_dispatch)
    monkeypatch.setattr(backend_main, "_safe_dispatch_pending_compute_task", forbidden_dispatch)
    monkeypatch.setattr(backend_main, "_run_job", forbidden_run)

    job_id = "task_stage51_no_dispatch"
    _seed_cover_master(isolated_backend, job_id, duration_sec=31.0, amplitude=9000)

    responses = [
        client.get("/api/reviews/artifacts?quality=reviewable"),
        client.get(f"/api/jobs/{job_id}/artifacts"),
        client.get(f"/api/jobs/{job_id}"),
    ]

    assert [resp.status_code for resp in responses] == [200, 200, 200]
    assert calls == []
