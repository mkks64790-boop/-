from __future__ import annotations

import json
from datetime import datetime
from typing import Any

try:
    from ..db import get_connection
    from .job_service import canonical_current_stage, get_job_row, normalize_job_status
    from .model_service import get_voice_model_by_source_job
    from .smoke_filter import is_smoke_job_record
    from .stage_log_service import list_stage_logs
except ImportError:
    from db import get_connection
    from services.job_service import canonical_current_stage, get_job_row, normalize_job_status
    from services.model_service import get_voice_model_by_source_job
    from services.smoke_filter import is_smoke_job_record
    from services.stage_log_service import list_stage_logs


TRAIN_STAGE_FLOW = {
    "single_long_preprocess": [
        "train_upload",
        "train_preflight",
        "train_dataset_prepare",
        "train_preprocess",
        "train_pitch_extract",
        "train_feature_extract",
        "train_core",
        "train_index",
        "train_register_model",
    ],
    "multi_clean_direct": [
        "train_upload",
        "train_preflight",
        "train_dataset_prepare",
        "train_direct_prepare",
        "train_pitch_extract",
        "train_feature_extract",
        "train_core",
        "train_index",
        "train_register_model",
    ],
}

STAGE_LABELS = {
    "train_upload": "接收训练素材",
    "train_preflight": "环境与素材预检",
    "train_dataset_prepare": "建立训练数据集",
    "train_preprocess": "长素材切片预处理",
    "train_direct_prepare": "多文件直接整理",
    "train_pitch_extract": "提取 F0 / pitch",
    "train_feature_extract": "提取音频特征",
    "train_core": "执行 RVC 训练",
    "train_index": "生成检索索引",
    "train_register_model": "登记模型资产",
}


