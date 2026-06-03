from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import db as backend_db  # noqa: E402
from backend.services.asset_service import list_job_artifacts  # noqa: E402
from backend.services.model_service import get_voice_model_detail  # noqa: E402
from backend.services.preflight_service import run_cover_preflight  # noqa: E402
from backend.services.training_recovery_service import (  # noqa: E402
    TrainingRecoveryError,
    get_training_recovery_plan,
    register_training_recovery,
)


JOB_ID = "train_010253ec08f0"
EXP_NAME = "feishark_v_62f76886"
MODEL_NAME = "朱朱_recovered_e90"


class VerifyError(RuntimeError):
    pass


def step(message: str) -> None:
    print(f"[STAGE40A] {message}")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyError(message)


def find_train_py_processes() -> list[dict]:
    command = r"""
$needle = 'infer\\modules\\train\\' + 'train.py'
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -and $_.CommandLine -like "*$needle*" } |
  Select-Object ProcessId, CommandLine |
  ConvertTo-Json -Compress
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception as exc:
        raise VerifyError(f"unable to inspect train.py processes: {exc}") from exc
    if proc.returncode != 0:
        raise VerifyError(f"train.py process inspection failed: {proc.stderr.strip()}")
    payload = (proc.stdout or "").strip()
    if not payload:
        return []
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise VerifyError(f"invalid process inspection json: {payload[:300]}") from exc
    if isinstance(parsed, dict):
        return [parsed]
    return parsed if isinstance(parsed, list) else []


def existing_recovered_model() -> dict | None:
    conn = backend_db.get_connection()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM voice_models
            WHERE source_job_id = ?
            ORDER BY datetime(updated_at) DESC, rowid DESC
            """,
            (JOB_ID,),
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        item = dict(row)
        try:
            metadata = json.loads(item.get("metadata_json") or "{}")
        except Exception:
            metadata = {}
        if metadata.get("recovered_from_checkpoint") and metadata.get("recovered_exp_name") == EXP_NAME:
            return item
    return None


def assert_recovered_model_contract(model_id: str, model_name: str) -> None:
    detail = get_voice_model_detail(model_id, backend_db.PROJECT_ROOT, backend_db.WEIGHTS_DIR)
    expect(detail is not None, f"recovered model missing from voice_models: {model_id}")
    expect(bool(detail.get("usable")), f"recovered model is not usable: {detail}")
    pth_path = detail.get("resolved_pth_path") or ""
    index_path = detail.get("resolved_index_path") or ""
    expect(os.path.exists(pth_path), f"pth file missing: {pth_path}")
    expect(os.path.exists(index_path), f"index file missing: {index_path}")
    expect(os.path.getsize(pth_path) > 0, f"pth file empty: {pth_path}")
    expect(os.path.getsize(index_path) > 12, f"index file too small: {index_path}")

    artifacts = list_job_artifacts(JOB_ID)
    final_types = {item.get("artifact_type") for item in artifacts if item.get("is_final")}
    expect("train_model_pth" in final_types, "missing final train_model_pth artifact")
    expect("train_model_index" in final_types, "missing final train_model_index artifact")

    preflight = run_cover_preflight(model_id)
    expect(bool(preflight.get("ok")), f"cover preflight failed for recovered model: {preflight.get('errors')}")
    step(f"model usable: {model_id} / {model_name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="perform real checkpoint recovery")
    args = parser.parse_args()

    backend_db.init_db()

    plan = get_training_recovery_plan(JOB_ID)
    expect(plan.get("can_recover") is True, f"job cannot recover: {plan}")
    expect(plan.get("recommended_exp_name") == EXP_NAME, f"unexpected recommended exp: {plan.get('recommended_exp_name')}")
    top = plan["candidates"][0]
    expect(top.get("highest_epoch") == 90, f"unexpected highest epoch: {top}")
    step(f"candidate ok: {EXP_NAME} e{top.get('highest_epoch')} feature_count={top.get('feature_count')}")

    dry_run = register_training_recovery(
        JOB_ID,
        exp_name=EXP_NAME,
        model_name=MODEL_NAME,
        build_index_if_missing=True,
        dry_run=True,
    )
    expect(dry_run.get("success") is True and dry_run.get("dry_run") is True, f"dry_run failed: {dry_run}")
    step(f"dry_run ok: would_build_index={dry_run.get('would_build_index')}")

    train_py_processes = find_train_py_processes()
    expect(not train_py_processes, f"train.py process is running: {train_py_processes}")
    step("train.py process guard ok")

    if not args.execute:
        existing = existing_recovered_model()
        if existing:
            assert_recovered_model_contract(existing["legacy_model_id"] or existing["voice_model_id"], existing["model_name"])
        step("stage40 dry-run verification PASS")
        return 0

    existing = existing_recovered_model()
    if existing:
        step("existing recovered model found; validating instead of creating a duplicate")
        assert_recovered_model_contract(existing["legacy_model_id"] or existing["voice_model_id"], existing["model_name"])
        step("stage40 execute verification PASS")
        return 0

    try:
        result = register_training_recovery(
            JOB_ID,
            exp_name=EXP_NAME,
            model_name=MODEL_NAME,
            build_index_if_missing=True,
            dry_run=False,
        )
    except TrainingRecoveryError as exc:
        raise VerifyError(f"recovery register failed: {exc.to_detail()}") from exc
    expect(result.get("success") is True, f"recovery result not successful: {result}")
    assert_recovered_model_contract(result["model_id"], result["model_name"])
    step("stage40 execute verification PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerifyError as exc:
        print(f"[STAGE40A][FAIL] {exc}")
        raise SystemExit(1)
