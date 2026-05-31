from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from backend import db as backend_db
from backend.services.asset_service import register_job_artifact
from backend.services.job_service import create_cover_job


def _create_track(client, title: str = "Studio Export Track") -> str:
    batch = client.post("/api/batches", json={"batch_name": "Studio Effect API Batch"}).json()
    batch_id = batch["batch_id"]
    import_resp = client.post(
        f"/api/batches/{batch_id}/tracks/import",
        data={"titles_json": json.dumps([title]), "artist": "Studio Artist"},
        files=[("files", ("studio-export.wav", b"studio-export-source", "audio/wav"))],
    )
    assert import_resp.status_code == 200
    return import_resp.json()["imported_tracks"][0]["track_id"]


def _complete_cover_job_for_track(root: Path, track_id: str, job_id: str = "task_studio_effect_api") -> str:
    create_cover_job(
        job_id,
        input_path="shared_data/batches/input.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "studio_effect_api"},
        track_id=track_id,
        voice_model_id="vm_effect_api",
        voice_name="Effect API Model",
    )
    backend_db.update_task_status(job_id, "\u5df2\u5b8c\u6210", "")

    source = root / "shared_data" / "outputs" / job_id / "final_master.wav"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"RIFF-STUDIO-EFFECT-API-SOURCE")
    artifact_id = register_job_artifact(job_id, "cover_mix", "cover_master", str(source), is_final=True)
    assert artifact_id
    return artifact_id


def test_studio_effect_export_missing_track_returns_structured_error(client):
    resp = client.post(
        "/api/studio/effect-rack/export",
        json={
            "track_id": "trk_missing",
            "source_job_id": "task_missing",
            "effect_rack": [],
        },
    )

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "track_not_found"


def test_studio_effect_export_rejects_missing_source_artifact(client, isolated_backend):
    track_id = _create_track(client, "Missing Artifact Track")
    create_cover_job(
        "task_missing_artifact",
        input_path="shared_data/batches/input.wav",
        output_root="shared_data/jobs/task_missing_artifact",
        track_id=track_id,
        voice_model_id="vm_missing_artifact",
        voice_name="Missing Artifact Model",
    )

    resp = client.post(
        "/api/studio/effect-rack/export",
        json={
            "track_id": track_id,
            "source_job_id": "task_missing_artifact",
            "source_artifact_id": "art_missing",
            "effect_rack": [],
        },
    )

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "source_artifact_not_found"


def test_studio_effect_export_success_creates_downloadable_draft(client, isolated_backend):
    track_id = _create_track(client, "Successful Export Track")
    job_id = "task_studio_effect_success"
    source_artifact_id = _complete_cover_job_for_track(isolated_backend, track_id, job_id)

    resp = client.post(
        "/api/studio/effect-rack/export",
        json={
            "track_id": track_id,
            "source_job_id": job_id,
            "source_artifact_id": source_artifact_id,
            "effect_rack": [
                {
                    "id": "eq",
                    "enabled": True,
                    "status": "draft",
                    "params": {"low": -10, "mid": 1, "high": 10, "extra": 99},
                }
            ],
            "export_profile": "studio_balanced",
            "note": "api export",
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["processing_mode"] == "copy_only_no_dsp"
    assert payload["track_id"] == track_id
    assert payload["source_job_id"] == job_id
    assert payload["source_artifact_id"] == source_artifact_id
    assert payload["artifact_type"] == "studio_effect_draft_master"
    assert payload["download_url"].endswith("/download")

    parsed = urlparse(payload["studio_url"])
    query = parse_qs(parsed.query)
    assert parsed.path == "/studio"
    assert query["track_id"] == [track_id]
    assert query["job_id"] == [job_id]
    assert query["artifact_id"] == [payload["artifact_id"]]

    artifact_resp = client.get(f"/api/jobs/{job_id}/artifacts")
    assert artifact_resp.status_code == 200
    artifacts = artifact_resp.json()["artifacts"]
    created = next(item for item in artifacts if item["artifact_id"] == payload["artifact_id"])
    assert created["artifact_type"] == "studio_effect_draft_master"
    assert created["is_final"] == 0
    metadata = json.loads(created["metadata_json"])
    assert metadata["processing_mode"] == "copy_only_no_dsp"
    assert metadata["effect_rack"][0]["params"] == {"low": -6, "mid": 1, "high": 6}

    download_resp = client.get(payload["download_url"])
    assert download_resp.status_code == 200
    assert download_resp.content == b"RIFF-STUDIO-EFFECT-API-SOURCE"
