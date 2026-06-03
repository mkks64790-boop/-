from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from backend import main as backend_main
from backend.services import separation_eval_service as separation_eval


def _clear_material_env(monkeypatch) -> None:
    monkeypatch.delenv(separation_eval.SONOVOX_DEMO_DATASET_ENV, raising=False)
    monkeypatch.delenv(separation_eval.AUTHORIZED_DRY_VOCAL_ROOTS_ENV, raising=False)
    monkeypatch.delenv(separation_eval.LEGACY_TEST_MUSIC_OPT_IN_ENV, raising=False)


def _write_wav(path: Path, *, seconds: float = 1.0, sample_rate: int = 44100, amplitude: float = 0.25) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for index in range(frames):
            value = int(32767 * amplitude * math.sin(2 * math.pi * 440 * index / sample_rate))
            packed = struct.pack("<h", value)
            wf.writeframes(packed + packed)


def test_separation_eval_sources_api_is_stable_without_candidates(client, monkeypatch):
    _clear_material_env(monkeypatch)
    monkeypatch.setattr(backend_main, "PROJECT_ROOT", r"Z:\missing-feishark-test-root", raising=False)
    monkeypatch.setattr(separation_eval, "FIXED_SOURCE_DIRS", [], raising=False)
    monkeypatch.setattr(separation_eval, "_shallow_d_drive_keyword_dirs", lambda: [])

    resp = client.get("/api/separation/eval/sources")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["safe_rules"]["recursive_full_d_scan"] is False
    assert payload["total_candidates"] == 0
    assert payload["separation_eval_total"] == 0
    assert payload["candidates"] == []


def test_separation_eval_sources_api_lists_local_input(client, isolated_backend, monkeypatch):
    _clear_material_env(monkeypatch)
    monkeypatch.setattr(backend_main, "PROJECT_ROOT", str(isolated_backend), raising=False)
    monkeypatch.setattr(separation_eval, "FIXED_SOURCE_DIRS", [], raising=False)
    monkeypatch.setattr(separation_eval, "_shallow_d_drive_keyword_dirs", lambda: [])
    sample = isolated_backend / "shared_data" / "separation_eval" / "input" / "sample.wav"
    _write_wav(sample)

    resp = client.get("/api/separation/eval/sources")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total_candidates"] == 1
    candidate = payload["candidates"][0]
    assert candidate["file_name"] == "sample.wav"
    assert candidate["extension"] == ".wav"
    assert candidate["duration_seconds"] is None or candidate["duration_seconds"] > 0
    assert candidate["source_group"] == "project_input"
    assert candidate["material_role"] == "clean_song"
    assert candidate["separation_eval_allowed"] is True


def test_sonovox_demo_dataset_is_training_baseline_not_separation_source(tmp_path, monkeypatch):
    _clear_material_env(monkeypatch)
    sonovox_root = tmp_path / "Sonovox AI Demo Dataset"
    sample = sonovox_root / "Demo Song" / "Lead Vocal.wav"
    _write_wav(sample)
    monkeypatch.setenv(separation_eval.SONOVOX_DEMO_DATASET_ENV, str(sonovox_root))
    monkeypatch.setattr(separation_eval, "FIXED_SOURCE_DIRS", [], raising=False)
    monkeypatch.setattr(separation_eval, "_shallow_d_drive_keyword_dirs", lambda: [])

    payload = separation_eval.discover_sources(tmp_path / "project", max_items=5)

    assert payload["total_candidates"] == 1
    assert payload["separation_eval_total"] == 0
    assert payload["training_candidate_total"] == 1
    candidate = payload["candidates"][0]
    assert candidate["source_group"] == "sonovox_demo"
    assert candidate["library_key"] == "sonovox_ai_demo_dataset"
    assert candidate["material_role"] == "dry_vocal"
    assert candidate["material_profile"] == "clean_dry_vocal"
    assert candidate["training_candidate_allowed"] is True
    assert candidate["separation_eval_allowed"] is False
    assert payload["separation_eval_candidates"] == []


