from backend import db as backend_db
from backend.services.asset_service import register_job_artifact
from backend.services.job_service import create_cover_job


def test_completed_cover_job_exposes_studio_entry(client, isolated_backend):
    job_id = "stage43_cover_entry"
    output_root = isolated_backend / "shared_data" / "outputs" / job_id
    output_root.mkdir(parents=True, exist_ok=True)
    source_master = output_root / "final_master.wav"
    source_master.write_bytes(b"RIFFfake-stage43-master")

    create_cover_job(
        job_id,
        input_path="shared_data/uploads/stage43.wav",
        output_root=str(output_root),
        track_id="trk_stage43",
        voice_model_id="vm_stage43",
        voice_name="Stage43",
    )
    backend_db.update_task_status(job_id, "完成")
    artifact_id = register_job_artifact(
        job_id=job_id,
        stage_name="cover_mix",
        artifact_type="cover_master",
        source_path=str(source_master),
        is_final=True,
    )
    assert artifact_id

    detail = client.get(f"/api/jobs/{job_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["can_open_studio"] is True
    assert payload["final_artifact_id"] == artifact_id
    assert payload["studio_artifact_id"] == artifact_id
    assert payload["studio_track_id"] == "trk_stage43"
    assert payload["final_artifact_download_url"] == f"/api/jobs/{job_id}/artifacts/{artifact_id}/download"
    assert "job_id=stage43_cover_entry" in payload["studio_url"]

    status = client.get(f"/api/task_status/{job_id}")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["can_open_studio"] is True
    assert status_payload["final_artifact_download_url"] == payload["final_artifact_download_url"]
    assert status_payload["studio_url"] == payload["studio_url"]


def test_rvc_models_paging_search_filters_and_import_rvc(client, isolated_backend, monkeypatch):
    from backend.services import engine_manager_service as engines

    rvc_root = isolated_backend / "third_party_rvc_stage43"
    weights = rvc_root / "assets" / "weights"
    indices = rvc_root / "assets" / "indices"
    logs = rvc_root / "logs"
    train_dir = rvc_root / "infer" / "modules" / "train"
    weights.mkdir(parents=True)
    indices.mkdir(parents=True)
    logs.mkdir(parents=True)
    train_dir.mkdir(parents=True)
    (rvc_root / "infer-web.py").write_text("# fake", encoding="utf-8")
    (train_dir / "train.py").write_text("# fake", encoding="utf-8")
    alpha_pth = weights / "Alpha.pth"
    beta_pth = weights / "Beta.pth"
    alpha_index = indices / "Alpha.index"
    alpha_pth.write_bytes(b"alpha")
    beta_pth.write_bytes(b"beta")
    alpha_index.write_bytes(b"alpha-index")

    monkeypatch.setattr(engines, "RVC_WEBUI_DIR", str(rvc_root), raising=False)
    monkeypatch.setattr(engines, "RVC_WEIGHT_ROOT", str(weights), raising=False)
    monkeypatch.setattr(engines, "RVC_INDEX_ROOT", str(indices), raising=False)
    monkeypatch.setattr(engines, "RVC_API_BASE", "", raising=False)
    monkeypatch.setattr(engines, "RVC_FALLBACK_BASES", ["http://127.0.0.1:7866"], raising=False)
    monkeypatch.setattr(engines, "_probe_rvc_base", lambda base_url: False)

    page = client.get("/api/engines/rvc/models?limit=1&offset=0&force=true")
    assert page.status_code == 200
    page_payload = page.json()
    assert page_payload["total"] == 2
    assert page_payload["limit"] == 1
    assert len(page_payload["items"]) == 1
    assert page_payload["models"] == page_payload["items"]

    filtered = client.get("/api/engines/rvc/models?q=Alpha&has_index=true&registered=false")
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["pth_name"] == "Alpha.pth"

    imported = client.post(
        "/api/models/import-rvc",
        json={
            "model_name": "AlphaStage43",
            "pth_path": str(alpha_pth),
            "index_path": str(alpha_index),
            "default_pitch": 0,
            "engine_key": "rvc_webui_backup",
            "rvc_root": str(rvc_root),
            "rvc_base_url": "http://127.0.0.1:7865",
        },
    )
    assert imported.status_code == 200
    assert imported.json()["ok"] is True
    imported_model = imported.json()["model"]
    assert imported_model["origin_kind"] == "external_rvc_backup"
    assert imported_model["metadata"]["engine_key"] == "rvc_webui_backup"
    assert imported_model["metadata"]["rvc_base_url"] == "http://127.0.0.1:7865"

    duplicate = client.post(
        "/api/models/import-rvc",
        json={
            "model_name": "AlphaStage43",
            "pth_path": str(alpha_pth),
            "index_path": str(alpha_index),
            "default_pitch": 0,
        },
    )
    assert duplicate.status_code == 409

    missing = client.post(
        "/api/models/import-rvc",
        json={"model_name": "MissingStage43", "pth_path": str(weights / "Missing.pth")},
    )
    assert missing.status_code == 422


def test_training_presets_and_estimate_are_read_only(client):
    presets = client.get("/api/training/presets")
    assert presets.status_code == 200
    payload = presets.json()
    assert payload["read_only"] is True
    keys = {item["preset_key"] for item in payload["items"]}
    assert {"fast_preview", "balanced", "quality"}.issubset(keys)

    estimate = client.post(
        "/api/training/estimate",
        json={"preset_key": "quality", "duration_seconds": 2700, "file_count": 1},
    )
    assert estimate.status_code == 200
    data = estimate.json()
    assert data["preset_key"] == "quality"
    assert data["submission_creates_job"] is False
    assert data["gpu_risk_label"] in {"中", "高"}
    assert data["epochs"] == 150
