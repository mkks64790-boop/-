from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import uuid
from typing import Any

try:
    from .asset_service import get_final_job_artifact, get_job_artifact, register_job_artifact
    from .dataset_service import ensure_job_dirs
    from .job_service import get_job_row
    from .stage_log_service import log_stage
    from .track_service import get_track
except ImportError:
    from services.asset_service import get_final_job_artifact, get_job_artifact, register_job_artifact
    from services.dataset_service import ensure_job_dirs
    from services.job_service import get_job_row
    from services.stage_log_service import log_stage
    from services.track_service import get_track


PROCESSING_MODE = "copy_only_no_dsp"
COPY_ONLY_RENDER_ENGINE = "copy_only"
FFMPEG_RENDER_ENGINE = "ffmpeg_dsp_v0"
FFMPEG_PROCESSING_MODE = "ffmpeg_dsp_v0"
EXPORT_STAGE_NAME = "studio_effect_export"
EXPORT_ARTIFACT_TYPE = "studio_effect_draft_master"
EXPORT_WARNING = "当前未执行真实 DSP/VST，只复制源音频作为处理版草稿。"
RENDER_STAGE_NAME = "studio_effect_render"
RENDER_ARTIFACT_TYPE = "studio_effect_render_master"
RENDER_TIMEOUT_SECONDS = 180

SLOT_PARAM_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "eq": {
        "low": (-6.0, 6.0),
        "mid": (-6.0, 6.0),
        "high": (-6.0, 6.0),
    },
    "compressor": {
        "threshold": (-30.0, 0.0),
        "ratio": (1.0, 8.0),
    },
    "reverb": {
        "mix": (0.0, 100.0),
    },
    "limiter": {
        "ceiling": (-6.0, 0.0),
    },
}

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}


class StudioEffectExportError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def to_detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


