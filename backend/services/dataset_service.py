import os
import shutil
import uuid
from typing import Iterable

from fastapi import UploadFile

try:
    from ..db import get_connection, JOBS_ROOT, PROJECT_ROOT
    from .smoke_filter import is_smoke_dataset_record
except ImportError:
    from db import get_connection, JOBS_ROOT, PROJECT_ROOT
    from services.smoke_filter import is_smoke_dataset_record


def get_job_root(job_id: str) -> str:
    return os.path.join(JOBS_ROOT, job_id)


def discard_job_workspace(job_id: str) -> bool:
    root = os.path.realpath(get_job_root(job_id))
    jobs_root = os.path.realpath(JOBS_ROOT)
    try:
        within_root = os.path.commonpath([root, jobs_root]) == jobs_root
    except ValueError:
        within_root = False

    if not within_root or not os.path.isdir(root):
        return False

    shutil.rmtree(root)
    return True


def ensure_job_dirs(job_id: str) -> dict[str, str]:
    root = get_job_root(job_id)
    paths = {
        "root": root,
        "input": os.path.join(root, "input"),
        "dataset": os.path.join(root, "dataset"),
        "artifacts": os.path.join(root, "artifacts"),
    }
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
    return paths


async def save_cover_upload(job_id: str, file: UploadFile) -> dict:
    dirs = ensure_job_dirs(job_id)
    ext = os.path.splitext(file.filename or "")[1].lower() or ".wav"
    file_name = f"{job_id}{ext}"
    abs_path = os.path.join(dirs["input"], file_name)
    rel_path = os.path.relpath(abs_path, PROJECT_ROOT)

    size = 0
    with open(abs_path, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            size += len(chunk)

    return {
        "abs_path": abs_path,
        "rel_path": rel_path.replace("\\", "/"),
        "file_name": file_name,
        "file_size": size,
    }


async def save_train_uploads(job_id: str, files: Iterable[UploadFile]) -> dict:
    dirs = ensure_job_dirs(job_id)
    dataset_dir = dirs["dataset"]
    saved_files: list[dict] = []
    total_bytes = 0

    for idx, upload_file in enumerate(files, start=1):
        ext = os.path.splitext(upload_file.filename or "")[1].lower() or ".wav"
        file_name = f"{idx:04d}_{job_id}{ext}"
        abs_path = os.path.join(dataset_dir, file_name)
        size = 0
        with open(abs_path, "wb") as out:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)
        total_bytes += size
        saved_files.append(
            {
                "abs_path": abs_path,
                "rel_path": os.path.relpath(abs_path, PROJECT_ROOT).replace("\\", "/"),
                "file_name": file_name,
                "file_size": size,
                "file_ext": ext,
            }
        )

    return {
        "dataset_abs_path": dataset_dir,
        "dataset_rel_path": os.path.relpath(dataset_dir, PROJECT_ROOT).replace("\\", "/"),
        "saved_files": saved_files,
        "file_count": len(saved_files),
        "total_bytes": total_bytes,
    }


def create_dataset_record(job_id: str, dataset_name: str, root_path: str, strategy_key: str, file_count: int, total_bytes: int, metadata: dict | None = None) -> str:
    import json

    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO datasets (
                dataset_id, job_id, dataset_name, strategy_key, root_path,
                file_count, total_bytes, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dataset_id, job_id, dataset_name, strategy_key, root_path, file_count, total_bytes, json.dumps(metadata or {}, ensure_ascii=False)),
        )
        conn.commit()
        return dataset_id
    finally:
        conn.close()


def get_dataset_for_job(job_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM datasets WHERE job_id = ? ORDER BY datetime(created_at) DESC, rowid DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_datasets(
    job_id: str | None = None,
    strategy_key: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_smoke: bool = False,
) -> list[dict]:
    conn = get_connection()
    try:
        query = "SELECT * FROM datasets WHERE 1=1"
        params: list[object] = []
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        if strategy_key:
            query += " AND strategy_key = ?"
            params.append(strategy_key)
        query += " ORDER BY datetime(created_at) DESC, rowid DESC"
        rows = conn.execute(query, tuple(params)).fetchall()
        items = [dict(r) for r in rows]
        if not include_smoke:
            if job_id:
                return items[offset: offset + limit]
            job_rows = {}
            if items:
                job_ids = sorted({item["job_id"] for item in items if item.get("job_id")})
                if job_ids:
                    placeholders = ",".join("?" for _ in job_ids)
                    job_rows = {
                        row["job_id"]: dict(row)
                        for row in conn.execute(f"SELECT * FROM jobs WHERE job_id IN ({placeholders})", tuple(job_ids)).fetchall()
                    }
            items = [item for item in items if not is_smoke_dataset_record(item, job_rows.get(item.get("job_id")))]
        return items[offset: offset + limit]
    finally:
        conn.close()
