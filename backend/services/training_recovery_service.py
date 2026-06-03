from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

try:
    from .. import db as backend_db
    from ..model_trainer import TRAIN_VERSION, run_training_index
    from .asset_service import register_job_artifact
    from .model_service import build_trained_model_metadata, upsert_voice_model
    from .stage_log_service import list_stage_logs, log_stage
    from .training_runtime_guard import inspect_training_checkpoint
except ImportError:
    import db as backend_db
    from model_trainer import TRAIN_VERSION, run_training_index
    from services.asset_service import register_job_artifact
    from services.model_service import build_trained_model_metadata, upsert_voice_model
    from services.stage_log_service import list_stage_logs, log_stage
    from services.training_runtime_guard import inspect_training_checkpoint


EXP_NAME_PATTERN = re.compile(r"\bfeishark_v_[0-9a-fA-F]{8}\b")


class TrainingRecoveryError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def to_detail(self) -> dict[str, Any]:
        return {"error": self.code, "message": self.message}


def get_training_recovery_plan(job_id: str) -> dict[str, Any]:
    job = _get_job_row(job_id)
    if not job:
        raise TrainingRecoveryError("job_not_found", f"Job 不存在: {job_id}", status_code=404)
    if (job.get("job_type") or "") != "train":
        raise TrainingRecoveryError("job_not_train", "只有训练任务支持 checkpoint 恢复。", status_code=422)

    exp_names = collect_training_exp_names(job, list_stage_logs(job_id))
    candidates = [_build_candidate(exp_name) for exp_name in exp_names]
    candidates = [item for item in candidates if item.get("exists")]
    candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
    for index, item in enumerate(candidates):
        item["is_recommended"] = index == 0 and _candidate_can_recover(item)

    recommended = candidates[0] if candidates and _candidate_can_recover(candidates[0]) else None
    warnings = []
    if not exp_names:
        warnings.append("未在任务元数据或阶段日志中发现 feishark_v_* 实验名。")
    if candidates and not recommended:
        warnings.append("检测到实验目录，但缺少可登记 checkpoint 或可构建 index 的特征目录。")

    reason = "未检测到可恢复 checkpoint。"
    if recommended:
        reason = (
            f"检测到最高 e{recommended.get('highest_epoch')} checkpoint，"
            f"且特征目录可用于构建 index。"
        )

    return {
        "job_id": job["job_id"],
        "can_recover": bool(recommended),
        "recommended_exp_name": recommended.get("exp_name") if recommended else "",
        "reason": reason,
        "candidates": candidates,
        "warnings": warnings,
    }


