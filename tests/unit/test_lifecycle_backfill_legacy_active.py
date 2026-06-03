from __future__ import annotations

import json

from backend import db as backend_db
from backend.services.job_service import create_cover_job
from backend.services.lifecycle_service import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_TEST_DATA,
    LIFECYCLE_TRANSIENT,
    backfill_lifecycle_states,
    should_backfill_lifecycle_state,
)
from backend.services.model_service import upsert_voice_model


def test_should_backfill_when_stored_active_but_inferred_differs():
    assert should_backfill_lifecycle_state("active", LIFECYCLE_TRANSIENT)
    assert not should_backfill_lifecycle_state("test_data", LIFECYCLE_ACTIVE)
    assert not should_backfill_lifecycle_state("archived", LIFECYCLE_ACTIVE)


def test_backfill_smoke_artifact_migration_default_active(isolated_backend):
    job_id = "smoke_backfill_artifact"
    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"smoke": True, "test_scope": "smoke"},
        voice_name="smoke_voice",
    )

    conn = backend_db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO job_artifacts (
                artifact_id, job_id, stage_name, artifact_type,
                file_path, file_size, is_final, lifecycle_state, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "art_backfill_smoke",
                job_id,
                "cover_split",
                "cover_vocal",
                f"shared_data/outputs/{job_id}/vocal.wav",
                128,
                0,
                "active",
                "{}",
            ),
        )
        conn.commit()
        stats = backfill_lifecycle_states(conn)
        conn.commit()
        row = conn.execute(
            "SELECT lifecycle_state FROM job_artifacts WHERE artifact_id = ?",
            ("art_backfill_smoke",),
        ).fetchone()
        assert stats["job_artifacts"] >= 1
        assert row["lifecycle_state"] == LIFECYCLE_TEST_DATA
    finally:
        conn.close()


def test_backfill_real_job_transient_intermediate(isolated_backend):
    job_id = "real_backfill_transient"
    create_cover_job(
        job_id,
        input_path=f"shared_data/jobs/{job_id}/input/source.wav",
        output_root=f"shared_data/jobs/{job_id}",
        metadata={"source": "stage47_real_acceptance"},
        voice_name="RealVoice",
    )

    conn = backend_db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO job_artifacts (
                artifact_id, job_id, stage_name, artifact_type,
                file_path, file_size, is_final, lifecycle_state, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "art_backfill_transient",
                job_id,
                "cover_split",
                "cover_vocal",
                f"shared_data/outputs/{job_id}/vocal.wav",
                128,
                0,
                "active",
                "{}",
            ),
        )
        conn.commit()
        backfill_lifecycle_states(conn)
        conn.commit()
        row = conn.execute(
            "SELECT lifecycle_state FROM job_artifacts WHERE artifact_id = ?",
            ("art_backfill_transient",),
        ).fetchone()
        assert row["lifecycle_state"] == LIFECYCLE_TRANSIENT
    finally:
        conn.close()


def test_backfill_smoke_voice_model_migration_default_active(isolated_backend):
    model_id = "v_smoke_backfill"
    upsert_voice_model(
        model_id,
        "smoke_model_name",
        "shared_data/weights/smoke.pth",
        "shared_data/weights/smoke.index",
        metadata={"smoke": True},
    )

    conn = backend_db.get_connection()
    try:
        conn.execute(
            "UPDATE voice_models SET lifecycle_state = 'active' WHERE voice_model_id = ?",
            (model_id,),
        )
        conn.commit()
        stats = backfill_lifecycle_states(conn)
        conn.commit()
        row = conn.execute(
            "SELECT lifecycle_state FROM voice_models WHERE voice_model_id = ?",
            (model_id,),
        ).fetchone()
        assert stats["voice_models"] >= 1
        assert row["lifecycle_state"] == LIFECYCLE_TEST_DATA
    finally:
        conn.close()