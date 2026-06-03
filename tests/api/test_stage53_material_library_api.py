from __future__ import annotations

import math
import json
import wave
from pathlib import Path

from backend import main as backend_main
from backend import db as backend_db
from backend.services.asset_service import register_job_artifact
from backend.services.job_service import create_cover_job
from backend.services import material_library_service


def _write_wav(path: Path, *, seconds: float = 1.0, sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for index in range(frames):
            value = int(8000 * math.sin(2 * math.pi * 220 * index / sample_rate))
            handle.writeframes(value.to_bytes(2, "little", signed=True))


def test_material_library_scan_indexes_repo_dry_vocals(client, isolated_backend, monkeypatch):
    monkeypatch.delenv(material_library_service.SONOVOX_DEMO_DATASET_ENV, raising=False)
    monkeypatch.delenv(material_library_service.AUTHORIZED_DRY_VOCAL_ROOTS_ENV, raising=False)
    sample = isolated_backend / "shared_data" / "material_library" / "authorized_dry_vocals" / "user" / "dry_voice.wav"
    _write_wav(sample)

    scan_resp = client.post("/api/material-library/scan")
    summary_resp = client.get("/api/material-library/summary")
    items_resp = client.get("/api/material-library/items?role=dry_vocal")

    assert scan_resp.status_code == 200
    scan_payload = scan_resp.json()
    assert scan_payload["summary"]["dry_vocal_count"] == 1
    assert scan_payload["summary"]["separation_benchmark_count"] == 0
    assert scan_payload["safety"]["destructive_cleanup"] is False

    assert summary_resp.status_code == 200
    assert summary_resp.json()["summary"]["dry_vocal_count"] == 1

    assert items_resp.status_code == 200
    items = items_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["file_name"] == "dry_voice.wav"
    assert items[0]["source_group"] == "authorized_dry_vocal"
    assert items[0]["material_role"] == "dry_vocal"
    assert items[0]["material_profile"] == "clean_dry_vocal"
    assert items[0]["route_hint"] == "training_baseline_multi_clean_direct"
    assert items[0]["retention_status"] == "active"


def test_material_library_env_root_is_external_read_only(client, isolated_backend, tmp_path, monkeypatch):
    external_root = tmp_path / "authorized_external"
    _write_wav(external_root / "external_voice.wav")
    monkeypatch.setenv(material_library_service.AUTHORIZED_DRY_VOCAL_ROOTS_ENV, str(external_root))
    monkeypatch.delenv(material_library_service.SONOVOX_DEMO_DATASET_ENV, raising=False)

    resp = client.post("/api/material-library/scan")

    assert resp.status_code == 200
    payload = resp.json()
    libraries = {item["library_key"]: item for item in payload["libraries"]}
    assert libraries["authorized_dry_vocal_env_1"]["root_path"] == str(external_root)
    assert libraries["authorized_dry_vocal_env_1"]["storage_policy"] == "external_read_only"
    external_items = [item for item in payload["items"] if item["file_name"] == "external_voice.wav"]
    assert len(external_items) == 1
    assert external_items[0]["license_status"] == "user_provided_local"


def test_material_library_cover_source_is_not_training_baseline(client, isolated_backend, monkeypatch):
    monkeypatch.delenv(material_library_service.SONOVOX_DEMO_DATASET_ENV, raising=False)
    monkeypatch.delenv(material_library_service.AUTHORIZED_DRY_VOCAL_ROOTS_ENV, raising=False)
    source = isolated_backend / "shared_data" / "material_library" / "cover_source_candidates" / "user" / "cover_source.wav"
    _write_wav(source)

    resp = client.post("/api/material-library/scan")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["summary"]["dry_vocal_count"] == 0
    assert payload["summary"]["cover_source_count"] == 1
    cover_items = [item for item in payload["items"] if item["file_name"] == "cover_source.wav"]
    assert len(cover_items) == 1
    assert cover_items[0]["material_role"] == "cover_source"
    assert cover_items[0]["material_profile"] == "cover_source_manual_candidate"
    assert cover_items[0]["route_hint"] == "cover_source_manual_review_only"


def test_material_library_manifest_external_user_material_is_indexed(client, isolated_backend, tmp_path, monkeypatch):
    monkeypatch.delenv(material_library_service.SONOVOX_DEMO_DATASET_ENV, raising=False)
    monkeypatch.delenv(material_library_service.AUTHORIZED_DRY_VOCAL_ROOTS_ENV, raising=False)
    external_root = tmp_path / "desktop_dry"
    external_file = external_root / "zhu_test_voice.wav"
    _write_wav(external_file)
    manifest = isolated_backend / "shared_data" / "material_library" / "manifests" / "material_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": "zhu_test_voice_manifest",
                        "category": "authorized_dry_vocal",
                        "external_path": str(external_file),
                        "license_or_rights_basis": "user_provided_local_pending_manual_rights_confirmation",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    resp = client.post("/api/material-library/scan")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["summary"]["dry_vocal_count"] == 1
    manifest_items = [item for item in payload["items"] if item["file_name"] == "zhu_test_voice.wav"]
    assert len(manifest_items) == 1
    assert manifest_items[0]["route_hint"] == "training_baseline_external_manifest"
    assert manifest_items[0]["metadata"]["storage_policy"] == "external_manifest_only"


def test_material_library_hygiene_is_non_destructive(client, isolated_backend, monkeypatch):
    calls: list[str] = []

    def forbidden_dispatch(*args, **kwargs):
        calls.append("dispatch")
        raise AssertionError("material hygiene must not dispatch compute")

    monkeypatch.setattr(backend_main, "_dispatch_pending_compute_task", forbidden_dispatch)
    monkeypatch.setattr(backend_main, "_safe_dispatch_pending_compute_task", forbidden_dispatch)

    job_id = "task_stage53_hygiene"
    source = isolated_backend / "shared_data" / "jobs" / job_id / "input" / "source.wav"
    _write_wav(source)
    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "stage53_hygiene_test"},
        voice_model_id="v_stage53",
        voice_name="Stage53 Voice",
    )
    backend_db.update_task_status(job_id, "completed", "")
    artifact = isolated_backend / "shared_data" / "outputs" / job_id / "final_master.wav"
    _write_wav(artifact, seconds=0.5)
    register_job_artifact(
        job_id,
        "cover_mix",
        "cover_master",
        str(artifact),
        is_final=True,
        metadata={"quality_verdict": "blocked_auto", "quality_flags": ["too_short_under_10s"]},
    )

    resp = client.get("/api/material-library/hygiene")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["policy"]["mode"] == "non_destructive_review_only"
    assert payload["policy"]["delete_files"] is False
    assert payload["summary"]["cover_master_archive_candidates"] == 1
    assert payload["archive_candidates"][0]["job_id"] == job_id
    assert payload["archive_candidates"][0]["delete_allowed"] is False
    assert calls == []
