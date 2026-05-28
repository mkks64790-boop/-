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
    from ..services.smoke_filter import is_smoke_job_record
    from ..services.stage_log_service import list_stage_logs, log_stage
    from ..strategies.strategy_registry import get_strategy
except ImportError:
    from services.smoke_filter import is_smoke_job_record
    from services.stage_log_service import list_stage_logs, log_stage
    from strategies.strategy_registry import get_strategy


@dataclass(kw_only=True)
class BaseJob:
    job_id: str
    job_type: str
    strategy_key: str
    status: str = "pending"
    current_stage: str = ""
    compute_ready: int = 0
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


def create_cover_job(job_id: str, input_path: str, output_root: str, metadata: dict | None = None) -> CoverJob:
    create_task(job_id, input_path, task_type="upload")
    job = CoverJob(
        job_id=job_id,
        legacy_task_id=job_id,
        strategy_key="cover_strategy",
        input_path=input_path,
        output_root=output_root,
        metadata=metadata or {},
    )
    _insert_job(job)
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
                job_id, legacy_task_id, job_type, strategy_key, status, current_stage,
                compute_ready, voice_model_id, voice_name, input_path, output_root,
                error_log, metadata_json, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                COALESCE((SELECT created_at FROM jobs WHERE job_id = ?), CURRENT_TIMESTAMP),
                CURRENT_TIMESTAMP
            )
            """,
            (
                job.job_id,
                job.legacy_task_id or job.job_id,
                job.job_type,
                job.strategy_key,
                job.status,
                job.current_stage,
                job.compute_ready,
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
    if status == "pending":
        return "pending"
    if status == "已取消":
        return "cancelled"

    business_logs = [
        log for log in (stage_logs or [])
        if log.get("stage_name") not in {"job_dispatch", "job_control"}
    ]
    if business_logs:
        return business_logs[-1]["stage_name"]

    current_stage = (job_row.get("current_stage") or "").strip()
    if current_stage and current_stage not in {"job_dispatch", "job_control"}:
        return current_stage

    job_type = job_row.get("job_type") or ""
    if status == "完成":
        return "cover_mix" if job_type == "cover" else "train_register_model"
    if status == "失败":
        return "failed"
    return status


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
        strategy_key=row.get("strategy_key") or "",
        status=row.get("status") or "pending",
        current_stage=row.get("current_stage") or "",
        compute_ready=row.get("compute_ready") or 0,
        voice_model_id=row.get("voice_model_id") or "",
        voice_name=row.get("voice_name") or "",
        input_path=row.get("input_path") or "",
        output_root=row.get("output_root") or "",
        error_log=row.get("error_log") or "",
        metadata=metadata,
    )


def activate_cover_job(job_id: str, voice_model_id: str) -> BaseJob | None:
    set_task_model_id(job_id, voice_model_id)
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET job_type = 'cover', strategy_key = 'cover_strategy',
                compute_ready = 1, voice_model_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? OR legacy_task_id = ?
            """,
            (voice_model_id, job_id, job_id),
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
            SET job_type = 'train', compute_ready = 1, updated_at = CURRENT_TIMESTAMP
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
    return reserved


def release_job(job_id: str) -> None:
    release_compute_slot(job_id)


def set_job_pending(job_id: str, message: str = "") -> None:
    update_task_status(job_id, "pending", message)


def fail_job(job_id: str, message: str) -> None:
    update_task_status(job_id, "失败", message[:500])


def complete_job(job_id: str) -> None:
    update_task_status(job_id, "完成", "")


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


