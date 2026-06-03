from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from backend import vocal_separator


def _write_wav(path: Path, seconds: float, sample_rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for index in range(frames):
            value = int(10000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            wf.writeframes(struct.pack("<h", value))


def test_uvr_runner_template_uses_model_frame_windows_without_time_crop():
    script = vocal_separator._RUNNER_SCRIPT

    assert "frames_per_chunk = model_frames" in script
    assert "chunk_seconds = 5" not in script
    assert "real = real[:, :model_frames]" not in script
    assert "imag = imag[:, :model_frames]" not in script
    assert "time chunk exceeds model_frames" in script
    assert "length=len(audio)" in script


def test_duration_preservation_guard_reports_mismatch(tmp_path):
    input_path = tmp_path / "input.wav"
    vocal_path = tmp_path / "vocal.wav"
    instrumental_path = tmp_path / "instrumental.wav"
    _write_wav(input_path, 10.0)
    _write_wav(vocal_path, 6.0)
    _write_wav(instrumental_path, 6.0)

    error = vocal_separator._validate_duration_preservation(
        str(input_path),
        str(vocal_path),
        str(instrumental_path),
    )

    assert "duration mismatch" in error
    assert "input=10.000s" in error
    assert "vocal=6.000s" in error
    assert "instrumental=6.000s" in error


def test_duration_preservation_guard_accepts_near_equal_lengths(tmp_path):
    input_path = tmp_path / "input.wav"
    vocal_path = tmp_path / "vocal.wav"
    instrumental_path = tmp_path / "instrumental.wav"
    _write_wav(input_path, 10.0)
    _write_wav(vocal_path, 9.8)
    _write_wav(instrumental_path, 9.8)

    error = vocal_separator._validate_duration_preservation(
        str(input_path),
        str(vocal_path),
        str(instrumental_path),
    )

    assert error == ""
