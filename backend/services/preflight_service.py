import importlib.util
import os
import shutil
import subprocess
from typing import Any

from gradio_client import Client
from gradio_client.exceptions import AppError

try:
    from ..services.model_service import get_voice_model, resolve_voice_model_file
    from ..services.audio_material_service import build_material_check
    from ..voice_changer import (
        get_rvc_service_status,
        _discover_rvc_base_url,
        _refresh_rvc_choices,
        _load_rvc_model,
        _sync_index_to_rvc_runtime,
        _sync_weight_to_rvc_runtime,
    )
    from ..model_trainer import (
        RVC_LOGS_DIR,
        RVC_PYTHON,
        RVC_WEBUI_DIR,
    )
    from ..db import PROJECT_ROOT
except ImportError:
    from services.model_service import get_voice_model, resolve_voice_model_file
    from services.audio_material_service import build_material_check
    from voice_changer import (
        get_rvc_service_status,
        _discover_rvc_base_url,
        _refresh_rvc_choices,
        _load_rvc_model,
        _sync_index_to_rvc_runtime,
        _sync_weight_to_rvc_runtime,
    )
    from model_trainer import (
        RVC_LOGS_DIR,
        RVC_PYTHON,
        RVC_WEBUI_DIR,
    )
    from db import PROJECT_ROOT


def _check_path(label: str, path: str, kind: str = "file") -> dict:
    ok = os.path.isdir(path) if kind == "dir" else os.path.isfile(path)
    return {"check": label, "ok": ok, "value": path, "kind": kind}