def latest_training_observer(project_root: str, weights_dir: str, *, include_smoke: bool = False) -> dict[str, Any]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE job_type = 'train'
            ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC, rowid DESC
            LIMIT 25
            """
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        job = dict(row)
        if include_smoke or not is_smoke_job_record(job):
            return training_observer(job["job_id"], project_root, weights_dir)

    return {
        "ok": False,
        "code": "no_training_job",
        "message": "尚未发现可观察的训练任务。",
        "observer": None,
    }


def training_observer(job_id: str, project_root: str, weights_dir: str) -> dict[str, Any]:
    job = get_job_row(job_id)
    if not job:
        return {"ok": False, "code": "job_not_found", "message": "训练任务不存在。", "observer": None}
    if (job.get("job_type") or "") != "train":
        return {"ok": False, "code": "job_not_train", "message": "该任务不是训练任务。", "observer": None}

    logs = list_stage_logs(job_id)
    model = get_voice_model_by_source_job(job_id, project_root, weights_dir)
    observer = build_training_observer(job, logs, model)
    return {"ok": True, "observer": observer}


def build_training_observer(job: dict, stage_logs: list[dict], model: dict | None = None) -> dict[str, Any]:
    metadata = _loads(job.get("metadata_json"))
    status = job.get("status") or ""
    normalized_status = normalize_job_status(status)
    current_stage = canonical_current_stage(job, stage_logs)
    strategy_key = job.get("strategy_key") or metadata.get("recommended_route") or "single_long_preprocess"
    flow = TRAIN_STAGE_FLOW.get(strategy_key) or TRAIN_STAGE_FLOW["single_long_preprocess"]
    progress = _stage_progress(flow, current_stage, normalized_status, stage_logs)
    last_log = stage_logs[-1] if stage_logs else None
    current_stage_log = _latest_stage_log(stage_logs, current_stage)
    registration = _model_registration_status(model, current_stage, normalized_status)
    return {
        "job_id": job.get("job_id") or "",
        "voice_name": job.get("voice_name") or "",
        "status": status,
        "normalized_status": normalized_status,
        "strategy_key": strategy_key,
        "current_stage": current_stage,
        "current_stage_label": STAGE_LABELS.get(current_stage, current_stage or "等待调度"),
        "current_stage_started_at": current_stage_log.get("created_at") if current_stage_log else "",
        "last_stage_log_at": last_log.get("created_at") if last_log else "",
        "last_stage_log": _public_log(last_log),
        "stage_progress": progress,
        "model_registration_status": registration["status"],
        "model_registration_label": registration["label"],
        "generated_model_id": (model or {}).get("model_id") or "",
        "generated_model_name": (model or {}).get("model_name") or "",
        "generated_model_usable": bool((model or {}).get("usable")),
        "generated_model_summary": (model or {}).get("source_summary") or "",
        "training_config": metadata.get("training_config") or {},
        "material_profile": (metadata.get("material_decision") or {}).get("material_profile") if isinstance(metadata.get("material_decision"), dict) else "",
        "next_step": _next_step(normalized_status, current_stage, registration),
        "stage_logs_tail": [_public_log(item) for item in stage_logs[-6:]],
        "heartbeat_at": last_log.get("created_at") if last_log else job.get("updated_at") or "",
        "created_at": job.get("created_at") or "",
        "updated_at": job.get("updated_at") or "",
    }


def _stage_progress(flow: list[str], current_stage: str, normalized_status: str, stage_logs: list[dict]) -> dict[str, Any]:
    completed_statuses = {"completed", "complete", "done", "success", "已完成", "完成"}
    completed_from_logs = {
        item.get("stage_name")
        for item in stage_logs
        if str(item.get("status") or "").strip().lower() in completed_statuses
    }
    if normalized_status == "completed":
        completed_count = len(flow)
    else:
        try:
            current_index = flow.index(current_stage)
        except ValueError:
            current_index = -1
        completed_count = sum(1 for index, stage in enumerate(flow) if stage in completed_from_logs or index < current_index)
    total = len(flow)
    return {
        "completed": max(0, min(completed_count, total)),
        "total": total,
        "label": f"{max(0, min(completed_count, total))}/{total}",
        "flow": [{"stage": stage, "label": STAGE_LABELS.get(stage, stage)} for stage in flow],
    }


def _model_registration_status(model: dict | None, current_stage: str, normalized_status: str) -> dict[str, str]:
    if model and model.get("usable"):
        return {"status": "model_usable", "label": "模型已登记，可用于翻唱"}
    if model:
        return {"status": "model_registered_unusable", "label": "模型已登记，但文件待检查"}
    if normalized_status == "failed":
        return {"status": "failed_without_model", "label": "训练失败，未生成可用模型"}
    if current_stage == "train_register_model" or normalized_status == "completed":
        return {"status": "registration_missing", "label": "已到登记阶段，但未发现模型入库"}
    return {"status": "not_registered", "label": "模型尚未登记"}


def _next_step(normalized_status: str, current_stage: str, registration: dict[str, str]) -> str:
    if registration["status"] == "model_usable":
        return "下一步：用该模型跑短翻唱 smoke，确认音色方向和噪声情况。"
    if registration["status"] == "model_registered_unusable":
        return "下一步：检查 .pth/.index 路径，确认模型文件是否存在。"
    if normalized_status == "failed":
        return "下一步：查看失败诊断和 checkpoint 恢复，不要直接重跑长训练。"
    if normalized_status == "processing":
        if current_stage == "train_core":
            return "核心训练可能长时间停留在同一阶段；保持后端/RVC/GPU 不要关闭。"
        return "训练仍在推进，观察最近阶段日志时间和当前阶段。"
    if normalized_status == "pending":
        return "训练正在排队，等待 GPU 算力槽释放。"
    return "等待训练进入下一阶段。"


def _latest_stage_log(stage_logs: list[dict], stage_name: str) -> dict:
    if not stage_name:
        return {}
    for item in reversed(stage_logs):
        if item.get("stage_name") == stage_name:
            return item
    return {}


def _public_log(log: dict | None) -> dict | None:
    if not log:
        return None
    return {
        "stage_name": log.get("stage_name") or "",
        "status": log.get("status") or "",
        "message": log.get("message") or "",
        "created_at": log.get("created_at") or "",
        "detail": _loads(log.get("detail_json")),
    }


def _loads(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}
