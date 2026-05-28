from __future__ import annotations

import os
import shutil
from pathlib import Path

try:
    from .db import JOBS_ROOT, OUTPUT_ROOT, PROJECT_ROOT
except ImportError:
    from db import JOBS_ROOT, OUTPUT_ROOT, PROJECT_ROOT

TRANSIENT_OUTPUT_FILENAMES = {
    "vocal.wav",
    "instrumental.wav",
    "fixed.wav",
    "transformed.wav",
    "vocal_fixed.wav",
    "vocal_transformed.wav",
}

TRANSIENT_JOB_DIRNAMES = {
    "_temp_segments",
    "_tmp",
    "tmp",
    "temp",
}


def _is_within(path: str, root: str) -> bool:
    path = os.path.realpath(path)
    root = os.path.realpath(root)
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _safe_remove_file(path: str) -> bool:
    if not os.path.exists(path) or not os.path.isfile(path):
        return False
    os.remove(path)
    return True


def _safe_remove_tree(path: str) -> bool:
    if not os.path.exists(path):
        return False
    shutil.rmtree(path)
    return True


def cleanup_job_transients(job_id: str, *, keep_output_files: tuple[str, ...] = ("final_master.wav",)) -> dict:
    """Safely remove transient files that belong to one job only."""

    removed_files: list[str] = []
    removed_dirs: list[str] = []

    output_root = os.path.join(OUTPUT_ROOT, job_id)
    if os.path.isdir(output_root) and _is_within(output_root, OUTPUT_ROOT):
        for name in os.listdir(output_root):
            path = os.path.join(output_root, name)
            if os.path.isdir(path):
                if name in TRANSIENT_JOB_DIRNAMES and _is_within(path, output_root):
                    if _safe_remove_tree(path):
                        removed_dirs.append(path)
                continue

            if name in keep_output_files:
                continue

            should_remove = (
                name in TRANSIENT_OUTPUT_FILENAMES
                or name.endswith((".tmp", ".temp", ".part", ".bak"))
            )
            if should_remove and _safe_remove_file(path):
                removed_files.append(path)

    job_root = os.path.join(JOBS_ROOT, job_id)
    if os.path.isdir(job_root) and _is_within(job_root, JOBS_ROOT):
        for name in TRANSIENT_JOB_DIRNAMES:
            candidate = os.path.join(job_root, name)
            if os.path.isdir(candidate) and _is_within(candidate, job_root):
                if _safe_remove_tree(candidate):
                    removed_dirs.append(candidate)

    return {
        "job_id": job_id,
        "removed_files": removed_files,
        "removed_dirs": removed_dirs,
        "output_root": str(Path(output_root)),
        "job_root": str(Path(job_root)),
    }
