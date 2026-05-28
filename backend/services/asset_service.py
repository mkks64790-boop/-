import json
import os
import shutil
import uuid

try:
    from ..db import get_connection
    from .dataset_service import ensure_job_dirs
except ImportError:
    from db import get_connection
    from services.dataset_service import ensure_job_dirs


def register_audio_asset(
    job_id: str,
    asset_role: str,
    file_path: str,
    dataset_id: str = "",
    file_name: str | None = None,
    file_ext: str | None = None,
    file_size: int | None = None,
    duration_sec: float = 0.0,
    metadata: dict | None = None,
) -> str:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT asset_id
            FROM audio_assets
            WHERE job_id = ? AND COALESCE(dataset_id, '') = COALESCE(?, '') AND asset_role = ? AND file_path = ?
            LIMIT 1
            """,
            (job_id, dataset_id, asset_role, file_path),
        ).fetchone()
        if row:
            return row["asset_id"]
    finally:
        conn.close()

    asset_id = f"asset_{uuid.uuid4().hex[:12]}"
    file_name = file_name or os.path.basename(file_path)
    file_ext = file_ext or os.path.splitext(file_name)[1].lower()
    file_size = file_size if file_size is not None else (os.path.getsize(file_path) if os.path.exists(file_path) else 0)

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO audio_assets (
                asset_id, dataset_id, job_id, asset_role, file_name, file_ext,
                file_path, file_size, duration_sec, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                dataset_id,
                job_id,
                asset_role,
                file_name,
                file_ext,
                file_path,
                file_size,
                duration_sec,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
        return asset_id
    finally:
        conn.close()


def register_job_artifact(
    job_id: str,
    stage_name: str,
    artifact_type: str,
    source_path: str,
    is_final: bool = False,
    mirror_into_job_dir: bool = True,
    metadata: dict | None = None,
) -> str | None:
    if not source_path or not os.path.exists(source_path):
        return None

    artifact_path = source_path
    if mirror_into_job_dir:
        dirs = ensure_job_dirs(job_id)
        stage_dir = os.path.join(dirs["artifacts"], stage_name)
        os.makedirs(stage_dir, exist_ok=True)
        artifact_path = os.path.join(stage_dir, os.path.basename(source_path))
        if os.path.abspath(source_path) != os.path.abspath(artifact_path):
            shutil.copy2(source_path, artifact_path)

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT artifact_id
            FROM job_artifacts
            WHERE job_id = ? AND stage_name = ? AND artifact_type = ? AND file_path = ?
            LIMIT 1
            """,
            (job_id, stage_name, artifact_type, artifact_path),
        ).fetchone()
        if row:
            return row["artifact_id"]
    finally:
        conn.close()

    artifact_id = f"art_{uuid.uuid4().hex[:12]}"
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO job_artifacts (
                artifact_id, job_id, stage_name, artifact_type,
                file_path, file_size, is_final, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                job_id,
                stage_name,
                artifact_type,
                artifact_path,
                os.path.getsize(artifact_path),
                1 if is_final else 0,
                json.dumps(metadata or {"source_path": source_path}, ensure_ascii=False),
            ),
        )
        conn.commit()
        return artifact_id
    finally:
        conn.close()


def register_cover_stage_outputs(job_id: str, stage_name: str) -> list[str]:
    legacy_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "shared_data", "outputs", job_id)
    stage_map = {
        "cover_split": [("cover_vocal", "vocal.wav"), ("cover_instrumental", "instrumental.wav")],
        "cover_pitch": [("cover_fixed", "vocal_fixed.wav")],
        "cover_voice": [("cover_transformed", "vocal_transformed.wav")],
        "cover_mix": [("cover_master", "final_master.wav")],
    }
    artifact_ids: list[str] = []
    for artifact_type, file_name in stage_map.get(stage_name, []):
        artifact_id = register_job_artifact(
            job_id=job_id,
            stage_name=stage_name,
            artifact_type=artifact_type,
            source_path=os.path.join(legacy_dir, file_name),
            is_final=(file_name == "final_master.wav"),
        )
        if artifact_id:
            artifact_ids.append(artifact_id)
    return artifact_ids


def list_job_artifacts(job_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM job_artifacts WHERE job_id = ? ORDER BY datetime(created_at), rowid",
            (job_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_job_artifact(job_id: str, artifact_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM job_artifacts
            WHERE job_id = ? AND artifact_id = ?
            LIMIT 1
            """,
            (job_id, artifact_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_final_job_artifact(job_id: str) -> dict | None:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM job_artifacts
            WHERE job_id = ? AND is_final = 1
            ORDER BY
                CASE
                    WHEN artifact_type IN ('cover_master', 'train_model_pth') THEN 0
                    WHEN artifact_type IN ('cover_model', 'train_model_index') THEN 1
                    ELSE 2
                END,
                datetime(created_at) DESC,
                rowid DESC
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        return dict(rows) if rows else None
    finally:
        conn.close()
