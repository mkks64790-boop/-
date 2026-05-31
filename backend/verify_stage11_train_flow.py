from __future__ import annotations

import os
import subprocess
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
os.environ["FEISHARK_RVC_INDEX_TIMEOUT"] = "1800"
os.environ["FEISHARK_RVC_PREPROCESS_THREADS"] = "2"
os.environ["FEISHARK_RVC_TRAIN_FP16"] = "false"

from backend.db import init_db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.model_trainer import RVC_PYTHON  # noqa: E402


UPLOADS = PROJECT_ROOT / "shared_data" / "uploads"


class VerifyError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[STAGE11] {message}")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyError(message)


def wait_for_job(client: TestClient, job_id: str, timeout_seconds: int = 240) -> dict:
    deadline = time.time() + timeout_seconds
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/jobs/{job_id}").json()
        log(f"wait {job_id} -> {last.get('status')} / {last.get('current_stage')}")
        status_text = str(last.get("status") or "")
        if status_text not in {"pending", "processing"} and not status_text.endswith("中"):
            return last
        time.sleep(3)
    raise VerifyError(f"job timeout: {job_id}, last={last}")


def assert_frontend_uses_backend_only() -> None:
    train_js = (PROJECT_ROOT / "frontend" / "js" / "train.js").read_text(encoding="utf-8")
    expect("/api/train" in train_js, "frontend train panel does not submit to /api/train")
    forbidden_markers = ["7866", "infer-web.py", "gradio_client", "client.predict("]
    leaked = [marker for marker in forbidden_markers if marker in train_js]
    expect(not leaked, f"frontend train panel still contains direct RVC markers: {leaked}")

    models_js = (PROJECT_ROOT / "frontend" / "js" / "models.js").read_text(encoding="utf-8")
    expect("const previousValue = state.selectedCoverModelId || select.value;" in models_js, "cover model selection preservation marker missing")
    expect("usableModels.some(model => model.model_id === previousValue)" in models_js, "cover model fallback marker missing")

    main_js = (PROJECT_ROOT / "frontend" / "js" / "main.js").read_text(encoding="utf-8")
    expect("let refreshInFlight = null;" in main_js, "workspace refresh serialization marker missing")
    expect("function shouldPauseAutoRefresh()" in main_js, "auto refresh pause guard missing")


def assert_real_index(path_str: str) -> None:
    path = Path(path_str)
    expect(path.exists(), f"index artifact missing: {path}")
    expect(path.stat().st_size > 12, f"index artifact is still empty-shell sized: {path} ({path.stat().st_size} bytes)")
    proc = subprocess.run(
        [
            RVC_PYTHON,
            "-c",
            "import faiss, sys; faiss.read_index(sys.argv[1]); print('ok')",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    expect(proc.returncode == 0, f"RVC python cannot load index: {path} :: {proc.stderr or proc.stdout}")


def run_train_case(client: TestClient, voice_name: str, files: list[Path], expected_prepare_stage: str) -> dict:
    for file_path in files:
        expect(file_path.exists(), f"train source missing: {file_path}")

    handles = []
    try:
        payload = []
        for file_path in files:
            handle = open(file_path, "rb")
            handles.append(handle)
            payload.append(("files", (file_path.name, handle, "audio/wav")))
        resp = client.post("/api/train", data={"voice_name": voice_name, "smoke": "true"}, files=payload, timeout=1800)
    finally:
        for handle in handles:
            handle.close()

    expect(resp.status_code == 200, f"train create failed: {resp.status_code} {resp.text}")
    job_id = resp.json()["task_id"]
    job = wait_for_job(client, job_id)
    expect(job.get("status") == "完成", f"train job not completed: {job}")
    expect(job.get("current_stage") == "train_register_model", f"unexpected final current_stage: {job}")

    task_status = client.get(f"/api/task_status/{job_id}").json()
    expect(task_status.get("current_stage") == "train_register_model", f"task_status current_stage mismatch: {task_status}")

    logs = client.get(f"/api/jobs/{job_id}/stage-logs").json()["stage_logs"]
    stages = [item["stage_name"] for item in logs]
    expected = [
        "train_dataset_prepare",
        expected_prepare_stage,
        "train_pitch_extract",
        "train_feature_extract",
        "train_core",
        "train_index",
        "train_register_model",
    ]
    for stage in expected:
        expect(stage in stages, f"missing stage {stage} for {job_id}: {stages}")

    artifacts = client.get(f"/api/jobs/{job_id}/artifacts").json()["artifacts"]
    pth_item = next((item for item in artifacts if item["artifact_type"] == "train_model_pth"), None)
    index_item = next((item for item in artifacts if item["artifact_type"] == "train_model_index"), None)
    expect(pth_item is not None, f"train_model_pth missing for {job_id}")
    expect(index_item is not None, f"train_model_index missing for {job_id}")
    expect(Path(pth_item["file_path"]).exists(), f"missing pth file: {pth_item}")
    assert_real_index(index_item["file_path"])

    expect(client.get(f"/api/jobs/{job_id}/artifacts/{pth_item['artifact_id']}/download").status_code == 200, "pth download failed")
    expect(client.get(f"/api/jobs/{job_id}/artifacts/{index_item['artifact_id']}/download").status_code == 200, "index download failed")
    expect(client.get(f"/api/download/{job_id}").status_code == 200, "default download failed")

    return {"job": job, "artifacts": artifacts}


def assert_short_single_train_rejected(client: TestClient) -> dict:
    file_path = UPLOADS / "train_c12177a47818.wav"
    expect(file_path.exists(), f"short single train source missing: {file_path}")

    with file_path.open("rb") as handle:
        resp = client.post(
            "/api/train",
            data={"voice_name": f"stage11_short_reject_{int(time.time())}", "smoke": "true"},
            files=[("files", (file_path.name, handle, "audio/wav"))],
            timeout=1800,
        )

    expect(resp.status_code == 422, f"short single train should be rejected: {resp.status_code} {resp.text}")
    detail = resp.json().get("detail", {})
    expect(detail.get("code") == "train_material_not_eligible", f"unexpected rejection code: {detail}")
    expect(detail.get("material_profile") == "single_short_out_of_window", f"unexpected material profile: {detail}")
    expect(detail.get("recommended_route") == "multi_clean_direct", f"unexpected recommended route: {detail}")
    expect(detail.get("single_long_eligible") is False, f"short single must not be eligible: {detail}")
    expect(detail.get("submission_allowed") is False, f"short single submission must be blocked: {detail}")
    expect(bool(detail.get("reason")), f"short rejection missing reason: {detail}")
    expect(bool(detail.get("next_step")), f"short rejection missing next_step: {detail}")
    return detail


def main() -> int:
    init_db()
    assert_frontend_uses_backend_only()
    with TestClient(app) as client:
        short_rejection = assert_short_single_train_rejected(client)
        multi = run_train_case(
            client,
            voice_name=f"stage11_multi_smoke_{int(time.time())}",
            files=[UPLOADS / "train_e5790874eb1e.wav", UPLOADS / "train_def71bf124f9.wav"],
            expected_prepare_stage="train_direct_prepare",
        )
    log(f"short single rejected -> {short_rejection.get('code')} / {short_rejection.get('material_profile')}")
    log(f"multi ok -> {multi['job']['job_id']}")
    log("stage11 verification PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerifyError as exc:
        print(f"[STAGE11][FAIL] {exc}")
        raise SystemExit(1)
