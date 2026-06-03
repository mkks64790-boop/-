from __future__ import annotations

import json
from pathlib import Path

from backend import db as backend_db
from backend.services.asset_service import register_job_artifact
from backend.services.job_service import create_cover_job


def _seed_cover_artifact(root: Path, job_id: str = "task_stage49_review") -> str:
    input_path = root / "shared_data" / "jobs" / job_id / "input" / "source.wav"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"RIFF-STAGE49-SOURCE")

    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "stage49_review_test"},
        voice_model_id="v_stage49",
        voice_name="Stage49 Voice",
    )
    backend_db.update_task_status(job_id, "完成", "")

    final_path = root / "shared_data" / "outputs" / job_id / "final_master.wav"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_bytes(b"RIFF-STAGE49-FINAL")
    artifact_id = register_job_artifact(job_id, "cover_mix", "cover_master", str(final_path), is_final=True)
    assert artifact_id
    return artifact_id


def test_artifact_listening_review_roundtrip(client, isolated_backend):
    job_id = "task_stage49_review_roundtrip"
    artifact_id = _seed_cover_artifact(isolated_backend, job_id)

    resp = client.patch(
        f"/api/jobs/{job_id}/artifacts/{artifact_id}/review",
        json={
            "verdict": "release_candidate",
            "overall_score": 4,
            "vocal_score": 5,
            "noise_score": 3,
            "mix_score": 4,
            "notes": "A/B passed; mild separation noise remains.",
        },
    )

    assert resp.status_code == 200
    review = resp.json()["review"]
    assert review["verdict"] == "release_candidate"
    assert review["overall_score"] == 4
    assert review["schema"] == "stage49_listening_review_v1"

    get_resp = client.get(f"/api/jobs/{job_id}/artifacts/{artifact_id}/review")
    assert get_resp.status_code == 200
    assert get_resp.json()["review"]["notes"].startswith("A/B passed")

    conn = backend_db.get_connection()
    try:
        row = conn.execute(
            "SELECT metadata_json FROM job_artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    finally:
        conn.close()
    metadata = json.loads(row["metadata_json"])
    assert metadata["listening_review"]["verdict"] == "release_candidate"


def test_artifact_listening_review_validates_payload(client, isolated_backend):
    job_id = "task_stage49_review_invalid"
    artifact_id = _seed_cover_artifact(isolated_backend, job_id)

    bad_score = client.patch(
        f"/api/jobs/{job_id}/artifacts/{artifact_id}/review",
        json={"verdict": "usable", "overall_score": 6},
    )
    assert bad_score.status_code == 422

    bad_verdict = client.patch(
        f"/api/jobs/{job_id}/artifacts/{artifact_id}/review",
        json={"verdict": "ship_it"},
    )
    assert bad_verdict.status_code == 422


def test_job_source_audio_download_is_project_scoped(client, isolated_backend):
    job_id = "task_stage49_source_download"
    _seed_cover_artifact(isolated_backend, job_id)

    resp = client.get(f"/api/jobs/{job_id}/source-audio/download")

    assert resp.status_code == 200
    assert resp.content == b"RIFF-STAGE49-SOURCE"
