import json
from dataclasses import dataclass, field

try:
    from ..db import (
        ACTIVE_COMPUTE_STATUSES,
        create_task,
        create_train_task,
        get_connection,
        mark_task_compute_ready,
        release_compute_slot,
        reserve_compute_slot,
        set_task_model_id,
        update_task_status,
    )
except ImportError:
    from db import (
        ACTIVE_COMPUTE_STATUSES,
        create_task,
        create_train_task,
        get_connection,
        mark_task_compute_ready,
        release_compute_slot,
        reserve_compute_slot,
        set_task_model_id,
        update_task_status,
    )

try:
    from ..services.smoke_filter import explain_test_data_filter_reason, is_smoke_job_record, is_smoke_model_record
    from ..pipelines.runner import run_registered_pipeline
    from ..services.stage_log_service import list_stage_logs, log_stage
    from ..services.training_runtime_guard import (
        DUPLICATE_TRAIN_CORE_CODE,
        extract_exp_name_from_job,
        has_unclosed_stage,
        inspect_training_checkpoint,
        summarize_training_error,
    )
    from ..services.track_service import (
        mark_track_cover_job_complete,
        mark_track_cover_job_created,
        mark_track_cover_job_failed,
        mark_track_cover_job_pending,
        mark_track_cover_job_processing,
        reset_track_cover_job_state,
    )
except ImportError:
    from services.smoke_filter import explain_test_data_filter_reason, is_smoke_job_record, is_smoke_model_record
    from pipelines.runner import run_registered_pipeline
    from services.stage_log_service import list_stage_logs, log_stage
    from services.training_runtime_guard import (
        DUPLICATE_TRAIN_CORE_CODE,
        extract_exp_name_from_job,
        has_unclosed_stage,
        inspect_training_checkpoint,
        summarize_training_error,
    )
    from services.track_service import (
        mark_track_cover_job_complete,
        mark_track_cover_job_created,
        mark_track_cover_job_failed,
        mark_track_cover_job_pending,
        mark_track_cover_job_processing,
        reset_track_cover_job_state,
    )


@dataclass(kw_only=True)
class BaseJob:
    job_id: str
    job_type: str
    job_kind: str
    strategy_key: str
    status: str = "pending"
    current_stage: str = ""
    compute_ready: int = 0
    track_id: str = ""
    resource_class: str = "gpu_heavy"
    depends_on: list[str] = field(default_factory=list)
    voice_model_id: str = ""
    voice_name: str = ""
    input_path: str = ""
    output_root: str = ""
    legacy_task_id: str = ""
    error_log: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(kw_only=True)
class CoverJob(BaseJob):
    job_type: str = "cover"


@dataclass(kw_only=True)
class TrainJob(BaseJob):
    job_type: str = "train"


def create_cover_job(
    job_id: str,
    input_path: str,
    output_root: str,
    metadata: dict | None = None,
    *,
    track_id: str = "",
    voice_model_id: str = "",
    voice_name: str = "",
    resource_class: str = "gpu_heavy",
    depends_on: list[str] | None = None,
) -> CoverJob:
    create_task(job_id, input_path, task_type="upload")
    job = CoverJob(
        job_id=job_id,
        legacy_task_id=job_id,
        job_kind="cover",
        strategy_key="cover_strategy",
        track_id=track_id,
        resource_class=resource_class,
        depends_on=list(depends_on or []),
        voice_model_id=voice_model_id,
        voice_name=voice_name,
        input_path=input_path,
        output_root=output_root,
        metadata=metadata or {},
    )
    _insert_job(job)
    if job.track_id:
        mark_track_cover_job_created(
            job.track_id,
            job.job_id,
            model_id=job.voice_model_id,
            voice_name=job.voice_name,
            depends_on=job.depends_on,
            metadata=job.metadata,
        )
    return job


def create_train_job(
    job_id: str,
    voice_name: str,
    dataset_path: str,
    output_root: str,
    strategy_key: str,
    metadata: dict | None = None,
) -> TrainJob:
    create_train_task(job_id, voice_name, dataset_path)
    job = TrainJob(
        job_id=job_id,
        legacy_task_id=job_id,
        job_kind="train",
        strategy_key=strategy_key,
        voice_name=voice_name,
        input_path=dataset_path,
        output_root=output_root,
        compute_ready=1,
        metadata=metadata or {},
    )
    _insert_job(job)
    return job


