import sqlite3
import sys
import uuid
from collections import Counter
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.db import DB_PATH, init_db, update_task_status  # noqa: E402
from backend.main import PIPELINE_START_STATUS, app  # noqa: E402
from backend.services.job_service import create_cover_job, release_job, reserve_job  # noqa: E402
from backend.services.model_service import resolve_voice_model_file  # noqa: E402
from backend.services.smoke_filter import is_smoke_job_record, is_smoke_model_record  # noqa: E402


def _print_result(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" :: {detail}" if detail else ""))
    return ok


def _api_json(client: TestClient, path: str):
    resp = client.get(path)
    return resp.status_code, resp.json() if resp.status_code == 200 else None


def _cleanup_synthetic_control_jobs() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT job_id, status
            FROM jobs
            WHERE job_id LIKE 'smoke_busy_%'
               OR job_id LIKE 'stage13_busy_%'
               OR job_id LIKE 'stage13_retry_%'
               OR job_id LIKE 'stage13_cancel_%'
               OR job_id LIKE 'stage13_queue_%'
            """
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        if row["status"] in {"pending", "processing", "分离中", "修音中", "变声中", "混音中", "切片中", "训练中"}:
            update_task_status(row["job_id"], "失败", "self_check synthetic cleanup")


def check_duplicate_routes() -> bool:
    seen = Counter()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = tuple(sorted(m for m in route.methods if m not in {"HEAD", "OPTIONS"}))
        if not methods:
            continue
        seen[(route.path, methods)] += 1
    dupes = [f"{path} {methods}" for (path, methods), count in seen.items() if count > 1]
    return _print_result("duplicate routes", len(dupes) == 0, ", ".join(dupes))


def check_frontend_model_selection_preservation() -> bool:
    source = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "models.js").read_text(encoding="utf-8")
    required_markers = [
        "const previousValue = state.selectedCoverModelId || select.value;",
        "usableModels.some(model => model.model_id === previousValue)",
        "state.selectedCoverModelId = nextValue",
    ]
    missing = [marker for marker in required_markers if marker not in source]
    return _print_result("frontend model selection preservation", len(missing) == 0, ", ".join(missing))


def check_frontend_refresh_guard() -> bool:
    source = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "main.js").read_text(encoding="utf-8")
    required_markers = [
        "let refreshInFlight = null;",
        "let queuedFocusJobId = null;",
        "function shouldPauseAutoRefresh()",
    ]
    missing = [marker for marker in required_markers if marker not in source]
    return _print_result("frontend auto refresh guard", len(missing) == 0, ", ".join(missing))


def check_frontend_artifact_download_binding() -> bool:
    source = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "jobs.js").read_text(encoding="utf-8")
    required_markers = [
        'data-artifact-download="true"',
        "artifactDownloadLabel(item)",
        "window.open(artifactUrl.startsWith(\"http\") ? artifactUrl : `${window.location.origin}${artifactUrl}`",
    ]
    missing = [marker for marker in required_markers if marker not in source]
    return _print_result("frontend artifact download binding", len(missing) == 0, ", ".join(missing))


def check_health_engine_summary(client: TestClient) -> bool:
    status, data = _api_json(client, "/api/health")
    if status != 200 or not isinstance(data, dict):
        return _print_result("health engine summary", False, f"status={status}")

    engine = data.get("engine") or data.get("rvc") or {}
    required = {
        "engine_kind",
        "base_url",
        "online",
        "rvc_root",
        "cover_inference_mode",
        "train_backend_mode",
    }
    keys = set(engine.keys()) if isinstance(engine, dict) else set()
    ok = isinstance(engine, dict) and required.issubset(keys)
    return _print_result("health engine summary", ok, ",".join(sorted(required - keys)))


def check_launcher_guard() -> bool:
    launcher_path = Path(__file__).resolve().parents[1] / "feishark-launcher.ps1"
    if not launcher_path.exists():
        return _print_result("launcher guard", False, "missing launcher")

    source = launcher_path.read_text(encoding="utf-8")
    required_markers = [
        "--noautoopen",
        '$apiPort = 8000',
        'Start-Process "http://127.0.0.1:$apiPort/"',
    ]
    missing = [marker for marker in required_markers if marker not in source]
    wrong_target = 'Start-Process $rvcUrl' in source or 'http://127.0.0.1:7866/' in source
    ok = not missing and not wrong_target
    detail_parts = []
    if missing:
        detail_parts.append("missing=" + ",".join(missing))
    if wrong_target:
        detail_parts.append("browser_target_points_to_rvc")
    return _print_result("launcher guard", ok, "; ".join(detail_parts))


def _pick_any_job(conn) -> str | None:
    row = conn.execute(
        """
        SELECT job_id
        FROM jobs
        WHERE status IN ('完成', '失败')
        ORDER BY datetime(created_at) DESC, rowid DESC
        LIMIT 1
        """
    ).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        "SELECT job_id FROM jobs ORDER BY datetime(created_at) DESC, rowid DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def _pick_cover_job_with_final_artifact(conn) -> str | None:
    row = conn.execute(
        """
        SELECT ja.job_id
        FROM job_artifacts ja
        JOIN jobs j ON j.job_id = ja.job_id
        WHERE ja.is_final = 1
          AND ja.artifact_type = 'cover_master'
          AND j.job_type = 'cover'
        ORDER BY datetime(ja.created_at) DESC, ja.rowid DESC
        LIMIT 1
        """
    ).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        """
        SELECT job_id
        FROM jobs
        WHERE job_type = 'cover'
        ORDER BY datetime(created_at) DESC, rowid DESC
        LIMIT 1
        """
    ).fetchone()
    return row[0] if row else None


def _pick_train_job_with_model_artifacts(conn) -> str | None:
    row = conn.execute(
        """
        SELECT ja.job_id
        FROM job_artifacts ja
        JOIN jobs j ON j.job_id = ja.job_id
        WHERE j.job_type = 'train'
          AND ja.is_final = 1
          AND ja.artifact_type IN ('train_model_pth', 'train_model_index')
          AND ja.file_size > 1024
        GROUP BY ja.job_id
        HAVING COUNT(DISTINCT ja.artifact_type) = 2
        ORDER BY MAX(datetime(ja.created_at)) DESC, MAX(ja.rowid) DESC
        LIMIT 1
        """
    ).fetchone()
    return row[0] if row else None


def check_models_structure(client: TestClient) -> bool:
    status, data = _api_json(client, "/api/models?include_unavailable=true")
    if status != 200 or not isinstance(data, list):
        return _print_result("models list structure", False, f"status={status}")
    if not data:
        return _print_result("models list structure", True, "empty list")
    sample = data[0]
    required = {"exists", "model_id", "model_name", "default_pitch", "usable", "resolved_pth_path", "resolved_source"}
    return _print_result("models list structure", required.issubset(sample.keys()), str(sample))


def check_default_models_hide_smoke(client: TestClient) -> bool:
    status, data = _api_json(client, "/api/models?include_unavailable=true")
    if status != 200 or not isinstance(data, list):
        return _print_result("default models hide smoke", False, f"status={status}")
    leaked = [item["model_id"] for item in data if is_smoke_model_record(item)]
    return _print_result("default models hide smoke", len(leaked) == 0, ",".join(leaked[:5]))


def check_model_detail_consistency(client: TestClient) -> bool:
    status, data = _api_json(client, "/api/models?include_unavailable=true")
    if status != 200 or not data:
        return _print_result("model detail consistency", False, "no models")
    sample = data[0]
    detail_status, detail = _api_json(client, f"/api/models/{sample['model_id']}")
    if detail_status != 200:
        return _print_result("model detail consistency", False, f"detail_status={detail_status}")
    resolver = resolve_voice_model_file(
        sample["model_id"],
        str(Path(__file__).resolve().parents[1]),
        str(Path(__file__).resolve().parents[1] / "shared_data" / "weights"),
    )
    ok = (
        detail.get("usable") == bool(resolver["ok"])
        and detail.get("resolved_pth_path") == resolver["resolved_path"]
        and detail.get("resolved_source") == resolver["source"]
    )
    return _print_result("model detail consistency", ok, f"{sample['model_id']} -> {detail.get('usable')} / {resolver['ok']}")


def check_current_stage_consistency(client: TestClient) -> bool:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        job_id = _pick_any_job(conn)
    finally:
        conn.close()
    if not job_id:
        return _print_result("current_stage consistency", False, "no job found")

    job_status, job_data = _api_json(client, f"/api/jobs/{job_id}")
    task_status, task_data = _api_json(client, f"/api/task_status/{job_id}")
    logs_status, logs_data = _api_json(client, f"/api/jobs/{job_id}/stage-logs")
    if job_status != 200 or task_status != 200 or logs_status != 200:
        return _print_result("current_stage consistency", False, f"job={job_status}, task={task_status}, logs={logs_status}")
    business_logs = [log for log in logs_data["stage_logs"] if log["stage_name"] not in {"job_dispatch", "job_control"}]
    expected_stage = job_data["current_stage"]
    if job_data["status"] in {"完成", "失败"} and business_logs:
        expected_stage = business_logs[-1]["stage_name"]
    ok = job_data["current_stage"] == task_data["current_stage"] == expected_stage
    return _print_result("current_stage consistency", ok, f"{job_id}: job={job_data['current_stage']} task={task_data['current_stage']} logs={expected_stage}")


def check_cover_artifact_uniqueness(conn, job_id: str) -> bool:
    rows = conn.execute(
        """
        SELECT stage_name, artifact_type, file_path, COUNT(*) AS c
        FROM job_artifacts
        WHERE job_id = ?
        GROUP BY stage_name, artifact_type, file_path
        HAVING COUNT(*) > 1
        """,
        (job_id,),
    ).fetchall()
    return _print_result("cover artifact uniqueness", len(rows) == 0, f"job_id={job_id}, dupes={len(rows)}")


def check_final_artifact_priority(conn, job_id: str) -> bool:
    rows = conn.execute(
        """
        SELECT artifact_type, COUNT(*) AS c
        FROM job_artifacts
        WHERE job_id = ? AND is_final = 1
        GROUP BY artifact_type
        """,
        (job_id,),
    ).fetchall()
    primary_count = sum(row[1] for row in rows if row[0] in {"cover_master", "train_model_pth"})
    return _print_result("final artifact priority", primary_count <= 1, f"job_id={job_id}, primary_final_count={primary_count}")


def check_download_resolution(client: TestClient, job_id: str) -> bool:
    resp = client.get(f"/api/download/{job_id}")
    ok = resp.status_code == 200
    return _print_result("download final artifact", ok, f"status={resp.status_code}, content-type={resp.headers.get('content-type')}")


def check_artifact_download_resolution(client: TestClient, job_id: str) -> bool:
    status, data = _api_json(client, f"/api/jobs/{job_id}/artifacts")
    if status != 200:
        return _print_result("download artifact item", False, f"status={status}")
    final_items = [item for item in data.get("artifacts", []) if item.get("is_final") and item.get("artifact_id")]
    if not final_items:
        return _print_result("download artifact item", False, "no final artifact")
    item = final_items[0]
    resp = client.get(f"/api/jobs/{job_id}/artifacts/{item['artifact_id']}/download")
    ok = resp.status_code == 200
    return _print_result("download artifact item", ok, f"status={resp.status_code}, artifact={item['artifact_type']}")


def check_retry_requeue_cancel_flow(client: TestClient) -> bool:
    busy_job_id = f"smoke_busy_{uuid.uuid4().hex[:8]}"
    busy_job = create_cover_job(
        busy_job_id,
        input_path=f"shared_data/jobs/{busy_job_id}/input/busy.wav",
        output_root=f"shared_data/jobs/{busy_job_id}",
        metadata={"smoke": True, "test_scope": "self_check"},
    )
    busy_reserved = reserve_job(busy_job, PIPELINE_START_STATUS)

    job_id = f"smoke_retry_{uuid.uuid4().hex[:8]}"
    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/dummy.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"smoke": True, "test_scope": "self_check"},
    )
    try:
        update_task_status(job_id, "失败", "self check synthetic failure")

        retry_resp = client.post(f"/api/jobs/{job_id}/retry")
        if retry_resp.status_code != 200:
            return _print_result("retry/requeue/cancel flow", False, f"retry_status={retry_resp.status_code}, body={retry_resp.text}")
        retry_data = retry_resp.json()
        if retry_data.get("status") != "pending" or retry_data.get("current_stage") != "pending" or retry_data.get("error_log") != "":
            return _print_result("retry/requeue/cancel flow", False, f"retry_payload={retry_data}")

        requeue_resp = client.post(f"/api/jobs/{job_id}/requeue")
        if requeue_resp.status_code != 200:
            return _print_result("retry/requeue/cancel flow", False, f"requeue_status={requeue_resp.status_code}, body={requeue_resp.text}")
        requeue_data = requeue_resp.json()
        if requeue_data.get("status") != "pending" or requeue_data.get("current_stage") != "pending" or requeue_data.get("error_log") != "":
            return _print_result("retry/requeue/cancel flow", False, f"requeue_payload={requeue_data}")

        cancel_resp = client.post(f"/api/jobs/{job_id}/cancel")
        if cancel_resp.status_code != 200:
            return _print_result("retry/requeue/cancel flow", False, f"cancel_status={cancel_resp.status_code}, body={cancel_resp.text}")
        cancel_data = cancel_resp.json()
        if cancel_data.get("status") != "已取消" or cancel_data.get("current_stage") != "cancelled":
            return _print_result("retry/requeue/cancel flow", False, f"cancel_payload={cancel_data}")

        job_detail = client.get(f"/api/jobs/{job_id}").json()
        task_status = client.get(f"/api/task_status/{job_id}").json()
        stage_logs = client.get(f"/api/jobs/{job_id}/stage-logs").json()["stage_logs"]
        last_log = stage_logs[-1] if stage_logs else {}
        ok = (
            job_detail.get("status") == "已取消"
            and task_status.get("status") == "已取消"
            and job_detail.get("current_stage") == "cancelled"
            and task_status.get("current_stage") == "cancelled"
            and last_log.get("stage_name") == "job_control"
        )
        detail = (
            f"retry={retry_data.get('status')}/{retry_data.get('queue_state')} "
            f"requeue={requeue_data.get('status')}/{requeue_data.get('queue_state')} "
            f"cancel={cancel_data.get('status')} "
            f"job={job_detail.get('status')}/{job_detail.get('current_stage')} "
            f"task={task_status.get('status')}/{task_status.get('current_stage')}"
        )
        return _print_result("retry/requeue/cancel flow", ok, detail)
    finally:
        if busy_reserved:
            release_job(busy_job_id)
        update_task_status(busy_job_id, "失败", "self_check synthetic busy cleanup")


def check_real_train_index_artifact(conn, job_id: str) -> bool:
    row = conn.execute(
        """
        SELECT file_path, file_size
        FROM job_artifacts
        WHERE job_id = ?
          AND artifact_type = 'train_model_index'
          AND is_final = 1
        ORDER BY datetime(created_at) DESC, rowid DESC
        LIMIT 1
        """,
        (job_id,),
    ).fetchone()
    if not row:
        return _print_result("real train index artifact", False, f"job_id={job_id}, missing")
    file_path = Path(row[0])
    file_size = row[1] or 0
    ok = file_path.exists() and file_size > 12 and file_path.stat().st_size > 12
    return _print_result("real train index artifact", ok, f"job_id={job_id}, size={file_size}, path={file_path}")


def check_train_preflight_structure(client: TestClient) -> bool:
    resp = client.get("/api/preflight/train?file_count=1")
    if resp.status_code != 200:
        return _print_result("train preflight structure", False, f"status={resp.status_code}")
    data = resp.json()
    required = {"ok", "job_type", "strategy_key", "checks", "errors"}
    new_fields = {"recommended_route", "material_profile", "submission_allowed"}
    ok = bool(data.get("ok")) and not data.get("errors") and required.issubset(data.keys()) and new_fields.issubset(data.keys())
    return _print_result("train preflight structure", ok, str(data.get("errors", [])[:1]))


def check_train_environment_ready(client: TestClient) -> bool:
    resp = client.get("/api/preflight/train?file_count=1")
    if resp.status_code != 200:
        return _print_result("train environment ready", False, f"status={resp.status_code}")
    data = resp.json()
    return _print_result("train environment ready", bool(data.get("ok")), str(data.get("errors", [])))


def check_train_material_routing(client: TestClient) -> bool:
    long_resp = client.get("/api/preflight/train?file_count=1&duration_seconds=2709.9951")
    short_resp = client.get("/api/preflight/train?file_count=1&duration_seconds=932.702025")
    if long_resp.status_code != 200 or short_resp.status_code != 200:
        return _print_result("train material routing", False, f"long={long_resp.status_code}, short={short_resp.status_code}")

    long_data = long_resp.json()
    short_data = short_resp.json()
    ok = (
        long_data.get("single_long_eligible") is True
        and long_data.get("recommended_route") == "single_long_preprocess"
        and bool(long_data.get("submission_allowed"))
        and short_data.get("single_long_eligible") is False
        and short_data.get("recommended_route") == "multi_clean_direct"
        and short_data.get("submission_allowed") is False
    )
    detail = (
        f"long={long_data.get('material_profile')}/{long_data.get('recommended_route')} "
        f"short={short_data.get('material_profile')}/{short_data.get('recommended_route')}"
    )
    return _print_result("train material routing", ok, detail)


def check_cover_preflight_missing_model(client: TestClient) -> bool:
    resp = client.get("/api/preflight/cover?model_id=__missing__")
    if resp.status_code != 200:
        return _print_result("cover preflight missing model", False, f"status={resp.status_code}")
    data = resp.json()
    missing = [err for err in data.get("errors", []) if err.get("check") == "voice_model_row"]
    ok = (data.get("ok") is False) and bool(missing)
    return _print_result("cover preflight missing model", ok, str(missing[:1]))


def check_cover_preflight_usable_model(client: TestClient) -> bool:
    resp = client.get("/api/models?include_unavailable=true")
    if resp.status_code != 200:
        return _print_result("cover preflight usable model", False, f"models={resp.status_code}")
    models = resp.json()
    usable = [item for item in models if item.get("usable")]
    if not usable:
        return _print_result("cover preflight usable model", False, "no usable model present")
    model_id = usable[0]["model_id"]
    pre = client.get(f"/api/preflight/cover?model_id={model_id}")
    ok = pre.status_code == 200 and bool(pre.json().get("ok"))
    return _print_result("cover preflight usable model", ok, f"model_id={model_id}, preflight_ok={pre.json().get('ok') if pre.status_code == 200 else 'n/a'}")


def check_jobs_api_shapes(client: TestClient) -> bool:
    status, data = _api_json(client, "/api/jobs?limit=5&offset=0")
    if status != 200 or not isinstance(data, dict) or "items" not in data:
        return _print_result("jobs api shape", False, f"status={status}")
    return _print_result("jobs api shape", isinstance(data["items"], list), f"count={len(data['items'])}")


def check_default_jobs_hide_smoke(client: TestClient) -> bool:
    status, data = _api_json(client, "/api/jobs?limit=20&offset=0")
    if status != 200 or not isinstance(data, dict):
        return _print_result("default jobs hide smoke", False, f"status={status}")
    leaked = [item["job_id"] for item in data.get("items", []) if is_smoke_job_record(item)]
    return _print_result("default jobs hide smoke", len(leaked) == 0, ",".join(leaked[:5]))


def main():
    init_db()
    _cleanup_synthetic_control_jobs()
    client = TestClient(app)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cover_job_id = _pick_cover_job_with_final_artifact(conn)
        train_job_id = _pick_train_job_with_model_artifacts(conn)
    finally:
        conn.close()

    code_results = [
        check_duplicate_routes(),
        check_frontend_model_selection_preservation(),
        check_frontend_refresh_guard(),
        check_frontend_artifact_download_binding(),
        check_health_engine_summary(client),
        check_launcher_guard(),
        check_models_structure(client),
        check_default_models_hide_smoke(client),
        check_model_detail_consistency(client),
        check_current_stage_consistency(client),
        check_jobs_api_shapes(client),
        check_default_jobs_hide_smoke(client),
        check_train_preflight_structure(client),
        check_cover_preflight_missing_model(client),
    ]

    runtime_results = [
        check_train_environment_ready(client),
        check_train_material_routing(client),
        check_cover_preflight_usable_model(client),
    ]

    conn = sqlite3.connect(DB_PATH)
    try:
        if cover_job_id:
            code_results.append(check_cover_artifact_uniqueness(conn, cover_job_id))
            code_results.append(check_final_artifact_priority(conn, cover_job_id))
            code_results.append(check_download_resolution(client, cover_job_id))
            code_results.append(check_artifact_download_resolution(client, cover_job_id))
        else:
            code_results.append(_print_result("cover artifact uniqueness", False, "no cover job with final artifact found"))
            code_results.append(_print_result("final artifact priority", False, "no cover job with final artifact found"))
            code_results.append(_print_result("download final artifact", False, "no cover job with final artifact found"))
            code_results.append(_print_result("download artifact item", False, "no cover job with final artifact found"))
        code_results.append(check_retry_requeue_cancel_flow(client))
        if train_job_id:
            code_results.append(check_real_train_index_artifact(conn, train_job_id))
        else:
            code_results.append(_print_result("real train index artifact", False, "no train job with final artifacts found"))
    finally:
        conn.close()

    print("")
    print("CODE_STRUCTURE_SUMMARY", "PASS" if all(code_results) else "FAIL")
    print("RUNTIME_ENVIRONMENT_SUMMARY", "PASS" if all(runtime_results) else "FAIL")
    print("SELF_CHECK_SUMMARY", "PASS" if all(code_results) and all(runtime_results) else "FAIL")
    return 0 if all(code_results) and all(runtime_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
