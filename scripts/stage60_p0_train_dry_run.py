"""Stage60 P0: training dry-run with workspace external/ engines (human-approved P0)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Fast smoke training profile
os.environ.setdefault("FEISHARK_RVC_TRAIN_EPOCHS", "1")
os.environ.setdefault("FEISHARK_RVC_TRAIN_BATCH_SIZE", "2")
os.environ.setdefault("FEISHARK_RVC_SAVE_EVERY_EPOCH", "1")
os.environ.setdefault("FEISHARK_RVC_TRAIN_TIMEOUT", "3600")
os.environ.setdefault("FEISHARK_RVC_INDEX_TIMEOUT", "1800")
os.environ.setdefault("FEISHARK_RVC_PREPROCESS_THREADS", "2")
os.environ.setdefault("FEISHARK_RVC_TRAIN_FP16", "false")
os.environ.setdefault("FEISHARK_RVC_DIR", str(PROJECT_ROOT / "external" / "rvc-webui"))
os.environ.setdefault("FEISHARK_RVC_BACKUP_DIR", str(PROJECT_ROOT / "external" / "rvc-webui-backup"))
os.environ.setdefault("FEISHARK_AUDIO_PIPELINE", str(PROJECT_ROOT / "external" / "audio-pipeline"))
os.environ.setdefault("FEISHARK_RVC_PYTHON", r"D:\Miniconda3\envs\rvc\python.exe")
os.environ.setdefault("FEISHARK_RVC_GPUS", "0")

from fastapi.testclient import TestClient  # noqa: E402

from backend.db import init_db  # noqa: E402
from backend.main import app  # noqa: E402


UPLOADS = PROJECT_ROOT / "shared_data" / "uploads"
REPORT = PROJECT_ROOT / "docs" / "agent-md" / "worker" / "stage-60-p0-train-dry-run-report.md"


def log(msg: str) -> None:
    print(f"[P0-TRAIN] {msg}", flush=True)


def main() -> int:
    init_db()
    files = [UPLOADS / "train_e5790874eb1e.wav", UPLOADS / "train_def71bf124f9.wav"]
    for f in files:
        if not f.exists():
            log(f"FAIL missing source: {f}")
            return 1

    with TestClient(app) as client:
        pf = client.get("/api/preflight/train", params={"file_count": len(files)}).json()
        log(f"preflight ok={pf.get('ok')} route={pf.get('recommended_route')} errors={pf.get('errors')}")
        if not pf.get("ok"):
            return 1

        voice_name = f"stage60_p0_dry_{int(time.time())}"
        handles = []
        try:
            payload = []
            for path in files:
                h = path.open("rb")
                handles.append(h)
                payload.append(("files", (path.name, h, "audio/wav")))
            training_config = json.dumps(
                {
                    "preset_key": "fast_preview",
                    "epochs": 1,
                    "batch_size": 2,
                }
            )
            resp = client.post(
                "/api/train",
                data={
                    "voice_name": voice_name,
                    "smoke": "true",
                    "training_config": training_config,
                },
                files=payload,
                timeout=3600,
            )
        finally:
            for h in handles:
                h.close()

        if resp.status_code != 200:
            log(f"FAIL create train {resp.status_code}: {resp.text[:500]}")
            return 1

        job_id = resp.json().get("task_id") or resp.json().get("job_id")
        log(f"job created: {job_id}")

        deadline = time.time() + 3600
        last = None
        while time.time() < deadline:
            last = client.get(f"/api/jobs/{job_id}").json()
            status = str(last.get("status") or "")
            stage = str(last.get("current_stage") or "")
            log(f"poll status={status} stage={stage}")
            if status not in {"pending", "processing"} and not status.endswith("中"):
                break
            time.sleep(5)

        ok = last and last.get("status") == "完成" and last.get("current_stage") == "train_register_model"
        artifacts = client.get(f"/api/jobs/{job_id}/artifacts").json().get("artifacts", [])
        has_pth = any(a.get("artifact_type") == "train_model_pth" for a in artifacts)
        has_index = any(a.get("artifact_type") == "train_model_index" for a in artifacts)

        lines = [
            "# Stage60 P0 Train Dry-Run Report",
            "",
            f"- **job_id**: `{job_id}`",
            f"- **voice_name**: `{voice_name}`",
            f"- **preflight ok**: {pf.get('ok')}",
            f"- **final status**: {last.get('status') if last else 'n/a'}",
            f"- **final stage**: {last.get('current_stage') if last else 'n/a'}",
            f"- **artifacts pth/index**: {has_pth} / {has_index}",
            f"- **PASS**: {ok and has_pth and has_index}",
            "",
        ]
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        log(f"report -> {REPORT}")
        return 0 if ok and has_pth and has_index else 1


if __name__ == "__main__":
    raise SystemExit(main())