def _check_python_import(python_exe: str, module_name: str, cwd: str | None = None) -> dict:
    if not (python_exe and os.path.exists(python_exe)):
        return {"check": f"python_import:{module_name}", "ok": False, "value": python_exe, "detail": "python executable missing"}
    proc = subprocess.run(
        [python_exe, "-c", f"import {module_name}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        cwd=cwd,
    )
    return {
        "check": f"python_import:{module_name}",
        "ok": proc.returncode == 0,
        "value": module_name,
        "detail": (proc.stderr or proc.stdout or "").strip(),
    }


def _extract_choice_values(payload: Any) -> list[str]:
    values: list[str] = []
    if isinstance(payload, dict):
        for item in payload.get("choices", []) or []:
            if isinstance(item, (list, tuple)) and item:
                value = item[-1]
                if isinstance(value, str):
                    values.append(value)
            elif isinstance(item, str):
                values.append(item)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            values.extend(_extract_choice_values(item))
    return values


def _check_meta(check_name: str) -> dict:
    if check_name.startswith("python_import:"):
        module_name = check_name.split(":", 1)[1]
        return {
            "category": "dependency",
            "label": f"Python 依赖 {module_name}",
            "next_step": f"需要在 RVC 训练环境中补齐 Python 依赖：{module_name}",
            "needs_external_fix": True,
        }

    mapping = {
        "rvc_root": {
            "category": "path",
            "label": "RVC 根目录",
            "next_step": "检查 FEISHARK_RVC_DIR 或本地 RVC 安装目录是否正确。",
            "needs_external_fix": True,
        },
        "rvc_python": {
            "category": "environment",
            "label": "RVC Python",
            "next_step": "检查 FEISHARK_RVC_PYTHON 或本地 RVC 虚拟环境 Python 路径。",
            "needs_external_fix": True,
        },
        "ffmpeg": {
            "category": "environment",
            "label": "FFmpeg",
            "next_step": "确认 ffmpeg 已安装并已加入 PATH。",
            "needs_external_fix": True,
        },
        "train_preprocess_script": {
            "category": "script",
            "label": "训练预处理脚本",
            "next_step": "检查 RVC 安装目录中的 preprocess.py 是否存在。",
            "needs_external_fix": True,
        },
        "train_feature_script": {
            "category": "script",
            "label": "训练特征提取脚本",
            "next_step": "检查 RVC 安装目录中的 extract_feature_print.py 是否存在。",
            "needs_external_fix": True,
        },
        "train_f0_script": {
            "category": "script",
            "label": "训练 F0 / pitch 脚本",
            "next_step": "检查 RVC 安装目录中的 extract_f0_rmvpe.py 是否存在。",
            "needs_external_fix": True,
        },
        "train_core_script": {
            "category": "script",
            "label": "训练主脚本",
            "next_step": "检查 RVC 安装目录中的 train.py 是否存在。",
            "needs_external_fix": True,
        },
        "train_index_script": {
            "category": "script",
            "label": "训练索引脚本",
            "next_step": "检查 RVC 安装目录中的 train-index-v2.py 是否存在。",
            "needs_external_fix": True,
        },
        "train_material_profile": {
            "category": "material",
            "label": "训练素材分流",
            "next_step": "请根据素材识别结果切换到正确的训练入口。",
            "needs_external_fix": False,
        },
        "hubert_model": {
            "category": "asset",
            "label": "Hubert 模型",
            "next_step": "补齐 hubert_base.pt 到 RVC 资产目录。",
            "needs_external_fix": True,
        },
        "rmvpe_model": {
            "category": "asset",
            "label": "RMVPE 模型",
            "next_step": "补齐 rmvpe.pt 到 RVC 资产目录。",
            "needs_external_fix": True,
        },
        "rvc_logs_dir": {
            "category": "path",
            "label": "RVC logs 目录",
            "next_step": "确认 RVC logs 目录存在并可写入。",
            "needs_external_fix": True,
        },
        "voice_model_row": {
            "category": "model",
            "label": "模型登记记录",
            "next_step": "先在模型面板导入或重扫模型，再重新尝试翻唱。",
            "needs_external_fix": False,
        },
        "voice_model_pth": {
            "category": "model_path",
            "label": "模型权重路径",
            "next_step": "检查模型 .pth 路径是否正确，或重新扫描 shared_data/weights。",
            "needs_external_fix": False,
        },
        "rvc_service": {
            "category": "service",
            "label": "RVC 服务在线状态",
            "next_step": "需要先启动本地 RVC / Gradio 服务后再进行翻唱。",
            "needs_external_fix": True,
        },
        "rvc_runtime_sync": {
            "category": "path",
            "label": "RVC 运行时模型同步",
            "next_step": "检查模型文件和索引文件是否可复制到 RVC 运行目录。",
            "needs_external_fix": True,
        },
        "rvc_model_choice": {
            "category": "service",
            "label": "RVC 模型列表刷新",
            "next_step": "检查 RVC 服务是否能刷新模型列表，必要时重启 RVC 服务。",
            "needs_external_fix": True,
        },
        "rvc_model_load_probe": {
            "category": "model_runtime",
            "label": "RVC 模型加载探针",
            "next_step": "说明模型文件存在但当前 RVC 实例无法真正加载，需要检查模型兼容性或运行时环境。",
            "needs_external_fix": True,
        },
        "vocal_separator_module": {
            "category": "script",
            "label": "分离模块",
            "next_step": "检查后端的 vocal_separator.py 是否存在。",
            "needs_external_fix": False,
        },
        "pitch_processor_module": {
            "category": "script",
            "label": "修音模块",
            "next_step": "检查后端的 pitch_processor.py 是否存在。",
            "needs_external_fix": False,
        },
        "voice_changer_module": {
            "category": "script",
            "label": "变声模块",
            "next_step": "检查后端的 voice_changer.py 是否存在。",
            "needs_external_fix": False,
        },
        "audio_mixer_module": {
            "category": "script",
            "label": "混音模块",
            "next_step": "检查后端的 audio_mixer.py 是否存在。",
            "needs_external_fix": False,
        },
    }
    return mapping.get(
        check_name,
        {
            "category": "unknown",
            "label": check_name,
            "next_step": "请根据详细日志进一步排查。",
            "needs_external_fix": False,
        },
    )


def _enrich_checks(checks: list[dict]) -> list[dict]:
    enriched = []
    for check in checks:
        meta = _check_meta(check["check"])
        enriched.append({**check, **meta})
    return enriched


def _probe_cover_model_loadability(model_id: str, resolved_path: str, index_path: str = "") -> tuple[list[dict], list[dict]]:
    checks: list[dict] = []
    errors: list[dict] = []

    base_url = _discover_rvc_base_url()
    if not base_url:
        item = {"check": "rvc_model_load_probe", "ok": False, "value": "", "detail": "rvc service offline"}
        return [item], [item]

    try:
        model_name = _sync_weight_to_rvc_runtime(resolved_path)
        resolved_index_path = ""
        if index_path:
            resolved_index_path = index_path if os.path.isabs(index_path) else os.path.join(PROJECT_ROOT, index_path)
        synced_index = _sync_index_to_rvc_runtime(resolved_index_path) if resolved_index_path else ""
        checks.append(
            {
                "check": "rvc_runtime_sync",
                "ok": True,
                "value": model_name,
                "detail": synced_index or "",
            }
        )
    except Exception as exc:
        item = {"check": "rvc_runtime_sync", "ok": False, "value": resolved_path, "detail": str(exc)}
        return [item], [item]

    try:
        client = Client(base_url, verbose=False)
        refresh_payload = _refresh_rvc_choices(client)
        choice_values = _extract_choice_values(refresh_payload)
        in_choices = model_name in choice_values
        choice_check = {
            "check": "rvc_model_choice",
            "ok": in_choices,
            "value": model_name,
            "detail": f"choices={choice_values[:10]}",
        }
        checks.append(choice_check)
        if not in_choices:
            errors.append(choice_check)
            return checks, errors
    except Exception as exc:
        item = {"check": "rvc_model_choice", "ok": False, "value": model_id, "detail": str(exc)}
        checks.append(item)
        errors.append(item)
        return checks, errors

    try:
        _load_rvc_model(client, model_name, 0.33)
        checks.append({"check": "rvc_model_load_probe", "ok": True, "value": model_name, "detail": base_url})
    except (AppError, Exception) as exc:
        item = {
            "check": "rvc_model_load_probe",
            "ok": False,
            "value": model_name,
            "detail": str(exc),
        }
        checks.append(item)
        errors.append(item)
    return checks, errors


def run_train_preflight(strategy_key: str, material_decision: dict | None = None) -> dict:
    env_checks = _enrich_checks([
        _check_path("rvc_root", RVC_WEBUI_DIR, "dir"),
        _check_path("rvc_python", RVC_PYTHON, "file"),
        _check_path("train_preprocess_script", os.path.join(RVC_WEBUI_DIR, "infer", "modules", "train", "preprocess.py")),
        _check_path("train_feature_script", os.path.join(RVC_WEBUI_DIR, "infer", "modules", "train", "extract_feature_print.py")),
        _check_path("train_f0_script", os.path.join(RVC_WEBUI_DIR, "infer", "modules", "train", "extract", "extract_f0_rmvpe.py")),
        _check_path("train_core_script", os.path.join(RVC_WEBUI_DIR, "infer", "modules", "train", "train.py")),
        _check_path("train_index_script", os.path.join(RVC_WEBUI_DIR, "tools", "infer", "train-index-v2.py")),
        _check_path("hubert_model", os.path.join(RVC_WEBUI_DIR, "assets", "hubert", "hubert_base.pt")),
        _check_path("rmvpe_model", os.path.join(RVC_WEBUI_DIR, "assets", "rmvpe", "rmvpe.pt")),
        _check_path("rvc_logs_dir", RVC_LOGS_DIR, "dir"),
        {"check": "ffmpeg", "ok": shutil.which("ffmpeg") is not None, "value": shutil.which("ffmpeg") or ""},
        _check_python_import(RVC_PYTHON, "fairseq", cwd=RVC_WEBUI_DIR),
        _check_python_import(RVC_PYTHON, "faiss", cwd=RVC_WEBUI_DIR),
        _check_python_import(RVC_PYTHON, "sklearn", cwd=RVC_WEBUI_DIR),
    ])
    checks = list(env_checks)
    if material_decision:
        checks.append(_enrich_checks([build_material_check(material_decision)])[0])

    environment_ok = all(check["ok"] for check in env_checks)
    material_ok = True
    if material_decision and material_decision.get("submission_allowed") is not None:
        material_ok = bool(material_decision.get("submission_allowed"))

    ok = environment_ok and material_ok
    return {
        "ok": ok,
        "environment_ok": environment_ok,
        "material_ok": material_ok,
        "submission_allowed": ok,
        "job_type": "train",
        "strategy_key": strategy_key,
        "material_profile": material_decision.get("material_profile") if material_decision else "",
        "duration_seconds": material_decision.get("duration_seconds") if material_decision else None,
        "duration_label": material_decision.get("duration_label") if material_decision else "",
        "sample_rate": material_decision.get("sample_rate") if material_decision else None,
        "channels": material_decision.get("channels") if material_decision else None,
        "codec": material_decision.get("codec") if material_decision else "",
        "container": material_decision.get("container") if material_decision else "",
        "bit_rate": material_decision.get("bit_rate") if material_decision else None,
        "recommended_route": material_decision.get("recommended_route") if material_decision else strategy_key,
        "single_long_eligible": material_decision.get("single_long_eligible") if material_decision else None,
        "reason": material_decision.get("reason") if material_decision else "",
        "next_step": material_decision.get("next_step") if material_decision else "",
        "material_decision": material_decision or None,
        "checks": checks,
        "errors": [c for c in checks if not c["ok"]],
    }


def run_cover_preflight(model_id: str = "v_001") -> dict:
    voice_model = get_voice_model(model_id)
    resolved = resolve_voice_model_file(model_id, PROJECT_ROOT, os.path.join(PROJECT_ROOT, "shared_data", "weights"))
    checks = _enrich_checks([
        {"check": "voice_model_row", "ok": voice_model is not None, "value": model_id},
        _check_path("vocal_separator_module", os.path.join(os.path.dirname(os.path.dirname(__file__)), "vocal_separator.py")),
        _check_path("pitch_processor_module", os.path.join(os.path.dirname(os.path.dirname(__file__)), "pitch_processor.py")),
        _check_path("voice_changer_module", os.path.join(os.path.dirname(os.path.dirname(__file__)), "voice_changer.py")),
        _check_path("audio_mixer_module", os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio_mixer.py")),
        {"check": "rvc_service", "ok": get_rvc_service_status().get("online", False), "value": get_rvc_service_status().get("base_url", "")},
    ])
    if voice_model:
        checks.append(_enrich_checks([{"check": "voice_model_pth", "ok": resolved["ok"], "value": resolved["resolved_path"], "detail": resolved["source"]}])[0])
    if voice_model and resolved["ok"]:
        probe_checks, probe_errors = _probe_cover_model_loadability(
            model_id=model_id,
            resolved_path=resolved["resolved_path"],
            index_path=(voice_model.get("index_path") or ""),
        )
        enriched_probe_checks = _enrich_checks(probe_checks)
        checks.extend(enriched_probe_checks)
        enriched_probe_errors = [item for item in enriched_probe_checks if not item["ok"]]
    else:
        enriched_probe_errors = []
    errors = [c for c in checks if not c["ok"]]
    if enriched_probe_errors:
        errors.extend([item for item in enriched_probe_errors if item not in errors])
    ok = len(errors) == 0
    return {
        "ok": ok,
        "job_type": "cover",
        "model_id": model_id,
        "resolved_model_path": resolved["resolved_path"],
        "checks": checks,
        "errors": errors,
    }
