"""
Stage59C-2 — in-memory transient UVR artifact metadata (no physical files).

``register_job_artifact`` requires ``os.path.exists``; Stage59 mock execute uses this
JSON contract store until a later DB integration stage.
"""

from __future__ import annotations

from typing import Any

STAGE_LABEL = "stage59c2"
REQUIRES_LATER_DB_INTEGRATION = True

_RUN_STORE: dict[str, dict[str, Any]] = {}


def _artifact_id(entry_id: str, artifact_type: str) -> str:
    safe_entry = entry_id.replace(" ", "_").replace("/", "_")
    return f"stage59c2_{safe_entry}_{artifact_type}"


def _planned_path(entry_id: str, artifact_type: str) -> str:
    return f"shared_data/separation_eval/stage59/{entry_id}/{artifact_type}.wav"


def register_transient_uvr_artifacts(
    *,
    run_id: str,
    entry_id: str,
    source_path: str,
    clip_seconds: int,
    manifest_path: str,
) -> list[dict[str, Any]]:
    """Register metadata-only transient artifacts; does not touch disk."""
    records: list[dict[str, Any]] = []
    for artifact_type in ("uvr_vocal", "uvr_instrumental"):
        records.append(
            {
                "artifact_id": _artifact_id(entry_id, artifact_type),
                "run_id": run_id,
                "artifact_type": artifact_type,
                "lifecycle_state": "transient",
                "planned_path": _planned_path(entry_id, artifact_type),
                "source_path": source_path,
                "material_entry_id": entry_id,
                "clip_seconds": clip_seconds,
                "file_exists": False,
                "metadata_only": True,
                "playback_enabled": False,
                "download_enabled": False,
                "requires_later_db_integration": REQUIRES_LATER_DB_INTEGRATION,
            }
        )

    _RUN_STORE[run_id] = {
        "run_id": run_id,
        "stage": STAGE_LABEL,
        "entry_id": entry_id,
        "source_path": source_path,
        "manifest_path": manifest_path,
        "clip_seconds": clip_seconds,
        "artifact_records": records,
        "audio_files_written": False,
        "listening_contract": None,
    }
    return records


def attach_listening_contract(run_id: str, contract: dict[str, Any]) -> None:
    if run_id in _RUN_STORE:
        _RUN_STORE[run_id]["listening_contract"] = contract


def get_transient_run(run_id: str) -> dict[str, Any] | None:
    payload = _RUN_STORE.get(run_id)
    if payload is None:
        return None
    return dict(payload)


def list_transient_artifact_records(run_id: str) -> list[dict[str, Any]]:
    run = get_transient_run(run_id)
    if run is None:
        return []
    return list(run.get("artifact_records") or [])


def clear_transient_store() -> None:
    """Test helper — reset in-memory store."""
    _RUN_STORE.clear()