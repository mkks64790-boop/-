from __future__ import annotations

import os
from pathlib import Path

from backend import db as backend_db
from backend.services.asset_service import register_job_artifact
from backend.services.job_service import create_cover_job


def _seed_cover_artifact(root: Path, job_id: str = "task_download_sandbox") -> str:
    input_path = root / "shared_data" / "jobs" / job_id / "input" / "source.wav"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"RIFF-DOWNLOAD-SANDBOX-SOURCE")

    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "download_path_sandbox_test"},
        voice_model_id="v_download_sandbox",
        voice_name="Download Sandbox Voice",
    )
    backend_db.update_task_status(job_id, "完成", "")

    final_path = root / "shared_data" / "outputs" / job_id / "final_master.wav"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_bytes(b"RIFF-DOWNLOAD-SANDBOX-FINAL")
    artifact_id = register_job_artifact(job_id, "cover_mix", "cover_master", str(final_path), is_final=True)
    assert artifact_id
    return artifact_id


def _set_artifact_file_path(artifact_id: str, file_path: str) -> None:
    conn = backend_db.get_connection()
    try:
        conn.execute(
            "UPDATE job_artifacts SET file_path = ? WHERE artifact_id = ?",
            (file_path, artifact_id),
        )
        conn.commit()
    finally:
        conn.close()


def _set_job_input_path(job_id: str, input_path: str) -> None:
    conn = backend_db.get_connection()
    try:
        conn.execute(
            "UPDATE jobs SET input_path = ? WHERE job_id = ?",
            (input_path, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def test_artifact_download_rejects_path_outside_project(client, isolated_backend):
    job_id = "task_download_sandbox_artifact"
    artifact_id = _seed_cover_artifact(isolated_backend, job_id)

    outside = isolated_backend.parent / "outside_artifact_secret.wav"
    outside.write_bytes(b"OUTSIDE-ARTIFACT-SECRET")
    _set_artifact_file_path(artifact_id, str(outside))

    resp = client.get(f"/api/jobs/{job_id}/artifacts/{artifact_id}/download")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "artifact_not_found"


def test_artifact_download_rejects_traversal_path(client, isolated_backend):
    job_id = "task_download_sandbox_traversal"
    artifact_id = _seed_cover_artifact(isolated_backend, job_id)

    outside = isolated_backend.parent / "traversal_secret.wav"
    outside.write_bytes(b"TRAVERSAL-SECRET")
    rel_escape = os.path.relpath(outside, isolated_backend)
    _set_artifact_file_path(artifact_id, rel_escape)

    resp = client.get(f"/api/jobs/{job_id}/artifacts/{artifact_id}/download")
    assert resp.status_code == 404


def test_task_download_rejects_malicious_final_artifact_path(client, isolated_backend):
    job_id = "task_download_sandbox_task"
    artifact_id = _seed_cover_artifact(isolated_backend, job_id)

    outside = isolated_backend.parent / "outside_task_secret.wav"
    outside.write_bytes(b"OUTSIDE-TASK-SECRET")
    _set_artifact_file_path(artifact_id, str(outside))

    resp = client.get(f"/api/download/{job_id}")
    assert resp.status_code == 404


def test_source_audio_download_rejects_path_outside_project(client, isolated_backend):
    job_id = "task_download_sandbox_source"
    _seed_cover_artifact(isolated_backend, job_id)

    outside = isolated_backend.parent / "outside_source_secret.wav"
    outside.write_bytes(b"OUTSIDE-SOURCE-SECRET")
    _set_job_input_path(job_id, str(outside))

    resp = client.get(f"/api/jobs/{job_id}/source-audio/download")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "source_audio_not_found"


def test_sandboxed_downloads_still_serve_in_project_files(client, isolated_backend):
    job_id = "task_download_sandbox_ok"
    artifact_id = _seed_cover_artifact(isolated_backend, job_id)

    artifact_resp = client.get(f"/api/jobs/{job_id}/artifacts/{artifact_id}/download")
    assert artifact_resp.status_code == 200
    assert artifact_resp.content == b"RIFF-DOWNLOAD-SANDBOX-FINAL"

    task_resp = client.get(f"/api/download/{job_id}")
    assert task_resp.status_code == 200
    assert task_resp.content == b"RIFF-DOWNLOAD-SANDBOX-FINAL"

    source_resp = client.get(f"/api/jobs/{job_id}/source-audio/download")
    assert source_resp.status_code == 200
    assert source_resp.content == b"RIFF-DOWNLOAD-SANDBOX-SOURCE"