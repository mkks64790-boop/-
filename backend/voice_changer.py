"""
FeiShark Studio - RVC 推理桥接模块

当前版本直接对接 Gradio 6 风格的 RVC WebUI:
  - /infer_refresh
  - /infer_change_voice
  - /infer_convert
"""

import os
import shutil
import time
import wave

import requests
from gradio_client import Client
from gradio_client.exceptions import AppError


def _pick_first_existing(*paths: str) -> str:
    for path in paths:
        if path and os.path.exists(path):
            return path
    return paths[0] if paths else ""


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "shared_data", "outputs")

RVC_WEBUI_DIR = os.environ.get("FEISHARK_RVC_DIR") or _pick_first_existing(
    r"D:\RVC\RVCv2",
    r"D:\RVC\RVC",
    r"C:\Users\ASUS\WorkBuddy\20260427153731\RVC-WebUI",
)
RVC_WEIGHT_ROOT = os.path.join(RVC_WEBUI_DIR, "assets", "weights")
RVC_INDEX_ROOT = os.path.join(RVC_WEBUI_DIR, "assets", "indices")

RVC_API_BASE = os.environ.get("FEISHARK_RVC_API", "").strip()
RVC_FALLBACK_BASES = [
    "http://127.0.0.1:7866",
    "http://127.0.0.1:7865",
]
ENGINE_KIND = "rvc_webui_local"
COVER_INFERENCE_MODE = "webui_api_local_compat"
TRAIN_BACKEND_MODE = "local_rvc_scripts"

CONNECT_TIMEOUT = 5
STATUS_VC_PROCESSING = "变声中"
STATUS_MIX_READY = "混音中"
STATUS_FAILED = "失败"


