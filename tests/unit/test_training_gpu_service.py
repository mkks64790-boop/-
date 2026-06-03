from __future__ import annotations

import json
from types import SimpleNamespace

from backend.services import training_gpu_service


def test_parse_gpu_ids_supports_rvc_dash_format():
    assert training_gpu_service.parse_gpu_ids("0") == [0]
    assert training_gpu_service.parse_gpu_ids("0-1") == [0, 1]
    assert training_gpu_service.parse_gpu_ids("0, 2") == [0, 2]
    assert training_gpu_service.parse_gpu_ids("bad-1") == [1]


def test_training_gpu_status_uses_nvidia_smi_and_torch_cuda(monkeypatch, tmp_path):
    rvc_python = tmp_path / "python.exe"
    rvc_python.write_text("fake", encoding="utf-8")
    rvc_root = tmp_path / "rvc"
    rvc_root.mkdir()

    monkeypatch.setattr(training_gpu_service.shutil, "which", lambda name: "nvidia-smi.exe" if name == "nvidia-smi" else None)

    def fake_run(cmd, **kwargs):
        if cmd[0] == "nvidia-smi.exe":
            return SimpleNamespace(
                returncode=0,
                stdout="0, NVIDIA Test GPU, 8192, 4096, 3\n",
                stderr="",
            )
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "torch_version": "2.0.0+cu",
                    "cuda_available": True,
                    "cuda_version": "12.1",
                    "device_count": 1,
                    "devices": ["NVIDIA Test GPU"],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(training_gpu_service.subprocess, "run", fake_run)

    status = training_gpu_service.get_training_gpu_status(
        rvc_python=str(rvc_python),
        rvc_webui_dir=str(rvc_root),
        train_gpus="0",
    )

    assert status["acceleration_available"] is True
    assert status["device_mode"] == "cuda"
    assert status["selected_gpus"] == [0]
    assert status["nvidia_smi"]["gpus"][0]["memory_free_mb"] == 4096
    assert status["torch_cuda"]["devices"] == ["NVIDIA Test GPU"]
    assert status["starts_train_py"] is False


def test_training_gpu_status_rejects_missing_selected_gpu(monkeypatch, tmp_path):
    rvc_python = tmp_path / "python.exe"
    rvc_python.write_text("fake", encoding="utf-8")

    monkeypatch.setattr(
        training_gpu_service,
        "probe_nvidia_smi",
        lambda **kwargs: {"available": True, "path": "nvidia-smi", "gpus": [{"index": 0}], "detail": ""},
    )
    monkeypatch.setattr(
        training_gpu_service,
        "probe_torch_cuda",
        lambda *args, **kwargs: {
            "available": True,
            "python": str(rvc_python),
            "device_count": 1,
            "devices": ["GPU0"],
            "detail": "",
        },
    )

    status = training_gpu_service.get_training_gpu_status(
        rvc_python=str(rvc_python),
        rvc_webui_dir=str(tmp_path),
        train_gpus="1",
    )

    assert status["acceleration_available"] is False
    assert status["device_mode"] == "cpu"
    assert any(item["check"] == "train_gpu_selection" for item in status["errors"])
