from __future__ import annotations

import json
import os

from backend.services.asset_service import register_job_artifact
from backend.services.job_service import create_cover_job


def test_lifecycle_contract_endpoint(client):
    resp = client.get("/api/lifecycle/contract")
    assert resp.status_code == 200
    payload = resp.json()
    assert "active" in payload["lifecycle_states"]
    assert "transient" in payload["lifecycle_states"]
    assert payload["authoritative_cleanup_field"] == "lifecycle_state"


def test_job_artifacts_expose_lifecycle_state(client, isolated_backend):
    job_id = "stage59a_lifecycle_cover"
    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "stage59a_acceptance"},
        voice_name="Stage59ARealCover",
    )

    output_dir = os.path.join(isolated_backend, "shared_data", "outputs", job_id)
    os.makedirs(output_dir, exist_ok=True)
    vocal_path = os.path.join(output_dir, "vocal.wav")
    with open(vocal_path, "wb") as handle:
        handle.write(b"RIFF" + b"\x00" * 40)

    register_job_artifact(
        job_id,
        "cover_split",
        "cover_vocal",
        vocal_path,
        is_final=False,
        mirror_into_job_dir=False,
    )
    register_job_artifact(
        job_id,
        "cover_mix",
        "cover_master",
        vocal_path,
        is_final=True,
        mirror_into_job_dir=False,
    )

    resp = client.get(f"/api/jobs/{job_id}/artifacts")
    assert resp.status_code == 200
    artifacts = {item["artifact_type"]: item for item in resp.json()["artifacts"]}
    assert artifacts["cover_vocal"]["lifecycle_state"] == "transient"
    assert artifacts["cover_vocal"]["lifecycle_deletable"] is True
    assert artifacts["cover_master"]["lifecycle_state"] == "active"
    assert artifacts["cover_master"]["lifecycle_downloadable"] is True


def test_smoke_job_artifact_lifecycle_test_data(client):
    job_id = "smoke_stage59a_probe"
    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"smoke": True, "test_scope": "smoke"},
        voice_name="smoke_voice",
    )
    resp = client.get(f"/api/jobs/{job_id}/artifacts")
    assert resp.status_code == 200
    # job with no artifacts still returns list
    assert resp.json()["job_id"] == job_id


def test_patch_artifact_lifecycle_archives_transient(client, isolated_backend):
    job_id = "stage59a_patch_lifecycle"
    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "stage59a_patch"},
        voice_name="Stage59APatch",
    )
    output_dir = os.path.join(isolated_backend, "shared_data", "outputs", job_id)
    os.makedirs(output_dir, exist_ok=True)
    vocal_path = os.path.join(output_dir, "vocal.wav")
    with open(vocal_path, "wb") as handle:
        handle.write(b"RIFF" + b"\x00" * 40)

    artifact_id = register_job_artifact(
        job_id,
        "cover_split",
        "cover_vocal",
        vocal_path,
        is_final=False,
        mirror_into_job_dir=False,
    )
    assert artifact_id

    patch = client.patch(
        f"/api/jobs/{job_id}/artifacts/{artifact_id}/lifecycle",
        json={"lifecycle_state": "archived"},
    )
    assert patch.status_code == 200
    assert patch.json()["lifecycle_state"] == "archived"