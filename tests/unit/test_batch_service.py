from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from backend.services.audit_service import list_audit_events
from backend.services.batch_service import create_batch, get_batch, import_tracks_to_batch, list_batches


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(content))


def test_create_batch_and_import_tracks(isolated_backend):
    batch = create_batch("Batch Alpha", ["douyin", "bilibili"])
    assert batch["batch_name"] == "Batch Alpha"
    assert batch["status"] == "draft"

    imported = asyncio.run(
        import_tracks_to_batch(
            batch["batch_id"],
            [_upload("alpha.wav", b"alpha"), _upload("beta.mp3", b"beta")],
            titles=["Alpha Song", "Beta Song"],
            artist="Test Artist",
            notes="batch import",
            metadata={"smoke": False},
        )
    )

    assert len(imported) == 2
    assert imported[0]["title"] == "Alpha Song"
    assert imported[1]["title"] == "Beta Song"

    batch_detail = get_batch(batch["batch_id"])
    assert batch_detail is not None
    assert batch_detail["track_count"] == 2
    assert len(batch_detail["tracks"]) == 2

    stored_path = Path(isolated_backend, imported[0]["source_audio_path"])
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"alpha"

    batches = list_batches(limit=10, offset=0)
    assert batches[0]["batch_id"] == batch["batch_id"]
    assert batches[0]["track_count"] == 2

    audit_events = list_audit_events(entity_type="batch", entity_id=batch["batch_id"], limit=10, offset=0)
    assert any(event["action"] == "create" for event in audit_events)
