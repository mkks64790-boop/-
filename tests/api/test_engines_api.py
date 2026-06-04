from pathlib import Path

from backend.services import engine_manager_service as engines


def _patch_rvc_paths(monkeypatch, root: Path):
    monkeypatch.setattr(engines, "RVC_WEBUI_DIR", str(root), raising=False)
    monkeypatch.setattr(engines, "RVC_WEIGHT_ROOT", str(root / "assets" / "weights"), raising=False)
    monkeypatch.setattr(engines, "RVC_INDEX_ROOT", str(root / "assets" / "indices"), raising=False)
    monkeypatch.setattr(engines, "RVC_API_BASE", "", raising=False)
    monkeypatch.setattr(engines, "RVC_FALLBACK_BASES", ["http://127.0.0.1:7866"], raising=False)
    monkeypatch.setattr(engines, "RVC_WEBUI_BACKUP_DIR", str(root.parent / "missing-backup-rvc"), raising=False)
    monkeypatch.setattr(engines, "RVC_BACKUP_WEIGHT_ROOT", str(root.parent / "missing-backup-rvc" / "assets" / "weights"), raising=False)
    monkeypatch.setattr(engines, "RVC_BACKUP_INDEX_ROOT", str(root.parent / "missing-backup-rvc" / "assets" / "indices"), raising=False)
    monkeypatch.setattr(engines, "RVC_BACKUP_LOGS_ROOT", str(root.parent / "missing-backup-rvc" / "logs"), raising=False)
    monkeypatch.setattr(engines, "RVC_BACKUP_API_BASE", "", raising=False)


def test_engines_contract_handles_unconfigured_rvc_and_svc(client, isolated_backend, monkeypatch):
    missing_rvc_root = isolated_backend / "missing-rvc"
    _patch_rvc_paths(monkeypatch, missing_rvc_root)
    monkeypatch.setattr(engines, "_probe_rvc_base", lambda base_url: False)
    monkeypatch.delenv("FEISHARK_SVC_ROOT", raising=False)

    resp = client.get("/api/engines")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["read_only"] is True
    assert {item["engine_key"] for item in payload["engines"]} == {
        "rvc_webui",
        "rvc_webui_backup",
        "uvr",
        "svc_fallback",
    }

    rvc = next(item for item in payload["engines"] if item["engine_key"] == "rvc_webui")
    backup = next(item for item in payload["engines"] if item["engine_key"] == "rvc_webui_backup")
    svc = next(item for item in payload["engines"] if item["engine_key"] == "svc_fallback")
    assert rvc["status"] == "not_configured"
    assert backup["status"] == "not_configured"
    assert backup["train_capable"] is False
    assert rvc["read_only"] is True
    assert isinstance(rvc["checks"], list)
    assert svc["status"] == "not_configured"

    scan_resp = client.post("/api/engines/scan")
    assert scan_resp.status_code == 200
    assert scan_resp.json()["read_only"] is True


def test_rvc_model_scan_pairs_index_and_marks_registered(client, isolated_backend, monkeypatch):
    rvc_root = isolated_backend / "third_party_rvc"
    weights = rvc_root / "assets" / "weights"
    indices = rvc_root / "assets" / "indices"
    train_dir = rvc_root / "infer" / "modules" / "train"
    logs = rvc_root / "logs"
    weights.mkdir(parents=True)
    indices.mkdir(parents=True)
    train_dir.mkdir(parents=True)
    logs.mkdir(parents=True)
    (rvc_root / "infer-web.py").write_text("# fake rvc webui", encoding="utf-8")
    (train_dir / "train.py").write_text("# fake train script", encoding="utf-8")
    pth_path = weights / "SingerA.pth"
    index_path = indices / "SingerA.index"
    pth_path.write_bytes(b"fake-pth")
    index_path.write_bytes(b"fake-index")

    _patch_rvc_paths(monkeypatch, rvc_root)
    monkeypatch.setattr(engines, "_probe_rvc_base", lambda base_url: False)

    import_resp = client.post(
        "/api/models/import",
        json={
            "model_name": "SingerA",
            "pth_path": str(pth_path),
            "index_path": str(index_path),
            "default_pitch": 0,
        },
    )
    assert import_resp.status_code == 200

    resp = client.get("/api/engines/rvc/models")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["engine_key"] == "rvc_webui"
    assert payload["status"] == "offline"
    assert payload["model_count"] == 1
    model = payload["models"][0]
    assert model["pth_name"] == "SingerA.pth"
    assert model["index_name"] == "SingerA.index"
    assert model["paired_by"] == "exact_name"
    assert model["registered"] is True
    assert model["registered_model_name"] == "SingerA"


def test_single_engine_endpoint_and_unknown_key(client, isolated_backend, monkeypatch):
    _patch_rvc_paths(monkeypatch, isolated_backend / "missing-rvc")
    monkeypatch.setattr(engines, "_probe_rvc_base", lambda base_url: False)

    resp = client.get("/api/engines/rvc")
    assert resp.status_code == 200
    assert resp.json()["engine_key"] == "rvc_webui"

    backup = client.get("/api/engines/qiufeng")
    assert backup.status_code == 200
    assert backup.json()["engine_key"] == "rvc_webui_backup"

    missing = client.get("/api/engines/not-real")
    assert missing.status_code == 404


def test_backup_rvc_model_scan_is_first_class(client, isolated_backend, monkeypatch):
    primary_root = isolated_backend / "primary_rvc"
    backup_root = isolated_backend / "backup_rvc"
    primary_root.mkdir(parents=True)
    weights = backup_root / "assets" / "weights"
    indices = backup_root / "assets" / "indices"
    train_dir = backup_root / "infer" / "modules" / "train"
    logs = backup_root / "logs"
    weights.mkdir(parents=True)
    indices.mkdir(parents=True)
    train_dir.mkdir(parents=True)
    logs.mkdir(parents=True)
    (backup_root / "infer-web.py").write_text("# fake backup rvc webui", encoding="utf-8")
    (train_dir / "train.py").write_text("# fake backup train script", encoding="utf-8")
    pth_path = weights / "Qiufeng.pth"
    index_path = indices / "Qiufeng.index"
    pth_path.write_bytes(b"fake-backup-pth")
    index_path.write_bytes(b"fake-backup-index")

    _patch_rvc_paths(monkeypatch, primary_root)
    monkeypatch.setattr(engines, "RVC_WEBUI_BACKUP_DIR", str(backup_root), raising=False)
    monkeypatch.setattr(engines, "RVC_BACKUP_WEIGHT_ROOT", str(weights), raising=False)
    monkeypatch.setattr(engines, "RVC_BACKUP_INDEX_ROOT", str(indices), raising=False)
    monkeypatch.setattr(engines, "RVC_BACKUP_LOGS_ROOT", str(logs), raising=False)
    monkeypatch.setattr(engines, "RVC_FALLBACK_BASES", ["http://127.0.0.1:7866", "http://127.0.0.1:7865"], raising=False)
    monkeypatch.setattr(engines, "_probe_rvc_base", lambda base_url: False)

    resp = client.get("/api/engines/rvc/models?engine_key=rvc_webui_backup&force=true")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["engine_key"] == "rvc_webui_backup"
    assert payload["status"] == "offline"
    assert payload["model_count"] == 1
    model = payload["models"][0]
    assert model["pth_name"] == "Qiufeng.pth"
    assert model["source_engine"] == "rvc_webui_backup"
    assert model["origin_kind"] == "external_rvc_backup"
