"""
Stage59C-2/4a — run-scoped UVR artifact metadata (persistence-ready; no physical files).

Delegates contract shape to ``stage59_artifact_persistence_service``. In-memory store until
real smoke files exist and ``register_job_artifact`` can run.
"""

from __future__ import annotations

from typing import Any

from backend.services.stage59_artifact_persistence_service import (
    REQUIRES_LATER_DB_INTEGRATION as ARTIFACTS_REQUIRE_LATER_DB_INTEGRATION,
    STAGE_LABEL,
    build_mock_uvr_artifact_contracts,
    build_run_persistence_bundle,
    clear_persistence_store,
    get_run_artifact_contract,
    store_run_artifact_contract,
)
from backend.services.stage59_job_artifact_promotion_service import (
    build_job_artifact_promotion_plan,
)

STAGE_LABEL_C2 = "stage59c2"
REQUIRES_LATER_DB_INTEGRATION = ARTIFACTS_REQUIRE_LATER_DB_INTEGRATION

_RUN_STORE: dict[str, dict[str, Any]] = {}


def register_transient_uvr_artifacts(
    *,
    run_id: str,
    entry_id: str,
    source_path: str,
    clip_seconds: int,
    manifest_path: str,
) -> list[dict[str, Any]]:
    """Register metadata-only transient artifacts; does not touch disk."""
    records = build_mock_uvr_artifact_contracts(run_id=run_id, entry_id=entry_id)
    bundle = build_run_persistence_bundle(
        run_id=run_id,
        entry_id=entry_id,
        artifact_records=records,
    )
    promotion_plan = build_job_artifact_promotion_plan(
        job_id=None,
        artifact_contract=bundle,
    )
    store_run_artifact_contract(run_id, bundle)

    _RUN_STORE[run_id] = {
        "run_id": run_id,
        "stage": STAGE_LABEL,
        "entry_id": entry_id,
        "source_path": source_path,
        "manifest_path": manifest_path,
        "clip_seconds": clip_seconds,
        "artifact_records": records,
        "artifact_persistence_contract": bundle,
        "promotion_plan": promotion_plan,
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


def get_artifact_contract_for_run(run_id: str) -> dict[str, Any] | None:
    run = get_transient_run(run_id)
    if run and run.get("artifact_persistence_contract"):
        return dict(run["artifact_persistence_contract"])
    return get_run_artifact_contract(run_id)


def list_transient_artifact_records(run_id: str) -> list[dict[str, Any]]:
    run = get_transient_run(run_id)
    if run is None:
        return []
    return list(run.get("artifact_records") or [])


def clear_transient_store() -> None:
    """Test helper — reset in-memory store."""
    _RUN_STORE.clear()
    clear_persistence_store()
