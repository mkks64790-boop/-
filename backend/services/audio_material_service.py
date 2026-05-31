from __future__ import annotations

import json
import math
import os
import shutil
import subprocess


SINGLE_LONG_MIN_SECONDS = int(os.getenv("FEISHARK_SINGLE_LONG_MIN_SECONDS", "1800"))
SINGLE_LONG_MAX_SECONDS = int(os.getenv("FEISHARK_SINGLE_LONG_MAX_SECONDS", "3000"))


def format_duration_label(duration_seconds: float | int | None) -> str:
    if duration_seconds is None:
        return ""

    total_seconds = max(0, int(round(float(duration_seconds))))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}小时{minutes}分{seconds}秒"
    if minutes:
        return f"{minutes}分{seconds}秒"
    return f"{seconds}秒"


def _as_int(value) -> int | None:
    if value in (None, "", 0, "0"):
        return 0 if value in (0, "0") else None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _base_material_payload(
    *,
    file_count: int,
    duration_seconds: float | None = None,
    sample_rate: int | None = None,
    channels: int | None = None,
    codec: str = "",
    container: str = "",
    bit_rate: int | None = None,
    file_size: int | None = None,
    file_name: str = "",
    mime_type: str = "",
) -> dict:
    return {
        "file_count": int(file_count),
        "duration_seconds": duration_seconds,
        "duration_label": format_duration_label(duration_seconds),
        "sample_rate": sample_rate,
        "channels": channels,
        "codec": codec or "",
        "container": container or "",
        "bit_rate": bit_rate,
        "file_size": file_size,
        "file_name": file_name or "",
        "mime_type": mime_type or "",
    }


def decide_train_material_route(
    file_count: int,
    *,
    duration_seconds: float | None = None,
    sample_rate: int | None = None,
    channels: int | None = None,
    codec: str = "",
    container: str = "",
    bit_rate: int | None = None,
    file_size: int | None = None,
    file_name: str = "",
    mime_type: str = "",
) -> dict:
    payload = _base_material_payload(
        file_count=file_count,
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        channels=channels,
        codec=codec,
        container=container,
        bit_rate=bit_rate,
        file_size=file_size,
        file_name=file_name,
        mime_type=mime_type,
    )

    if file_count > 1:
        return {
            **payload,
            "input_mode": "multi_file",
            "material_profile": "multi_file_dataset",
            "recommended_route": "multi_clean_direct",
            "single_long_eligible": False,
            "submission_allowed": True,
            "reason": f"检测到 {file_count} 个文件，将进入多文件精训链路。",
            "next_step": "可直接创建多文件精训任务。",
        }

    if duration_seconds is None:
        return {
            **payload,
            "input_mode": "single_file",
            "material_profile": "single_duration_pending",
            "recommended_route": "single_long_preprocess",
            "single_long_eligible": None,
            "submission_allowed": None,
            "reason": "尚未拿到单文件时长，提交前请先完成素材识别。",
            "next_step": "等待页面读出时长，或直接提交后由后端再次验收素材。",
        }

    duration_label = payload["duration_label"] or "未知时长"
    if SINGLE_LONG_MIN_SECONDS <= duration_seconds <= SINGLE_LONG_MAX_SECONDS:
        return {
            **payload,
            "input_mode": "single_file",
            "material_profile": "single_long_candidate",
            "recommended_route": "single_long_preprocess",
            "single_long_eligible": True,
            "submission_allowed": True,
            "reason": f"单文件时长约 {duration_label}，命中 30-50 分钟快速训练窗口。",
            "next_step": "可直接创建单文件快速训练任务。",
        }

    if duration_seconds < SINGLE_LONG_MIN_SECONDS:
        return {
            **payload,
            "input_mode": "single_file",
            "material_profile": "single_short_out_of_window",
            "recommended_route": "multi_clean_direct",
            "single_long_eligible": False,
            "submission_allowed": False,
            "reason": f"单文件时长约 {duration_label}，未达到 30 分钟下限，不能按单文件长干声快速训练处理。",
            "next_step": "请改用多文件精训素材，或准备 30-50 分钟单干声后再提交。",
        }

    return {
        **payload,
        "input_mode": "single_file",
        "material_profile": "single_long_out_of_window",
        "recommended_route": "multi_clean_direct",
        "single_long_eligible": False,
        "submission_allowed": False,
        "reason": f"单文件时长约 {duration_label}，超过 50 分钟上限，不再按单文件快速训练窗口处理。",
        "next_step": "请拆分或整理为 30-50 分钟单干声，或改用多文件精训素材。",
    }


