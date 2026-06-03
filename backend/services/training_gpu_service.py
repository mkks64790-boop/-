from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from io import StringIO
from pathlib import Path
from typing import Any


def parse_gpu_ids(raw: str | None) -> list[int]:
    values: list[int] = []
    for chunk in str(raw or "").replace(",", "-").split("-"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            values.append(int(chunk))
        except ValueError:
            continue
    return values


def probe_nvidia_smi(*, timeout: int = 5) -> dict[str, Any]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {
            "ok": False,
            "available": False,
            "path": "",
            "gpus": [],
            "detail": "nvidia-smi not found",
        }

    cmd = [
        exe,
        "--query-gpu=index,name,memory.total,memory.free,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "available": False, "path": exe, "gpus": [], "detail": str(exc)}

    if proc.returncode != 0:
        return {
            "ok": False,
            "available": False,
            "path": exe,
            "gpus": [],
            "detail": (proc.stderr or proc.stdout or "").strip(),
        }

    gpus = []
    for row in csv.reader(StringIO(proc.stdout or "")):
        if len(row) < 5:
            continue
        try:
            index = int(str(row[0]).strip())
        except ValueError:
            continue
        gpus.append(
            {
                "index": index,
                "name": str(row[1]).strip(),
                "memory_total_mb": _safe_int(row[2]),
                "memory_free_mb": _safe_int(row[3]),
                "utilization_gpu_percent": _safe_int(row[4]),
            }
        )

    return {
        "ok": bool(gpus),
        "available": bool(gpus),
        "path": exe,
        "gpus": gpus,
        "detail": "" if gpus else "nvidia-smi returned no GPU rows",
    }


def probe_torch_cuda(python_exe: str, *, cwd: str = "", timeout: int = 20) -> dict[str, Any]:
    if not python_exe or not Path(python_exe).is_file():
        return {
            "ok": False,
            "available": False,
            "python": python_exe,
            "detail": "RVC python executable missing",
        }

    script = r"""
import json
try:
    import torch
    payload = {
        "torch_version": getattr(torch, "__version__", ""),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_version": getattr(torch.version, "cuda", None),
        "device_count": int(torch.cuda.device_count()),
        "devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
    }
except Exception as exc:
    payload = {"error": str(exc)}
print(json.dumps(payload, ensure_ascii=False))
"""
    try:
        proc = subprocess.run(
            [python_exe, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd or None,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "available": False, "python": python_exe, "detail": str(exc)}

    raw = (proc.stdout or "").strip()
    try:
        payload = json.loads(raw.splitlines()[-1]) if raw else {}
    except Exception:
        payload = {"error": raw or (proc.stderr or "").strip()}

    cuda_available = bool(payload.get("cuda_available"))
    device_count = int(payload.get("device_count") or 0)
    ok = proc.returncode == 0 and cuda_available and device_count > 0
    detail = ""
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
    elif payload.get("error"):
        detail = str(payload.get("error"))
    elif not ok:
        detail = "torch.cuda is not available in RVC python"

    return {
        "ok": ok,
        "available": ok,
        "python": python_exe,
        "torch_version": payload.get("torch_version") or "",
        "cuda_version": payload.get("cuda_version") or "",
        "device_count": device_count,
        "devices": payload.get("devices") if isinstance(payload.get("devices"), list) else [],
        "detail": detail,
    }


def get_training_gpu_status(
    *,
    rvc_python: str,
    rvc_webui_dir: str,
    train_gpus: str = "0",
    timeout: int = 20,
) -> dict[str, Any]:
    selected_gpus = parse_gpu_ids(train_gpus) or [0]
    nvidia = probe_nvidia_smi(timeout=min(timeout, 5))
    torch_cuda = probe_torch_cuda(rvc_python, cwd=rvc_webui_dir, timeout=timeout)
    device_count = int(torch_cuda.get("device_count") or 0)
    selection_ok = bool(torch_cuda.get("available")) and all(0 <= gpu_id < device_count for gpu_id in selected_gpus)
    acceleration_available = bool(nvidia.get("available") and torch_cuda.get("available") and selection_ok)

    checks = [
        {
            "check": "train_gpu_nvidia_smi",
            "ok": bool(nvidia.get("available")),
            "value": nvidia.get("path") or "",
            "detail": nvidia.get("detail") or "",
        },
        {
            "check": "train_gpu_torch_cuda",
            "ok": bool(torch_cuda.get("available")),
            "value": torch_cuda.get("python") or "",
            "detail": torch_cuda.get("detail") or torch_cuda.get("torch_version") or "",
        },
        {
            "check": "train_gpu_selection",
            "ok": selection_ok,
            "value": train_gpus,
            "detail": f"selected={selected_gpus}; device_count={device_count}",
        },
    ]
    next_step = "GPU acceleration is available for RVC training."
    if not acceleration_available:
        next_step = "Fix nvidia-smi, RVC torch CUDA, or FEISHARK_RVC_GPUS before starting long training."

    return {
        "ok": acceleration_available,
        "acceleration_available": acceleration_available,
        "gpu_acceleration_available": acceleration_available,
        "device_mode": "cuda" if acceleration_available else "cpu",
        "selected_gpus": selected_gpus,
        "train_gpus": train_gpus,
        "nvidia_smi": nvidia,
        "torch_cuda": torch_cuda,
        "checks": checks,
        "errors": [item for item in checks if not item["ok"]],
        "next_step": next_step,
        "starts_train_py": False,
    }


def _safe_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0
