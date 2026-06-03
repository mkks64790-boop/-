from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

from backend import db as backend_db
from backend import pitch_processor, voice_changer
from backend.services import asset_service
from backend.services.job_service import create_cover_job
from backend.services.stage_log_service import list_stage_logs
from backend.strategies import cover_strategy


def _write_wav(path: Path, seconds: float = 1.0, sample_rate: int = 44100, amplitude: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for index in range(frames):
            value = int(amplitude * math.sin(2 * math.pi * 220 * index / sample_rate))
            wf.writeframes(struct.pack("<h", value))


def _seed_task(job_id: str, status: str) -> None:
    backend_db.create_task(job_id, f"shared_data/jobs/{job_id}/input/source.wav")
    backend_db.update_task_status(job_id, status, "")


def _patch_pitch_engine(monkeypatch, tmp_path: Path, stderr: str) -> None:
    audio_pipeline = tmp_path / "AudioPipeline"
    venv_python = audio_pipeline / "venv" / "Scripts" / "python.exe"
    rmvpe = audio_pipeline / "rmvpe.onnx"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("python", encoding="utf-8")
    rmvpe.write_text("model", encoding="utf-8")

    monkeypatch.setattr(pitch_processor, "AUDIO_PIPELINE_DIR", str(audio_pipeline))
    monkeypatch.setattr(pitch_processor, "AUDIO_PIPELINE_VENV", str(venv_python))
    monkeypatch.setattr(pitch_processor, "RMVPE_MODEL_PATH", str(rmvpe))

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr=stderr)

    monkeypatch.setattr(pitch_processor.subprocess, "run", fake_run)


def test_pitch_fallback_only_matches_known_frame_broadcast_error():
    known = "ValueError: operands could not be broadcast together with shapes (1944,) (2048,) (1944,)"
    unrelated_same_size = "ValueError: operands could not be broadcast together with shapes (2048,) (2048,) (2048,)"
    unrelated_other = "RuntimeError: RMVPE failed to load model"

    assert pitch_processor._is_safe_pitch_fallback_error(known)
    assert not pitch_processor._is_safe_pitch_fallback_error(unrelated_same_size)
    assert not pitch_processor._is_safe_pitch_fallback_error(unrelated_other)


def test_pitch_fallback_copies_vocal_and_reports_contract(isolated_backend, monkeypatch, tmp_path):
    job_id = "task_stage57_pitch_fallback"
    output_root = isolated_backend / "shared_data" / "outputs"
    vocal_path = output_root / job_id / "vocal.wav"
    fixed_path = output_root / job_id / "vocal_fixed.wav"
    _write_wav(vocal_path, seconds=1.0)
    _seed_task(job_id, pitch_processor.STATUS_PITCH_FIXING)
    monkeypatch.setattr(pitch_processor, "OUTPUT_ROOT", str(output_root))

    stderr = "ValueError: operands could not be broadcast together with shapes (1944,) (2048,) (1944,)"
    _patch_pitch_engine(monkeypatch, tmp_path, stderr)

    result = pitch_processor.fix_vocal_pitch(job_id)

    assert result["success"] is True
    assert result["fallback"] == "copy_original_vocal"
    assert result["output"] == str(fixed_path)
    assert fixed_path.read_bytes() == vocal_path.read_bytes()


def test_pitch_fallback_does_not_mask_unknown_errors_or_missing_source(isolated_backend, monkeypatch, tmp_path):
    job_id = "task_stage57_pitch_unknown"
    output_root = isolated_backend / "shared_data" / "outputs"
    vocal_path = output_root / job_id / "vocal.wav"
    fixed_path = output_root / job_id / "vocal_fixed.wav"
    _write_wav(vocal_path, seconds=1.0)
    _seed_task(job_id, pitch_processor.STATUS_PITCH_FIXING)
    monkeypatch.setattr(pitch_processor, "OUTPUT_ROOT", str(output_root))
    _patch_pitch_engine(monkeypatch, tmp_path, "RuntimeError: PitchCorrector failed for unknown reason")

    result = pitch_processor.fix_vocal_pitch(job_id)

    assert result["success"] is False
    assert "fallback" not in result
    assert not fixed_path.exists()

    missing_fixed = tmp_path / "missing" / "vocal_fixed.wav"
    missing_result = pitch_processor._copy_vocal_as_fixed(str(tmp_path / "missing.wav"), str(missing_fixed))
    assert missing_result["success"] is False
    assert not missing_fixed.exists()


