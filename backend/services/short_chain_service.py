from __future__ import annotations

# Stage60 durable facade: keep Stage59 short-chain imports behind a stable name.
# Implementation stays in the existing modules until the shim-deletion stage.

from .short_chain_manifest_service import (
    ManifestPathSafetyError,
    ShortChainGateResult,
    build_short_chain_whitelist,
    default_manifest_path,
    entry_blocking_reasons,
    evaluate_short_chain_gate,
    load_manifest,
    project_root_from_here,
    resolve_safe_manifest_path,
    rights_gate_allows_entry,
    summarize_manifest,
    validate_manifest,
    validate_manifest_structure,
)
from .short_chain_uvr_service import (
    EXECUTE_BLOCKED_REASON,
    UVR_STAGE,
    Stage59UvrBlockedError,
    evaluate_uvr_ab_readiness,
    plan_dry_run,
    plan_short_chain_uvr,
    select_uvr_ab_entries,
)


__all__ = [
    "EXECUTE_BLOCKED_REASON",
    "ManifestPathSafetyError",
    "ShortChainGateResult",
    "Stage59UvrBlockedError",
    "UVR_STAGE",
    "build_short_chain_whitelist",
    "default_manifest_path",
    "entry_blocking_reasons",
    "evaluate_short_chain_gate",
    "evaluate_uvr_ab_readiness",
    "load_manifest",
    "plan_dry_run",
    "plan_short_chain_uvr",
    "project_root_from_here",
    "resolve_safe_manifest_path",
    "rights_gate_allows_entry",
    "select_uvr_ab_entries",
    "summarize_manifest",
    "validate_manifest",
    "validate_manifest_structure",
]
