"""
Stage59C-4a — persistence-ready UVR artifact contract (metadata-only; no DB write).

``register_job_artifact`` requires ``os.path.exists``; mock/smoke stems use this contract
until real files exist under ``shared_data/stage59_runtime/<run_id>/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

STAGE_LABEL = "stage59c4a"
CONTRACT_SCHEMA = "stage59_uvr_artifact_persistence_v1"
CANONICAL_STORE = "stage59_runtime"
REQUIRES_LATER_DB_INTEGRATION = True

UVR_ARTIFACT_KINDS = frozenset({"uvr_vocal", "uvr_instrumental"})
DEFAULT_LIFECYCLE = "transient"

STAGE_RUNTIME_REL = Path("shared_data") / "stage59_runtime"

_RUN_CONTRACT_STORE: dict[str, dict[str, Any]] = {}


def stable_artifact_id(entry_id: str, artifact_type: str) -> str:
    safe_entry = entry_id.replace(" ", "_").replace("/", "_").replace("\\", "_")
    return f"stage59_{safe_entry}_{artifact_type}"


def planned_sandbox_path(run_id: str, artifact_type: str) -> str:
    safe_run = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run_id)[:128]
    return (STAGE_RUNTIME_REL / safe_run / f"{artifact_type}.wav").as_posix()


def _validate_planned_path_under_sandbox(planned_path: str, run_id: str) -> list[str]:
    errors: list[str] = []
    norm = planned_path.replace("\\", "/")
    prefix = f"shared_data/stage59_runtime/{run_id}"
    safe_prefix = f"shared_data/stage59_runtime/{''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in run_id)[:128]}"
    if ".." in norm:
        errors.append("path_traversal_forbidden")
    if not norm.startswith("shared_data/stage59_runtime/"):
        errors.append("path_outside_stage59_runtime")
    if safe_prefix not in norm and prefix not in norm:
        errors.append("path_run_id_mismatch")
    return errors


def build_artifact_contract_record(
    *,
    run_id: str,
    entry_id: str,
    artifact_type: str,
    metadata_only: bool = True,
    file_exists: bool = False,
) -> dict[str, Any]:
    if artifact_type not in UVR_ARTIFACT_KINDS:
        raise ValueError(f"unsupported_artifact_type:{artifact_type}")

    planned = planned_sandbox_path(run_id, artifact_type)
    path_errors = _validate_planned_path_under_sandbox(planned, run_id)

    return {
        "artifact_id": stable_artifact_id(entry_id, artifact_type),
        "run_id": run_id,
        "entry_id": entry_id,
        "artifact_type": artifact_type,
        "job_artifact_kind": artifact_type,
        "lifecycle_state": DEFAULT_LIFECYCLE,
        "metadata_only": bool(metadata_only),
        "file_exists": bool(file_exists),
        "planned_path": planned,
        "canonical_store": CANONICAL_STORE,
        "download_enabled": False,
        "playback_enabled": False,
        "cleanup_required": True,
        "promotable_to_job_artifact": file_exists and not metadata_only,
        "requires_later_db_integration": REQUIRES_LATER_DB_INTEGRATION,
        "path_validation_errors": path_errors,
        "stage": STAGE_LABEL,
    }


def build_mock_uvr_artifact_contracts(
    *,
    run_id: str,
    entry_id: str,
) -> list[dict[str, Any]]:
    """Metadata-only mock contracts; never ``active`` lifecycle."""
    records: list[dict[str, Any]] = []
    for kind in sorted(UVR_ARTIFACT_KINDS):
        record = build_artifact_contract_record(
            run_id=run_id,
            entry_id=entry_id,
            artifact_type=kind,
            metadata_only=True,
            file_exists=False,
        )
        errors = validate_artifact_contract_record(record)
        if errors:
            record["contract_validation_errors"] = errors
        records.append(record)
    return records


def validate_artifact_contract_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("artifact_type") not in UVR_ARTIFACT_KINDS:
        errors.append("invalid_artifact_type")
    if record.get("lifecycle_state") == "active":
        errors.append("mock_smoke_must_not_be_active")
    if record.get("metadata_only") and record.get("file_exists"):
        errors.append("metadata_only_cannot_have_file_exists")
    if record.get("metadata_only") and (
        record.get("playback_enabled") or record.get("download_enabled")
    ):
        errors.append("metadata_only_must_not_be_playable")
    if not record.get("metadata_only") and not record.get("file_exists"):
        errors.append("non_metadata_requires_file_exists_for_promotion")
    planned = str(record.get("planned_path") or "")
    run_id = str(record.get("run_id") or "")
    errors.extend(_validate_planned_path_under_sandbox(planned, run_id))
    return errors


def build_run_persistence_bundle(
    *,
    run_id: str,
    entry_id: str,
    artifact_records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": CONTRACT_SCHEMA,
        "stage": STAGE_LABEL,
        "run_id": run_id,
        "entry_id": entry_id,
        "artifacts": artifact_records,
        "metadata_only": True,
        "file_exists": False,
        "playback_enabled": False,
        "download_enabled": False,
        "lifecycle_default": DEFAULT_LIFECYCLE,
        "requires_later_db_integration": REQUIRES_LATER_DB_INTEGRATION,
        "db_write_policy": "deferred_until_physical_file_exists",
        "canonical_store": CANONICAL_STORE,
        "cleanup_policy": {
            "cleanup_required": True,
            "cleanup_on_failure": True,
            "deletable_states": ["transient"],
            "never_promote_without_file_exists": True,
        },
    }


def store_run_artifact_contract(run_id: str, bundle: dict[str, Any]) -> None:
    _RUN_CONTRACT_STORE[run_id] = dict(bundle)


def get_run_artifact_contract(run_id: str) -> dict[str, Any] | None:
    payload = _RUN_CONTRACT_STORE.get(run_id)
    if payload is None:
        return None
    return dict(payload)


def clear_persistence_store() -> None:
    """Test helper."""
    _RUN_CONTRACT_STORE.clear()