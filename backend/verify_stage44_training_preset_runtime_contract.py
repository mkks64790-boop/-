from __future__ import annotations

import sys
import uuid

from fastapi.testclient import TestClient

try:
    from .db import init_db
    from .main import app
    from .model_trainer import build_training_command_preview
    from .services.job_service import create_train_job
    from .services.training_tuning_service import normalize_training_config
except ImportError:
    from db import init_db
    from main import app
    from model_trainer import build_training_command_preview
    from services.job_service import create_train_job
    from services.training_tuning_service import normalize_training_config


def _fail(message: str) -> int:
    print(f"[STAGE44A][FAIL] {message}")
    return 1


def main() -> int:
    if "--execute-smoke" in sys.argv:
        return _fail("--execute-smoke is intentionally not implemented in Stage44A; default contract must not start train.py")

    init_db()
    client = TestClient(app)

    presets_resp = client.get("/api/training/presets")
    if presets_resp.status_code != 200:
        return _fail(f"training presets unavailable: status={presets_resp.status_code}")
    preset_keys = {item.get("preset_key") for item in presets_resp.json().get("items", [])}
    if not {"fast_preview", "balanced", "quality"}.issubset(preset_keys):
        return _fail(f"missing presets: {preset_keys}")

    config = normalize_training_config(
        {"preset_key": "fast_preview", "epochs": 12, "batch_size": 3, "index_enabled": False}
    )
    job_id = f"stage44_contract_{uuid.uuid4().hex[:8]}"
    create_train_job(
        job_id,
        "stage44_single_smoke_contract",
        "shared_data/datasets/stage44_contract",
        f"shared_data/jobs/{job_id}",
        "single_long_preprocess",
        metadata={
            "smoke": True,
            "test_scope": "verify",
            "training_config": config,
        },
    )

    detail_resp = client.get(f"/api/jobs/{job_id}")
    if detail_resp.status_code != 200:
        return _fail(f"job detail unavailable: status={detail_resp.status_code}")
    detail = detail_resp.json()
    saved_config = detail.get("training_config") or {}
    if saved_config.get("preset_key") != "fast_preview":
        return _fail(f"training_config not persisted: {saved_config}")
    if not detail.get("training_config_summary"):
        return _fail("training_config_summary missing")

    preview = build_training_command_preview("stage44_contract_preview", saved_config)
    expected = {
        "epochs": 12,
        "batch_size": 3,
        "sample_rate": "40k",
        "f0_enabled": True,
        "index_enabled": False,
    }
    mismatches = {key: preview.get(key) for key, value in expected.items() if preview.get(key) != value}
    if mismatches:
        return _fail(f"command preview mismatch: {mismatches}")
    if preview.get("starts_train_py"):
        return _fail("dry-run preview unexpectedly starts train.py")

    cmd = preview.get("cmd") or []
    if cmd[cmd.index("-te") + 1] != "12" or cmd[cmd.index("-bs") + 1] != "3":
        return _fail(f"train command does not include expected epochs/batch: {cmd}")
    if cmd[cmd.index("-sr") + 1] != "40k" or cmd[cmd.index("-f0") + 1] != "1":
        return _fail(f"train command does not include expected sample_rate/f0: {cmd}")

    print(
        "[STAGE44A][PASS] training preset runtime contract dry-run ok "
        f"job_id={job_id} preset={saved_config.get('preset_key')} starts_train_py=False"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
