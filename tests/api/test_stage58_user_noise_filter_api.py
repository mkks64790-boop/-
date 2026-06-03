from __future__ import annotations

import json

from backend import db as backend_db
from backend.services.job_service import create_cover_job, create_train_job
from backend.services.model_service import upsert_voice_model


def _job_ids(payload: dict) -> set[str]:
    return {item["job_id"] for item in payload["items"]}


def _seed_stage58_jobs() -> dict[str, str]:
    real_stage47 = "stage47_real_single_long_training"
    create_train_job(
        real_stage47,
        voice_name="Stage47RealSinger",
        dataset_path=f"shared_data/jobs/{real_stage47}/dataset",
        output_root=f"shared_data/jobs/{real_stage47}",
        strategy_key="single_long_preprocess",
        metadata={"source": "stage47_real_single_long_training"},
    )
    backend_db.update_task_status(real_stage47, "completed", "")

    real_stage56 = "stage56_actual_rvc_cover"
    create_cover_job(
        real_stage56,
        input_path=f"shared_data/jobs/{real_stage56}/input/source.wav",
        output_root=f"shared_data/jobs/{real_stage56}",
        metadata={"source": "stage56_actual_rvc_connectivity"},
        voice_name="Stage56ActualCover",
    )
    backend_db.update_task_status(real_stage56, "completed", "")

    smoke_prefix = "smoke_stale_pending_cover"
    create_cover_job(
        smoke_prefix,
        input_path=f"shared_data/jobs/{smoke_prefix}/input/source.wav",
        output_root=f"shared_data/jobs/{smoke_prefix}",
        metadata={"source": "stage58_noise_filter"},
        voice_name="smoke_queued_voice",
    )
    backend_db.update_task_status(smoke_prefix, "pending", "")

    metadata_smoke = "stage58_metadata_smoke"
    create_train_job(
        metadata_smoke,
        voice_name="Stage58MetadataSmoke",
        dataset_path=f"shared_data/jobs/{metadata_smoke}/dataset",
        output_root=f"shared_data/jobs/{metadata_smoke}",
        strategy_key="single_long_preprocess",
        metadata={"smoke": True, "test_scope": "smoke"},
    )
    backend_db.update_task_status(metadata_smoke, "completed", "")

    playwright_job = "stage58_playwright_self_check"
    create_cover_job(
        playwright_job,
        input_path=f"shared_data/jobs/{playwright_job}/input/source.wav",
        output_root=f"shared_data/jobs/{playwright_job}",
        metadata={"source": "playwright_stage58_self_check"},
        voice_name="Stage58PlaywrightSelfCheck",
    )
    backend_db.update_task_status(playwright_job, "failed", "synthetic playwright failure")

    separation_eval_job = "stage58_separation_eval_probe"
    create_cover_job(
        separation_eval_job,
        input_path=f"shared_data/jobs/{separation_eval_job}/input/source.wav",
        output_root=f"shared_data/jobs/{separation_eval_job}",
        metadata={"test_scope": "separation_eval"},
        voice_name="Stage58SeparationEvalProbe",
    )
    backend_db.update_task_status(separation_eval_job, "completed", "")

    return {
        "real_stage47": real_stage47,
        "real_stage56": real_stage56,
        "smoke_prefix": smoke_prefix,
        "metadata_smoke": metadata_smoke,
        "playwright_job": playwright_job,
        "separation_eval_job": separation_eval_job,
    }


