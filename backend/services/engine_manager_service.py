from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable

import requests

try:
    from ..engine_paths import (
        AUDIO_PIPELINE_DIR,
        AUDIO_PIPELINE_VENV,
        RVC_API_BASE,
        RVC_BACKUP_API_BASE,
        RVC_BACKUP_INDEX_ROOT,
        RVC_BACKUP_LOGS_ROOT,
        RVC_BACKUP_WEIGHT_ROOT,
        RVC_FALLBACK_BASES,
        RVC_INDEX_ROOT,
        RVC_LOGS_ROOT,
        RVC_WEBUI_BACKUP_DIR,
        RVC_WEBUI_DIR,
        RVC_WEIGHT_ROOT,
        UVR5_MODEL_PATH,
    )
    from ..services.model_service import list_models
    from ..voice_changer import (
        COVER_INFERENCE_MODE,
        TRAIN_BACKEND_MODE,
    )
except ImportError:
    from engine_paths import (
        AUDIO_PIPELINE_DIR,
        AUDIO_PIPELINE_VENV,
        RVC_API_BASE,
        RVC_BACKUP_API_BASE,
        RVC_BACKUP_INDEX_ROOT,
        RVC_BACKUP_LOGS_ROOT,
        RVC_BACKUP_WEIGHT_ROOT,
        RVC_FALLBACK_BASES,
        RVC_INDEX_ROOT,
        RVC_LOGS_ROOT,
        RVC_WEBUI_BACKUP_DIR,
        RVC_WEBUI_DIR,
        RVC_WEIGHT_ROOT,
        UVR5_MODEL_PATH,
    )
    from services.model_service import list_models
    from voice_changer import (
        COVER_INFERENCE_MODE,
        TRAIN_BACKEND_MODE,
    )


ENGINE_KEYS = {"rvc_webui", "rvc_webui_backup", "uvr", "svc_fallback"}
PROBE_TIMEOUT = float(os.environ.get("FEISHARK_ENGINE_PROBE_TIMEOUT", "0.8"))
MAX_RVC_MODEL_FILES = int(os.environ.get("FEISHARK_ENGINE_SCAN_LIMIT", "400"))
RVC_SCAN_CACHE_TTL_SECONDS = float(os.environ.get("FEISHARK_RVC_SCAN_CACHE_TTL", "20"))
_RVC_MODEL_SCAN_CACHE: dict[str, object] = {"expires_at": 0.0, "items": [], "root_key": ""}


def list_engines(project_root: str, weights_dir: str) -> list[dict]:
    return [
        get_rvc_engine(project_root, weights_dir, include_models=False),
        get_rvc_backup_engine(project_root, weights_dir, include_models=False),
        get_uvr_engine(),
        get_svc_fallback_engine(),
    ]


def get_engine(engine_key: str, project_root: str, weights_dir: str) -> dict | None:
    normalized = _normalize_engine_key(engine_key)
    if normalized == "rvc_webui":
        return get_rvc_engine(project_root, weights_dir, include_models=False)
    if normalized == "rvc_webui_backup":
        return get_rvc_backup_engine(project_root, weights_dir, include_models=False)
    if normalized == "uvr":
        return get_uvr_engine()
    if normalized == "svc_fallback":
        return get_svc_fallback_engine()
    return None


def scan_engines(project_root: str, weights_dir: str, *, force: bool = False) -> dict:
    if force:
        _clear_rvc_model_cache()
    return {
        "read_only": True,
        "engines": list_engines(project_root, weights_dir),
        "force": bool(force),
    }


