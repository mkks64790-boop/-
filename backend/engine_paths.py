from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_ROOT = PROJECT_ROOT / "external"


def _env_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def _pick_first_existing(*paths: str | Path) -> Path:
    candidates = [Path(path) for path in paths if path]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0] if candidates else Path("")


def _port_from_env(name: str, default: int) -> int:
    try:
        return int(_env_value(name) or default)
    except ValueError:
        return default


def _base_url_from_port(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/") if value else ""


RVC_PRIMARY_PORT = _port_from_env("FEISHARK_RVC_PORT", 7866)
RVC_BACKUP_PORT = _port_from_env("FEISHARK_RVC_BACKUP_PORT", 7865)

RVC_WEBUI_DIR = str(
    _pick_first_existing(
        _env_value("FEISHARK_RVC_DIR"),
        EXTERNAL_ROOT / "rvc-webui",
        EXTERNAL_ROOT / "rvc",
        r"D:\RVC\RVCv2",
        r"D:\RVC\RVC",
        r"C:\Users\ASUS\WorkBuddy\20260427153731\RVC-WebUI",
    )
)
RVC_WEBUI_BACKUP_DIR = str(
    _pick_first_existing(
        _env_value("FEISHARK_RVC_BACKUP_DIR"),
        EXTERNAL_ROOT / "rvc-webui-backup",
        EXTERNAL_ROOT / "rvc-qiufeng",
        "",
    )
)

RVC_WEIGHT_ROOT = str(Path(RVC_WEBUI_DIR) / "assets" / "weights") if RVC_WEBUI_DIR else ""
RVC_INDEX_ROOT = str(Path(RVC_WEBUI_DIR) / "assets" / "indices") if RVC_WEBUI_DIR else ""
RVC_LOGS_ROOT = str(Path(RVC_WEBUI_DIR) / "logs") if RVC_WEBUI_DIR else ""

RVC_BACKUP_WEIGHT_ROOT = (
    str(Path(RVC_WEBUI_BACKUP_DIR) / "assets" / "weights") if RVC_WEBUI_BACKUP_DIR else ""
)
RVC_BACKUP_INDEX_ROOT = (
    str(Path(RVC_WEBUI_BACKUP_DIR) / "assets" / "indices") if RVC_WEBUI_BACKUP_DIR else ""
)
RVC_BACKUP_LOGS_ROOT = str(Path(RVC_WEBUI_BACKUP_DIR) / "logs") if RVC_WEBUI_BACKUP_DIR else ""

RVC_API_BASE = _normalize_base_url(_env_value("FEISHARK_RVC_API"))
RVC_BACKUP_API_BASE = _normalize_base_url(_env_value("FEISHARK_RVC_BACKUP_API"))


def candidate_rvc_bases(*, include_backup: bool = True) -> list[str]:
    bases: list[str] = []
    for value in [
        RVC_API_BASE,
        _base_url_from_port(RVC_PRIMARY_PORT),
        RVC_BACKUP_API_BASE if include_backup else "",
        _base_url_from_port(RVC_BACKUP_PORT) if include_backup else "",
    ]:
        base = _normalize_base_url(value)
        if base and base not in bases:
            bases.append(base)
    return bases


RVC_FALLBACK_BASES = candidate_rvc_bases(include_backup=True)


def _rvc_python(root: str, *, backup: bool = False) -> str:
    env_name = "FEISHARK_RVC_BACKUP_PYTHON" if backup else "FEISHARK_RVC_PYTHON"
    return str(
        _pick_first_existing(
            _env_value(env_name),
            Path(root) / "runtime" / "python.exe" if root else "",
            Path(root) / "venv" / "Scripts" / "python.exe" if root else "",
            _env_value("FEISHARK_RVC_PYTHON") if backup else "",
            r"D:\Miniconda3\envs\rvc\python.exe",
            sys.executable,
        )
    )


RVC_PYTHON = _rvc_python(RVC_WEBUI_DIR)
RVC_BACKUP_PYTHON = _rvc_python(RVC_WEBUI_BACKUP_DIR, backup=True)


def rvc_engine_paths(kind: str = "primary") -> dict:
    normalized = (kind or "primary").strip().lower()
    backup = normalized in {"backup", "rvc_webui_backup", "qiufeng", "rvc_qiufeng"}
    root = RVC_WEBUI_BACKUP_DIR if backup else RVC_WEBUI_DIR
    port = RVC_BACKUP_PORT if backup else RVC_PRIMARY_PORT
    configured_base = RVC_BACKUP_API_BASE if backup else RVC_API_BASE
    return {
        "engine_key": "rvc_webui_backup" if backup else "rvc_webui",
        "source_engine": "rvc_webui_backup" if backup else "rvc_webui",
        "origin_kind": "external_rvc_backup" if backup else "external_rvc_primary",
        "root": root,
        "python": RVC_BACKUP_PYTHON if backup else RVC_PYTHON,
        "weights": RVC_BACKUP_WEIGHT_ROOT if backup else RVC_WEIGHT_ROOT,
        "indices": RVC_BACKUP_INDEX_ROOT if backup else RVC_INDEX_ROOT,
        "logs": RVC_BACKUP_LOGS_ROOT if backup else RVC_LOGS_ROOT,
        "port": port,
        "base_url": configured_base or _base_url_from_port(port),
        "train_capable": not backup,
    }


AUDIO_PIPELINE_DIR = str(
    _pick_first_existing(
        _env_value("FEISHARK_AUDIO_PIPELINE"),
        EXTERNAL_ROOT / "audio-pipeline",
        r"D:\AudioPipeline",
        r"C:\Users\ASUS\AudioPipeline",
    )
)
AUDIO_PIPELINE_VENV = str(
    _pick_first_existing(
        _env_value("FEISHARK_AUDIO_PIPELINE_PYTHON"),
        Path(AUDIO_PIPELINE_DIR) / "venv" / "Scripts" / "python.exe" if AUDIO_PIPELINE_DIR else "",
    )
)
UVR5_MODEL_PATH = _env_value("FEISHARK_UVR5_MODEL") or str(
    Path(AUDIO_PIPELINE_DIR) / "models" / "UVR-MDX-NET-Voc_FT.onnx"
)


def audio_pipeline_paths() -> dict:
    return {
        "engine_key": "uvr",
        "root": AUDIO_PIPELINE_DIR,
        "python": AUDIO_PIPELINE_VENV,
        "model": UVR5_MODEL_PATH,
    }
