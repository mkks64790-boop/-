from __future__ import annotations

import json
from pathlib import Path

from backend import db as backend_db
from backend.services.asset_service import register_job_artifact
from backend.services.job_service import create_cover_job


def _create_track(client, title: str = "Studio Versions Track") -> str:
    batch = client.post("/api/batches", json={"batch_name": "Studio Versions Batch"}).json()
    batch_id = batch["batch_id"]
    import_resp = client.post(
        f"/api/batches/{batch_id}/tracks/import",
        data={"titles_json": json.dumps([title]), "artist": "Versions Artist"},
        files=[("files", ("versions-source.wav", b"versions-source", "audio/wav"))],
    )
    assert import_resp.status_code == 200
    return import_resp.json()["imported_tracks"][0]["track_id"]


def _complete_cover_job(root: Path, track_id: str, job_id: str = "task_versions_cover") -> str:
    create_cover_job(
        job_id,
        input_path="shared_data/batches/input.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "studio_versions_api"},
        track_id=track_id,
        voice_model_id=f"vm_{job_id}",
        voice_name="Versions Model",
    )
    backend_db.update_task_status(job_id, "\u5df2\u5b8c\u6210", "")

    source = root / "shared_data" / "outputs" / job_id / "final_master.wav"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"RIFF-STUDIO-VERSIONS-SOURCE")
    artifact_id = register_job_artifact(job_id, "cover_mix", "cover_master", str(source), is_final=True)
    assert artifact_id
    return artifact_id


def _export_draft(client, track_id: str, job_id: str, source_artifact_id: str, note: str = "draft") -> dict:
    resp = client.post(
        "/api/studio/effect-rack/export",
        json={
            "track_id": track_id,
            "source_job_id": job_id,
            "source_artifact_id": source_artifact_id,
            "effect_rack": [{"id": "limiter", "enabled": True, "params": {"ceiling": -2}}],
            "note": note,
        },
    )
    assert resp.status_code == 200
    return resp.json()


def test_cover_master_enters_track_studio_versions(client, isolated_backend):
    track_id = _create_track(client, "Cover Master Versions")
    job_id = "task_versions_cover_master"
    cover_artifact_id = _complete_cover_job(isolated_backend, track_id, job_id)

    resp = client.get(f"/api/tracks/{track_id}/studio-versions")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["track_id"] == track_id
    assert payload["current_master_job_id"] == ""
    versions = payload["items"]
    assert len(versions) == 1
    item = versions[0]
    assert item["artifact_id"] == cover_artifact_id
    assert item["artifact_type"] == "cover_master"
    assert item["stage_name"] == "cover_mix"
    assert item["processing_mode"] == "original_cover"
    assert item["downloadable"] is True
    assert item["download_url"].endswith("/download")
    assert item["studio_url"].startswith(f"/studio?track_id={track_id}&job_id={job_id}")


def test_multiple_studio_effect_drafts_are_listed(client, isolated_backend):
    track_id = _create_track(client, "Multiple Draft Versions")
    job_id = "task_versions_multi_draft"
    cover_artifact_id = _complete_cover_job(isolated_backend, track_id, job_id)

    first = _export_draft(client, track_id, job_id, cover_artifact_id, note="first")
    second = _export_draft(client, track_id, job_id, cover_artifact_id, note="second")

    payload = client.get(f"/api/tracks/{track_id}/studio-versions").json()
    versions = payload["items"]
    artifact_ids = {item["artifact_id"] for item in versions}
    assert {cover_artifact_id, first["artifact_id"], second["artifact_id"]}.issubset(artifact_ids)
    drafts = [item for item in versions if item["artifact_type"] == "studio_effect_draft_master"]
    assert len(drafts) == 2
    assert {item["processing_mode"] for item in drafts} == {"copy_only_no_dsp"}
    assert all(item["is_processing_draft"] is True for item in drafts)
    assert all(item["is_final"] is False for item in drafts)


def test_studio_effect_draft_can_be_explicit_current_master(client, isolated_backend):
    track_id = _create_track(client, "Draft Master Versions")
    job_id = "task_versions_draft_master"
    cover_artifact_id = _complete_cover_job(isolated_backend, track_id, job_id)
    draft = _export_draft(client, track_id, job_id, cover_artifact_id)

    resp = client.post(
        f"/api/tracks/{track_id}/master",
        json={"job_id": job_id, "artifact_id": draft["artifact_id"]},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["current_master_job_id"] == job_id
    assert payload["current_master_artifact_id"] == draft["artifact_id"]
    assert payload["current_master_artifact_type"] == "studio_effect_draft_master"
    assert payload["current_master_processing_mode"] == "copy_only_no_dsp"

    versions = client.get(f"/api/tracks/{track_id}/studio-versions").json()["items"]
    current = next(item for item in versions if item["artifact_id"] == draft["artifact_id"])
    assert current["is_current_master"] is True
    assert current["processing_mode"] == "copy_only_no_dsp"

    jobs_payload = client.get(f"/api/tracks/{track_id}/jobs").json()
    assert jobs_payload["current_master_artifact_id"] == draft["artifact_id"]
    job_item = jobs_payload["items"][0]
    assert job_item["is_current_master"] is True
    assert job_item["is_current_master_job"] is True
    assert job_item["current_master_artifact_id"] == draft["artifact_id"]
    assert job_item["current_master_artifact_type"] == "studio_effect_draft_master"
    assert job_item["current_master_processing_mode"] == "copy_only_no_dsp"


def test_non_audio_or_training_artifact_cannot_be_current_master(client, isolated_backend):
    track_id = _create_track(client, "Reject Non Audio Master")
    job_id = "task_versions_reject_non_audio"
    _complete_cover_job(isolated_backend, track_id, job_id)

    pth_path = isolated_backend / "shared_data" / "jobs" / job_id / "artifacts" / "train_register_model" / "model.pth"
    pth_path.parent.mkdir(parents=True, exist_ok=True)
    pth_path.write_bytes(b"not-audio-model")
    training_artifact_id = register_job_artifact(
        job_id,
        "train_register_model",
        "train_model_pth",
        str(pth_path),
        is_final=False,
    )
    assert training_artifact_id

    resp = client.post(
        f"/api/tracks/{track_id}/master",
        json={"job_id": job_id, "artifact_id": training_artifact_id},
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "master_artifact_type_not_allowed"


def test_missing_artifact_file_is_not_returned_as_downloadable_version(client, isolated_backend):
    track_id = _create_track(client, "Missing File Versions")
    job_id = "task_versions_missing_file"
    cover_artifact_id = _complete_cover_job(isolated_backend, track_id, job_id)

    conn = backend_db.get_connection()
    try:
        row = conn.execute(
            "SELECT file_path FROM job_artifacts WHERE artifact_id = ?",
            (cover_artifact_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    Path(row["file_path"]).unlink()

    resp = client.get(f"/api/tracks/{track_id}/studio-versions")

    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_other_track_artifact_cannot_be_current_master(client, isolated_backend):
    track_a = _create_track(client, "Owner Track A")
    track_b = _create_track(client, "Owner Track B")
    other_job_id = "task_versions_other_track"
    other_artifact_id = _complete_cover_job(isolated_backend, track_b, other_job_id)

    resp = client.post(
        f"/api/tracks/{track_a}/master",
        json={"job_id": other_job_id, "artifact_id": other_artifact_id},
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "master_job_not_found_for_track"
