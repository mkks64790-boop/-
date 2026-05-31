from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from backend import db as backend_db
from backend import main as backend_main
from backend.services.asset_service import register_job_artifact
from backend.services.job_service import create_cover_job
from backend.services.track_service import (
    mark_track_cover_job_complete,
    set_track_current_lyrics,
)


def _create_track(client, title: str = "Bridge Track") -> str:
    batch = client.post("/api/batches", json={"batch_name": "Track Job Bridge Batch"}).json()
    batch_id = batch["batch_id"]
    import_resp = client.post(
        f"/api/batches/{batch_id}/tracks/import",
        data={"titles_json": json.dumps([title]), "artist": "Factory Artist"},
        files=[("files", ("bridge-track.wav", b"bridge-track", "audio/wav"))],
    )
    assert import_resp.status_code == 200
    return import_resp.json()["imported_tracks"][0]["track_id"]


def _complete_cover_job_for_track(isolated_backend, track_id: str, job_id: str, voice_name: str):
    create_cover_job(
        job_id,
        input_path="shared_data/batches/input.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "unit_track_bridge"},
        track_id=track_id,
        voice_model_id=f"vm_{job_id}",
        voice_name=voice_name,
        depends_on=["tl_done_v1"],
    )
    backend_db.update_task_status(job_id, "\u5df2\u5b8c\u6210", "")

    final_master = Path(isolated_backend) / "shared_data" / "outputs" / job_id / "final_master.wav"
    final_master.parent.mkdir(parents=True, exist_ok=True)
    final_master.write_bytes(b"RIFFFAKEWAVE")
    register_job_artifact(job_id, "cover_mix", "cover_master", str(final_master), is_final=True)
    mark_track_cover_job_complete(track_id, job_id, model_id=f"vm_{job_id}", voice_name=voice_name)