def _run_ffprobe(abs_path: str) -> dict:
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        raise RuntimeError("ffprobe_not_found")

    proc = subprocess.run(
        [
            ffprobe_bin,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            abs_path,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "ffprobe_failed").strip())
    return json.loads(proc.stdout or "{}")


def probe_audio_material(abs_path: str, *, file_name: str = "", mime_type: str = "", file_size: int | None = None) -> dict:
    payload = _run_ffprobe(abs_path)
    streams = payload.get("streams") or []
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), streams[0] if streams else {})
    format_info = payload.get("format") or {}
    duration_seconds = _as_float(audio_stream.get("duration")) or _as_float(format_info.get("duration"))
    sample_rate = _as_int(audio_stream.get("sample_rate"))
    channels = _as_int(audio_stream.get("channels"))
    codec = str(audio_stream.get("codec_name") or "").strip()
    container = str(format_info.get("format_name") or "").split(",")[0].strip()
    bit_rate = _as_int(audio_stream.get("bit_rate")) or _as_int(format_info.get("bit_rate"))
    resolved_size = file_size if file_size is not None else _as_int(format_info.get("size"))

    return {
        "duration_seconds": duration_seconds,
        "duration_label": format_duration_label(duration_seconds),
        "sample_rate": sample_rate,
        "channels": channels,
        "codec": codec,
        "container": container,
        "bit_rate": bit_rate,
        "file_size": resolved_size,
        "file_name": file_name or os.path.basename(abs_path),
        "mime_type": mime_type or "",
        "source_path": abs_path,
    }


def profile_train_saved_uploads(saved_files: list[dict]) -> dict:
    file_count = len(saved_files or [])
    if file_count <= 0:
        raise ValueError("empty_train_upload")

    if file_count > 1:
        first = saved_files[0] if saved_files else {}
        return decide_train_material_route(
            file_count,
            file_name=first.get("file_name") or "",
            file_size=sum(int(item.get("file_size") or 0) for item in saved_files),
        )

    item = saved_files[0]
    file_meta = probe_audio_material(
        item["abs_path"],
        file_name=item.get("file_name") or "",
        file_size=int(item.get("file_size") or 0),
    )
    return decide_train_material_route(
        file_count,
        duration_seconds=file_meta.get("duration_seconds"),
        sample_rate=file_meta.get("sample_rate"),
        channels=file_meta.get("channels"),
        codec=file_meta.get("codec") or "",
        container=file_meta.get("container") or "",
        bit_rate=file_meta.get("bit_rate"),
        file_size=file_meta.get("file_size"),
        file_name=file_meta.get("file_name") or "",
        mime_type=file_meta.get("mime_type") or "",
    )


def build_material_rejection_detail(material: dict) -> dict:
    reason = (material.get("reason") or "训练素材不符合当前入口要求。").strip()
    next_step = (material.get("next_step") or "").strip()
    message = reason if not next_step else f"{reason} {next_step}"
    return {
        "error": message,
        "code": "train_material_not_eligible",
        "material_profile": material.get("material_profile"),
        "duration_seconds": material.get("duration_seconds"),
        "duration_label": material.get("duration_label"),
        "recommended_route": material.get("recommended_route"),
        "single_long_eligible": material.get("single_long_eligible"),
        "submission_allowed": material.get("submission_allowed"),
        "reason": reason,
        "next_step": next_step,
        "material_decision": material,
    }


def build_material_check(material: dict) -> dict:
    submission_allowed = material.get("submission_allowed")
    return {
        "check": "train_material_profile",
        "ok": True if submission_allowed is None else bool(submission_allowed),
        "value": material.get("material_profile") or "",
        "detail": material.get("reason") or "",
        "category": "material",
        "label": "训练素材分流",
        "next_step": material.get("next_step") or "",
        "needs_external_fix": False,
    }