def _clamp_number(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(minimum, min(maximum, number))


def _compact_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def get_ffmpeg_path() -> str:
    configured = (os.environ.get("FEISHARK_FFMPEG_PATH") or "").strip()
    if configured and os.path.exists(configured):
        return configured
    return shutil.which("ffmpeg") or ""


def get_effect_rack_capabilities() -> dict:
    ffmpeg_path = get_ffmpeg_path()
    return {
        "ok": True,
        "engines": [
            {
                "id": COPY_ONLY_RENDER_ENGINE,
                "label": "登记草稿",
                "available": True,
                "processing_mode": PROCESSING_MODE,
            },
            {
                "id": FFMPEG_RENDER_ENGINE,
                "label": "ffmpeg DSP v0",
                "available": bool(ffmpeg_path),
                "processing_mode": FFMPEG_PROCESSING_MODE,
                "ffmpeg_path": ffmpeg_path,
            },
        ],
        "artifact_types": [
            EXPORT_ARTIFACT_TYPE,
            RENDER_ARTIFACT_TYPE,
        ],
    }


def validate_effect_rack_slots(effect_rack: Any) -> None:
    if not isinstance(effect_rack, list):
        raise StudioEffectExportError(
            "invalid_effect_rack",
            "effect_rack must be an array.",
            status_code=422,
        )
    for item in effect_rack:
        slot_id = str((item or {}).get("id") or "").strip() if isinstance(item, dict) else ""
        if slot_id not in SLOT_PARAM_RANGES:
            raise StudioEffectExportError(
                "unknown_effect_slot",
                f"Unsupported effect slot: {slot_id or '<empty>'}",
                status_code=422,
            )


def normalize_effect_rack_payload(effect_rack: Any) -> list[dict]:
    validate_effect_rack_slots(effect_rack)
    normalized: list[dict] = []
    for item in effect_rack:
        slot_id = str(item.get("id") or "").strip()
        allowed_params = SLOT_PARAM_RANGES[slot_id]
        raw_params = item.get("params") if isinstance(item.get("params"), dict) else {}
        params = {}
        for name, (minimum, maximum) in allowed_params.items():
            if name not in raw_params:
                continue
            params[name] = _compact_number(_clamp_number(raw_params.get(name), minimum, maximum))

        normalized.append(
            {
                "id": slot_id,
                "enabled": _as_bool(item.get("enabled", False)),
                "status": str(item.get("status") or "draft").strip() or "draft",
                "params": params,
            }
        )
    return normalized


def _resolve_source_artifact(source_job_id: str, source_artifact_id: str = "") -> dict:
    artifact = (
        get_job_artifact(source_job_id, source_artifact_id)
        if source_artifact_id
        else get_final_job_artifact(source_job_id)
    )
    if not artifact:
        raise StudioEffectExportError(
            "source_artifact_not_found",
            "Source artifact does not exist or is not downloadable.",
            status_code=404,
        )

    file_path = artifact.get("file_path") or ""
    if not file_path or not os.path.exists(file_path):
        raise StudioEffectExportError(
            "source_artifact_not_found",
            "Source artifact file does not exist or is not downloadable.",
            status_code=404,
        )

    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext and file_ext not in SUPPORTED_AUDIO_EXTENSIONS:
        raise StudioEffectExportError(
            "source_artifact_not_audio",
            "Source artifact is not a supported audio file.",
            status_code=422,
        )
    return artifact


def _db_to_linear(db_value: float) -> float:
    return max(0.001, min(1.0, math.pow(10.0, db_value / 20.0)))


def _build_ffmpeg_filters(effect_rack: list[dict]) -> tuple[list[str], list[dict], list[dict]]:
    filters: list[str] = []
    applied_effects: list[dict] = []
    unsupported_effects: list[dict] = []

    for slot in effect_rack:
        if not slot.get("enabled"):
            continue
        slot_id = slot.get("id") or ""
        params = slot.get("params") or {}

        if slot_id == "eq":
            eq_bands = [
                ("low", 100),
                ("mid", 1000),
                ("high", 8000),
            ]
            applied_params = {}
            for param_name, frequency in eq_bands:
                gain = float(params.get(param_name) or 0)
                if gain == 0:
                    continue
                filters.append(f"equalizer=f={frequency}:t=q:w=1:g={gain}")
                applied_params[param_name] = _compact_number(gain)
            if applied_params:
                applied_effects.append({"id": "eq", "params": applied_params})
            continue

        if slot_id == "compressor":
            if "threshold" not in params and "ratio" not in params:
                continue
            threshold_db = float(params.get("threshold", -18))
            ratio = float(params.get("ratio", 2))
            filters.append(f"acompressor=threshold={_db_to_linear(threshold_db):.6f}:ratio={ratio:.3f}")
            applied_effects.append(
                {
                    "id": "compressor",
                    "params": {
                        "threshold": _compact_number(threshold_db),
                        "ratio": _compact_number(ratio),
                    },
                }
            )
            continue

        if slot_id == "limiter":
            if "ceiling" not in params:
                continue
            ceiling_db = float(params.get("ceiling", -1))
            filters.append(f"alimiter=limit={_db_to_linear(ceiling_db):.6f}")
            applied_effects.append({"id": "limiter", "params": {"ceiling": _compact_number(ceiling_db)}})
            continue

        if slot_id == "reverb":
            unsupported_effects.append(
                {
                    "id": "reverb",
                    "reason": "ffmpeg_dsp_v0 does not implement reverb yet.",
                }
            )

    return filters, applied_effects, unsupported_effects


def _run_ffmpeg_render(source_path: str, output_path: str, effect_rack: list[dict]) -> tuple[list[dict], list[dict], list[str], str]:
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        raise StudioEffectExportError(
            "ffmpeg_not_available",
            "ffmpeg is not available on this machine.",
            status_code=503,
        )

    filters, applied_effects, unsupported_effects = _build_ffmpeg_filters(effect_rack)
    command = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-i",
        source_path,
        "-vn",
    ]
    if filters:
        command.extend(["-af", ",".join(filters)])
    command.extend(["-ar", "44100", "-ac", "2", output_path])

    try:
        completed = subprocess.run(
            command,
            shell=False,
            capture_output=True,
            text=True,
            timeout=RENDER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = (exc.stderr or "")[:1000]
        raise StudioEffectExportError(
            "ffmpeg_render_failed",
            f"ffmpeg render timed out. {stderr}".strip(),
            status_code=500,
        ) from exc

    if completed.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
        stderr = (completed.stderr or completed.stdout or "ffmpeg render failed")[:1000]
        raise StudioEffectExportError(
            "ffmpeg_render_failed",
            f"ffmpeg render failed: {stderr}",
            status_code=500,
        )

    return applied_effects, unsupported_effects, command, ffmpeg_path


def _validate_track_and_source(track_id: str, source_job_id: str) -> dict:
    track = get_track(track_id)
    if not track:
        raise StudioEffectExportError("track_not_found", "Track does not exist.", status_code=404)

    job = get_job_row(source_job_id)
    if not job:
        raise StudioEffectExportError("source_job_not_found", "Source job does not exist.", status_code=404)
    if (job.get("track_id") or "") != track_id:
        raise StudioEffectExportError(
            "source_job_not_for_track",
            "Source job does not belong to the requested track.",
            status_code=422,
        )
    return job


def _export_copy_only_draft(
    *,
    track_id: str,
    source_job_id: str,
    source_artifact_id: str,
    source_path: str,
    normalized_rack: list[dict],
    export_profile: str,
    note: str,
) -> dict:
    stage_dir = os.path.join(ensure_job_dirs(source_job_id)["artifacts"], EXPORT_STAGE_NAME)
    os.makedirs(stage_dir, exist_ok=True)
    file_ext = os.path.splitext(source_path)[1].lower() or ".wav"
    draft_token = uuid.uuid4().hex[:12]
    draft_path = os.path.join(stage_dir, f"studio_effect_draft_{draft_token}{file_ext}")
    shutil.copy2(source_path, draft_path)

    metadata = {
        "source_job_id": source_job_id,
        "source_artifact_id": source_artifact_id,
        "track_id": track_id,
        "effect_rack": normalized_rack,
        "export_profile": export_profile,
        "render_engine": COPY_ONLY_RENDER_ENGINE,
        "processing_mode": PROCESSING_MODE,
        "warning": EXPORT_WARNING,
    }
    if note:
        metadata["note"] = note[:500]

    artifact_id = register_job_artifact(
        source_job_id,
        EXPORT_STAGE_NAME,
        EXPORT_ARTIFACT_TYPE,
        draft_path,
        is_final=False,
        mirror_into_job_dir=False,
        metadata=metadata,
    )
    if not artifact_id:
        raise StudioEffectExportError(
            "studio_effect_export_failed",
            "Failed to register Studio effect draft artifact.",
            status_code=500,
        )

    log_stage(
        source_job_id,
        EXPORT_STAGE_NAME,
        "completed",
        "studio effect draft exported (copy only, no DSP)",
        {
            "artifact_id": artifact_id,
            "artifact_type": EXPORT_ARTIFACT_TYPE,
            "render_engine": COPY_ONLY_RENDER_ENGINE,
            "processing_mode": PROCESSING_MODE,
            "source_artifact_id": source_artifact_id,
            "track_id": track_id,
        },
    )

    return {
        "ok": True,
        "render_engine": COPY_ONLY_RENDER_ENGINE,
        "processing_mode": PROCESSING_MODE,
        "track_id": track_id,
        "source_job_id": source_job_id,
        "source_artifact_id": source_artifact_id,
        "artifact_id": artifact_id,
        "artifact_type": EXPORT_ARTIFACT_TYPE,
        "download_url": f"/api/jobs/{source_job_id}/artifacts/{artifact_id}/download",
        "studio_url": f"/studio?track_id={track_id}&job_id={source_job_id}&artifact_id={artifact_id}",
        "message": "已登记处理版草稿；当前为复制源音频，不包含真实 DSP/VST 处理。",
        "effect_rack": normalized_rack,
        "metadata": json.loads(json.dumps(metadata, ensure_ascii=False)),
    }


def _export_ffmpeg_render(
    *,
    track_id: str,
    source_job_id: str,
    source_artifact_id: str,
    source_path: str,
    normalized_rack: list[dict],
    export_profile: str,
    note: str,
) -> dict:
    stage_dir = os.path.join(ensure_job_dirs(source_job_id)["artifacts"], RENDER_STAGE_NAME)
    os.makedirs(stage_dir, exist_ok=True)
    render_token = uuid.uuid4().hex[:12]
    render_path = os.path.join(stage_dir, f"studio_effect_render_{render_token}.wav")
    applied_effects, unsupported_effects, command, ffmpeg_path = _run_ffmpeg_render(
        source_path,
        render_path,
        normalized_rack,
    )

    metadata = {
        "source_job_id": source_job_id,
        "source_artifact_id": source_artifact_id,
        "track_id": track_id,
        "effect_rack": normalized_rack,
        "export_profile": export_profile,
        "render_engine": FFMPEG_RENDER_ENGINE,
        "processing_mode": FFMPEG_PROCESSING_MODE,
        "applied_effects": applied_effects,
        "unsupported_effects": unsupported_effects,
        "ffmpeg_path": ffmpeg_path,
        "ffmpeg_filtergraph": ",".join(command[command.index("-af") + 1:command.index("-ar")]) if "-af" in command else "",
    }
    if note:
        metadata["note"] = note[:500]

    artifact_id = register_job_artifact(
        source_job_id,
        RENDER_STAGE_NAME,
        RENDER_ARTIFACT_TYPE,
        render_path,
        is_final=False,
        mirror_into_job_dir=False,
        metadata=metadata,
    )
    if not artifact_id:
        raise StudioEffectExportError(
            "studio_effect_render_failed",
            "Failed to register Studio effect render artifact.",
            status_code=500,
        )

    log_stage(
        source_job_id,
        RENDER_STAGE_NAME,
        "completed",
        "studio effect render exported (ffmpeg DSP v0)",
        {
            "artifact_id": artifact_id,
            "artifact_type": RENDER_ARTIFACT_TYPE,
            "render_engine": FFMPEG_RENDER_ENGINE,
            "processing_mode": FFMPEG_PROCESSING_MODE,
            "applied_effects": applied_effects,
            "unsupported_effects": unsupported_effects,
            "source_artifact_id": source_artifact_id,
            "track_id": track_id,
        },
    )

    return {
        "ok": True,
        "render_engine": FFMPEG_RENDER_ENGINE,
        "processing_mode": FFMPEG_PROCESSING_MODE,
        "track_id": track_id,
        "source_job_id": source_job_id,
        "source_artifact_id": source_artifact_id,
        "artifact_id": artifact_id,
        "artifact_type": RENDER_ARTIFACT_TYPE,
        "download_url": f"/api/jobs/{source_job_id}/artifacts/{artifact_id}/download",
        "studio_url": f"/studio?track_id={track_id}&job_id={source_job_id}&artifact_id={artifact_id}",
        "message": "已完成 ffmpeg DSP v0 渲染；当前不包含 VST 处理。",
        "effect_rack": normalized_rack,
        "applied_effects": applied_effects,
        "unsupported_effects": unsupported_effects,
        "metadata": json.loads(json.dumps(metadata, ensure_ascii=False)),
    }


def export_effect_rack_draft(
    *,
    track_id: str,
    source_job_id: str,
    source_artifact_id: str = "",
    effect_rack: Any,
    export_profile: str = "studio_balanced",
    note: str = "",
    render_engine: str = COPY_ONLY_RENDER_ENGINE,
) -> dict:
    track_id = (track_id or "").strip()
    source_job_id = (source_job_id or "").strip()
    source_artifact_id = (source_artifact_id or "").strip()
    export_profile = (export_profile or "studio_balanced").strip() or "studio_balanced"
    note = (note or "").strip()
    render_engine = (render_engine or COPY_ONLY_RENDER_ENGINE).strip() or COPY_ONLY_RENDER_ENGINE

    if render_engine not in {COPY_ONLY_RENDER_ENGINE, FFMPEG_RENDER_ENGINE}:
        raise StudioEffectExportError(
            "unsupported_render_engine",
            f"Unsupported render engine: {render_engine}",
            status_code=422,
        )

    _validate_track_and_source(track_id, source_job_id)
    normalized_rack = normalize_effect_rack_payload(effect_rack)
    source_artifact = _resolve_source_artifact(source_job_id, source_artifact_id)
    source_artifact_id = source_artifact.get("artifact_id") or source_artifact_id
    source_path = source_artifact["file_path"]

    if render_engine == COPY_ONLY_RENDER_ENGINE:
        return _export_copy_only_draft(
            track_id=track_id,
            source_job_id=source_job_id,
            source_artifact_id=source_artifact_id,
            source_path=source_path,
            normalized_rack=normalized_rack,
            export_profile=export_profile,
            note=note,
        )
    return _export_ffmpeg_render(
        track_id=track_id,
        source_job_id=source_job_id,
        source_artifact_id=source_artifact_id,
        source_path=source_path,
        normalized_rack=normalized_rack,
        export_profile=export_profile,
        note=note,
    )