def list_rvc_models(
    project_root: str,
    weights_dir: str,
    *,
    limit: int = 50,
    offset: int = 0,
    q: str = "",
    registered: str = "all",
    has_index: str = "all",
    engine_key: str = "rvc_webui",
    force: bool = False,
) -> dict:
    normalized_engine_key = _normalize_engine_key(engine_key)
    engine = (
        get_rvc_backup_engine(project_root, weights_dir, force=force)
        if normalized_engine_key == "rvc_webui_backup"
        else get_rvc_engine(project_root, weights_dir, force=force)
    )
    filtered = _filter_rvc_models(
        engine["models"],
        q=q,
        registered=registered,
        has_index=has_index,
    )
    safe_limit = max(1, min(int(limit or 50), 200))
    safe_offset = max(0, int(offset or 0))
    items = filtered[safe_offset:safe_offset + safe_limit]
    return {
        "engine_key": engine["engine_key"],
        "source_engine": engine["engine_key"],
        "root_path": engine["root_path"],
        "status": engine["status"],
        "read_only": True,
        "total": len(filtered),
        "limit": safe_limit,
        "offset": safe_offset,
        "items": items,
        "model_count": len(engine["models"]),
        "models": items,
        "registered": registered,
        "has_index": has_index,
        "q": q,
        "requested_engine_key": engine_key,
        "warnings": engine["warnings"],
        "next_step": engine["next_step"],
    }


def get_rvc_engine(
    project_root: str,
    weights_dir: str,
    *,
    include_models: bool = True,
    force: bool = False,
) -> dict:
    root = Path(RVC_WEBUI_DIR) if RVC_WEBUI_DIR else Path("")
    weight_root = Path(RVC_WEIGHT_ROOT) if RVC_WEIGHT_ROOT else root / "assets" / "weights"
    index_root = Path(RVC_INDEX_ROOT) if RVC_INDEX_ROOT else root / "assets" / "indices"
    logs_root = root / "logs"
    base_url = _discover_online_rvc_base()
    scanned_models = _get_cached_rvc_models(
        root,
        weight_root,
        index_root,
        logs_root,
        project_root,
        weights_dir,
        force=force,
    )

    checks = [
        _path_check("rvc_root", root, "dir"),
        _url_check("rvc_webui", base_url or _candidate_rvc_bases()[0] if _candidate_rvc_bases() else ""),
        _path_check("rvc_weights_dir", weight_root, "dir"),
        _path_check("rvc_indices_dir", index_root, "dir"),
        _path_check("rvc_logs_dir", logs_root, "dir"),
        _path_check("rvc_infer_web", root / "infer-web.py", "file"),
        _path_check("rvc_train_script", root / "infer" / "modules" / "train" / "train.py", "file"),
    ]
    warnings = [f"{item['check']} missing" for item in checks if not item["ok"] and item["check"] != "rvc_webui"]
    if not base_url:
        warnings.append("rvc_webui offline")

    root_exists = root.is_dir()
    if not root_exists:
        status = "not_configured"
        next_step = "配置 FEISHARK_RVC_DIR，或确认本机第三方 RVC 根目录存在。"
    elif not base_url:
        status = "offline"
        next_step = "启动本机 RVC WebUI，并确认 Gradio API 地址可访问。"
    elif warnings:
        status = "degraded"
        next_step = "补齐缺失的 RVC 目录或脚本后再执行训练/翻唱。"
    else:
        status = "online"
        next_step = "RVC WebUI 已在线，可用于翻唱推理；训练仍通过本地 RVC 脚本执行。"

    return {
        "engine_key": "rvc_webui",
        "label": "RVC WebUI",
        "status": status,
        "role": "voice_conversion",
        "base_url": base_url or (_candidate_rvc_bases()[0] if _candidate_rvc_bases() else ""),
        "root_path": str(root),
        "detected": root_exists or bool(base_url),
        "read_only": True,
        "checks": checks,
        "models": scanned_models if include_models else [],
        "model_count": len(scanned_models),
        "registered_model_count": sum(1 for item in scanned_models if item.get("registered")),
        "warnings": warnings,
        "next_step": next_step,
        "cover_inference_mode": COVER_INFERENCE_MODE,
        "train_backend_mode": TRAIN_BACKEND_MODE,
    }


