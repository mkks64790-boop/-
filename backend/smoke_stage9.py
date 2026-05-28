from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["FEISHARK_RVC_TRAIN_EPOCHS"] = "1"
os.environ["FEISHARK_RVC_TRAIN_BATCH_SIZE"] = "1"
os.environ["FEISHARK_RVC_SAVE_EVERY_EPOCH"] = "1"
os.environ["FEISHARK_RVC_TRAIN_TIMEOUT"] = "1800"
os.environ["FEISHARK_RVC_PREPROCESS_THREADS"] = "2"
os.environ["FEISHARK_RVC_TRAIN_FP16"] = "false"

from backend.db import init_db  # noqa: E402
from backend.main import app  # noqa: E402


UPLOADS = PROJECT_ROOT / "shared_data" / "uploads"


class SmokeError(RuntimeError):
    pass


def step(message: str) -> None:
    print(f"[SMOKE] {message}")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def wait_for_job(client: TestClient, job_id: str, timeout_seconds: int = 240) -> dict:
    deadline = time.time() + timeout_seconds
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/jobs/{job_id}").json()
        status = last.get("status")
        stage = last.get("current_stage")
        print(f"[WAIT] {job_id} -> {status} / {stage}")
        status_text = str(status or "")
        if status_text not in {"pending", "processing"} and not status_text.endswith("中"):
            return last
        time.sleep(3)
    raise SmokeError(f"job timeout: {job_id}, last={last}")


def assert_download(client: TestClient, job_id: str) -> None:
    resp = client.get(f"/api/download/{job_id}")
    expect(resp.status_code == 200, f"download failed for {job_id}: {resp.status_code}")
    expect(len(resp.content) > 0, f"download empty for {job_id}")


def assert_artifact_exists(path_str: str) -> None:
    path = Path(path_str)
    expect(path.exists(), f"artifact missing: {path}")
    if path.suffix.lower() == ".index":
        expect(path.stat().st_size > 12, f"index artifact is still empty-shell sized: {path} ({path.stat().st_size} bytes)")
        return
    expect(path.stat().st_size > 0, f"artifact empty: {path}")


def pick_cover_model(client: TestClient) -> str:
    models = client.get("/api/models").json()
    expect(len(models) > 0, "no usable cover model available")
    preferred = next((item for item in models if item["model_id"] == "v_77d72349"), None)
    return (preferred or models[0])["model_id"]


def run_cover(client: TestClient) -> dict:
    model_id = pick_cover_model(client)
    audio = UPLOADS / "suno_test.wav"
    expect(audio.exists(), f"cover source missing: {audio}")

    step(f"cover start model={model_id}")
    with open(audio, "rb") as fh:
      upload = client.post("/api/upload_task", data={"smoke": "true"}, files={"file": (audio.name, fh, "audio/wav")})
    expect(upload.status_code == 200, f"cover upload failed: {upload.status_code} {upload.text}")
    task_id = upload.json()["task_id"]

    process = client.post(f"/api/process/{task_id}?model_id={model_id}")
    expect(process.status_code == 200, f"cover process failed: {process.status_code} {process.text}")

    job = wait_for_job(client, task_id)
    expect(job.get("status") == "完成", f"cover job not completed: {job}")
    artifacts = client.get(f"/api/jobs/{task_id}/artifacts").json()["artifacts"]
    cover_master = next((item for item in artifacts if item["artifact_type"] == "cover_master"), None)
    expect(cover_master is not None, f"cover_master missing for {task_id}")
    expect(Path(cover_master["file_path"]).name == "final_master.wav", f"unexpected cover final artifact: {cover_master['file_path']}")
    assert_artifact_exists(cover_master["file_path"])
    artifact_download = client.get(f"/api/jobs/{task_id}/artifacts/{cover_master['artifact_id']}/download")
    expect(artifact_download.status_code == 200, f"cover artifact download failed: {artifact_download.status_code}")
    assert_download(client, task_id)
    return {"job": job, "artifacts": artifacts, "model_id": model_id}


def run_train(client: TestClient, voice_name: str, files: list[Path]) -> dict:
    for file_path in files:
        expect(file_path.exists(), f"train source missing: {file_path}")

    step(f"train start voice={voice_name} files={len(files)}")
    handles = []
    try:
        payload = []
        for file_path in files:
            fh = open(file_path, "rb")
            handles.append(fh)
            payload.append(("files", (file_path.name, fh, "audio/wav")))
        resp = client.post("/api/train", data={"voice_name": voice_name, "smoke": "true"}, files=payload, timeout=1800)
    finally:
        for fh in handles:
            fh.close()

    expect(resp.status_code == 200, f"train create failed: {resp.status_code} {resp.text}")
    job_id = resp.json()["task_id"]
    job = wait_for_job(client, job_id)
    expect(job.get("status") == "完成", f"train job not completed: {job}")
    logs = client.get(f"/api/jobs/{job_id}/stage-logs").json()["stage_logs"]
    stage_names = [item["stage_name"] for item in logs]
    expected_stages = [
        "train_dataset_prepare",
        "train_preprocess" if len(files) == 1 else "train_direct_prepare",
        "train_pitch_extract",
        "train_feature_extract",
        "train_core",
        "train_index",
        "train_register_model",
    ]
    for stage_name in expected_stages:
        expect(stage_name in stage_names, f"missing train stage {stage_name} for {job_id}: {stage_names}")
    artifacts = client.get(f"/api/jobs/{job_id}/artifacts").json()["artifacts"]
    model_pth = next((item for item in artifacts if item["artifact_type"] == "train_model_pth"), None)
    model_index = next((item for item in artifacts if item["artifact_type"] == "train_model_index"), None)
    expect(model_pth is not None, f"train pth missing: {job_id}")
    expect(model_index is not None, f"train index missing: {job_id}")
    expect(Path(model_pth["file_path"]).suffix.lower() == ".pth", f"unexpected train pth artifact: {model_pth['file_path']}")
    expect(Path(model_index["file_path"]).suffix.lower() == ".index", f"unexpected train index artifact: {model_index['file_path']}")
    assert_artifact_exists(model_pth["file_path"])
    assert_artifact_exists(model_index["file_path"])
    expect(client.get(f"/api/jobs/{job_id}/artifacts/{model_pth['artifact_id']}/download").status_code == 200, "train pth download failed")
    expect(client.get(f"/api/jobs/{job_id}/artifacts/{model_index['artifact_id']}/download").status_code == 200, "train index download failed")

    download = client.get(f"/api/download/{job_id}")
    expect(download.status_code == 200, f"train download failed: {job_id} {download.status_code}")

    return {"job": job, "artifacts": artifacts}


def main() -> int:
    init_db()
    with TestClient(app) as client:
        cover_result = run_cover(client)
        single_result = run_train(
            client,
            voice_name=f"stage10_single_smoke_{int(time.time())}",
            files=[UPLOADS / "train_c12177a47818.wav"],
        )
        multi_result = run_train(
            client,
            voice_name=f"stage10_multi_smoke_{int(time.time())}",
            files=[
                UPLOADS / "train_e5790874eb1e.wav",
                UPLOADS / "train_def71bf124f9.wav",
            ],
        )

    step("cover pass")
    print(cover_result["job"]["job_id"], cover_result["model_id"])
    step("single train pass")
    print(single_result["job"]["job_id"])
    step("multi train pass")
    print(multi_result["job"]["job_id"])
    step("all smoke checks pass")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as exc:
        print(f"[SMOKE][FAIL] {exc}")
        raise SystemExit(1)
