from __future__ import annotations

import json

from backend.db import get_connection
from backend.services.batch_service import create_batch
from backend.services.track_service import (
    get_track,
    list_tracks,
    set_track_current_lyrics,
    update_track,
)


def _insert_track(
    *,
    batch_id: str,
    track_id: str,
    title: str,
    artist: str = "",
    status: str = "draft",
    metadata: dict | None = None,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO tracks (
                track_id, batch_id, title, artist, source_type, status,
                notes, source_audio_path, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                track_id,
                batch_id,
                title,
                artist,
                "upload",
                status,
                "seeded by unit test",
                f"shared_data/batches/{batch_id}/{track_id}.wav",
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_get_track_and_list_tracks(isolated_backend):
    batch = create_batch("Unit Batch")
    _insert_track(
        batch_id=batch["batch_id"],
        track_id="trk_unit_alpha",
        title="Alpha Song",
        artist="Artist A",
        status="imported",
        metadata={"source": "unit"},
    )
    _insert_track(
        batch_id=batch["batch_id"],
        track_id="trk_unit_beta",
        title="Beta Song",
        artist="Artist B",
        status="draft",
    )

    detail = get_track("trk_unit_alpha")
    assert detail is not None
    assert detail["track_id"] == "trk_unit_alpha"
    assert detail["batch_name"] == "Unit Batch"
    assert detail["metadata"]["source"] == "unit"

    tracks = list_tracks(batch_id=batch["batch_id"], limit=10, offset=0)
    assert [item["track_id"] for item in tracks] == ["trk_unit_beta", "trk_unit_alpha"]


def test_update_track_and_set_current_lyrics(isolated_backend):
    batch = create_batch("Track Update Batch")
    _insert_track(
        batch_id=batch["batch_id"],
        track_id="trk_update_case",
        title="Original Title",
        artist="Original Artist",
        status="draft",
    )

    updated = update_track(
        "trk_update_case",
        {
            "title": "Updated Title",
            "artist": "Updated Artist",
            "status": "lyrics_ready",
            "notes": "patched",
            "ignored_field": "should_not_apply",
        },
    )
    assert updated is not None
    assert updated["title"] == "Updated Title"
    assert updated["artist"] == "Updated Artist"
    assert updated["status"] == "lyrics_ready"
    assert "ignored_field" not in updated

    set_track_current_lyrics(
        "trk_update_case",
        lyric_document_id="lyr_current_001",
        timeline_id="tl_current_001",
    )
    detail = get_track("trk_update_case")
    assert detail is not None
    assert detail["current_lyric_document_id"] == "lyr_current_001"
    assert detail["current_timeline_version_id"] == "tl_current_001"

    set_track_current_lyrics("trk_update_case", lyric_document_id=None, timeline_id="tl_current_002")
    detail = get_track("trk_update_case")
    assert detail is not None
    assert detail["current_lyric_document_id"] == "lyr_current_001"
    assert detail["current_timeline_version_id"] == "tl_current_002"