def _insert_job(job: BaseJob) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO jobs (
                job_id, legacy_task_id, job_type, job_kind, strategy_key, status, current_stage,
                compute_ready, track_id, resource_class, depends_on_json, voice_model_id, voice_name, input_path, output_root,
                error_log, metadata_json, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                COALESCE((SELECT created_at FROM jobs WHERE job_id = ?), CURRENT_TIMESTAMP),
                CURRENT_TIMESTAMP
            )
            """,
            (
                job.job_id,
                job.legacy_task_id or job.job_id,
                job.job_type,
                job.job_kind or job.job_type,
                job.strategy_key,
                job.status,
                job.current_stage,
                job.compute_ready,
                job.track_id,
                job.resource_class,
                json.dumps(job.depends_on or [], ensure_ascii=False),
                job.voice_model_id,
                job.voice_name,
                job.input_path,
                job.output_root,
                job.error_log,
                json.dumps(job.metadata or {}, ensure_ascii=False),
                job.job_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_job(job_id: str) -> BaseJob | None:
    row = get_job_row(job_id)
    if not row:
        return None
    return _row_to_job(row)


def get_job_row(job_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ? OR legacy_task_id = ? LIMIT 1",
            (job_id, job_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def canonical_current_stage(job_row: dict | None, stage_logs: list[dict] | None = None) -> str:
    if not job_row:
        return ""

    status = job_row.get("status") or ""
    normalized_status = normalize_job_status(status)
    job_type = job_row.get("job_type") or ""
    metadata = _parse_metadata(job_row.get("metadata_json"))
    if job_type == "train" and normalized_status == "completed" and _has_generated_or_recovered_model(job_row, metadata):
        return "train_register_model"
    if normalized_status == "pending":
        return "pending"
    if normalized_status == "cancelled":
        return "cancelled"

    business_logs = [
        log for log in (stage_logs or [])
        if log.get("stage_name") not in {"job_dispatch", "job_control"}
    ]
    if business_logs:
        return business_logs[-1]["stage_name"]

    current_stage = (job_row.get("current_stage") or "").strip()
    if current_stage and current_stage not in {"pending", "job_dispatch", "job_control"}:
        return current_stage

    if normalized_status == "completed":
        return "cover_mix" if job_type == "cover" else "train_register_model"
    if normalized_status == "failed":
        return "failed"
    return status


def _parse_metadata(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _has_generated_or_recovered_model(job_row: dict, metadata: dict) -> bool:
    if metadata.get("recovered_from_checkpoint") or metadata.get("recovered_model_id"):
        return True
    job_id = job_row.get("job_id") or job_row.get("legacy_task_id") or ""
    if not job_id:
        return False
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT voice_model_id FROM voice_models WHERE source_job_id = ? LIMIT 1",
            (job_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _row_to_job(row: dict) -> BaseJob:
    metadata = {}
    if row.get("metadata_json"):
        try:
            metadata = json.loads(row["metadata_json"])
        except Exception:
            metadata = {}
    cls = TrainJob if row.get("job_type") == "train" else CoverJob
    return cls(
        job_id=row["job_id"],
        legacy_task_id=row.get("legacy_task_id") or row["job_id"],
        job_kind=row.get("job_kind") or row.get("job_type") or "cover",
        strategy_key=row.get("strategy_key") or "",
        status=row.get("status") or "pending",
        current_stage=row.get("current_stage") or "",
        compute_ready=row.get("compute_ready") or 0,
        track_id=row.get("track_id") or "",
        resource_class=row.get("resource_class") or "gpu_heavy",
        depends_on=json.loads(row.get("depends_on_json") or "[]") if row.get("depends_on_json") else [],
        voice_model_id=row.get("voice_model_id") or "",
        voice_name=row.get("voice_name") or "",
        input_path=row.get("input_path") or "",
        output_root=row.get("output_root") or "",
        error_log=row.get("error_log") or "",
        metadata=metadata,
    )


def activate_cover_job(job_id: str, voice_model_id: str, voice_name: str = "") -> BaseJob | None:
    set_task_model_id(job_id, voice_model_id)
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET job_type = 'cover', job_kind = 'cover', resource_class = 'gpu_heavy', strategy_key = 'cover_strategy',
                compute_ready = 1, voice_model_id = ?, voice_name = COALESCE(NULLIF(?, ''), voice_name), updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? OR legacy_task_id = ?
            """,
            (voice_model_id, voice_name, job_id, job_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_job(job_id)


def activate_train_job(job_id: str) -> BaseJob | None:
    mark_task_compute_ready(job_id, "train")
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET job_type = 'train', job_kind = 'train', resource_class = 'gpu_heavy', compute_ready = 1, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? OR legacy_task_id = ?
            """,
            (job_id, job_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_job(job_id)


def reserve_job(job: BaseJob, start_status: str) -> bool:
    reserved = reserve_compute_slot(
        task_id=job.job_id,
        task_type=job.job_type,
        start_status=start_status,
        model_id=job.voice_model_id,
    )
    if reserved:
        update_task_status(job.job_id, start_status, "")
        if job.track_id and job.job_kind == "cover":
            mark_track_cover_job_processing(
                job.track_id,
                job.job_id,
                model_id=job.voice_model_id,
                voice_name=job.voice_name,
            )
    return reserved


def release_job(job_id: str) -> None:
    release_compute_slot(job_id)


def set_job_pending(job_id: str, message: str = "") -> None:
    update_task_status(job_id, "pending", message)


def fail_job(job_id: str, message: str) -> None:
    update_task_status(job_id, "\u5931\u8d25", message[:500])


def complete_job(job_id: str) -> None:
    update_task_status(job_id, "\u5df2\u5b8c\u6210", "")


def normalize_job_status(status: str) -> str:
    value = (status or "").strip().lower()
    if value in {"pending", "queued", "排队中", "等待中"}:
        return "pending"
    if value in {"完成", "已完成", "completed", "complete", "done", "success", "succeeded"}:
        return "completed"
    if value in {"失败", "failed", "fail", "error"}:
        return "failed"
    if value in {"已取消", "cancelled", "canceled"}:
        return "cancelled"
    if value in {"训练中", "处理中", "running", "processing", "分离中", "修音中", "变声中", "混音中", "切片中"}:
        return "processing"
    return value


def get_next_pending_job() -> BaseJob | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE status = 'pending'
              AND compute_ready = 1
            ORDER BY datetime(created_at) ASC, rowid ASC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    return _row_to_job(dict(row)) if row else None


def _test_voice_model_ids(conn) -> set[str]:
    rows = conn.execute("SELECT * FROM voice_models").fetchall()
    model_ids: set[str] = set()
    for row in rows:
        item = dict(row)
        if is_smoke_model_record(item):
            for key in ("voice_model_id", "legacy_model_id"):
                value = item.get(key)
                if value:
                    model_ids.add(str(value))
    return model_ids


def _job_filter_reason(item: dict, test_model_ids: set[str] | None = None) -> str:
    reason = explain_test_data_filter_reason(item, kind="job")
    if reason:
        return reason
    model_id = str(item.get("voice_model_id") or "").strip()
    if model_id and test_model_ids and model_id in test_model_ids:
        return "voice_model.test_data"
    return ""


def list_jobs(
    job_type: str | None = None,
    status: str | None = None,
    strategy_key: str | None = None,
    voice_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_smoke: bool = False,
    include_test_data: bool = False,
) -> list[dict]:
    conn = get_connection()
    try:
        query = "SELECT * FROM jobs WHERE 1=1"
        params: list[object] = []
        if job_type:
            query += " AND job_type = ?"
            params.append(job_type)
        normalized_filter = normalize_job_status(status) if status else ""
        if strategy_key:
            query += " AND strategy_key = ?"
            params.append(strategy_key)
        if voice_name:
            query += " AND voice_name LIKE ?"
            params.append(f"%{voice_name}%")
        query += " ORDER BY datetime(created_at) DESC, rowid DESC"
        rows = conn.execute(query, tuple(params)).fetchall()
        items = [dict(r) for r in rows]
        test_model_ids = _test_voice_model_ids(conn)
        include_filtered = bool(include_smoke or include_test_data)
        if not include_filtered:
            items = [item for item in items if not _job_filter_reason(item, test_model_ids)]
        else:
            for item in items:
                reason = _job_filter_reason(item, test_model_ids)
                if reason:
                    item["filter_reason"] = reason
        if status:
            items = [item for item in items if normalize_job_status(item.get("status") or "") == normalized_filter]
        return items[offset: offset + limit]
    finally:
        conn.close()


def hidden_test_job_count(
    job_type: str | None = None,
    status: str | None = None,
    strategy_key: str | None = None,
    voice_name: str | None = None,
) -> int:
    conn = get_connection()
    try:
        query = "SELECT * FROM jobs WHERE 1=1"
        params: list[object] = []
        if job_type:
            query += " AND job_type = ?"
            params.append(job_type)
        if strategy_key:
            query += " AND strategy_key = ?"
            params.append(strategy_key)
        if voice_name:
            query += " AND voice_name LIKE ?"
            params.append(f"%{voice_name}%")
        rows = [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]
        test_model_ids = _test_voice_model_ids(conn)
        if status:
            normalized_filter = normalize_job_status(status)
            rows = [row for row in rows if normalize_job_status(row.get("status") or "") == normalized_filter]
        return sum(1 for row in rows if _job_filter_reason(row, test_model_ids))
    finally:
        conn.close()


def job_summary(include_smoke: bool = False, include_test_data: bool = False) -> dict:
    conn = get_connection()
    try:
        rows = [
            dict(row)
            for row in conn.execute("SELECT job_id, legacy_task_id, status, job_type, voice_name, voice_model_id, input_path, output_root, metadata_json FROM jobs").fetchall()
        ]
        test_model_ids = _test_voice_model_ids(conn)
        hidden_test_count = sum(1 for row in rows if _job_filter_reason(row, test_model_ids))
        if not (include_smoke or include_test_data):
            rows = [row for row in rows if not _job_filter_reason(row, test_model_ids)]
        status_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for row in rows:
            normalized_status = normalize_job_status(row["status"])
            status_counts[normalized_status] = status_counts.get(normalized_status, 0) + 1
            type_counts[row["job_type"]] = type_counts.get(row["job_type"], 0) + 1
        return {
            "pending_count": status_counts.get("pending", 0),
            "processing_count": status_counts.get("processing", 0),
            "failed_count": status_counts.get("failed", 0),
            "completed_count": status_counts.get("completed", 0),
            "cancelled_count": status_counts.get("cancelled", 0),
            "cover_count": type_counts.get("cover", 0),
            "train_count": type_counts.get("train", 0),
            "hidden_test_count": hidden_test_count,
            "include_test_data": bool(include_smoke or include_test_data),
        }
    finally:
        conn.close()


def has_active_compute_jobs() -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT job_id
            FROM jobs
            WHERE status IN ({})
            LIMIT 1
            """.format(",".join("?" for _ in ACTIVE_COMPUTE_STATUSES)),
            tuple(ACTIVE_COMPUTE_STATUSES),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _build_control_result(job_id: str, action: str, message: str) -> dict:
    job_row = get_job_row(job_id) or {}
    stage_logs = list_stage_logs(job_id)
    last_log = stage_logs[-1] if stage_logs else None
    return {
        "ok": True,
        "action": action,
        "job_id": job_id,
        "status": job_row.get("status") or "",
        "current_stage": canonical_current_stage(job_row, stage_logs),
        "error_log": job_row.get("error_log") or "",
        "message": message,
        "last_stage_log": {
            "stage_name": last_log.get("stage_name"),
            "status": last_log.get("status"),
            "message": last_log.get("message"),
        } if last_log else None,
    }


def retry_job(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        return {"ok": False, "error": "job_not_found", "message": "浠诲姟涓嶅瓨鍦?"}
    if normalize_job_status(job.status) != "failed":
        return {"ok": False, "error": "only_failed_job_can_retry", "message": "鍙湁澶辫触浠诲姟鎵嶈兘閲嶈瘯"}
    set_job_pending(job_id, "")
    if job.track_id and job.job_kind == "cover":
        mark_track_cover_job_pending(job.track_id)
    log_stage(job_id, "job_control", "completed", "retry -> pending", {"action": "retry", "status": "pending"})
    return _build_control_result(
        job_id,
        action="retry",
        message="澶辫触浠诲姟宸查噸鏂版斁鍥為槦鍒楋紝绠楀姏绌洪棽鏃朵細鑷姩鍚姩銆?",
    )


def requeue_job(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        return {"ok": False, "error": "job_not_found", "message": "浠诲姟涓嶅瓨鍦?"}
    if normalize_job_status(job.status) not in {"pending", "failed"}:
        return {
            "ok": False,
            "error": "only_pending_or_failed_job_can_requeue",
            "message": "鍙湁 pending 鎴栧け璐ヤ换鍔℃墠鑳介噸鏂板叆闃?",
        }
    set_job_pending(job_id, "")
    if job.track_id and job.job_kind == "cover":
        mark_track_cover_job_pending(job.track_id)
    log_stage(job_id, "job_control", "completed", "requeue -> pending", {"action": "requeue", "status": "pending"})
    return _build_control_result(
        job_id,
        action="requeue",
        message="浠诲姟宸查噸鏂板叆闃燂紱濡傛灉褰撳墠绠楀姏蹇欙紝浼氱户缁湪闃熷垪涓瓑寰呫€?",
    )


def cancel_job(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        return {"ok": False, "error": "job_not_found", "message": "浠诲姟涓嶅瓨鍦?"}
    if normalize_job_status(job.status) != "pending":
        return {"ok": False, "error": "only_pending_job_can_cancel", "message": "鍙湁 pending 浠诲姟鎵嶈兘鍙栨秷"}
    update_task_status(job_id, "\u5df2\u53d6\u6d88", "cancelled by user")
    if job.track_id and job.job_kind == "cover":
        reset_track_cover_job_state(job.track_id)
    log_stage(job_id, "job_control", "completed", "cancel -> cancelled", {"action": "cancel", "status": "cancelled"})
    return _build_control_result(
        job_id,
        action="cancel",
        message="浠诲姟宸插彇娑堬紝涓嶄細缁х画鍙備笌鍚庣画璋冨害銆?",
    )


def execute_job(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        fail_job(job_id, "Job not found")
        return {"success": False, "error": "job_not_found"}

    dispatch_key = job.strategy_key or job.job_kind or job.job_type
    if job.job_type == "train" and has_unclosed_stage(job.job_id, "train_core"):
        job_row = get_job_row(job.job_id) or {}
        stage_logs = list_stage_logs(job.job_id)
        exp_name = extract_exp_name_from_job(job_row, stage_logs)
        checkpoint = inspect_training_checkpoint(exp_name) if exp_name else {}
        error = "检测到该训练任务已有未闭合的核心训练记录，已阻止重复派发。请先人工确认 RVC 进程与 checkpoint 状态。"
        summary = summarize_training_error(f"{DUPLICATE_TRAIN_CORE_CODE}: {error}", exp_name=exp_name, checkpoint=checkpoint)
        fail_job(job.job_id, error)
        log_stage(
            job.job_id,
            "job_dispatch",
            "failed",
            "duplicate train_core dispatch blocked",
            {
                "error_code": DUPLICATE_TRAIN_CORE_CODE,
                "exp_name": exp_name,
                "checkpoint": checkpoint,
                "error_summary": summary,
            },
        )
        return {"success": False, "error": error, "error_summary": summary}

    log_stage(job.job_id, "job_dispatch", "started", f"dispatch -> {dispatch_key}")
    try:
        result = run_registered_pipeline(job)
        if result.get("success", False):
            log_stage(job.job_id, "job_dispatch", "completed", f"strategy done -> {dispatch_key}", result)
            if job.track_id and job.job_kind == "cover":
                mark_track_cover_job_complete(
                    job.track_id,
                    job.job_id,
                    model_id=job.voice_model_id,
                    voice_name=job.voice_name,
                )
        else:
            log_stage(job.job_id, "job_dispatch", "failed", f"strategy failed -> {dispatch_key}", result)
            if job.track_id and job.job_kind == "cover":
                mark_track_cover_job_failed(
                    job.track_id,
                    job.job_id,
                    error=result.get("error", ""),
                    model_id=job.voice_model_id,
                    voice_name=job.voice_name,
                )
        return result
    except Exception as exc:
        fail_job(job.job_id, str(exc))
        log_stage(job.job_id, "job_dispatch", "failed", f"strategy exception -> {dispatch_key}", {"error": str(exc)})
        if job.track_id and job.job_kind == "cover":
            mark_track_cover_job_failed(
                job.track_id,
                job.job_id,
                error=str(exc),
                model_id=job.voice_model_id,
                voice_name=job.voice_name,
            )
        return {"success": False, "error": str(exc)}