def get_rvc_backup_engine(
    project_root: str,
    weights_dir: str,
    *,
    include_models: bool = True,
    force: bool = False,
) -> dict:
    root = Path(RVC_WEBUI_BACKUP_DIR) if RVC_WEBUI_BACKUP_DIR else Path("")
    weight_root = Path(RVC_BACKUP_WEIGHT_ROOT) if RVC_BACKUP_WEIGHT_ROOT else root / "assets" / "weights"
    index_root = Path(RVC_BACKUP_INDEX_ROOT) if RVC_BACKUP_INDEX_ROOT else root / "assets" / "indices"
    logs_root = Path(RVC_BACKUP_LOGS_ROOT) if RVC_BACKUP_LOGS_ROOT else root / "logs"
    base_candidates = _candidate_rvc_bases("rvc_webui_backup")
    base_url = _discover_online_rvc_base(base_candidates)
    scanned_models = _get_cached_rvc_models(
        root,
        weight_root,
        index_root,
        logs_root,
        project_root,
        weights_dir,
        engine_key="rvc_webui_backup",
        source="external_rvc_backup",
        force=force,
    )

    checks = [
        _path_check("rvc_backup_root", root, "dir"),
        _url_check("rvc_webui_backup", base_url or (base_candidates[0] if base_candidates else "")),
        _path_check("rvc_backup_weights_dir", weight_root, "dir"),
        _path_check("rvc_backup_indices_dir", index_root, "dir"),
        _path_check("rvc_backup_logs_dir", logs_root, "dir"),
        _path_check("rvc_backup_infer_web", root / "infer-web.py", "file"),
        _path_check("rvc_backup_train_script", root / "infer" / "modules" / "train" / "train.py", "file"),
    ]
    warnings = [
        f"{item['check']} missing"
        for item in checks
        if not item["ok"] and item["check"] != "rvc_webui_backup"
    ]
    if not base_url:
        warnings.append("rvc_webui_backup offline")

    root_exists = root.is_dir()
    if not root_exists:
        status = "not_configured"
        next_step = "Place the backup RVC-WebUI in external/rvc-webui-backup or set FEISHARK_RVC_BACKUP_DIR."
    elif not base_url:
        status = "offline"
        next_step = "Start the backup RVC WebUI on its configured backup port before using it."
    elif warnings:
        status = "degraded"
        next_step = "Complete the missing backup RVC files before using it."
    else:
        status = "online"
        next_step = "Backup RVC is online for inference fallback. Training remains primary-only."

    return {
        "engine_key": "rvc_webui_backup",
        "label": "RVC WebUI Backup",
        "status": status,
        "role": "voice_conversion_backup",
        "base_url": base_url or (base_candidates[0] if base_candidates else ""),
        "root_path": str(root),
        "detected": root_exists or bool(base_url),
        "read_only": True,
        "checks": checks,
        "models": scanned_models if include_models else [],
        "model_count": len(scanned_models),
        "registered_model_count": sum(1 for item in scanned_models if item.get("registered")),
        "warnings": warnings,
        "next_step": next_step,
        "cover_inference_mode": COVER_INFERENCE_MODE,
        "train_backend_mode": TRAIN_BACKEND_MODE,
        "train_capable": False,
        "source": "external_rvc_backup",
        "source_engine": "rvc_webui_backup",
        "origin_kind": "external_rvc_backup",
    }


