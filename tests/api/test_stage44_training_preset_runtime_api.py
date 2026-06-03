import io

from backend import main as backend_main
from backend.model_trainer import build_training_command_preview


def _patch_train_creation(monkeypatch):
    async def fake_save_train_uploads(task_id, files):
        return {
            "dataset_rel_path": f"shared_data/datasets/{task_id}",
            "file_count": len(files),
            "total_bytes": 1234,
            "saved_files": [
                {
                    "rel_path": f"shared_data/datasets/{task_id}/0000.wav",
                    "file_name": "0000.wav",
                    "file_ext": ".wav",
                    "file_size": 1234,
                }
            ],
        }

    monkeypatch.setattr(backend_main, "save_train_uploads", fake_save_train_uploads)
    monkeypatch.setattr(
        backend_main,
        "profile_train_saved_uploads",
        lambda saved_files: {
            "recommended_route": "single_long_preprocess",
            "single_long_eligible": True,
            "submission_allowed": True,
            "material_profile": "single_long_candidate",
            "reason": "test material accepted",
        },
    )
    monkeypatch.setattr(
        backend_main,
        "run_train_preflight",
        lambda strategy_key, material_decision=None: {"ok": True, "checks": [], "errors": [], "strategy_key": strategy_key},
    )
    monkeypatch.setattr(backend_main, "create_dataset_record", lambda *args, **kwargs: "ds_stage44")
    monkeypatch.setattr(backend_main, "register_audio_asset", lambda *args, **kwargs: "asset_stage44")
    monkeypatch.setattr(backend_main, "reserve_job", lambda *args, **kwargs: False)
    monkeypatch.setattr(backend_main, "set_job_pending", lambda *args, **kwargs: None)
    monkeypatch.setattr(backend_main, "log_stage", lambda *args, **kwargs: None)


def test_train_api_uses_balanced_when_config_missing(client, isolated_backend, monkeypatch):
    _patch_train_creation(monkeypatch)
    resp = client.post(
        "/api/train",
        data={"voice_name": "Stage44Balanced"},
        files={"files": ("voice.wav", io.BytesIO(b"fake wav"), "audio/wav")},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["training_config"]["preset_key"] == "balanced"
    assert payload["training_config"]["epochs"] == 90
    assert payload["training_config"]["batch_size"] == 8

    detail = client.get(f"/api/jobs/{payload['task_id']}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["training_config"]["preset_key"] == "balanced"
    assert "balanced" in detail_payload["training_config_summary"]


def test_train_api_saves_fast_preview_and_quality_config(client, isolated_backend, monkeypatch):
    _patch_train_creation(monkeypatch)
    fast = client.post(
        "/api/train",
        data={"voice_name": "Stage44Fast", "preset_key": "fast_preview"},
        files={"files": ("voice.wav", io.BytesIO(b"fake wav"), "audio/wav")},
    )
    assert fast.status_code == 200
    assert fast.json()["training_config"]["preset_key"] == "fast_preview"
    assert fast.json()["training_config"]["epochs"] == 30

    quality = client.post(
        "/api/train",
        data={"voice_name": "Stage44Quality", "training_config": '{"preset_key":"quality","batch_size":4}'},
        files={"files": ("voice.wav", io.BytesIO(b"fake wav"), "audio/wav")},
    )
    assert quality.status_code == 200
    assert quality.json()["training_config"]["preset_key"] == "quality"
    assert quality.json()["training_config"]["epochs"] == 150
    assert quality.json()["training_config"]["batch_size"] == 4


def test_train_api_rejects_invalid_sample_rate(client, isolated_backend, monkeypatch):
    _patch_train_creation(monkeypatch)
    resp = client.post(
        "/api/train",
        data={"voice_name": "Stage44Invalid", "sample_rate": "96k"},
        files={"files": ("voice.wav", io.BytesIO(b"fake wav"), "audio/wav")},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "invalid_training_config"


def test_epochs_and_batch_are_clamped_and_command_preview_maps_runtime_options():
    config = {
        "preset_key": "quality",
        "epochs": 999,
        "batch_size": 0,
        "sample_rate": "48k",
        "f0_enabled": False,
        "index_enabled": False,
    }
    preview = build_training_command_preview("stage44_preview", config)
    assert preview["starts_train_py"] is False
    assert preview["epochs"] == 300
    assert preview["batch_size"] == 1
    assert preview["sample_rate"] == "48k"
    assert preview["f0_enabled"] is False
    assert preview["index_enabled"] is False
    cmd = preview["cmd"]
    assert cmd[cmd.index("-te") + 1] == "300"
    assert cmd[cmd.index("-bs") + 1] == "1"
    assert cmd[cmd.index("-sr") + 1] == "48k"
    assert cmd[cmd.index("-f0") + 1] == "0"
