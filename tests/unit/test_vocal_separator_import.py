from __future__ import annotations


def test_vocal_separator_import_initializes_project_root():
    from backend import vocal_separator

    assert vocal_separator.PROJECT_ROOT
    assert "external" in vocal_separator.AUDIO_PIPELINE_DIR or vocal_separator.AUDIO_PIPELINE_DIR