def get_uvr_engine() -> dict:
    root = Path(AUDIO_PIPELINE_DIR) if AUDIO_PIPELINE_DIR else Path("")
    runner_path = root / "run_uvr5_split.py"
    checks = [
        _path_check("uvr_root", root, "dir"),
        _path_check("uvr_python", Path(AUDIO_PIPELINE_VENV), "file"),
        _path_check("uvr_model", Path(UVR5_MODEL_PATH), "file"),
        _path_check("uvr_runner", runner_path, "file"),
    ]
    missing = [item for item in checks if not item["ok"]]
    if not root.is_dir():
        status = "not_configured"
        next_step = "如需启用 UVR 分离，请配置 FEISHARK_AUDIO_PIPELINE 并放置 UVR 模型。"
    elif missing:
        status = "degraded"
        next_step = "补齐 AudioPipeline venv、UVR 模型或 runner 后再执行分离。"
    else:
        status = "online"
        next_step = "UVR 本地分离入口已就绪。"

    models = []
    model_path = Path(UVR5_MODEL_PATH)
    if model_path.is_file():
        models.append(
            {
                "model_key": model_path.stem,
                "label": model_path.name,
                "path": str(model_path),
                "exists": True,
                "registered": False,
            }
        )

    return {
        "engine_key": "uvr",
        "label": "UVR / Vocal Separation",
        "status": status,
        "role": "source_separation",
        "base_url": "",
        "root_path": str(root),
        "detected": root.is_dir(),
        "read_only": True,
        "checks": checks,
        "models": models,
        "model_count": len(models),
        "warnings": [f"{item['check']} missing" for item in missing],
        "next_step": next_step,
    }


def get_svc_fallback_engine() -> dict:
    root_value = os.environ.get("FEISHARK_SVC_ROOT", "").strip()
    root = Path(root_value) if root_value else Path("")
    configured = bool(root_value)
    root_exists = configured and root.is_dir()
    checks = [_path_check("svc_root", root, "dir")] if configured else [
        {"check": "svc_root", "ok": False, "value": "", "kind": "dir", "detail": "FEISHARK_SVC_ROOT not configured"}
    ]

    if not configured:
        status = "not_configured"
        next_step = "本阶段仅预留 SVC/SVT 备用引擎契约；如需接入，请先配置 FEISHARK_SVC_ROOT。"
    elif not root_exists:
        status = "not_configured"
        next_step = "FEISHARK_SVC_ROOT 已配置但路径不存在，请修正为真实 SVC/SVT 根目录。"
    else:
        status = "degraded"
        next_step = "已检测到候选目录，但 FeiShark 尚未接入真实 SVC/SVT runner。"

    return {
        "engine_key": "svc_fallback",
        "label": "SVC / SVT Fallback",
        "status": status,
        "role": "svc_fallback",
        "base_url": "",
        "root_path": str(root) if configured else "",
        "detected": root_exists,
        "read_only": True,
        "checks": checks,
        "models": [],
        "model_count": 0,
        "warnings": [] if configured and root_exists else ["svc_fallback not configured"],
        "next_step": next_step,
    }


def _scan_rvc_models(
    root: Path,
    weight_root: Path,
    index_root: Path,
    logs_root: Path,
    project_root: str,
    weights_dir: str,
    *,
    engine_key: str = "rvc_webui",
    source: str = "external_rvc",
) -> list[dict]:
    if not root.is_dir():
        return []

    pth_files = _collect_files([weight_root, logs_root], ".pth")
    index_files = _collect_files([index_root, logs_root], ".index")
    registered = _registered_model_lookup(project_root, weights_dir)
    models: list[dict] = []
    seen: set[str] = set()

    for pth in pth_files:
        abs_key = _norm_path(pth)
        if abs_key in seen:
            continue
        seen.add(abs_key)
        pair = _pair_index(pth, index_files)
        matched = _match_registered_model(pth, pair, registered)
        models.append(
            {
                "model_key": pth.stem,
                "label": pth.stem,
                "pth_name": pth.name,
                "pth_path": str(pth),
                "pth_exists": pth.is_file(),
                "index_name": pair["path"].name if pair["path"] else "",
                "index_path": str(pair["path"]) if pair["path"] else "",
                "index_exists": bool(pair["path"] and pair["path"].is_file()),
                "paired_by": pair["paired_by"],
                "registered": bool(matched),
                "registered_model_id": matched.get("model_id", "") if matched else "",
                "registered_model_name": matched.get("model_name", "") if matched else "",
                "source": source,
                "source_engine": engine_key,
                "engine_key": engine_key,
                "origin_kind": "external_rvc_backup" if engine_key == "rvc_webui_backup" else "external_rvc_primary",
                "rvc_root": str(root),
            }
        )

    return sorted(models, key=lambda item: item["label"].lower())


