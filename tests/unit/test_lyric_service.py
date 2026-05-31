from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from backend.services.batch_service import create_batch, import_tracks_to_batch
from backend.services.lyric_service import align_lyrics, extract_lyrics, list_lyric_versions, promote_lyric_timeline


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(content))


def test_extract_align_and_promote_lyric_versions(isolated_backend):
    batch = create_batch("Lyrics Batch")
    imported = asyncio.run(
        import_tracks_to_batch(
            batch["batch_id"],
            [_upload("lyrics.wav", b"lyrics-data")],
            titles=["Lyrics Track"],
            artist="Singer A",
        )
    )
    track_id = imported[0]["track_id"]

    extract_payload = extract_lyrics(
        track_id,
        lyric_text="Line one\nLine two",
        source="unit_test",
    )
    document = extract_payload["lyric_document"]
    assert document["track_id"] == track_id
    assert "Line one" in document["text_content"]

    align_payload = align_lyrics(
        track_id,
        lyric_document_id=document["lyric_document_id"],
        engine="unit_align_v1",
        append_outro_card=False,
    )
    current_version_id = align_payload["current_timeline_version_id"]
    versions = align_payload["versions"]
    assert current_version_id
    assert len(versions) == 1

    version = versions[0]
    for field in ("txt_path", "lrc_path", "srt_path", "ass_path"):
        path = Path(isolated_backend, version[field])
        assert path.exists(), field

    second_align = align_lyrics(
        track_id,
        lyric_text="New first line\nNew second line",
        engine="unit_align_v2",
        append_outro_card=True,
    )
    assert len(second_align["versions"]) == 2
    newer_version_id = second_align["current_timeline_version_id"]
    older_version_id = next(item["timeline_id"] for item in second_align["versions"] if item["timeline_id"] != newer_version_id)

    promoted = promote_lyric_timeline(track_id, older_version_id)
    assert promoted["current_timeline_version_id"] == older_version_id

    latest = list_lyric_versions(track_id)
    assert latest["current_timeline_version_id"] == older_version_id
