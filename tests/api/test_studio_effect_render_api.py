from __future__ import annotations

import json
import math
import wave
from pathlib import Path

from backend import db as backend_db
from backend.services import studio_effect_service
from backend.services.asset_service import register_job_artifact
from backend.services.job_service import create_cover_job


def _write_test_wav(path: Path, seconds: float = 0.2, sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for index in range(frames):
            sample = int(0.2 * 32767 * math.sin(2 * math.pi * 440 * index / sample_rate))
            handle.writeframesraw(sample.to_bytes(2, "little", signed=True))


def _create_track(client, title: str = "Studio Render Track") -> str:
    batch = client.post("/api/batches", json={"batch_name": "Studio Render API Batch"}).json()
    batch_id = batch["batch_id"]
    import_resp = client.post(
        f"/api/batches/{batch_id}/tracks/import",
        data={"titles_json": json.dumps([title]), "artist": "Render Artist"},
        files=[("files", ("studio-render.wav", b"studio-render-source", "audio/wav"))],
    )
    assert import_resp.status_code == 200
    return import_resp.json()["imported_tracks"][0]["track_id"]


def _complete_cover_job_for_track(root: Path, track_id: str, job_id: str = "task_studio_render_api") -> str:
    create_cover_job(
        job_id,
        input_path="shared_data/batches/input.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "studio_render_api"},
        track_id=track_id,
        voice_model_id="vm_render_api",
        voice_name="Render API Model",
    )
    backend_db.update_task_status(job_id, "\u5df2\u5b8c\u6210", "")

    source = root / "shared_data" / "outputs" / job_id / "final_master.wav"
    _write_test_wav(source)
    artifact_id = register_job_artifact(job_id, "cover_mix", "cover_master", str(source), is_final=True)
    assert artifact_id
    return artifact_id


def test_effect_rack_capabilities_endpoint_reports_engines(client):
    resp = client.get("/api/studio/effect-rack/capabilities")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    engines = {item["id"]: item for item in payload["engines"]}
    assert engines["copy_only"]["available"] is True
    assert engines["copy_only"]["processing_mode"] == "copy_only_no_dsp"
    assert "ffmpeg_dsp_v0" in engines
    assert "studio_effect_render_master" in payload["artifact_types"]


def test_unsupported_render_engine_returns_structured_error(client):
    resp = client.post(
        "/api/studio/effect-rack/export",
        json={
            "track_id": "trk_missing",
            "source_job_id": "task_missing",
            "effect_rack": [],
            "render_engine": "vst_native",
        },
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "unsupported_render_engine"


def test_ffmpeg_not_available_returns_error_without_copy_fallback(client, isolated_backend, monkeypatch):
    track_id = _create_track(client, "Render No FFmpeg")
    job_id = "task_render_no_ffmpeg"
    source_artifact_id = _complete_cover_job_for_track(isolated_backend, track_id, job_id)
    monkeypatch.setattr(studio_effect_service, "get_ffmpeg_path", lambda: "")

    resp = client.post(
        "/api/studio/effect-rack/export",
        json={
            "track_id": track_id,
            "source_job_id": job_id,
            "source_artifact_id": source_artifact_id,
            "effect_rack": [],
            "render_engine": "ffmpeg_dsp_v0",
        },
    )

    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "ffmpeg_not_available"


def test_ffmpeg_render_creates_render_artifact_versions_and_master(client, isolated_backend):
    track_id = _create_track(client, "Render Success")
    job_id = "task_render_success"
    source_artifact_id = _complete_cover_job_for_track(isolated_backend, track_id, job_id)

    resp = client.post(
        "/api/studio/effect-rack/export",
        json={
            "track_id": track_id,
            "source_job_id": job_id,
            "source_artifact_id": source_artifact_id,
            "effect_rack": [
                {"id": "eq", "enabled": True, "params": {"low": 2, "mid": 0, "high": -1}},
                {"id": "compressor", "enabled": True, "params": {"threshold": -12, "ratio": 2}},
                {"id": "limiter", "enabled": True, "params": {"ceiling": -1}},
                {"id": "reverb", "enabled": True, "params": {"mix": 20}},
            ],
            "render_engine": "ffmpeg_dsp_v0",
            "export_profile": "studio_balanced",
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["render_engine"] == "ffmpeg_dsp_v0"
    assert payload["processing_mode"] == "ffmpeg_dsp_v0"
    assert payload["artifact_type"] == "studio_effect_render_master"
    assert {item["id"] for item in payload["applied_effects"]} == {"eq", "compressor", "limiter"}
    assert payload["unsupported_effects"][0]["id"] == "reverb"

    artifacts = client.get(f"/api/jobs/{job_id}/artifacts").json()["artifacts"]
    created = next(item for item in artifacts if item["artifact_id"] == payload["artifact_id"])
    assert created["artifact_type"] == "studio_effect_render_master"
    assert created["stage_name"] == "studio_effect_render"
    assert created["is_final"] == 0
    assert created["file_size"] > 0
    metadata = json.loads(created["metadata_json"])
    assert metadata["processing_mode"] == "ffmpeg_dsp_v0"
    assert metadata["render_engine"] == "ffmpeg_dsp_v0"
    assert metadata["applied_effects"]
    assert metadata["unsupported_effects"][0]["id"] == "reverb"

    versions = client.get(f"/api/tracks/{track_id}/studio-versions").json()["items"]
    render_version = next(item for item in versions if item["artifact_id"] == payload["artifact_id"])
    assert render_version["artifact_type"] == "studio_effect_render_master"
    assert render_version["processing_mode"] == "ffmpeg_dsp_v0"
    assert render_version["downloadable"] is True

    master_resp = client.post(
        f"/api/tracks/{track_id}/master",
        json={"job_id": job_id, "artifact_id": payload["artifact_id"]},
    )
    assert master_resp.status_code == 200
    master_payload = master_resp.json()
    assert master_payload["current_master_artifact_id"] == payload["artifact_id"]
    assert master_payload["current_master_artifact_type"] == "studio_effect_render_master"
    assert master_payload["current_master_processing_mode"] == "ffmpeg_dsp_v0"