def _get_cached_rvc_models(
    root: Path,
    weight_root: Path,
    index_root: Path,
    logs_root: Path,
    project_root: str,
    weights_dir: str,
    *,
    engine_key: str = "rvc_webui",
    source: str = "external_rvc",
    force: bool = False,
) -> list[dict]:
    now = time.monotonic()
    root_key = "|".join(str(item) for item in [engine_key, root, weight_root, index_root, logs_root])
    if (
        not force
        and _RVC_MODEL_SCAN_CACHE.get("root_key") == root_key
        and float(_RVC_MODEL_SCAN_CACHE.get("expires_at") or 0) > now
    ):
        return list(_RVC_MODEL_SCAN_CACHE.get("items") or [])

    items = _scan_rvc_models(
        root,
        weight_root,
        index_root,
        logs_root,
        project_root,
        weights_dir,
        engine_key=engine_key,
        source=source,
    )
    _RVC_MODEL_SCAN_CACHE["items"] = items
    _RVC_MODEL_SCAN_CACHE["expires_at"] = now + RVC_SCAN_CACHE_TTL_SECONDS
    _RVC_MODEL_SCAN_CACHE["root_key"] = root_key
    return items


def _clear_rvc_model_cache() -> None:
    _RVC_MODEL_SCAN_CACHE["items"] = []
    _RVC_MODEL_SCAN_CACHE["expires_at"] = 0.0
    _RVC_MODEL_SCAN_CACHE["root_key"] = ""


def _filter_rvc_models(
    models: list[dict],
    *,
    q: str = "",
    registered: str = "all",
    has_index: str = "all",
) -> list[dict]:
    query = (q or "").strip().lower()
    registered_filter = _normalize_tri_state(registered)
    index_filter = _normalize_tri_state(has_index)

    result = []
    for item in models:
        if query:
            haystack = " ".join(
                str(item.get(field) or "")
                for field in [
                    "model_key",
                    "label",
                    "pth_name",
                    "pth_path",
                    "index_name",
                    "index_path",
                    "registered_model_id",
                    "registered_model_name",
                    "source_engine",
                    "engine_key",
                    "origin_kind",
                    "rvc_root",
                ]
            ).lower()
            if query not in haystack:
                continue
        if registered_filter != "all" and bool(item.get("registered")) != (registered_filter == "true"):
            continue
        if index_filter != "all" and bool(item.get("index_exists")) != (index_filter == "true"):
            continue
        result.append(item)
    return result


def _normalize_tri_state(value: str) -> str:
    normalized = str(value or "all").strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return "true"
    if normalized in {"false", "0", "no", "n"}:
        return "false"
    return "all"


def _registered_model_lookup(project_root: str, weights_dir: str) -> list[dict]:
    try:
        rows = list_models(project_root, weights_dir, include_unavailable=True, include_smoke=True)
    except Exception:
        return []

    result = []
    for row in rows:
        candidates = {
            str(row.get("model_name") or "").lower(),
            str(row.get("model_id") or "").lower(),
            Path(str(row.get("resolved_pth_path") or "")).name.lower(),
            Path(str(row.get("resolved_index_path") or "")).name.lower(),
            Path(str(row.get("resolved_pth_path") or "")).stem.lower(),
            Path(str(row.get("resolved_index_path") or "")).stem.lower(),
        }
        result.append(
            {
                "model_id": row.get("model_id") or "",
                "model_name": row.get("model_name") or "",
                "pth_path": _norm_path(row.get("resolved_pth_path") or ""),
                "index_path": _norm_path(row.get("resolved_index_path") or ""),
                "candidates": {item for item in candidates if item},
            }
        )
    return result


def _match_registered_model(pth: Path, pair: dict, registered: list[dict]) -> dict | None:
    pth_norm = _norm_path(pth)
    index_norm = _norm_path(pair["path"]) if pair.get("path") else ""
    names = {pth.name.lower(), pth.stem.lower()}
    if pair.get("path"):
        names.update({pair["path"].name.lower(), pair["path"].stem.lower()})

    for item in registered:
        if pth_norm and pth_norm == item.get("pth_path"):
            return item
        if index_norm and index_norm == item.get("index_path"):
            return item
        if names.intersection(item.get("candidates") or set()):
            return item
    return None


