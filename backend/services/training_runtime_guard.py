from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

try:
    from ..db import get_connection
except ImportError:
    from db import get_connection


TRAIN_CORE_TIMEOUT_CODE = "train_core_timeout"
DUPLICATE_TRAIN_CORE_CODE = "duplicate_train_core_blocked"


class TrainingRuntimeError(RuntimeError):
    def __init__(self, *, error_code: str, error_title: str, error_summary: str, detail: dict[str, Any]):
        super().__init__(error_summary)
        self.error_code = error_code
        self.error_title = error_title
        self.error_summary = error_summary
        self.detail = dict(detail)

    def to_summary(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "error_title": self.error_title,
            "error_summary": self.error_summary,
            "raw_error_preview": _trim_text(self.detail.get("raw_error_preview") or "", 500),
            "exp_name": self.detail.get("exp_name") or "",
            "checkpoint_hint": self.detail.get("checkpoint_hint") or "",
        }


def _trim_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def command_preview(cmd: list[str], limit: int = 500) -> str:
    return _trim_text(" ".join(str(part) for part in cmd), limit)


def ensure_training_identity(job) -> tuple[str, str]:
    metadata = dict(getattr(job, "metadata", None) or {})
    model_id = str(
        metadata.get("training_model_id")
        or metadata.get("generated_model_id")
        or metadata.get("model_id")
        or ""
    ).strip()
    exp_name = str(metadata.get("training_exp_name") or metadata.get("exp_name") or "").strip()

    if exp_name and not model_id and exp_name.startswith("feishark_"):
        model_id = exp_name.removeprefix("feishark_")
    if model_id and not exp_name:
        exp_name = f"feishark_{model_id}"
    if not model_id:
        model_id = f"v_{uuid.uuid4().hex[:8]}"
    if not exp_name:
        exp_name = f"feishark_{model_id}"

    metadata.update(
        {
            "training_model_id": model_id,
            "training_exp_name": exp_name,
            "generated_model_id": model_id,
            "exp_name": exp_name,
        }
    )
    _update_job_metadata(getattr(job, "job_id", ""), metadata)
    try:
        job.metadata = metadata
    except Exception:
        pass
    return model_id, exp_name


def _update_job_metadata(job_id: str, metadata: dict[str, Any]) -> None:
    if not job_id:
        return
    conn = get_connection()
    try:
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


def extract_exp_name_from_job(job_row: dict | None, stage_logs: list[dict] | None = None) -> str:
    metadata = {}
    if job_row and job_row.get("metadata_json"):
        try:
            parsed = json.loads(job_row.get("metadata_json") or "{}")
            metadata = parsed if isinstance(parsed, dict) else {}
        except Exception:
            metadata = {}
    exp_name = str(metadata.get("training_exp_name") or metadata.get("exp_name") or "").strip()
    if exp_name:
        return exp_name
    for log in reversed(stage_logs or []):
        detail = log.get("detail_json") or {}
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except Exception:
                detail = {}
        candidate = str((detail or {}).get("exp_name") or "").strip()
        if candidate:
            return candidate
        match = re.search(r"(feishark_[A-Za-z0-9_-]+)", str(log.get("message") or ""))
        if match:
            return match.group(1)
    return ""


