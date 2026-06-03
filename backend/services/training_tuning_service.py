from __future__ import annotations

from typing import Any


TRAINING_PRESETS = {
    "fast_preview": {
        "preset_key": "fast_preview",
        "label": "快速预览",
        "epochs": 30,
        "batch_size": 6,
        "sample_rate": "40k",
        "f0_enabled": True,
        "index_enabled": True,
        "gpu_risk_label": "低",
        "estimated_runtime_label": "较短，适合先确认音色方向",
        "notes": [
            "用于快速确认素材和音色方向，不建议作为最终发布模型。",
            "如果声音方向正确，再切换到 balanced 或 quality。",
        ],
    },
    "balanced": {
        "preset_key": "balanced",
        "label": "均衡推荐",
        "epochs": 90,
        "batch_size": 8,
        "sample_rate": "40k",
        "f0_enabled": True,
        "index_enabled": True,
        "gpu_risk_label": "中",
        "estimated_runtime_label": "中等，适合大多数本地训练",
        "notes": [
            "推荐默认档，兼顾时间和模型稳定性。",
            "适合已经通过素材预检的单文件长样本或多文件素材集。",
        ],
    },
    "quality": {
        "preset_key": "quality",
        "label": "高质量慢速",
        "epochs": 150,
        "batch_size": 6,
        "sample_rate": "40k",
        "f0_enabled": True,
        "index_enabled": True,
        "gpu_risk_label": "高",
        "estimated_runtime_label": "较长，请确认 GPU 空闲和散热稳定",
        "notes": [
            "适合最终模型打磨，耗时和显存风险更高。",
            "训练前建议先用 fast_preview 或 balanced 验证素材质量。",
        ],
    },
}

SUPPORTED_SAMPLE_RATES = {"32k", "40k", "48k"}
MIN_EPOCHS = 1
MAX_EPOCHS = 300
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 32


def list_training_presets() -> dict:
    return {
        "items": [TRAINING_PRESETS[key] for key in ["fast_preview", "balanced", "quality"]],
        "default_preset": "balanced",
        "read_only": True,
    }


def normalize_training_config(
    raw_config: dict | None = None,
    *,
    preset_key: str = "",
    overrides: dict | None = None,
) -> dict:
    raw_config = raw_config if isinstance(raw_config, dict) else {}
    overrides = overrides if isinstance(overrides, dict) else {}
    selected_key = (
        str(overrides.get("preset_key") or "").strip()
        or preset_key.strip()
        or str(raw_config.get("preset_key") or "").strip()
        or "balanced"
    )
    preset = TRAINING_PRESETS.get(selected_key) or TRAINING_PRESETS["balanced"]
    warnings: list[str] = []
    if selected_key not in TRAINING_PRESETS:
        warnings.append(f"unknown preset_key '{selected_key}', fallback to balanced")

    merged = {**preset, **raw_config, **{k: v for k, v in overrides.items() if v not in (None, "")}}
    sample_rate = str(merged.get("sample_rate") or preset["sample_rate"]).strip()
    if sample_rate not in SUPPORTED_SAMPLE_RATES:
        raise ValueError(f"unsupported sample_rate: {sample_rate}")

    epochs, epochs_warning = _clamped_int(merged.get("epochs"), preset["epochs"], MIN_EPOCHS, MAX_EPOCHS, "epochs")
    batch_size, batch_warning = _clamped_int(
        merged.get("batch_size"),
        preset["batch_size"],
        MIN_BATCH_SIZE,
        MAX_BATCH_SIZE,
        "batch_size",
    )
    warnings.extend(item for item in [epochs_warning, batch_warning] if item)

    config = {
        "preset_key": preset["preset_key"],
        "epochs": epochs,
        "batch_size": batch_size,
        "sample_rate": sample_rate,
        "f0_enabled": _as_bool(merged.get("f0_enabled"), bool(preset["f0_enabled"])),
        "index_enabled": _as_bool(merged.get("index_enabled"), bool(preset["index_enabled"])),
        "pitch_guidance": str(merged.get("pitch_guidance") or "default"),
        "created_by": str(merged.get("created_by") or "training_tuning_v0"),
        "warnings": warnings,
    }
    return config


def training_config_summary(config: dict | None) -> str:
    config = normalize_training_config(config or {})
    return (
        f"{config['preset_key']} · {config['epochs']} epochs · batch {config['batch_size']} · "
        f"{config['sample_rate']} · f0={'on' if config['f0_enabled'] else 'off'} · "
        f"index={'on' if config['index_enabled'] else 'off'}"
    )


def build_rvc_train_runtime_options(config: dict | None = None) -> dict:
    normalized = normalize_training_config(config or {})
    return {
        "training_config": normalized,
        "epochs": normalized["epochs"],
        "batch_size": normalized["batch_size"],
        "sample_rate": normalized["sample_rate"],
        "f0_enabled": normalized["f0_enabled"],
        "index_enabled": normalized["index_enabled"],
        "pitch_guidance": normalized["pitch_guidance"],
    }


def estimate_training(
    *,
    preset_key: str = "balanced",
    duration_seconds: float = 0.0,
    file_count: int = 1,
    gpu_label: str = "",
) -> dict:
    preset = TRAINING_PRESETS.get(preset_key) or TRAINING_PRESETS["balanced"]
    duration_seconds = max(0.0, float(duration_seconds or 0.0))
    file_count = max(1, int(file_count or 1))
    duration_minutes = duration_seconds / 60.0

    risk_score = 0
    notes = list(preset["notes"])
    if preset["preset_key"] == "quality":
        risk_score += 2
    elif preset["preset_key"] == "balanced":
        risk_score += 1
    if duration_minutes >= 45:
        risk_score += 2
        notes.append("素材较长，建议确认磁盘空间、GPU 空闲和训练超时配置。")
    elif duration_minutes >= 20:
        risk_score += 1
        notes.append("素材时长适中，训练前建议关闭其他高负载任务。")
    if file_count >= 8:
        risk_score += 1
        notes.append("多文件素材会增加预处理耗时，请确认文件命名和质量一致。")
    if gpu_label:
        notes.append(f"当前 GPU/算力提示：{gpu_label}")

    if risk_score >= 4:
        gpu_risk_label = "高"
        estimated_runtime_label = "较长，建议仅在算力空闲时运行"
    elif risk_score >= 2:
        gpu_risk_label = "中"
        estimated_runtime_label = "中等，请保持本地 RVC 环境稳定"
    else:
        gpu_risk_label = "低"
        estimated_runtime_label = "较短，适合先做训练预览"

    return {
        "preset_key": preset["preset_key"],
        "preset": preset,
        "duration_seconds": duration_seconds,
        "duration_minutes": round(duration_minutes, 2),
        "file_count": file_count,
        "epochs": preset["epochs"],
        "batch_size": preset["batch_size"],
        "sample_rate": preset["sample_rate"],
        "f0_enabled": preset["f0_enabled"],
        "index_enabled": preset["index_enabled"],
        "gpu_risk_label": gpu_risk_label,
        "estimated_runtime_label": estimated_runtime_label,
        "submission_creates_job": False,
        "notes": notes,
    }


def _clamped_int(value: Any, default: int, min_value: int, max_value: int, field_name: str) -> tuple[int, str]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default, f"{field_name} invalid, fallback to {default}"
    clamped = max(min_value, min(parsed, max_value))
    if clamped != parsed:
        return clamped, f"{field_name} clamped from {parsed} to {clamped}"
    return clamped, ""


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "y"}:
        return True
    if normalized in {"0", "false", "no", "off", "n"}:
        return False
    return default
