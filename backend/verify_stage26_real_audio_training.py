from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import requests

try:
    from backend.services.audio_material_service import probe_audio_material
except ImportError:
    from services.audio_material_service import probe_audio_material


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _sample_path(project_relative: str, legacy_external: str) -> Path:
    project_path = PROJECT_ROOT / project_relative
    if project_path.exists():
        return project_path
    return Path(legacy_external)


LONG_SAMPLE = _sample_path(
    r"shared_data\material_library\authorized_dry_vocals\user\朱朱干声唱.mp3",
    r"C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3",
)
SHORT_SAMPLE = _sample_path(
    r"shared_data\material_library\authorized_dry_vocals\user\朱朱干声.mp3",
    r"C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3",
)
HOST = os.getenv("FEISHARK_STAGE26_HOST", "127.0.0.1")
PORT = int(os.getenv("FEISHARK_STAGE26_PORT", "8016"))
BASE_URL = os.getenv("FEISHARK_STAGE26_BASE_URL", f"http://{HOST}:{PORT}")
MAX_WAIT_SECONDS = int(os.getenv("FEISHARK_STAGE26_MAX_WAIT_SECONDS", "900"))


class Stage26Error(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[STAGE26] {message}")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise Stage26Error(message)


def _request(method: str, path: str, **kwargs):
    response = requests.request(method, f"{BASE_URL}{path}", timeout=kwargs.pop("timeout", 60), **kwargs)
    return response


def wait_for_health(deadline_seconds: int = 45) -> dict:
    deadline = time.time() + deadline_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            response = _request("GET", "/api/health", timeout=10)
            if response.ok:
                return response.json()
            last_error = f"status={response.status_code} body={response.text[:300]}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(1)
    raise Stage26Error(f"health timeout: {last_error}")


def start_isolated_server() -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("FEISHARK_RVC_TRAIN_EPOCHS", "1")
    env.setdefault("FEISHARK_RVC_TRAIN_BATCH_SIZE", "1")
    env.setdefault("FEISHARK_RVC_SAVE_EVERY_EPOCH", "1")
    env.setdefault("FEISHARK_RVC_TRAIN_TIMEOUT", "1800")
    env.setdefault("FEISHARK_RVC_INDEX_TIMEOUT", "1800")
    env.setdefault("FEISHARK_RVC_PREPROCESS_THREADS", "2")
    env.setdefault("FEISHARK_RVC_TRAIN_FP16", "false")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            HOST,
            "--port",
            str(PORT),
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def summarize_probe(path: Path) -> dict:
    expect(path.exists(), f"sample missing: {path}")
    meta = probe_audio_material(str(path), file_name=path.name, file_size=path.stat().st_size)
    return {
        "path": str(path),
        "duration_seconds": meta.get("duration_seconds"),
        "duration_label": meta.get("duration_label"),
        "sample_rate": meta.get("sample_rate"),
        "channels": meta.get("channels"),
        "codec": meta.get("codec"),
        "container": meta.get("container"),
        "bit_rate": meta.get("bit_rate"),
        "file_size": meta.get("file_size"),
    }


def preflight_single(duration_seconds: float, file_name: str, file_size: int) -> dict:
    params = {
        "file_count": 1,
        "duration_seconds": duration_seconds,
        "file_name": file_name,
        "file_size": file_size,
        "mime_type": "audio/mpeg",
    }
    response = _request("GET", "/api/preflight/train", params=params, timeout=60)
    expect(response.status_code == 200, f"train preflight failed: {response.status_code} {response.text}")
    return response.json()


def submit_train(sample_path: Path, voice_name: str) -> requests.Response:
    with sample_path.open("rb") as handle:
        return _request(
            "POST",
            "/api/train",
            data={"voice_name": voice_name},
            files={"files": (sample_path.name, handle, "audio/mpeg")},
            timeout=1800,
        )


def poll_job(job_id: str) -> dict:
    deadline = time.time() + MAX_WAIT_SECONDS
    last_job = {}
    observed_stages: list[str] = []

    while time.time() < deadline:
        job_resp = _request("GET", f"/api/jobs/{job_id}", timeout=30)
        logs_resp = _request("GET", f"/api/jobs/{job_id}/stage-logs", timeout=30)
        expect(job_resp.status_code == 200, f"job detail failed: {job_resp.status_code} {job_resp.text}")
        expect(logs_resp.status_code == 200, f"job logs failed: {logs_resp.status_code} {logs_resp.text}")

        last_job = job_resp.json()
        stage_logs = logs_resp.json().get("stage_logs", [])
        observed_stages = [item.get("stage_name") for item in stage_logs]
        status = str(last_job.get("status") or "")
        current_stage = last_job.get("current_stage") or ""
        log(f"poll {job_id} -> {status} / {current_stage}")

        if status not in {"pending", "processing"} and not status.endswith("中"):
            return {
                "timed_out": False,
                "job": last_job,
                "stage_logs": stage_logs,
                "observed_stages": observed_stages,
            }
        time.sleep(5)

    return {
        "timed_out": True,
        "job": last_job,
        "stage_logs": stage_logs,
        "observed_stages": observed_stages,
    }


def fetch_train_artifacts(job_id: str) -> list[dict]:
    response = _request("GET", f"/api/jobs/{job_id}/artifacts", timeout=60)
    expect(response.status_code == 200, f"artifacts failed: {response.status_code} {response.text}")
    artifacts = response.json().get("artifacts", [])
    pth_item = next((item for item in artifacts if item.get("artifact_type") == "train_model_pth"), None)
    index_item = next((item for item in artifacts if item.get("artifact_type") == "train_model_index"), None)
    expect(pth_item is not None, f"missing pth artifact: {job_id}")
    expect(index_item is not None, f"missing index artifact: {job_id}")

    pth_path = Path(pth_item["file_path"])
    index_path = Path(index_item["file_path"])
    expect(pth_path.exists() and pth_path.stat().st_size > 0, f"pth artifact invalid: {pth_path}")
    expect(index_path.exists() and index_path.stat().st_size > 12, f"index artifact invalid: {index_path}")
    return artifacts


def main() -> int:
    server = start_isolated_server()
    long_probe = {}
    short_probe = {}
    long_preflight = {}
    short_preflight = {}
    long_submission = {}
    long_runtime = {}
    long_artifacts = []
    short_submit_payload = {}

    try:
        health = wait_for_health()
        log(f"health ok -> engine={health.get('engine', {}).get('engine_kind')} base={health.get('engine', {}).get('base_url')}")

        env_preflight = _request("GET", "/api/preflight/train?file_count=1", timeout=60)
        expect(env_preflight.status_code == 200, f"environment preflight failed: {env_preflight.status_code} {env_preflight.text}")
        env_preflight_payload = env_preflight.json()
        expect(bool(env_preflight_payload.get("ok")), f"environment preflight not ready: {env_preflight_payload}")

        long_probe = summarize_probe(LONG_SAMPLE)
        short_probe = summarize_probe(SHORT_SAMPLE)
        log(f"long sample -> {long_probe['duration_label']} / {long_probe['codec']} / {long_probe['sample_rate']}Hz / {long_probe['channels']}ch")
        log(f"short sample -> {short_probe['duration_label']} / {short_probe['codec']} / {short_probe['sample_rate']}Hz / {short_probe['channels']}ch")

        long_preflight = preflight_single(long_probe["duration_seconds"], LONG_SAMPLE.name, int(long_probe["file_size"]))
        short_preflight = preflight_single(short_probe["duration_seconds"], SHORT_SAMPLE.name, int(short_probe["file_size"]))

        expect(long_preflight.get("single_long_eligible") is True, f"long sample not eligible: {long_preflight}")
        expect(long_preflight.get("recommended_route") == "single_long_preprocess", f"long sample wrong route: {long_preflight}")
        expect(short_preflight.get("single_long_eligible") is False, f"short sample wrongly eligible: {short_preflight}")
        expect(short_preflight.get("recommended_route") == "multi_clean_direct", f"short sample wrong route: {short_preflight}")
        expect(short_preflight.get("submission_allowed") is False, f"short sample should be rejected: {short_preflight}")

        long_voice = f"stage26_real_long_{int(time.time())}"
        long_resp = submit_train(LONG_SAMPLE, long_voice)
        expect(long_resp.status_code == 200, f"long sample submit failed: {long_resp.status_code} {long_resp.text}")
        long_submission = long_resp.json()
        expect(long_submission.get("recommended_route") == "single_long_preprocess", f"long submission route mismatch: {long_submission}")
        expect(long_submission.get("single_long_eligible") is True, f"long submission eligibility mismatch: {long_submission}")
        log(f"long submit ok -> {long_submission.get('task_id')} / {long_submission.get('status')}")

        long_runtime = poll_job(long_submission["task_id"])
        observed_stages = set(long_runtime.get("observed_stages") or [])
        reached_real_train = bool(
            observed_stages.intersection(
                {
                    "train_dataset_prepare",
                    "train_preprocess",
                    "train_pitch_extract",
                    "train_feature_extract",
                    "train_core",
                    "train_index",
                    "train_register_model",
                }
            )
        )
        expect(reached_real_train, f"long sample did not reach real train stages: {long_runtime}")
        if long_runtime.get("job", {}).get("status") == "完成":
            long_artifacts = fetch_train_artifacts(long_submission["task_id"])

        short_voice = f"stage26_real_short_{int(time.time())}"
        short_resp = submit_train(SHORT_SAMPLE, short_voice)
        expect(short_resp.status_code == 422, f"short sample should be rejected: {short_resp.status_code} {short_resp.text}")
        short_submit_payload = short_resp.json().get("detail", {})
        expect(short_submit_payload.get("material_profile") == "single_short_out_of_window", f"short rejection payload mismatch: {short_submit_payload}")

        final_status = long_runtime.get("job", {}).get("status")
        final_stage = long_runtime.get("job", {}).get("current_stage")
        log(f"long runtime result -> status={final_status} stage={final_stage} timeout={long_runtime.get('timed_out')}")
        print("STAGE26_VERIFY PASS")
        return 0
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        if long_probe:
            print(f"LONG_SAMPLE_PROBE {long_probe}")
        if short_probe:
            print(f"SHORT_SAMPLE_PROBE {short_probe}")
        if long_preflight:
            print(f"LONG_SAMPLE_PREFLIGHT {long_preflight}")
        if short_preflight:
            print(f"SHORT_SAMPLE_PREFLIGHT {short_preflight}")
        if long_submission:
            print(f"LONG_SAMPLE_SUBMISSION {long_submission}")
        if long_runtime:
            print(
                "LONG_SAMPLE_RUNTIME "
                + str(
                    {
                        "timed_out": long_runtime.get("timed_out"),
                        "job": long_runtime.get("job"),
                        "observed_stages": long_runtime.get("observed_stages"),
                    }
                )
            )
        if short_submit_payload:
            print(f"SHORT_SAMPLE_SUBMIT_REJECTION {short_submit_payload}")
        if long_artifacts:
            print(f"LONG_SAMPLE_ARTIFACTS {long_artifacts}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Stage26Error as exc:
        print(f"[STAGE26][FAIL] {exc}")
        raise SystemExit(1)
