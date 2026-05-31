from __future__ import annotations

from backend.services.audio_material_service import decide_train_material_route, format_duration_label


def test_format_duration_label():
    assert format_duration_label(2709.9951) == "45分10秒"
    assert format_duration_label(932.702025) == "15分33秒"


def test_single_long_candidate_route():
    result = decide_train_material_route(
        1,
        duration_seconds=2709.9951,
        sample_rate=44100,
        channels=2,
        codec="mp3",
        container="mp3",
        bit_rate=320000,
        file_name="long.mp3",
    )
    assert result["material_profile"] == "single_long_candidate"
    assert result["recommended_route"] == "single_long_preprocess"
    assert result["single_long_eligible"] is True
    assert result["submission_allowed"] is True


def test_single_short_route_is_rejected():
    result = decide_train_material_route(
        1,
        duration_seconds=932.702025,
        sample_rate=44100,
        channels=2,
        codec="mp3",
        container="mp3",
        bit_rate=320000,
        file_name="short.mp3",
    )
    assert result["material_profile"] == "single_short_out_of_window"
    assert result["recommended_route"] == "multi_clean_direct"
    assert result["single_long_eligible"] is False
    assert result["submission_allowed"] is False


def test_multi_file_route_stays_multi_clean():
    result = decide_train_material_route(3, file_name="clip-1.wav")
    assert result["material_profile"] == "multi_file_dataset"
    assert result["recommended_route"] == "multi_clean_direct"
    assert result["submission_allowed"] is True
