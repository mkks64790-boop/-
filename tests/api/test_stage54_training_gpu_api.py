from __future__ import annotations

from backend import main as backend_main
from backend.services import preflight_service


def _fake_gpu_status():
    return {
        "ok": True,
        "acceleration_available": True,
        "device_mode": "cuda",
        "selected_gpus": [0],
        "train_gpus": "0",
        "nvidia_smi": {"gpus": [{"index": 0, "name": "NVIDIA Test GPU"}]},
        "torch_cuda": {"device_count": 1, "devices": ["NVIDIA Test GPU"]},
        "checks": [
            {"check": "train_gpu_nvidia_smi", "ok": True, "value": "nvidia-smi", "detail": ""},
            {"check": "train_gpu_torch_cuda", "ok": True, "value": "python", "detail": "2.0.0+cu"},
            {"check": "train_gpu_selection", "ok": True, "value": "0", "detail": "selected=[0]; device_count=1"},
        ],
        "errors": [],
        "next_step": "GPU acceleration is available for RVC training.",
        "starts_train_py": False,
    }


def test_training_gpu_status_endpoint_is_probe_only(client, monkeypatch):
    monkeypatch.setattr(backend_main, "get_training_gpu_status", lambda **kwargs: _fake_gpu_status())

    resp = client.get("/api/training/gpu-status")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["acceleration_available"] is True
    assert payload["device_mode"] == "cuda"
    assert payload["starts_train_py"] is False


def test_train_preflight_exposes_gpu_acceleration(client, monkeypatch):
    monkeypatch.setattr(preflight_service, "get_training_gpu_status", lambda **kwargs: _fake_gpu_status())
    monkeypatch.setattr(preflight_service, "_check_python_import", lambda *args, **kwargs: {"check": f"python_import:{args[1]}", "ok": True, "value": args[1], "detail": ""})

    resp = client.get("/api/preflight/train?file_count=1")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["gpu_acceleration_available"] is True
    assert payload["device_mode"] == "cuda"
    assert payload["gpu_status"]["starts_train_py"] is False
    assert any(item["check"] == "train_gpu_torch_cuda" for item in payload["checks"])
