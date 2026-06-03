"""
Stage59C-2/4a — Stage49-compatible listening A/B bridge for mock UVR execute.
"""

from __future__ import annotations

from typing import Any

from backend.services.stage59_artifact_persistence_service import CONTRACT_SCHEMA

LISTENING_BRIDGE_SCHEMA = "stage59_uvr_listening_bridge_v2"
STAGE49_COMPATIBLE_SCHEMA = "stage49_listening_review_v1"
METADATA_ONLY_REASON = "metadata_only_artifact"


def _artifact_ref(record: dict[str, Any], *, run_id: str) -> dict[str, Any]:
    return {
        "artifact_id": record.get("artifact_id", ""),
        "run_id": run_id,
        "persistence_schema": CONTRACT_SCHEMA,
        "artifact_type": record.get("artifact_type", ""),
        "lifecycle_state": record.get("lifecycle_state", "transient"),
    }


def _job_artifact_ref(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": None,
        "artifact_id": None,
        "promotable": bool(record.get("promotable_to_job_artifact")),
        "requires_file_exists": True,
    }


def build_listening_contract(
    *,
    run_id: str,
    entry_id: str,
    source_path: str,
    artifact_records: list[dict[str, Any]],
    clip_seconds: int,
    artifact_persistence_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Metadata-only A/B contract: stable artifact ids; not playable until files exist."""
    by_type = {str(item["artifact_type"]): item for item in artifact_records}

    def _side(key: str, artifact_type: str, *, role: str) -> dict[str, Any]:
        if role == "source":
            return {
                "side_key": key,
                "role": role,
                "artifact_id": f"stage59_{entry_id.replace(' ', '_')}_cover_source",
                "artifact_type": "cover_source",
                "planned_path": source_path,
                "source_path": source_path,
                "artifact_ref": {
                    "artifact_id": f"stage59_{entry_id.replace(' ', '_')}_cover_source",
                    "run_id": run_id,
                    "persistence_schema": CONTRACT_SCHEMA,
                    "artifact_type": "cover_source",
                    "lifecycle_state": "transient",
                },
                "job_artifact_ref": {
                    "job_id": None,
                    "artifact_id": None,
                    "promotable": False,
                    "requires_file_exists": True,
                },
                "can_play": False,
                "can_review": False,
                "reason": METADATA_ONLY_REASON,
                "playback_enabled": False,
                "download_enabled": False,
                "file_exists": False,
                "metadata_only": True,
            }

        record = by_type.get(artifact_type, {})
        return {
            "side_key": key,
            "role": role,
            "artifact_id": record.get("artifact_id", ""),
            "artifact_type": artifact_type,
            "planned_path": record.get("planned_path", ""),
            "source_path": record.get("planned_path", ""),
            "artifact_ref": _artifact_ref(record, run_id=run_id),
            "job_artifact_ref": _job_artifact_ref(record),
            "can_play": False,
            "can_review": False,
            "reason": METADATA_ONLY_REASON,
            "playback_enabled": False,
            "download_enabled": False,
            "file_exists": bool(record.get("file_exists")),
            "metadata_only": True,
        }

    sides = {
        "a_source": _side("a_source", "source", role="source"),
        "b_uvr_vocal": _side("b_uvr_vocal", "uvr_vocal", role="uvr_vocal"),
        "c_uvr_instrumental": _side(
            "c_uvr_instrumental",
            "uvr_instrumental",
            role="uvr_instrumental",
        ),
    }

    return {
        "schema": LISTENING_BRIDGE_SCHEMA,
        "compatible_with": STAGE49_COMPATIBLE_SCHEMA,
        "run_id": run_id,
        "material_entry_id": entry_id,
        "clip_seconds": clip_seconds,
        "playback_enabled": False,
        "download_enabled": False,
        "real_execute_allowed": False,
        "real_execute_required": True,
        "review_allowed": False,
        "artifact_persistence_schema": CONTRACT_SCHEMA,
        "artifact_persistence_contract": artifact_persistence_contract,
        "sides": sides,
        "ab_pairs": [
            {
                "pair_id": "source_vs_vocal",
                "label": "Source vs mock UVR vocal",
                "side_a": "a_source",
                "side_b": "b_uvr_vocal",
            },
            {
                "pair_id": "vocal_vs_instrumental",
                "label": "Mock vocal vs mock instrumental",
                "side_a": "b_uvr_vocal",
                "side_b": "c_uvr_instrumental",
            },
        ],
        "next_action": "requires_real_uvr_execute",
        "notes": "Stage59C-4a: metadata-only persistence contract; no audio on disk.",
    }


def get_listening_contract_for_run(run_payload: dict[str, Any]) -> dict[str, Any] | None:
    if not run_payload:
        return None
    contract = run_payload.get("listening_contract")
    if isinstance(contract, dict):
        return contract
    return build_listening_contract(
        run_id=str(run_payload.get("run_id") or ""),
        entry_id=str(run_payload.get("entry_id") or ""),
        source_path=str(run_payload.get("source_path") or ""),
        artifact_records=list(run_payload.get("artifact_records") or []),
        clip_seconds=int(run_payload.get("clip_seconds") or 45),
        artifact_persistence_contract=run_payload.get("artifact_persistence_contract"),
    )