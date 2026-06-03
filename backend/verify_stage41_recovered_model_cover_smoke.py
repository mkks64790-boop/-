from __future__ import annotations

import argparse
import math
import os
import struct
import sys
import time
import uuid
import wave
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.main as main_mod  # noqa: E402
from backend.db import init_db  # noqa: E402
from backend.services.asset_service import list_job_artifacts  # noqa: E402
from backend.services.batch_service import create_batch  # noqa: E402
from backend.services.job_service import create_cover_job, get_job_row, reserve_job  # noqa: E402
from backend.services.model_service import get_voice_model_detail  # noqa: E402
from backend.services.preflight_service import run_cover_preflight  # noqa: E402
from backend.services.stage_log_service import list_stage_logs, log_stage  # noqa: E402
from backend.services.track_service import (  # noqa: E402
    get_track_job_entry,
    list_track_studio_versions,
    set_track_current_master,
)


MODEL_ID = "v_2c1603c7"
MODEL_NAME = "朱朱_recovered_e90"
SOURCE_JOB_ID = "train_010253ec08f0"


class VerifyError(RuntimeError):
    pass


def step(message: str) -> None:
    print(f"[STAGE41A] {message}")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyError(message)


def make_short_wav(path: Path, seconds: float = 6.0, sample_rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(seconds * sample_rate)
    amplitude = 0.25
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for index in range(frame_count):
            value = int(32767 * amplitude * math.sin(2 * math.pi * 220 * index / sample_rate))
            handle.writeframes(struct.pack("<h", value))


def create_track_for_smoke(source_abs: Path) -> str:
    batch = create_batch(
        "stage41 recovered model smoke",
        metadata={"smoke": True, "test_scope": "stage41a"},
    )
    track_id = f"trk_stage41_{uuid.uuid4().hex[:8]}"
    rel_source = os.path.relpath(source_abs, PROJECT_ROOT).replace("\\", "/")
    conn = main_mod.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO tracks (
                track_id, batch_id, title, artist, source_type, status,
                notes, source_audio_path, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                track_id,
                batch["batch_id"],
                "Stage41 recovered smoke",
                "FeiShark",
                "generated_smoke",
                "imported",
                "stage41 recovered model cover smoke",
                rel_source,
                '{"smoke": true, "test_scope": "stage41a"}',
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return track_id


def assert_model_contract() -> dict:
    detail = get_voice_model_detail(MODEL_ID, main_mod.PROJECT_ROOT, main_mod.WEIGHTS_DIR)
    expect(detail is not None, f"missing recovered model: {MODEL_ID}")
    expect(detail.get("model_name") == MODEL_NAME, f"unexpected model name: {detail.get('model_name')}")
    expect(bool(detail.get("usable")), f"recovered model is not usable: {detail}")
    expect(detail.get("source_job_id") == SOURCE_JOB_ID, f"unexpected source job: {detail.get('source_job_id')}")
    preflight = run_cover_preflight(MODEL_ID)
    expect(bool(preflight.get("ok")), f"cover preflight failed: {preflight.get('errors')}")
    step(f"model preflight ok: {MODEL_ID} / {MODEL_NAME}")
    return detail


def build_model_snapshot(detail: dict) -> dict:
    return {
        "voice_model_origin_kind": detail.get("origin_kind") or "",
        "voice_model_source_job_id": detail.get("source_job_id") or "",
        "voice_model_source_summary": detail.get("source_summary") or "",
        "voice_model_source_strategy_key": detail.get("source_strategy_key") or "",
        "voice_model_source_material_profile": detail.get("source_material_profile") or "",
    }


def wait_for_job_terminal(job_id: str, timeout_seconds: int = 360) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        row = get_job_row(job_id)
        if row and row.get("status") in {"完成", "已完成", "completed", "失败", "failed"}:
            return row
        time.sleep(2)
    raise VerifyError(f"cover job did not finish within {timeout_seconds}s: {job_id}")


def assert_cover_outputs(client: TestClient, job_id: str, track_id: str) -> None:
    row = get_job_row(job_id)
    expect(row is not None, f"missing job row: {job_id}")
    expect(row.get("status") in {"完成", "已完成", "completed"}, f"cover job failed: {row}")
    expect(main_mod.canonical_current_stage(row, list_stage_logs(job_id)) == "cover_mix", f"unexpected current stage: {row}")

    artifacts = list_job_artifacts(job_id)
    final_items = [item for item in artifacts if item.get("is_final") and item.get("artifact_type") == "cover_master"]
    expect(bool(final_items), f"missing cover final artifact: {artifacts}")
    final_artifact = final_items[-1]
    expect(os.path.exists(final_artifact["file_path"]), f"final artifact file missing: {final_artifact}")
    expect(os.path.getsize(final_artifact["file_path"]) > 44, f"final artifact too small: {final_artifact}")

    download = client.get(f"/api/jobs/{job_id}/artifacts/{final_artifact['artifact_id']}/download")
    expect(download.status_code == 200 and len(download.content) > 44, f"artifact download failed: {download.status_code}")

    detail = client.get(f"/api/jobs/{job_id}").json()
    task_status = client.get(f"/api/task_status/{job_id}").json()
    expect(detail.get("voice_model_source_job_id") == SOURCE_JOB_ID, f"job detail missing model source: {detail}")
    expect(task_status.get("voice_model_source_job_id") == SOURCE_JOB_ID, f"task status missing model source: {task_status}")

    track_entry = get_track_job_entry(track_id, job_id, preferred_artifact_id=final_artifact["artifact_id"])
    expect(track_entry is not None, "track job entry missing")
    expect(track_entry.get("can_open_studio") is True, f"track job cannot open studio: {track_entry}")
    expect(track_entry.get("voice_model_source_job_id") == SOURCE_JOB_ID, f"track job missing model source: {track_entry}")
    set_track_current_master(track_id, job_id, final_artifact["artifact_id"])
    versions = list_track_studio_versions(track_id)
    expect(versions and versions.get("items"), f"studio versions missing: {versions}")
    step(f"cover final artifact ok: {final_artifact['file_path']}")


def execute_cover_smoke(client: TestClient, source_abs: Path, model_detail: dict) -> str:
    track_id = create_track_for_smoke(source_abs)
    job_id = f"task_stage41_{uuid.uuid4().hex[:8]}"
    source_rel = os.path.relpath(source_abs, PROJECT_ROOT).replace("\\", "/")
    metadata = {
        "source": "stage41_recovered_model_cover_smoke",
        "smoke": True,
        "track_id": track_id,
        "job_root": f"shared_data/jobs/{job_id}",
        **build_model_snapshot(model_detail),
    }
    job = create_cover_job(
        job_id,
        source_rel,
        f"shared_data/jobs/{job_id}",
        metadata=metadata,
        track_id=track_id,
        voice_model_id=MODEL_ID,
        voice_name=MODEL_NAME,
    )
    log_stage(job_id, "cover_preflight", "completed", "stage41 cover preflight ok", run_cover_preflight(MODEL_ID))
    reserved = reserve_job(job, main_mod.PIPELINE_START_STATUS)
    expect(reserved, "compute slot is busy; stage41 execute smoke cannot start safely")
    try:
        result = main_mod.execute_job(job_id)
        expect(bool(result.get("success")), f"cover strategy failed: {result}")
    finally:
        main_mod._finalize_compute_task(job_id)
    wait_for_job_terminal(job_id)
    assert_cover_outputs(client, job_id, track_id)
    return job_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="create and run a real short cover job")
    args = parser.parse_args()

    init_db()
    source_abs = PROJECT_ROOT / "shared_data" / "jobs" / "stage41_recovered_model_cover_smoke" / "input" / "short_smoke.wav"
    make_short_wav(source_abs)
    model_detail = assert_model_contract()
    step(f"short source ready: {source_abs}")

    with TestClient(main_mod.app) as client:
        if not args.execute:
            step("stage41 recovered model cover dry-run PASS")
            return 0
        job_id = execute_cover_smoke(client, source_abs, model_detail)
        step(f"stage41 recovered model cover execute PASS: {job_id}")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerifyError as exc:
        print(f"[STAGE41A][FAIL] {exc}")
        raise SystemExit(1)