def test_create_cover_job_from_track_writes_bridge_fields(client, isolated_backend, monkeypatch):
    track_id = _create_track(client)
    set_track_current_lyrics(track_id, lyric_document_id="lyr_bridge_doc", timeline_id="tl_bridge_v1")
    monkeypatch.setattr(backend_main, "PROJECT_ROOT", str(isolated_backend), raising=False)
    monkeypatch.setattr(
        backend_main,
        "_build_cover_model_snapshot",
        lambda model_id: {
            "voice_model_origin_kind": "trained_local",
            "voice_model_source_job_id": "train_bridge_source",
            "voice_model_source_summary": "来自本地训练任务 train_bridge_source",
            "voice_model_source_strategy_key": "single_long_preprocess",
            "voice_model_source_material_profile": "single_long_candidate",
        },
    )

    monkeypatch.setattr(
        backend_main,
        "run_cover_preflight",
        lambda model_id: {"ok": True, "job_type": "cover", "model_id": model_id, "checks": [], "errors": []},
    )
    monkeypatch.setattr(backend_main, "_resolve_cover_model_name", lambda model_id: "Bridge Model")
    monkeypatch.setattr(
        backend_main,
        "_activate_and_dispatch_cover_job",
        lambda job_id, model_id, background_tasks, voice_name="": (backend_main.get_job(job_id), False),
    )

    resp = client.post(f"/api/tracks/{track_id}/cover-jobs", json={"model_id": "vm_bridge"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["status"] == "pending"
    assert payload["queue_state"] == "waiting_for_compute_slot"
    assert payload["voice_name"] == "Bridge Model"
    assert payload["voice_model_origin_kind"] == "trained_local"
    assert payload["voice_model_source_job_id"] == "train_bridge_source"
    assert payload["voice_model_source_summary"] == "来自本地训练任务 train_bridge_source"

    conn = backend_db.get_connection()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (payload["job_id"],)).fetchone()
    finally:
        conn.close()

    assert row is not None
    job = dict(row)
    assert job["track_id"] == track_id
    assert job["job_type"] == "cover"
    assert job["job_kind"] == "cover"
    assert job["resource_class"] == "gpu_heavy"
    assert job["voice_model_id"] == "vm_bridge"
    assert job["voice_name"] == "Bridge Model"
    assert json.loads(job["depends_on_json"]) == ["tl_bridge_v1", "lyr_bridge_doc"]
    metadata = json.loads(job["metadata_json"])
    assert metadata["voice_model_origin_kind"] == "trained_local"
    assert metadata["voice_model_source_job_id"] == "train_bridge_source"
    assert metadata["voice_model_source_summary"] == "来自本地训练任务 train_bridge_source"

    detail = client.get(f"/api/tracks/{track_id}").json()
    assert detail["status"] == "cover_pending"
    assert any(event["action"] == "track_cover_job_create" for event in detail["audit_events"])

    jobs_payload = client.get(f"/api/tracks/{track_id}/jobs").json()
    assert jobs_payload["track_id"] == track_id
    assert len(jobs_payload["items"]) == 1
    related_job = jobs_payload["items"][0]
    assert related_job["job_id"] == payload["job_id"]
    assert related_job["job_kind"] == "cover"
    assert related_job["voice_model_id"] == "vm_bridge"
    assert related_job["voice_name"] == "Bridge Model"
    assert related_job["voice_model_origin_kind"] == "trained_local"
    assert related_job["voice_model_source_job_id"] == "train_bridge_source"
    assert related_job["voice_model_source_summary"] == "来自本地训练任务 train_bridge_source"
    assert related_job["has_final_artifact"] is False
    assert related_job["can_open_studio"] is False

    job_detail = client.get(f"/api/jobs/{payload['job_id']}").json()
    assert job_detail["voice_model_origin_kind"] == "trained_local"
    assert job_detail["voice_model_source_job_id"] == "train_bridge_source"
    assert job_detail["voice_model_source_summary"] == "来自本地训练任务 train_bridge_source"


def test_track_jobs_endpoint_exposes_studio_and_download_for_completed_cover(client, isolated_backend):
    track_id = _create_track(client, title="Completed Bridge Track")
    job_id = "task_bridge_done"

    _complete_cover_job_for_track(isolated_backend, track_id, job_id, "Done Model")

    jobs_payload = client.get(f"/api/tracks/{track_id}/jobs").json()
    assert len(jobs_payload["items"]) == 1
    item = jobs_payload["items"][0]
    assert item["job_id"] == job_id
    assert item["status"] == "\u5df2\u5b8c\u6210"
    assert item["current_stage"] == "cover_mix"
    assert item["has_final_artifact"] is True
    assert item["final_artifact_type"] == "cover_master"
    assert item["can_open_studio"] is True
    assert item["final_artifact_download_url"].endswith("/download")
    parsed = urlparse(item["studio_url"])
    query = parse_qs(parsed.query)
    assert parsed.path == "/studio"
    assert query.get("job_id") == [job_id]
    assert query.get("track_id") == [track_id]
    assert query.get("batch_id")
    assert query.get("artifact_id")

    detail = client.get(f"/api/tracks/{track_id}").json()
    assert detail["status"] == "cover_ready"
    assert any(event["action"] == "track_cover_job_complete" for event in detail["audit_events"])


def test_track_master_endpoint_sets_current_master_and_marks_job(client, isolated_backend):
    track_id = _create_track(client, title="Master Bridge Track")
    older_job_id = "task_bridge_master_old"
    latest_job_id = "task_bridge_master_new"

    _complete_cover_job_for_track(isolated_backend, track_id, older_job_id, "Older Master")
    _complete_cover_job_for_track(isolated_backend, track_id, latest_job_id, "Latest Master")

    jobs_before = client.get(f"/api/tracks/{track_id}/jobs").json()
    assert jobs_before["current_master_job_id"] == ""
    assert not any(item["is_current_master"] for item in jobs_before["items"])

    older_item = next(item for item in jobs_before["items"] if item["job_id"] == older_job_id)
    resp = client.post(
        f"/api/tracks/{track_id}/master",
        json={"job_id": older_job_id, "artifact_id": older_item["final_artifact_id"]},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["current_master_job_id"] == older_job_id
    assert payload["current_master_artifact_id"] == older_item["final_artifact_id"]
    assert payload["current_master"]["job_id"] == older_job_id

    detail = client.get(f"/api/tracks/{track_id}").json()
    assert detail["current_master_job_id"] == older_job_id
    assert detail["current_master"]["job_id"] == older_job_id
    assert any(event["action"] == "track_master_set" for event in detail["audit_events"])

    jobs_after = client.get(f"/api/tracks/{track_id}/jobs").json()
    assert jobs_after["current_master_job_id"] == older_job_id
    assert jobs_after["current_master_artifact_id"] == older_item["final_artifact_id"]
    old_after = next(item for item in jobs_after["items"] if item["job_id"] == older_job_id)
    latest_after = next(item for item in jobs_after["items"] if item["job_id"] == latest_job_id)
    assert old_after["is_current_master"] is True
    assert latest_after["is_current_master"] is False