def list_jobs(
    job_type: str | None = None,
    status: str | None = None,
    strategy_key: str | None = None,
    voice_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_smoke: bool = False,
) -> list[dict]:
    conn = get_connection()
    try:
        query = "SELECT * FROM jobs WHERE 1=1"
        params: list[object] = []
        if job_type:
            query += " AND job_type = ?"
            params.append(job_type)
        if status:
            query += " AND status = ?"
            params.append(status)
        if strategy_key:
            query += " AND strategy_key = ?"
            params.append(strategy_key)
        if voice_name:
            query += " AND voice_name LIKE ?"
            params.append(f"%{voice_name}%")
        query += " ORDER BY datetime(created_at) DESC, rowid DESC"
        rows = conn.execute(query, tuple(params)).fetchall()
        items = [dict(r) for r in rows]
        if not include_smoke:
            items = [item for item in items if not is_smoke_job_record(item)]
        return items[offset: offset + limit]
    finally:
        conn.close()


def job_summary(include_smoke: bool = False) -> dict:
    conn = get_connection()
    try:
        rows = [
            dict(row)
            for row in conn.execute("SELECT status, job_type, voice_name, metadata_json FROM jobs").fetchall()
        ]
        if not include_smoke:
            rows = [row for row in rows if not is_smoke_job_record(row)]
        status_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for row in rows:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
            type_counts[row["job_type"]] = type_counts.get(row["job_type"], 0) + 1
        return {
            "pending_count": status_counts.get("pending", 0),
            "processing_count": sum(status_counts.get(status, 0) for status in ACTIVE_COMPUTE_STATUSES),
            "failed_count": status_counts.get("失败", 0),
            "completed_count": status_counts.get("完成", 0),
            "cover_count": type_counts.get("cover", 0),
            "train_count": type_counts.get("train", 0),
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
        return {"ok": False, "error": "job_not_found", "message": "任务不存在"}
    if job.status != "失败":
        return {"ok": False, "error": "only_failed_job_can_retry", "message": "只有失败任务才能重试"}
    set_job_pending(job_id, "")
    log_stage(job_id, "job_control", "completed", "retry -> pending", {"action": "retry", "status": "pending"})
    return _build_control_result(
        job_id,
        action="retry",
        message="失败任务已重新放回队列，算力空闲时会自动启动。",
    )


def requeue_job(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        return {"ok": False, "error": "job_not_found", "message": "任务不存在"}
    if job.status not in {"pending", "失败"}:
        return {
            "ok": False,
            "error": "only_pending_or_failed_job_can_requeue",
            "message": "只有 pending 或失败任务才能重新入队",
        }
    set_job_pending(job_id, "")
    log_stage(job_id, "job_control", "completed", "requeue -> pending", {"action": "requeue", "status": "pending"})
    return _build_control_result(
        job_id,
        action="requeue",
        message="任务已重新入队；如果当前算力忙，会继续在队列中等待。",
    )


def cancel_job(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        return {"ok": False, "error": "job_not_found", "message": "任务不存在"}
    if job.status != "pending":
        return {"ok": False, "error": "only_pending_job_can_cancel", "message": "只有 pending 任务才能取消"}
    update_task_status(job_id, "已取消", "cancelled by user")
    log_stage(job_id, "job_control", "completed", "cancel -> cancelled", {"action": "cancel", "status": "cancelled"})
    return _build_control_result(
        job_id,
        action="cancel",
        message="任务已取消，不会继续参与后续调度。",
    )


def execute_job(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        fail_job(job_id, "Job not found")
        return {"success": False, "error": "job_not_found"}

    strategy = get_strategy(job.strategy_key)
    log_stage(job.job_id, "job_dispatch", "started", f"dispatch -> {job.strategy_key}")
    try:
        result = strategy.execute(job)
        if result.get("success", False):
            log_stage(job.job_id, "job_dispatch", "completed", f"strategy done -> {job.strategy_key}", result)
        else:
            log_stage(job.job_id, "job_dispatch", "failed", f"strategy failed -> {job.strategy_key}", result)
        return result
    except Exception as exc:
        fail_job(job.job_id, str(exc))
        log_stage(job.job_id, "job_dispatch", "failed", f"strategy exception -> {job.strategy_key}", {"error": str(exc)})
        return {"success": False, "error": str(exc)}