def has_unclosed_stage(job_id: str, stage_name: str) -> bool:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT status
            FROM job_stage_logs
            WHERE job_id = ? AND stage_name = ?
            ORDER BY datetime(created_at), rowid
            """,
            (job_id, stage_name),
        ).fetchall()
        if not rows:
            return False
        return rows[-1]["status"] == "started"
    finally:
        conn.close()


def inspect_training_checkpoint(
    exp_name: str,
    *,
    rvc_logs_dir: str = "",
    rvc_webui_dir: str = "",
    train_version: str = "v2",
) -> dict[str, Any]:
    exp_name = (exp_name or "").strip()
    if not exp_name:
        return {
            "exp_name": "",
            "exists": False,
            "highest_epoch": None,
            "highest_pth": "",
            "g_weight": "",
            "d_weight": "",
            "feature_dir": "",
            "feature_count": 0,
            "index_candidates": [],
            "index_feasible": False,
        }

    if not rvc_webui_dir:
        rvc_webui_dir = os.environ.get("FEISHARK_RVC_DIR") or r"D:\RVC\RVCv2"
    if not rvc_logs_dir:
        rvc_logs_dir = os.path.join(rvc_webui_dir, "logs")

    exp_dir = Path(rvc_logs_dir) / exp_name
    weights_dir = Path(rvc_webui_dir) / "assets" / "weights"
    indices_dir = Path(rvc_webui_dir) / "assets" / "indices"
    feature_dir = exp_dir / ("3_feature768" if train_version == "v2" else "3_feature256")

    pth_candidates: list[tuple[int, Path]] = []
    for path in weights_dir.glob(f"{exp_name}*.pth") if weights_dir.exists() else []:
        epoch = _extract_epoch(path.name)
        if epoch is not None:
            pth_candidates.append((epoch, path))
    if exp_dir.exists():
        for path in exp_dir.glob("*.pth"):
            if path.name.startswith(("G_", "D_")):
                continue
            epoch = _extract_epoch(path.name)
            if epoch is not None and path not in [item[1] for item in pth_candidates]:
                pth_candidates.append((epoch, path))

    pth_candidates.sort(key=lambda item: item[0], reverse=True)
    highest_epoch, highest_pth = pth_candidates[0] if pth_candidates else (None, Path(""))
    g_weight = _latest_named_weight(exp_dir, "G_")
    d_weight = _latest_named_weight(exp_dir, "D_")
    index_candidates = [
        str(path)
        for root in (exp_dir, indices_dir)
        if root.exists()
        for path in root.glob(f"*{exp_name}*.index")
        if path.is_file() and path.stat().st_size > 12
    ]
    feature_count = 0
    if feature_dir.is_dir():
        feature_count = sum(1 for path in feature_dir.glob("*.npy") if path.is_file())

    return {
        "exp_name": exp_name,
        "exists": exp_dir.exists() or bool(highest_pth),
        "exp_dir": str(exp_dir),
        "highest_epoch": highest_epoch,
        "highest_pth": str(highest_pth) if highest_pth else "",
        "g_weight": str(g_weight),
        "d_weight": str(d_weight),
        "feature_dir": str(feature_dir) if feature_dir.exists() else "",
        "feature_count": feature_count,
        "index_candidates": index_candidates,
        "index_feasible": bool(feature_count > 0 and highest_pth),
    }


def _extract_epoch(filename: str) -> int | None:
    match = re.search(r"_e(\d+)(?:_|\.pth$)", filename)
    if match:
        return int(match.group(1))
    return None


def _latest_named_weight(exp_dir: Path, prefix: str) -> str:
    if not exp_dir.exists():
        return ""
    candidates = []
    for path in exp_dir.glob(f"{prefix}*.pth"):
        match = re.search(rf"{re.escape(prefix)}(\d+)\.pth$", path.name)
        step = int(match.group(1)) if match else -1
        candidates.append((step, path))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return str(candidates[0][1]) if candidates else ""


def checkpoint_hint_from_inspection(inspection: dict[str, Any]) -> str:
    epoch = inspection.get("highest_epoch")
    if epoch:
        if inspection.get("index_feasible"):
            return f"检测到 e{epoch} checkpoint，可在修复后继续索引/登记。"
        return f"检测到 e{epoch} checkpoint，但还需要确认特征目录后再继续索引/登记。"
    if inspection.get("g_weight") or inspection.get("d_weight"):
        return "检测到 RVC G/D 中间权重，可人工确认是否能恢复。"
    return "未检测到可直接恢复登记的 checkpoint。"


def build_train_core_timeout_error(
    *,
    exp_name: str,
    timeout_seconds: int,
    cmd: list[str],
    raw_error: str = "",
    checkpoint: dict[str, Any] | None = None,
) -> TrainingRuntimeError:
    checkpoint = checkpoint or inspect_training_checkpoint(exp_name)
    detail = {
        "error_code": TRAIN_CORE_TIMEOUT_CODE,
        "exp_name": exp_name,
        "timeout_seconds": timeout_seconds,
        "command_preview": command_preview(cmd),
        "raw_error_preview": _trim_text(raw_error, 500),
        "checkpoint_hint": checkpoint_hint_from_inspection(checkpoint),
        "checkpoint": checkpoint,
    }
    return TrainingRuntimeError(
        error_code=TRAIN_CORE_TIMEOUT_CODE,
        error_title="核心训练超过后端保护时限",
        error_summary=f"RVC 核心训练运行超过 {timeout_seconds} 秒，任务已停止等待人工处理。",
        detail=detail,
    )


def summarize_training_error(
    error: Exception | str | None,
    *,
    exp_name: str = "",
    checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if isinstance(error, TrainingRuntimeError):
        return error.to_summary()

    raw = str(error or "").strip()
    if not raw:
        return None
    code = ""
    title = "训练失败"
    summary = "训练流程失败，请查看阶段日志定位失败步骤。"
    if TRAIN_CORE_TIMEOUT_CODE in raw or "timed out after" in raw:
        code = TRAIN_CORE_TIMEOUT_CODE
        title = "核心训练超过后端保护时限"
        summary = "RVC 核心训练超过后端保护时限，任务已停止等待人工处理。"
    elif DUPLICATE_TRAIN_CORE_CODE in raw:
        code = DUPLICATE_TRAIN_CORE_CODE
        title = "已阻止重复核心训练"
        summary = "检测到该任务已有未闭合的核心训练记录，已阻止重复派发。"
    if exp_name and checkpoint is None:
        checkpoint = inspect_training_checkpoint(exp_name)
    return {
        "error_code": code or "train_failed",
        "error_title": title,
        "error_summary": summary,
        "raw_error_preview": _trim_text(raw, 500),
        "exp_name": exp_name,
        "checkpoint_hint": checkpoint_hint_from_inspection(checkpoint or {}) if exp_name else "",
    }