def test_jobs_default_hide_test_noise_and_include_explicitly(client):
    ids = _seed_stage58_jobs()
    upsert_voice_model(
        "vm_stage58_hidden_model",
        model_name="stage58_hidden_cover_model",
        pth_path="shared_data/weights/stage58_hidden_cover_model.pth",
        index_path="",
        status="ready",
        metadata={},
    )
    create_cover_job(
        "task_stage58_hidden_by_model",
        input_path="shared_data/jobs/task_stage58_hidden_by_model/input/source.wav",
        output_root="shared_data/jobs/task_stage58_hidden_by_model",
        metadata={},
        voice_model_id="vm_stage58_hidden_model",
        voice_name="Hidden By Model",
    )
    backend_db.update_task_status("task_stage58_hidden_by_model", "completed", "")
    create_cover_job(
        "stage13_retry_stage58_noise",
        input_path="shared_data/jobs/stage13_retry_stage58_noise/input/source.wav",
        output_root="shared_data/jobs/stage13_retry_stage58_noise",
        metadata={},
        voice_name="Stage50 Voice Should Not Hide By Voice Name Alone",
    )
    backend_db.update_task_status("stage13_retry_stage58_noise", "failed", "old retry smoke")
    create_cover_job(
        "user_voice_name_stage50_visible",
        input_path="shared_data/jobs/user_voice_name_stage50_visible/input/source.wav",
        output_root="shared_data/jobs/user_voice_name_stage50_visible",
        metadata={},
        voice_name="Stage50 Voice Should Not Hide By Voice Name Alone",
    )
    backend_db.update_task_status("user_voice_name_stage50_visible", "completed", "")
    create_cover_job(
        "tmp_retry_stage58_noise",
        input_path="shared_data/jobs/tmp_retry_stage58_noise/input/source.wav",
        output_root="shared_data/jobs/tmp_retry_stage58_noise",
        metadata={},
        voice_name="Temporary Retry Noise",
    )
    backend_db.update_task_status("tmp_retry_stage58_noise", "failed", "tmp retry smoke")
    create_cover_job(
        "test_sep_stage58_noise",
        input_path="shared_data/jobs/test_sep_stage58_noise/input/source.wav",
        output_root="shared_data/jobs/test_sep_stage58_noise",
        metadata={},
        voice_name="Test Separation Noise",
    )
    backend_db.update_task_status("test_sep_stage58_noise", "completed", "")
    create_train_job(
        "train_stage58_single_real_noise",
        voice_name="Train Stage Noise",
        dataset_path="shared_data/jobs/train_stage58_single_real_noise/dataset",
        output_root="shared_data/jobs/train_stage58_single_real_noise",
        strategy_key="single_long_preprocess",
        metadata={},
    )
    backend_db.update_task_status("train_stage58_single_real_noise", "completed", "")
    create_train_job(
        "train_stage58_old_real_noise",
        voice_name="stage26_real_long_legacy",
        dataset_path="shared_data/jobs/train_stage58_old_real_noise/dataset",
        output_root="shared_data/jobs/train_stage58_old_real_noise",
        strategy_key="single_long_preprocess",
        metadata={"smoke": False},
    )
    backend_db.update_task_status("train_stage58_old_real_noise", "completed", "")

    default_payload = client.get("/api/jobs").json()
    default_ids = _job_ids(default_payload)

    assert default_payload["include_test_data"] is False
    assert default_payload["hidden_test_count"] >= 4
    assert ids["real_stage47"] in default_ids
    assert ids["real_stage56"] in default_ids
    assert "user_voice_name_stage50_visible" in default_ids
    assert ids["smoke_prefix"] not in default_ids
    assert ids["metadata_smoke"] not in default_ids
    assert ids["playwright_job"] not in default_ids
    assert ids["separation_eval_job"] not in default_ids
    assert "task_stage58_hidden_by_model" not in default_ids
    assert "stage13_retry_stage58_noise" not in default_ids
    assert "tmp_retry_stage58_noise" not in default_ids
    assert "test_sep_stage58_noise" not in default_ids
    assert "train_stage58_single_real_noise" not in default_ids
    assert "train_stage58_old_real_noise" not in default_ids

    included_payload = client.get("/api/jobs?include_test_data=true").json()
    included_items = {item["job_id"]: item for item in included_payload["items"]}

    assert included_payload["include_test_data"] is True
    assert ids["smoke_prefix"] in included_items
    assert ids["metadata_smoke"] in included_items
    assert ids["playwright_job"] in included_items
    assert ids["separation_eval_job"] in included_items
    assert "task_stage58_hidden_by_model" in included_items
    assert "stage13_retry_stage58_noise" in included_items
    assert "tmp_retry_stage58_noise" in included_items
    assert "test_sep_stage58_noise" in included_items
    assert "train_stage58_single_real_noise" in included_items
    assert "train_stage58_old_real_noise" in included_items
    assert "user_voice_name_stage50_visible" in included_items
    assert included_items[ids["smoke_prefix"]]["filter_reason"]
    assert included_items[ids["playwright_job"]]["filter_reason"]
    assert included_items["task_stage58_hidden_by_model"]["filter_reason"] == "voice_model.test_data"


def test_jobs_summary_and_status_filter_hide_test_noise(client):
    ids = _seed_stage58_jobs()

    default_failed = client.get("/api/jobs?status=failed").json()
    include_failed = client.get("/api/jobs?status=failed&include_test_data=true").json()
    summary = client.get("/api/jobs/summary").json()
    summary_with_tests = client.get("/api/jobs/summary?include_test_data=true").json()

    assert ids["playwright_job"] not in _job_ids(default_failed)
    assert ids["playwright_job"] in _job_ids(include_failed)
    assert default_failed["hidden_test_count"] >= 1
    assert summary["include_test_data"] is False
    assert summary["hidden_test_count"] >= 4
    assert summary["pending_count"] == 0
    assert summary_with_tests["include_test_data"] is True
    assert summary_with_tests["pending_count"] >= 1