def _collect_files(roots: Iterable[Path], suffix: str) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        try:
            iterator = root.rglob(f"*{suffix}") if root.name.lower() == "logs" else root.glob(f"*{suffix}")
            for path in iterator:
                if len(files) >= MAX_RVC_MODEL_FILES:
                    return files
                if not path.is_file():
                    continue
                key = _norm_path(path)
                if key in seen:
                    continue
                seen.add(key)
                files.append(path)
        except OSError:
            continue
    return files


def _pair_index(pth: Path, index_files: list[Path]) -> dict:
    pth_stem = pth.stem.lower()
    exact = [item for item in index_files if item.stem.lower() == pth_stem]
    if exact:
        return {"path": sorted(exact, key=lambda item: len(str(item)))[0], "paired_by": "exact_name"}

    contains = [
        item for item in index_files
        if pth_stem in item.stem.lower() or item.stem.lower() in pth_stem
    ]
    if contains:
        return {"path": sorted(contains, key=lambda item: len(str(item)))[0], "paired_by": "contains_name"}

    return {"path": None, "paired_by": "none"}


def _candidate_rvc_bases(engine_key: str = "rvc_webui") -> list[str]:
    bases: list[str] = []
    normalized = _normalize_engine_key(engine_key)
    if normalized == "rvc_webui_backup":
        if RVC_BACKUP_API_BASE:
            bases.append(RVC_BACKUP_API_BASE.rstrip("/"))
        for base in RVC_FALLBACK_BASES:
            base = base.rstrip("/")
            if base.endswith(":7865") and base not in bases:
                bases.append(base)
        if "http://127.0.0.1:7865" not in bases:
            bases.append("http://127.0.0.1:7865")
        return bases

    if RVC_API_BASE:
        bases.append(RVC_API_BASE.rstrip("/"))
    for base in RVC_FALLBACK_BASES:
        base = base.rstrip("/")
        if base not in bases:
            bases.append(base)
    return bases


def _discover_online_rvc_base(candidates: list[str] | None = None) -> str:
    for base_url in candidates or _candidate_rvc_bases():
        if _probe_rvc_base(base_url):
            return base_url
    return ""


def _probe_rvc_base(base_url: str) -> bool:
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/gradio_api/info", timeout=PROBE_TIMEOUT)
        if resp.status_code != 200:
            return False
        text = resp.text
        return "/infer_change_voice" in text and "/infer_convert" in text
    except Exception:
        return False


def _path_check(check: str, path: Path, kind: str) -> dict:
    ok = path.is_dir() if kind == "dir" else path.is_file()
    return {
        "check": check,
        "ok": bool(ok),
        "value": str(path),
        "kind": kind,
    }


def _url_check(check: str, value: str) -> dict:
    return {
        "check": check,
        "ok": bool(value and _probe_rvc_base(value)),
        "value": value,
        "kind": "url",
    }


def _normalize_engine_key(engine_key: str) -> str:
    normalized = (engine_key or "").strip().lower()
    aliases = {
        "rvc": "rvc_webui",
        "rvc_webui": "rvc_webui",
        "rvc_backup": "rvc_webui_backup",
        "rvc-webui-backup": "rvc_webui_backup",
        "rvc_webui_backup": "rvc_webui_backup",
        "rvc_qiufeng": "rvc_webui_backup",
        "qiufeng": "rvc_webui_backup",
        "uvr": "uvr",
        "svc": "svc_fallback",
        "svt": "svc_fallback",
        "svc_fallback": "svc_fallback",
    }
    return aliases.get(normalized, normalized)


def _norm_path(path: str | Path) -> str:
    if not path:
        return ""
    try:
        return str(Path(path).resolve()).lower()
    except Exception:
        return str(path).replace("\\", "/").lower()
