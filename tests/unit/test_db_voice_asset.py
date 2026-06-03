from __future__ import annotations

import pytest

from backend import db as backend_db


@pytest.fixture()
def voice_db(isolated_backend):
    del isolated_backend
    return backend_db


def test_add_voice_asset_inserts_and_returns_true(voice_db, capsys):
    job_id = "job_voice_asset_insert"
    voice_db.create_task(job_id, "shared_data/uploads/sample.wav")
    ok = voice_db.add_voice_asset(
        "v_test_insert",
        "Test Voice",
        "shared_data/weights/test.pth",
        "shared_data/weights/test.index",
        default_pitch=0,
        source_job_id=job_id,
        metadata={"stage": "unit"},
    )
    out = capsys.readouterr().out

    assert ok is True
    assert "[OK]" in out
    assert "[SKIP]" not in out

    conn = voice_db.get_connection()
    try:
        asset = conn.execute(
            "SELECT * FROM voice_assets WHERE model_id = ?", ("v_test_insert",)
        ).fetchone()
        model = conn.execute(
            "SELECT * FROM voice_models WHERE voice_model_id = ?", ("v_test_insert",)
        ).fetchone()
    finally:
        conn.close()

    assert asset is not None
    assert asset["model_name"] == "Test Voice"
    assert model is not None
    assert model["source_job_id"] == job_id


def test_add_voice_asset_skips_identical_duplicate(voice_db, capsys):
    kwargs = dict(
        model_id="v_test_skip",
        model_name="Skip Voice",
        pth_path="shared_data/weights/skip.pth",
        index_path="shared_data/weights/skip.index",
        default_pitch=0,
        metadata={"stage": "unit"},
    )
    assert voice_db.add_voice_asset(**kwargs) is True
    capsys.readouterr()

    ok = voice_db.add_voice_asset(**kwargs)
    out = capsys.readouterr().out

    assert ok is False
    assert "[SKIP]" in out
    assert "[OK]" not in out


def test_add_voice_asset_updates_model_when_paths_change(voice_db, capsys):
    model_id = "v_test_update"
    voice_db.add_voice_asset(
        model_id,
        "Update Voice",
        "shared_data/weights/old.pth",
        "shared_data/weights/old.index",
    )
    capsys.readouterr()

    ok = voice_db.add_voice_asset(
        model_id,
        "Update Voice",
        "shared_data/weights/new.pth",
        "shared_data/weights/new.index",
    )
    out = capsys.readouterr().out

    assert ok is True
    assert "[OK]" in out

    conn = voice_db.get_connection()
    try:
        model = conn.execute(
            "SELECT pth_path, index_path FROM voice_models WHERE voice_model_id = ?",
            (model_id,),
        ).fetchone()
    finally:
        conn.close()

    assert model["pth_path"] == "shared_data/weights/new.pth"
    assert model["index_path"] == "shared_data/weights/new.index"