import importlib


def test_engine_paths_env_overrides_primary_backup_and_audio(monkeypatch, tmp_path):
    primary = tmp_path / "primary-rvc"
    backup = tmp_path / "backup-rvc"
    audio = tmp_path / "audio-pipeline"
    for path in (primary, backup, audio):
        path.mkdir(parents=True)

    monkeypatch.setenv("FEISHARK_RVC_DIR", str(primary))
    monkeypatch.setenv("FEISHARK_RVC_BACKUP_DIR", str(backup))
    monkeypatch.setenv("FEISHARK_AUDIO_PIPELINE", str(audio))
    monkeypatch.setenv("FEISHARK_RVC_PORT", "7866")
    monkeypatch.setenv("FEISHARK_RVC_BACKUP_PORT", "7865")

    from backend import engine_paths

    reloaded = importlib.reload(engine_paths)
    assert reloaded.RVC_WEBUI_DIR == str(primary)
    assert reloaded.RVC_WEBUI_BACKUP_DIR == str(backup)
    assert reloaded.AUDIO_PIPELINE_DIR == str(audio)

    primary_paths = reloaded.rvc_engine_paths("primary")
    backup_paths = reloaded.rvc_engine_paths("backup")
    assert primary_paths["engine_key"] == "rvc_webui"
    assert primary_paths["train_capable"] is True
    assert backup_paths["engine_key"] == "rvc_webui_backup"
    assert backup_paths["train_capable"] is False
    assert "http://127.0.0.1:7866" in reloaded.candidate_rvc_bases()
    assert "http://127.0.0.1:7865" in reloaded.candidate_rvc_bases()


def test_engine_paths_workspace_external_preferred(monkeypatch):
    for key in [
        "FEISHARK_RVC_DIR",
        "FEISHARK_RVC_BACKUP_DIR",
        "FEISHARK_AUDIO_PIPELINE",
    ]:
        monkeypatch.delenv(key, raising=False)

    from backend import engine_paths

    reloaded = importlib.reload(engine_paths)
    assert "external" in reloaded.RVC_WEBUI_DIR.replace("\\", "/")
    assert "rvc-webui" in reloaded.RVC_WEBUI_DIR.replace("\\", "/")
    assert "rvc-webui-backup" in reloaded.RVC_WEBUI_BACKUP_DIR.replace("\\", "/")
    assert "audio-pipeline" in reloaded.AUDIO_PIPELINE_DIR.replace("\\", "/")
