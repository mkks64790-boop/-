from __future__ import annotations

from pathlib import Path

from backend import db as backend_db
from backend.services.dataset_service import create_dataset_record
from backend.services.job_service import create_train_job
from backend.services.model_service import build_trained_model_metadata, upsert_voice_model


def _write_weight_pair(root: Path, stem: str) -> tuple[str, str]:
    weights_dir = root / "shared_data" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    pth_path = weights_dir / f"{stem}.pth"
    index_path = weights_dir / f"{stem}.index"
    pth_path.write_bytes(b"fake-pth")
    index_path.write_bytes(b"fake-index-but-not-empty")
    return str(pth_path), str(index_path)


def _seed_trained_model(root: Path, job_id: str = "train_linked_case") -> str:
    dataset_root = root / "shared_data" / "jobs" / job_id / "dataset"
    dataset_root.mkdir(parents=True, exist_ok=True)
    create_train_job(
        job_id,
        "Linked Voice",
        str(dataset_root),
        str(root / "shared_data" / "jobs" / job_id),
        "single_long_preprocess",
        metadata={
            "file_count": 1,
            "material_decision": {
                "material_profile": "single_long_candidate",
                "recommended_route": "single_long_preprocess",
                "duration_label": "45分10秒",
                "file_count": 1,
            },
        },
    )
    create_dataset_record(
        job_id,
        "Linked Voice",
        str(dataset_root),
        "single_long_preprocess",
        1,
        123456,
        metadata={
            "material_decision": {
                "material_profile": "single_long_candidate",
                "recommended_route": "single_long_preprocess",
                "duration_label": "45分10秒",
                "file_count": 1,
            },
        },
    )

    conn = backend_db.get_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET status = '完成', current_stage = 'train_register_model', updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """,
            (job_id,),
        )
        conn.commit()
    finally:
        conn.close()

    pth_path, index_path = _write_weight_pair(root, "linked-trained")
    model_id = "v_linkedtrain"
    upsert_voice_model(
        voice_model_id=model_id,
        legacy_model_id=model_id,
        model_name="linked-trained",
        pth_path=pth_path,
        index_path=index_path,
        source_job_id=job_id,
        status="ready",
        metadata=build_trained_model_metadata(job_id),
    )
    return model_id


def test_trained_model_detail_exposes_lineage(client, isolated_backend):
    model_id = _seed_trained_model(isolated_backend)

    list_resp = client.get("/api/models?include_unavailable=true")
    assert list_resp.status_code == 200
    model = next(item for item in list_resp.json() if item["model_id"] == model_id)
    assert model["origin_kind"] == "trained_local"
    assert model["source_job_id"] == "train_linked_case"
    assert model["source_strategy_key"] == "single_long_preprocess"
    assert model["source_material_profile"] == "single_long_candidate"
    assert model["source_file_count"] == 1
    assert model["source_duration_label"] == "45分10秒"
    assert "train_linked_case" in model["source_summary"]

    detail_resp = client.get(f"/api/models/{model_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["source_dataset_id"].startswith("ds_")
    assert detail["source_job_status"] == "完成"
    assert detail["source_job_current_stage"] == "train_register_model"
    assert detail["resolved_index_path"].endswith("linked-trained.index")


def test_models_api_distinguishes_trained_and_imported_origin(client, isolated_backend):
    trained_model_id = _seed_trained_model(isolated_backend, job_id="train_linked_case_two")
    import_pth, import_index = _write_weight_pair(isolated_backend, "imported-demo")

    import_resp = client.post(
        "/api/models/import",
        json={
            "model_name": "imported-demo",
            "pth_path": import_pth,
            "index_path": import_index,
            "default_pitch": 2,
        },
    )
    assert import_resp.status_code == 200
    imported = import_resp.json()
    assert imported["origin_kind"] == "imported_external"

    list_resp = client.get("/api/models?include_unavailable=true")
    assert list_resp.status_code == 200
    items = {item["model_id"]: item for item in list_resp.json()}
    assert items[trained_model_id]["origin_kind"] == "trained_local"
    assert items[trained_model_id]["source_job_id"] == "train_linked_case_two"
    assert items[imported["model_id"]]["origin_kind"] == "imported_external"
    assert items[imported["model_id"]]["source_job_id"] == ""