def test_models_default_hide_stage_and_smoke_noise(client, isolated_backend):
    real_model_id = "vm_stage47_real"
    smoke_model_id = "vm_stage58_smoke"
    metadata_test_model_id = "vm_stage58_metadata"
    unprotected_stage_model_id = "vm_stage8_old_success"

    upsert_voice_model(
        real_model_id,
        model_name="朱朱_stage47_real_acceptance_model",
        pth_path="shared_data/weights/stage47_real_acceptance_model.pth",
        index_path="",
        status="ready",
        metadata={"source": "stage47_real_acceptance"},
    )
    upsert_voice_model(
        smoke_model_id,
        model_name="smoke_stage58_model",
        pth_path="shared_data/weights/smoke_stage58_model.pth",
        index_path="",
        status="ready",
        metadata={"source": "stage58_noise_filter"},
    )
    upsert_voice_model(
        metadata_test_model_id,
        model_name="stage58_playwright_model",
        pth_path="shared_data/weights/stage58_playwright_model.pth",
        index_path="",
        status="ready",
        metadata={"test_scope": "playwright"},
    )
    upsert_voice_model(
        unprotected_stage_model_id,
        model_name="stage8_multi_success4",
        pth_path="shared_data/weights/stage8_multi_success4.pth",
        index_path="",
        status="ready",
        metadata={},
    )

    default_items = {
        item["model_id"]: item
        for item in client.get("/api/models?include_unavailable=true").json()
    }
    included_items = {
        item["model_id"]: item
        for item in client.get("/api/models?include_unavailable=true&include_test_data=true").json()
    }
    summary = client.get("/api/models/summary?include_unavailable=true").json()
    summary_with_tests = client.get("/api/models/summary?include_unavailable=true&include_test_data=true").json()

    assert real_model_id in default_items
    assert smoke_model_id not in default_items
    assert metadata_test_model_id not in default_items
    assert unprotected_stage_model_id not in default_items
    assert smoke_model_id in included_items
    assert metadata_test_model_id in included_items
    assert unprotected_stage_model_id in included_items
    assert included_items[smoke_model_id]["filter_reason"]
    assert included_items[metadata_test_model_id]["filter_reason"] == "metadata.test_scope"
    assert included_items[unprotected_stage_model_id]["filter_reason"]
    assert summary["include_test_data"] is False
    assert summary["hidden_test_model_count"] >= 3
    assert summary["hidden_test_count"] == summary["hidden_test_model_count"]
    assert summary_with_tests["include_test_data"] is True
    assert summary_with_tests["model_count"] >= summary["model_count"]


def test_batches_and_tracks_default_hide_test_noise(client):
    conn = backend_db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO release_batches (batch_id, batch_name, status, metadata_json)
            VALUES (?, ?, ?, ?)
            """,
            ("batch_stage58_user", "FeiShark user batch", "draft", "{}"),
        )
        conn.execute(
            """
            INSERT INTO release_batches (batch_id, batch_name, status, metadata_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                "batch_stage58_smoke",
                "stage58_factory_smoke_batch",
                "draft",
                json.dumps({"smoke": True, "source": "playwright_factory_smoke"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO tracks (track_id, batch_id, title, status, source_audio_path, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("trk_stage58_user", "batch_stage58_user", "User song", "imported", "shared_data/user.wav", "{}"),
        )
        conn.execute(
            """
            INSERT INTO tracks (track_id, batch_id, title, status, source_audio_path, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "trk_stage58_smoke",
                "batch_stage58_smoke",
                "stage58_smoke_track",
                "imported",
                "shared_data/smoke.wav",
                json.dumps({"test_scope": "playwright"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO audit_events (event_id, entity_type, entity_id, action, detail_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("evt_stage58_user", "batch", "batch_stage58_user", "create", json.dumps({"batch_name": "FeiShark user batch"})),
        )
        conn.execute(
            """
            INSERT INTO audit_events (event_id, entity_type, entity_id, action, detail_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "evt_stage58_smoke",
                "batch",
                "batch_stage58_smoke",
                "create",
                json.dumps({"batch_name": "stage58_factory_smoke_batch", "smoke": True}),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    default_batches = client.get("/api/batches").json()
    included_batches = client.get("/api/batches?include_test_data=true").json()
    default_batch_ids = {item["batch_id"] for item in default_batches["items"]}
    included_batch_items = {item["batch_id"]: item for item in included_batches["items"]}

    assert default_batches["include_test_data"] is False
    assert default_batches["hidden_test_count"] >= 1
    assert "batch_stage58_user" in default_batch_ids
    assert "batch_stage58_smoke" not in default_batch_ids
    assert "batch_stage58_smoke" in included_batch_items
    assert included_batch_items["batch_stage58_smoke"]["filter_reason"]

    default_tracks = client.get("/api/batches/batch_stage58_smoke/tracks").json()
    included_tracks = client.get("/api/batches/batch_stage58_smoke/tracks?include_test_data=true").json()
    assert default_tracks["items"] == []
    assert default_tracks["hidden_test_count"] >= 1
    assert {item["track_id"] for item in included_tracks["items"]} == {"trk_stage58_smoke"}

    summary = client.get("/api/factory/summary").json()
    summary_with_tests = client.get("/api/factory/summary?include_test_data=true").json()
    assert summary["include_test_data"] is False
    assert summary["hidden_test_batch_count"] >= 1
    assert summary["hidden_test_track_count"] >= 1
    assert all("stage58_smoke" not in item.get("detail_json", "") for item in summary["recent_audit_events"])
    assert summary_with_tests["include_test_data"] is True
    assert summary_with_tests["batch_count"] >= summary["batch_count"]
    assert summary_with_tests["track_count"] >= summary["track_count"]
