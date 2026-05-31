from __future__ import annotations

import pytest

from backend.services import studio_effect_service
from backend.services.studio_effect_service import (
    FFMPEG_PROCESSING_MODE,
    FFMPEG_RENDER_ENGINE,
    StudioEffectExportError,
    _build_ffmpeg_filters,
    _run_ffmpeg_render,
    get_effect_rack_capabilities,
    normalize_effect_rack_payload,
)


def test_effect_rack_capabilities_always_include_copy_only(monkeypatch):
    monkeypatch.setattr(studio_effect_service, "get_ffmpeg_path", lambda: "")

    payload = get_effect_rack_capabilities()

    assert payload["ok"] is True
    engines = {item["id"]: item for item in payload["engines"]}
    assert engines["copy_only"]["available"] is True
    assert engines["copy_only"]["processing_mode"] == "copy_only_no_dsp"
    assert engines[FFMPEG_RENDER_ENGINE]["available"] is False
    assert engines[FFMPEG_RENDER_ENGINE]["processing_mode"] == FFMPEG_PROCESSING_MODE


def test_build_ffmpeg_filters_maps_supported_effects_and_marks_reverb_unsupported():
    rack = normalize_effect_rack_payload(
        [
            {"id": "eq", "enabled": True, "params": {"low": 3, "mid": 0, "high": -2}},
            {"id": "compressor", "enabled": True, "params": {"threshold": -12, "ratio": 3}},
            {"id": "limiter", "enabled": True, "params": {"ceiling": -1}},
            {"id": "reverb", "enabled": True, "params": {"mix": 40}},
        ]
    )

    filters, applied, unsupported = _build_ffmpeg_filters(rack)

    assert any(item.startswith("equalizer=f=100:") for item in filters)
    assert any(item.startswith("equalizer=f=8000:") for item in filters)
    assert any(item.startswith("acompressor=") for item in filters)
    assert any(item.startswith("alimiter=") for item in filters)
    assert {item["id"] for item in applied} == {"eq", "compressor", "limiter"}
    assert unsupported == [{"id": "reverb", "reason": "ffmpeg_dsp_v0 does not implement reverb yet."}]


def test_run_ffmpeg_render_reports_not_available(monkeypatch, tmp_path):
    monkeypatch.setattr(studio_effect_service, "get_ffmpeg_path", lambda: "")

    with pytest.raises(StudioEffectExportError) as exc:
        _run_ffmpeg_render(str(tmp_path / "source.wav"), str(tmp_path / "out.wav"), [])

    assert exc.value.code == "ffmpeg_not_available"
    assert exc.value.status_code == 503