def collect_training_exp_names(job_row: dict, stage_logs: list[dict]) -> list[str]:
    found: list[str] = []

    def add_from_value(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                add_from_value(child)
            return
        if isinstance(value, list):
            for child in value:
                add_from_value(child)
            return
        text = str(value or "")
        for match in EXP_NAME_PATTERN.findall(text):
            if match not in found:
                found.append(match)

    add_from_value(job_row.get("metadata_json") or "")
    add_from_value(job_row.get("error_log") or "")
    for log in stage_logs:
        add_from_value(log.get("message") or "")
        add_from_value(log.get("detail_json") or "")
    return found


def register_training_recovery(
    job_id: str,
    *,
    exp_name: str,
    model_name: str,
    build_index_if_missing: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    plan = get_training_recovery_plan(job_id)
    candidates = {item["exp_name"]: item for item in plan["candidates"]}
    selected = candidates.get((exp_name or "").strip())
    if not selected:
        raise TrainingRecoveryError("recovery_candidate_not_found", "指定 exp_name 不在该任务的恢复候选中。", status_code=404)
    if not _candidate_has_checkpoint(selected):
        raise TrainingRecoveryError("checkpoint_not_found", "候选实验缺少可登记的 .pth checkpoint。", status_code=422)

    requested_model_name = _validate_model_name(model_name)
    safe_model_name = _allocate_recovery_model_name(requested_model_name)
    index_candidates = list(selected.get("index_candidates") or [])
    needs_index = not index_candidates
    if needs_index and not selected.get("index_feasible"):
        raise TrainingRecoveryError("index_not_feasible", "候选实验缺少可构建 index 的特征目录。", status_code=422)
    if needs_index and not build_index_if_missing:
        raise TrainingRecoveryError("index_missing", "候选实验尚无 index；请允许构建 index 后再登记。", status_code=422)

    model_id = f"v_{uuid.uuid4().hex[:8]}"
    result = {
        "success": bool(dry_run),
        "dry_run": bool(dry_run),
        "job_id": job_id,
        "model_id": model_id,
        "model_name": safe_model_name,
        "exp_name": selected["exp_name"],
        "recovered_epoch": selected.get("highest_epoch"),
        "would_build_index": bool(needs_index and build_index_if_missing),
        "pth_source": selected.get("highest_pth") or "",
        "index_source": index_candidates[0] if index_candidates else "",
        "pth_path": "",
        "index_path": "",
        "plan": plan,
    }
    if dry_run:
        return result

    log_stage(job_id, "train_checkpoint_recover", "started", f"recover checkpoint: {selected['exp_name']}", selected)
    if needs_index:
        log_stage(job_id, "train_index", "started", f"build recovery index: {selected['exp_name']}", {"exp_name": selected["exp_name"]})
        run_training_index(selected["exp_name"])
        refreshed = _build_candidate(selected["exp_name"])
        if not refreshed.get("index_candidates"):
            log_stage(job_id, "train_index", "failed", "recovery index build produced no usable index", refreshed)
            raise TrainingRecoveryError("index_build_failed", "index 构建完成后仍未检测到可用 .index。", status_code=500)
        selected = refreshed
        index_candidates = list(selected.get("index_candidates") or [])
        log_stage(job_id, "train_index", "completed", "recovery index build completed", selected)

    pth_dest, index_dest = _copy_recovery_artifacts(
        selected["highest_pth"],
        index_candidates[0],
        safe_model_name,
    )
    pth_rel = _to_project_rel(pth_dest)
    index_rel = _to_project_rel(index_dest)
    metadata = {
        **build_trained_model_metadata(job_id),
        "origin_kind": "trained_local",
        "recovered_from_checkpoint": True,
        "recovered_exp_name": selected["exp_name"],
        "recovered_epoch": selected.get("highest_epoch"),
        "recovery_source_job_id": job_id,
        "source_summary": f"从训练任务 {job_id} 的 e{selected.get('highest_epoch')} checkpoint 恢复登记。",
    }

    log_stage(job_id, "train_register_model", "started", f"register recovered model: {safe_model_name}", metadata)
    upsert_voice_model(
        voice_model_id=model_id,
        legacy_model_id=model_id,
        model_name=safe_model_name,
        pth_path=pth_rel,
        index_path=index_rel,
        default_pitch=0,
        source_job_id=job_id,
        status="ready",
        metadata=metadata,
    )
    pth_artifact_id = register_job_artifact(
        job_id,
        "train_register_model",
        "train_model_pth",
        pth_dest,
        is_final=True,
        metadata={"source_path": selected["highest_pth"], "recovered_from_checkpoint": True},
    )
    index_artifact_id = register_job_artifact(
        job_id,
        "train_register_model",
        "train_model_index",
        index_dest,
        is_final=True,
        metadata={"source_path": index_candidates[0], "recovered_from_checkpoint": True},
    )
    _merge_job_metadata(
        job_id,
        {
            "recovered_from_checkpoint": True,
            "recovered_exp_name": selected["exp_name"],
            "recovered_epoch": selected.get("highest_epoch"),
            "recovered_model_id": model_id,
            "recovered_model_name": safe_model_name,
        },
    )
    backend_db.update_task_status(job_id, "完成", "")
    log_stage(
        job_id,
        "train_register_model",
        "completed",
        "recovered model registered",
        {
            "model_id": model_id,
            "model_name": safe_model_name,
            "pth_path": pth_rel,
            "index_path": index_rel,
            "pth_artifact_id": pth_artifact_id,
            "index_artifact_id": index_artifact_id,
            "recovered_exp_name": selected["exp_name"],
            "recovered_epoch": selected.get("highest_epoch"),
        },
    )
    log_stage(job_id, "train_checkpoint_recover", "completed", "checkpoint recovery completed", {"model_id": model_id})
    _set_job_current_stage(job_id, "train_register_model")

    result.update(
        {
            "success": True,
            "pth_path": pth_rel,
            "index_path": index_rel,
            "index_source": index_candidates[0],
            "pth_artifact_id": pth_artifact_id,
            "index_artifact_id": index_artifact_id,
        }
    )
    return result


def _build_candidate(exp_name: str) -> dict[str, Any]:
    inspection = inspect_training_checkpoint(exp_name, train_version=TRAIN_VERSION)
    epoch = int(inspection.get("highest_epoch") or 0)
    feature_count = int(inspection.get("feature_count") or 0)
    return {
        **inspection,
        "is_recommended": False,
        "score": epoch * 1000 + feature_count,
    }


def _candidate_has_checkpoint(candidate: dict[str, Any]) -> bool:
    path = candidate.get("highest_pth") or ""
    return bool(path and os.path.exists(path))


def _candidate_can_recover(candidate: dict[str, Any]) -> bool:
    has_index = bool(candidate.get("index_candidates"))
    return _candidate_has_checkpoint(candidate) and (has_index or bool(candidate.get("index_feasible")))


def _validate_model_name(model_name: str) -> str:
    value = (model_name or "").strip()
    if not value:
        raise TrainingRecoveryError("model_name_required", "请提供恢复后的模型名称。", status_code=400)
    if os.path.basename(value) != value or any(sep in value for sep in ("/", "\\")):
        raise TrainingRecoveryError("invalid_model_name", "模型名称不能包含路径分隔符。", status_code=400)
    return value


def _allocate_recovery_model_name(model_name: str) -> str:
    weights_dir = backend_db.WEIGHTS_DIR
    conn = backend_db.get_connection()
    try:
        existing_names = {
            row["model_name"]
            for row in conn.execute("SELECT model_name FROM voice_models").fetchall()
        }
    finally:
        conn.close()

    candidate = model_name
    suffix = 2
    while (
        candidate in existing_names
        or os.path.exists(os.path.join(weights_dir, f"{candidate}.pth"))
        or os.path.exists(os.path.join(weights_dir, f"{candidate}.index"))
    ):
        candidate = f"{model_name}_{suffix}"
        suffix += 1
    return candidate


def _copy_recovery_artifacts(pth_source: str, index_source: str, model_name: str) -> tuple[str, str]:
    weights_dir = backend_db.WEIGHTS_DIR
    os.makedirs(weights_dir, exist_ok=True)
    pth_dest = os.path.join(weights_dir, f"{model_name}.pth")
    index_dest = os.path.join(weights_dir, f"{model_name}.index")
    shutil.copy2(pth_source, pth_dest)
    shutil.copy2(index_source, index_dest)
    if os.path.getsize(index_dest) <= 12:
        raise TrainingRecoveryError("index_artifact_empty", "恢复得到的 index 文件为空壳，已拒绝登记。", status_code=422)
    return pth_dest, index_dest


def _to_project_rel(path: str) -> str:
    try:
        return os.path.relpath(path, backend_db.PROJECT_ROOT).replace("\\", "/")
    except ValueError:
        return path


def _get_job_row(job_id: str) -> dict | None:
    conn = backend_db.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ? OR legacy_task_id = ? LIMIT 1",
            (job_id, job_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _merge_job_metadata(job_id: str, patch: dict[str, Any]) -> None:
    conn = backend_db.get_connection()
    try:
        row = conn.execute(
            "SELECT metadata_json FROM jobs WHERE job_id = ? OR legacy_task_id = ? LIMIT 1",
            (job_id, job_id),
        ).fetchone()
        metadata = {}
        if row and row["metadata_json"]:
            try:
                parsed = json.loads(row["metadata_json"])
                metadata = parsed if isinstance(parsed, dict) else {}
            except Exception:
                metadata = {}
        metadata.update(patch)
        conn.execute(
            """
            UPDATE jobs
            SET metadata_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? OR legacy_task_id = ?
            """,
            (json.dumps(metadata, ensure_ascii=False), job_id, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def _set_job_current_stage(job_id: str, stage_name: str) -> None:
    conn = backend_db.get_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET current_stage = ?, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? OR legacy_task_id = ?
            """,
            (stage_name, job_id, job_id),
        )
        conn.commit()
    finally:
        conn.close()
