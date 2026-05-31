from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend import db as backend_db
from backend.services.asset_service import register_job_artifact
from backend.services.batch_service import create_batch
from backend.services.job_service import create_cover_job
from backend.services.studio_effect_service import (
    EXPORT_ARTIFACT_TYPE,
    PROCESSING_MODE,
    StudioEffectExportError,
    export_effect_rack_draft,
    normalize_effect_rack_payload,
)


def _insert_track(batch_id: str, track_id: str) -> None:
    conn = backend_db.get_connection()
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
                "Studio Effect Track",
                "Unit Artist",
                "upload",
                "cover_ready",
                "",
                f"shared_data/batches/{batch_id}/{track_id}.wav",
                "{}",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_cover_with_artifact(root: Path, track_id: str, job_id: str = "task_effect_unit") -> str:
    create_cover_job(
        job_id,
        input_path="shared_data/batches/input.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "studio_effect_unit"},
        track_id=track_id,
        voice_model_id="vm_effect",
        voice_name="Effect Model",
    )
    backend_db.update_task_status(job_id, "\u5df2\u5b8c\u6210", "")
    source = root / "shared_data" / "outputs" / job_id / "final_master.wav"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"RIFF-STUDIO-EFFECT-SOURCE")
    artifact_id = register_job_artifact(job_id, "cover_mix", "cover_master", str(source), is_final=True)
    assert artifact_id
    return artifact_id


def test_normalize_effect_rack_payload_clamps_and_filters_params():
    normalized = normalize_effect_rack_payload(
        [
            {
                "id": "eq",
                "enabled": "true",
                "status": "draft",
                "params": {"low": -99, "mid": "2.5", "high": 99, "ignored": 123},
            },
            {
                "id": "compressor",
                "enabled": False,
                "params": {"threshold": "-99", "ratio": "99"},
            },
        ]
    )

    assert normalized == [
        {"id": "eq", "enabled": True, "status": "draft", "params": {"low": -6, "mid": 2.5, "high": 6}},
        {"id": "compressor", "enabled": False, "status": "draft", "params": {"threshold": -30, "ratio": 8}},
    ]


def test_unknown_effect_slot_is_rejected():
    with pytest.raises(StudioEffectExportError) as exc:
        normalize_effect_rack_payload([{"id": "vst_magic", "enabled": True, "params": {}}])

    assert exc.value.code == "unknown_effect_slot"


def test_export_rejects_source_job_not_for_track(isolated_backend):
    batch = create_batch("Effect Service Batch")
    _insert_track(batch["batch_id"], "trk_effect_a")
    _insert_track(batch["batch_id"], "trk_effect_b")
    artifact_id = _seed_cover_with_artifact(isolated_backend, "trk_effect_a")

    with pytest.raises(StudioEffectExportError) as exc:
        export_effect_rack_draft(
            track_id="trk_effect_b",
            source_job_id="task_effect_unit",
            source_artifact_id=artifact_id,
            effect_rack=[],
        )

    assert exc.value.code == "source_job_not_for_track"


def test_export_effect_rack_draft_copies_audio_and_registers_artifact(isolated_backend):
    batch = create_batch("Effect Export Batch")
    track_id = "trk_effect_export"
    job_id = "task_effect_export"
    _insert_track(batch["batch_id"], track_id)
    source_artifact_id = _seed_cover_with_artifact(isolated_backend, track_id, job_id)

    result = export_effect_rack_draft(
        track_id=track_id,
        source_job_id=job_id,
        source_artifact_id=source_artifact_id,
        effect_rack=[{"id": "limiter", "enabled": True, "params": {"ceiling": -99}}],
        export_profile="studio_balanced",
        note="unit export",
    )

    assert result["ok"] is True
    assert result["processing_mode"] == PROCESSING_MODE
    assert result["artifact_type"] == EXPORT_ARTIFACT_TYPE
    assert result["source_artifact_id"] == source_artifact_id
    assert "artifact_id=" in result["studio_url"]

    conn = backend_db.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM job_artifacts WHERE artifact_id = ?",
            (result["artifact_id"],),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    artifact = dict(row)
    assert artifact["stage_name"] == "studio_effect_export"
    assert artifact["artifact_type"] == EXPORT_ARTIFACT_TYPE
    assert artifact["is_final"] == 0
    assert Path(artifact["file_path"]).exists()
    metadata = json.loads(artifact["metadata_json"])
    assert metadata["processing_mode"] == PROCESSING_MODE
    assert metadata["source_artifact_id"] == source_artifact_id
    assert metadata["effect_rack"][0]["params"]["ceiling"] == -6