def test_legacy_test_music_is_opt_in_and_risky_dj_stays_excluded(tmp_path, monkeypatch):
    _clear_material_env(monkeypatch)
    legacy_root = tmp_path / "legacy_music"
    clean_song = legacy_root / "plain_song.wav"
    risky_song = legacy_root / "依邦妮 - 口哨战歌 (DJ版).flac"
    _write_wav(clean_song)
    _write_wav(risky_song)
    monkeypatch.setattr(separation_eval, "FIXED_SOURCE_DIRS", [legacy_root], raising=False)
    monkeypatch.setattr(separation_eval, "_shallow_d_drive_keyword_dirs", lambda: [])

    blocked_payload = separation_eval.discover_sources(tmp_path / "project", max_items=5)
    assert blocked_payload["total_candidates"] == 0
    assert blocked_payload["excluded_candidates"] == []

    monkeypatch.setenv(separation_eval.LEGACY_TEST_MUSIC_OPT_IN_ENV, "1")
    opt_in_payload = separation_eval.discover_sources(tmp_path / "project", max_items=5)
    assert opt_in_payload["total_candidates"] == 1
    assert opt_in_payload["separation_eval_total"] == 1
    assert opt_in_payload["candidates"][0]["file_name"] == "plain_song.wav"
    assert opt_in_payload["candidates"][0]["source_group"] == "legacy_test_music"
    assert opt_in_payload["excluded_total"] == 1
    assert opt_in_payload["excluded_candidates"][0]["file_name"] == "依邦妮 - 口哨战歌 (DJ版).flac"
    assert opt_in_payload["excluded_candidates"][0]["material_role"] == "dj_mix"


def test_separation_eval_runs_api_and_missing_detail(client):
    list_resp = client.get("/api/separation/eval/runs")
    missing_resp = client.get("/api/separation/eval/runs/not_a_real_run")

    assert list_resp.status_code == 200
    assert "runs" in list_resp.json()
    assert missing_resp.status_code == 404


def test_separation_eval_run_detail_artifact_urls_and_post_policy(client, isolated_backend, monkeypatch):
    monkeypatch.setattr(backend_main, "PROJECT_ROOT", str(isolated_backend), raising=False)
    run_id = "stage45r_test_contract"
    item_dir = isolated_backend / "shared_data" / "separation_eval" / "runs" / run_id / "01_contract"
    original = item_dir / "original_excerpt.wav"
    vocal = item_dir / "vocal.wav"
    instrumental = item_dir / "instrumental.wav"
    _write_wav(original, seconds=10)
    _write_wav(vocal, seconds=8)
    _write_wav(instrumental, seconds=8)
    separation_eval.build_quality_report(
        source_path=str(original),
        item_dir=item_dir,
        products={
            "original_excerpt": str(original),
            "vocal": str(vocal),
            "instrumental": str(instrumental),
        },
    )
    (item_dir.parent / "run_manifest.json").write_text(
        '{"run_id":"stage45r_test_contract","executed":true,"source_count":1,"status":"completed"}',
        encoding="utf-8",
    )

    detail_resp = client.get(f"/api/separation/eval/runs/{run_id}")
    post_resp = client.post("/api/separation/eval/run")

    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["block_training"] is True
    item = detail["items"][0]
    assert item["duration_mismatch"] is True
    assert item["duration_mismatch_risk"] == "high"
    assert item["artifact_urls"]["original"].endswith("/artifacts/original")

    artifact_resp = client.get(item["artifact_urls"]["vocal"])
    assert artifact_resp.status_code == 200
    assert artifact_resp.headers["content-type"].startswith("audio/wav")
    assert artifact_resp.content

    missing_artifact = client.get(f"/api/separation/eval/runs/{run_id}/items/99/artifacts/vocal")
    assert missing_artifact.status_code == 404

    assert post_resp.status_code == 501
    assert post_resp.json()["detail"]["code"] == "separation_eval_execute_disabled"


def test_quality_report_shape_for_generated_wavs(tmp_path):
    item_dir = tmp_path / "audit_item"
    original = item_dir / "original_excerpt.wav"
    vocal = item_dir / "vocal.wav"
    instrumental = item_dir / "instrumental.wav"
    for path in (original, vocal, instrumental):
        _write_wav(path)

    report = separation_eval.build_quality_report(
        source_path=str(original),
        item_dir=item_dir,
        products={
            "original_excerpt": str(original),
            "vocal": str(vocal),
            "instrumental": str(instrumental),
        },
    )

    assert (item_dir / "quality_report.json").is_file()
    assert report["noise_risk"] in {"low", "medium", "high"}
    assert report["duration_mismatch"] is False
    assert report["duration_mismatch_risk"] == "low"
    for product in ("original_excerpt", "vocal", "instrumental"):
        metrics = report["metrics"][product]
        assert metrics["ok"] is True
        for key in (
            "duration_seconds",
            "sample_rate",
            "channels",
            "peak_db",
            "rms_db",
            "clipping_risk",
            "silence_ratio",
            "high_freq_energy_ratio",
            "zero_crossing_rate",
            "dc_offset_estimate",
        ):
            assert key in metrics