def transform_voice(
    task_id: str,
    model_id: str = "v_001",
    index_rate: float = 0.7,
    f0_method: str = "rmvpe",
    filter_radius: int = 3,
    rms_mix_rate: float = 0.25,
    protect: float = 0.33,
) -> dict:
    """执行单次 RVC 变声并将结果落盘到任务输出目录。"""
    try:
        from .db import get_connection, get_voice_asset, update_task_status
    except ImportError:
        from db import get_connection, get_voice_asset, update_task_status

    fixed_vocal_path = os.path.join(OUTPUT_ROOT, task_id, "vocal_fixed.wav")
    transformed_path = os.path.join(OUTPUT_ROOT, task_id, "vocal_transformed.wav")

    print(f"[变声] 启动任务 {task_id}")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        err = f"任务 {task_id} 不存在"
        print(f"[变声] {err}")
        return {"success": False, "error": err}

    if row["status"] != STATUS_VC_PROCESSING:
        print(f"[变声] 当前状态 '{row['status']}' ≠ '{STATUS_VC_PROCESSING}'，强制设置")
        update_task_status(task_id, STATUS_VC_PROCESSING)

    asset = get_voice_asset(model_id)
    if not asset:
        err = f"音色资产不存在: {model_id}"
        print(f"[变声] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    pth_path = _resolve_project_path(asset["pth_path"])
    index_path = _resolve_project_path(asset["index_path"])
    default_pitch = int(asset["default_pitch"] or 0)

    print(f"[变声] 音色: {asset['model_name']} ({model_id})")
    print(f"[变声] 模型: {pth_path}")
    print(f"[变声] 索引: {index_path or '(未提供)'}")
    print(f"[变声] 变调: {default_pitch}")

    if not os.path.exists(fixed_vocal_path):
        err = f"修音后干声不存在: {fixed_vocal_path}"
        print(f"[变声] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    if not os.path.exists(pth_path):
        err = f"音色模型文件不存在: {pth_path}"
        print(f"[变声] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    base_url = _discover_rvc_base_url()
    if not base_url:
        err = (
            "RVC 服务未在线，请先启动 RVC WebUI。"
            f" 已尝试: {', '.join(_candidate_rvc_bases())}"
        )
        print(f"[变声] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    try:
        model_name = _sync_weight_to_rvc_runtime(pth_path)
        synced_index_path = _sync_index_to_rvc_runtime(index_path)
        client = Client(base_url, verbose=False)
    except Exception as exc:
        err = f"RVC 运行目录准备失败: {exc}"
        print(f"[变声] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    try:
        _refresh_rvc_choices(client)
        _load_rvc_model(client, model_name, protect)
    except Exception as exc:
        err = f"RVC 模型加载失败: {exc}"
        print(f"[变声] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    print(f"[变声] 开始推理: {fixed_vocal_path}")
    try:
        t0 = time.time()
        result = _run_rvc_infer(
            client=client,
            input_path=fixed_vocal_path,
            f0_up_key=default_pitch,
            f0_method=f0_method,
            index_path=synced_index_path or index_path,
            index_rate=index_rate,
            filter_radius=filter_radius,
            rms_mix_rate=rms_mix_rate,
            protect=protect,
        )
        elapsed = time.time() - t0
        print(f"[变声] 推理耗时: {elapsed:.1f}s")
    except Exception as exc:
        err = f"RVC 推理失败: {exc}"
        print(f"[变声] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    try:
        _save_rvc_output(result, transformed_path)
    except Exception as exc:
        err = f"保存输出失败: {exc}"
        print(f"[变声] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    if not os.path.exists(transformed_path):
        err = "vocal_transformed.wav 未生成"
        print(f"[变声] {err}")
        update_task_status(task_id, STATUS_FAILED, err)
        return {"success": False, "error": err}

    update_task_status(task_id, STATUS_MIX_READY)
    duration = _get_wav_duration(transformed_path)
    print(f"[变声] 完成: {transformed_path} ({duration:.2f}s)")

    return {
        "success": True,
        "output": transformed_path,
        "duration": duration,
        "elapsed": elapsed,
        "rvc_base_url": base_url,
    }


def get_rvc_service_status() -> dict:
    """返回当前可发现的 RVC 服务状态。"""
    base_url = _discover_rvc_base_url()
    return {
        "base_url": base_url or (_candidate_rvc_bases()[0] if _candidate_rvc_bases() else ""),
        "online": bool(base_url),
    }


def get_engine_summary() -> dict:
    """Return a product-facing summary for the local RVC engine."""
    status = get_rvc_service_status()
    return {
        **status,
        "engine_kind": ENGINE_KIND,
        "rvc_root": RVC_WEBUI_DIR,
        "cover_inference_mode": COVER_INFERENCE_MODE,
        "train_backend_mode": TRAIN_BACKEND_MODE,
    }


def _resolve_project_path(path: str) -> str:
    if not path:
        return ""
    return path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)


def _candidate_rvc_bases() -> list[str]:
    bases: list[str] = []
    if RVC_API_BASE:
        bases.append(RVC_API_BASE.rstrip("/"))
    for base in RVC_FALLBACK_BASES:
        base = base.rstrip("/")
        if base not in bases:
            bases.append(base)
    return bases


def _discover_rvc_base_url() -> str | None:
    for base_url in _candidate_rvc_bases():
        if _check_rvc_service(base_url):
            return base_url
    return None


def _check_rvc_service(base_url: str) -> bool:
    try:
        resp = requests.get(
            f"{base_url}/gradio_api/info",
            timeout=CONNECT_TIMEOUT,
        )
        if resp.status_code != 200:
            return False
        text = resp.text
        return "/infer_change_voice" in text and "/infer_convert" in text
    except requests.RequestException:
        return False
    except Exception:
        return False


def _refresh_rvc_choices(client: Client):
    return client.predict(api_name="/infer_refresh")


def _sync_weight_to_rvc_runtime(source_path: str) -> str:
    if not RVC_WEBUI_DIR:
        raise FileNotFoundError("未找到 RVC WebUI 目录")

    os.makedirs(RVC_WEIGHT_ROOT, exist_ok=True)
    model_name = os.path.basename(source_path)
    target_path = os.path.join(RVC_WEIGHT_ROOT, model_name)

    if (
        os.path.abspath(source_path) != os.path.abspath(target_path)
        and _copy_needed(source_path, target_path)
    ):
        shutil.copy2(source_path, target_path)
        print(f"[变声] 已同步模型到 RVC 目录: {target_path}")

    return model_name


def _sync_index_to_rvc_runtime(source_path: str) -> str:
    if not source_path or not os.path.exists(source_path):
        return ""

    os.makedirs(RVC_INDEX_ROOT, exist_ok=True)
    target_path = os.path.join(RVC_INDEX_ROOT, os.path.basename(source_path))

    if (
        os.path.abspath(source_path) != os.path.abspath(target_path)
        and _copy_needed(source_path, target_path)
    ):
        shutil.copy2(source_path, target_path)
        print(f"[变声] 已同步索引到 RVC 目录: {target_path}")

    return target_path


def _copy_needed(source_path: str, target_path: str) -> bool:
    if not os.path.exists(target_path):
        return True
    return (
        os.path.getsize(source_path) != os.path.getsize(target_path)
        or int(os.path.getmtime(source_path)) != int(os.path.getmtime(target_path))
    )


def _load_rvc_model(client: Client, model_name: str, protect: float):
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            if attempt:
                _refresh_rvc_choices(client)
            client.predict(
                model_name,
                float(protect),
                float(protect),
                api_name="/infer_change_voice",
            )
            print(f"[变声] 模型加载成功: {model_name}")
            return
        except AppError as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc
            break

    raise RuntimeError(str(last_error) if last_error else "未知错误")


def _run_rvc_infer(
    client: Client,
    input_path: str,
    f0_up_key: int,
    f0_method: str,
    index_path: str,
    index_rate: float,
    filter_radius: int,
    rms_mix_rate: float,
    protect: float,
):
    abs_input = os.path.abspath(input_path)
    abs_index = os.path.abspath(index_path) if index_path and os.path.exists(index_path) else ""

    return client.predict(
        0,
        abs_input,
        int(f0_up_key),
        None,
        f0_method,
        abs_index,
        None,
        float(index_rate),
        int(filter_radius),
        0,
        float(rms_mix_rate),
        float(protect),
        api_name="/infer_convert",
    )


def _save_rvc_output(result, output_path: str):
    if not isinstance(result, (list, tuple)) or len(result) < 2:
        raise ValueError(f"RVC 返回格式异常: {type(result)}")

    info_text = result[0]
    audio_data = result[1]
    print(f"[变声] RVC 返回信息: {str(info_text)[:120]}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if isinstance(audio_data, str) and os.path.exists(audio_data):
        shutil.copy2(audio_data, output_path)
        return

    if isinstance(audio_data, dict) and "path" in audio_data and os.path.exists(audio_data["path"]):
        shutil.copy2(audio_data["path"], output_path)
        return

    raise ValueError(f"无法解析 RVC 输出音频: {audio_data!r}")


def _get_wav_duration(path: str) -> float:
    try:
        with wave.open(path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / rate if rate else 0.0
    except Exception:
        return 0.0


def smoke_test():
    """仅验证 RVC 服务发现，不执行真实推理。"""
    print("[变声] RVC 状态:", get_rvc_service_status())


if __name__ == "__main__":
    smoke_test()
