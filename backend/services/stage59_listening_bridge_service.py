"""
Stage59C-2 — Stage49-compatible listening A/B bridge for mock UVR execute.
"""

from __future__ import annotations

from typing import Any

LISTENING_BRIDGE_SCHEMA = "stage59_uvr_listening_bridge_v1"
STAGE49_COMPATIBLE_SCHEMA = "stage49_listening_review_v1"


def build_listening_contract(
    *,
    run_id: str,
    entry_id: str,
    source_path: str,
    artifact_records: list[dict[str, Any]],
    clip_seconds: int,
) -> dict[str, Any]:
    """Metadata-only A/B contract: source vs planned vocal/instrumental stems."""
    by_type = {str(item["artifact_type"]): item for item in artifact_records}

    def _side(key: str, artifact_type: str, *, role: str) -> dict[str, Any]:
        record = by_type.get(artifact_type, {})
        return {
            "side_key": key,
            "role": role,
            "artifact_id": record.get("artifact_id", ""),
            "artifact_type": artifact_type,
            "planned_path": record.get("planned_path", ""),
            "source_path": source_path if role == "source" else record.get("planned_path", ""),
            "playback_enabled": False,
            "download_enabled": False,
            "file_exists": False,
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
    sides["a_source"]["source_path"] = source_path
    sides["a_source"]["artifact_type"] = "cover_source"
    sides["a_source"]["planned_path"] = source_path

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
        "notes": "Stage59C-2 mock execute: metadata-only; no audio on disk.",
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
    )