def test_voice_stage_uses_vocal_fixed_after_pitch_fallback(isolated_backend, monkeypatch):
    job_id = "task_stage57_voice_uses_fixed"
    model_id = "v_stage57"
    output_root = isolated_backend / "shared_data" / "outputs"
    fixed_vocal = output_root / job_id / "vocal_fixed.wav"
    produced = isolated_backend / "rvc_result.wav"
    pth = isolated_backend / "shared_data" / "weights" / "voice.pth"
    index = isolated_backend / "shared_data" / "weights" / "voice.index"
    _write_wav(fixed_vocal, seconds=1.0)
    _write_wav(produced, seconds=1.0)
    pth.parent.mkdir(parents=True, exist_ok=True)
    pth.write_bytes(b"pth")
    index.write_bytes(b"index")
    _seed_task(job_id, voice_changer.STATUS_VC_PROCESSING)
    backend_db.add_voice_asset(model_id, "Stage57 Voice", str(pth), str(index), default_pitch=0)

    seen_inputs: list[str] = []
    monkeypatch.setattr(voice_changer, "OUTPUT_ROOT", str(output_root))
    monkeypatch.setattr(voice_changer, "_discover_rvc_base_url", lambda: "http://127.0.0.1:7866")
    monkeypatch.setattr(voice_changer, "_sync_weight_to_rvc_runtime", lambda path: Path(path).name)
    monkeypatch.setattr(voice_changer, "_sync_index_to_rvc_runtime", lambda path: str(path))
    monkeypatch.setattr(voice_changer, "Client", lambda *args, **kwargs: object())
    monkeypatch.setattr(voice_changer, "_refresh_rvc_choices", lambda client: None)
    monkeypatch.setattr(voice_changer, "_load_rvc_model", lambda client, model_name, protect: None)

    def fake_infer(**kwargs):
        seen_inputs.append(kwargs["input_path"])
        return ["ok", str(produced)]

    monkeypatch.setattr(voice_changer, "_run_rvc_infer", fake_infer)

    result = voice_changer.transform_voice(job_id, model_id=model_id)

    assert result["success"] is True
    assert seen_inputs == [str(fixed_vocal)]
    assert Path(result["output"]).name == "vocal_transformed.wav"
    assert Path(result["output"]).exists()


def test_cover_strategy_logs_stage_artifacts_and_final_quality_contract(isolated_backend, monkeypatch):
    job_id = "task_stage57_cover_contract"
    input_path = isolated_backend / "shared_data" / "jobs" / job_id / "input" / "source.wav"
    output_root = isolated_backend / "shared_data" / "outputs" / job_id
    _write_wav(input_path, seconds=1.0)
    job = create_cover_job(
        job_id,
        input_path=str(input_path),
        output_root=f"shared_data/jobs/{job_id}",
        voice_model_id="v_stage57",
        voice_name="Stage57 Voice",
    )

    stage_files = {
        "cover_split": [("cover_vocal", "vocal.wav"), ("cover_instrumental", "instrumental.wav")],
        "cover_pitch": [("cover_fixed", "vocal_fixed.wav")],
        "cover_voice": [("cover_transformed", "vocal_transformed.wav")],
        "cover_mix": [("cover_master", "final_master.wav")],
    }

    def fake_split(job_id_arg: str, input_path_arg: str) -> dict:
        _write_wav(output_root / "vocal.wav", seconds=1.0)
        _write_wav(output_root / "instrumental.wav", seconds=1.0)
        return {"success": True, "vocal": str(output_root / "vocal.wav"), "instrumental": str(output_root / "instrumental.wav")}

    def fake_pitch(job_id_arg: str, **kwargs) -> dict:
        _write_wav(output_root / "vocal_fixed.wav", seconds=1.0)
        return {"success": True, "output": str(output_root / "vocal_fixed.wav"), "fallback": "copy_original_vocal"}

    def fake_voice(job_id_arg: str, **kwargs) -> dict:
        assert (output_root / "vocal_fixed.wav").exists()
        _write_wav(output_root / "vocal_transformed.wav", seconds=1.0)
        return {"success": True, "output": str(output_root / "vocal_transformed.wav")}

    def fake_mix(job_id_arg: str) -> dict:
        _write_wav(output_root / "final_master.wav", seconds=12.0, sample_rate=44100)
        return {
            "success": True,
            "output": str(output_root / "final_master.wav"),
            "duration": 12.0,
            "stats": {"sample_rate": 44100},
        }

    def register_from_isolated_outputs(job_id_arg: str, stage_name: str) -> list[str]:
        artifact_ids = []
        for artifact_type, file_name in stage_files[stage_name]:
            artifact_id = asset_service.register_job_artifact(
                job_id_arg,
                stage_name,
                artifact_type,
                str(output_root / file_name),
                is_final=(artifact_type == "cover_master"),
            )
            if artifact_id:
                artifact_ids.append(artifact_id)
        return artifact_ids

    monkeypatch.setattr(cover_strategy, "split_audio", fake_split)
    monkeypatch.setattr(cover_strategy, "fix_vocal_pitch", fake_pitch)
    monkeypatch.setattr(cover_strategy, "transform_voice", fake_voice)
    monkeypatch.setattr(cover_strategy, "merge_master_audio", fake_mix)
    monkeypatch.setattr(cover_strategy, "register_cover_stage_outputs", register_from_isolated_outputs)
    monkeypatch.setattr(cover_strategy, "cleanup_job_transients", lambda job_id_arg: {})

    result = cover_strategy.CoverStrategy().execute(job)

    assert result["success"] is True

    logs = list_stage_logs(job_id)
    completed = [log for log in logs if log["status"] == "completed"]
    assert [log["stage_name"] for log in completed] == ["cover_split", "cover_pitch", "cover_voice", "cover_mix"]
    for log in completed:
        detail = json.loads(log["detail_json"])
        assert len(detail["artifact_ids"]) == cover_strategy.EXPECTED_COVER_STAGE_ARTIFACTS[log["stage_name"]]

    artifacts = asset_service.list_job_artifacts(job_id)
    by_stage = {(item["stage_name"], item["artifact_type"]): item for item in artifacts}
    for stage_name, pairs in stage_files.items():
        for artifact_type, _file_name in pairs:
            assert (stage_name, artifact_type) in by_stage

    final_artifact = by_stage[("cover_mix", "cover_master")]
    assert final_artifact["is_final"] == 1
    quality = asset_service.summarize_artifact_audio_quality(final_artifact)
    assert quality["duration_sec"] == 12.0
    assert quality["sample_rate"] == 44100
    assert quality["quality_verdict"] == "needs_manual_quality_check"
