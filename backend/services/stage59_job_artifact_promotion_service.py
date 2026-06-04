"""
Legacy shim for Stage59C-4a job artifact promotion (Stage60C transition).

All new code must import from the durable facade:
    from backend.services.artifact_lifecycle_service import build_job_artifact_promotion_plan, ...

"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .artifact_lifecycle_service import (
    UVR_ARTIFACT_KINDS,
    validate_artifact_contract_record,
)

STAGE_LABEL = "stage59c4a"
REGISTER_REQUIRES_PHYSICAL_FILE = True


def build_job_artifact_promotion_plan(
    *,
    job_id: str | None,
    artifact_contract: dict[str, Any],
    file_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Dry plan only — no DB writes in Stage59C-4a.
    """
    artifacts = list(artifact_contract.get("artifacts") or [])
    file_paths = file_paths or {}
    blocked_reasons: list[str] = []
    per_artifact: list[dict[str, Any]] = []

    if not job_id:
        blocked_reasons.append("job_id_required_for_promotion")

    if REGISTER_REQUIRES_PHYSICAL_FILE:
        blocked_reasons.append("register_job_artifact_requires_os_path_exists")

    for record in artifacts:
        artifact_type = str(record.get("artifact_type") or "")
        planned = str(record.get("planned_path") or "")
        resolved = file_paths.get(artifact_type) or planned
        exists = bool(resolved) and os.path.exists(resolved)
        validation_errors = validate_artifact_contract_record(record)
        item_blocked: list[str] = list(validation_errors)

        if record.get("metadata_only"):
            item_blocked.append("metadata_only_not_promotable")
        if not exists:
            item_blocked.append("file_missing_at_planned_path")
        if exists:
            try:
                if os.path.getsize(resolved) == 0:
                    item_blocked.append("file_empty")
            except Exception:
                pass
        if record.get("lifecycle_state") != "transient":
            item_blocked.append("only_transient_promotable_in_smoke")
        if artifact_type not in UVR_ARTIFACT_KINDS:
            item_blocked.append("unsupported_artifact_kind")

        can_promote = not item_blocked and bool(job_id)

        per_artifact.append(
            {
                "artifact_id": record.get("artifact_id"),
                "artifact_type": artifact_type,
                "can_promote": can_promote,
                "blocked_reasons": item_blocked,
                "required_file_checks": [
                    "os.path.exists(resolved_path)",
                    "file_size > 0",
                    "path_under_shared_data/stage59_runtime/<run_id>/",
                ],
                "resolved_path": resolved,
                "file_exists": exists,
                "target_job_artifact_fields": {
                    "job_id": job_id,
                    "stage_name": "uvr_ab",
                    "artifact_type": artifact_type,
                    "source_path": resolved,
                    "lifecycle_state": "transient",
                    "is_final": False,
                    "metadata": {
                        "stage59_run_id": record.get("run_id"),
                        "material_entry_id": record.get("entry_id"),
                        "metadata_only": False,
                        "promoted_from": STAGE_LABEL,
                    },
                },
                "cleanup_on_failure": True,
            }
        )

    any_promotable = any(item["can_promote"] for item in per_artifact)
    if not artifacts:
        blocked_reasons.append("no_artifacts_in_contract")

    return {
        "ok": True,
        "stage": STAGE_LABEL,
        "can_promote": any_promotable and not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "per_artifact": per_artifact,
        "db_write_performed": False,
        "requires_later_db_integration": True,
        "register_requires_physical_file": REGISTER_REQUIRES_PHYSICAL_FILE,
    }


def promote_file_backed_uvr_artifacts(
    *,
    job_id: str | None,
    artifact_contract: dict[str, Any],
    file_paths: dict[str, str] | None = None,
    project_root: Path | str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Entry point for file-backed UVR artifact promotion into job_artifacts.
    In governance/safety stages this returns a plan and does not perform DB writes.
    When dry_run=False and preflight passes, a future implementation may call
    asset_service.register_job_artifact for each promotable stem (requires explicit
    human approval + real runner enablement outside this sprint).
    """
    from pathlib import Path as _Path

    plan = build_job_artifact_promotion_plan(
        job_id=job_id,
        artifact_contract=artifact_contract,
        file_paths=file_paths,
    )
    # Attach extra context for callers.
    plan = dict(plan)
    plan["promote_file_backed_called"] = True
    plan["dry_run"] = bool(dry_run)
    plan["project_root"] = str(project_root) if project_root else None
    # Real promotion (register) is intentionally not executed here per Stage59C/60 invariants.
    plan["db_write_performed"] = False
    return plan
