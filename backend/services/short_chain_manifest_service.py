"""
Stage59B — real-material short-chain manifest schema, rights gate, and validation.

Does not invoke UVR/RVC. 59C/59D runners must whitelist manifest entry ids only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "stage59.short_chain.v1"
STAGE_LABEL = "stage59"

ALLOWED_LIFECYCLE_STATES = frozenset({"active", "archived"})
ALLOWED_CHAIN_STEPS = frozenset({"preflight", "uvr_ab", "rvc_cover"})
ALLOWED_MATERIAL_ROLES = frozenset(
    {
        "dry_vocal",
        "cover_source",
        "separation_eval_candidate",
        "listening_acceptance_source",
    }
)
ALLOWED_LICENSE_STATUSES = frozenset({"approved", "pending", "unknown", "restricted"})

RIGHTS_APPROVED = "approved"
DURATION_MIN_SEC = 20.0
DURATION_MAX_SEC = 60.0

REQUIRED_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "generated_at",
        "stage",
        "entries",
        "blocking_flags",
        "rights_policy",
    }
)
REQUIRED_ENTRY_KEYS = frozenset(
    {
        "id",
        "source_path",
        "material_role",
        "lifecycle_state",
        "intended_chain",
        "license_status",
        "duration_seconds",
    }
)

DEFAULT_MANIFEST_REL = Path("shared_data") / "materials" / "stage59" / "short_chain_manifest.json"


@dataclass
class ShortChainGateResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked_entry_ids: list[str] = field(default_factory=list)
    approved_entry_ids: list[str] = field(default_factory=list)


def project_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]


def default_manifest_path(project_root: Path | None = None) -> Path:
    root = project_root or project_root_from_here()
    return root / DEFAULT_MANIFEST_REL


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("manifest_root_must_be_object")
    return payload


def _resolve_source_path(project_root: Path, raw: str) -> tuple[Path | None, str | None]:
    text = (raw or "").strip()
    if not text:
        return None, "source_path_empty"
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = project_root / text
    try:
        resolved = candidate.resolve()
        resolved.relative_to(project_root.resolve())
    except ValueError:
        return None, "source_path_outside_project"
    except OSError as exc:
        return None, f"source_path_invalid:{exc}"
    return resolved, None


def _duration_in_short_chain_window(value: Any) -> tuple[bool, str | None]:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return False, "duration_seconds_invalid"
    if seconds < DURATION_MIN_SEC:
        return False, f"duration_below_min:{DURATION_MIN_SEC}"
    if seconds > DURATION_MAX_SEC:
        return False, f"duration_above_max:{DURATION_MAX_SEC}"
    return True, None


def rights_gate_allows_entry(entry: dict[str, Any], *, policy: dict[str, Any] | None = None) -> tuple[bool, str]:
    """Rights gate: only approved license may enter 59C/59D automation."""
    policy = policy or {}
    require_approved = bool(policy.get("require_license_approved", True))
    license_status = str(entry.get("license_status") or "unknown").strip().lower()
    if not require_approved:
        return True, ""
    if license_status == RIGHTS_APPROVED:
        return True, ""
    return False, f"license_not_approved:{license_status}"


def entry_blocking_reasons(
    entry: dict[str, Any],
    *,
    project_root: Path,
    policy: dict[str, Any] | None = None,
    check_file_exists: bool = True,
) -> list[str]:
    reasons: list[str] = []
    entry_id = str(entry.get("id") or "")

    lifecycle = str(entry.get("lifecycle_state") or "").strip().lower()
    if lifecycle not in ALLOWED_LIFECYCLE_STATES:
        reasons.append(f"{entry_id}:lifecycle_not_allowed:{lifecycle}")
    if lifecycle == "archived":
        reasons.append(f"{entry_id}:lifecycle_archived")

    license_ok, license_reason = rights_gate_allows_entry(entry, policy=policy)
    if not license_ok and license_reason:
        reasons.append(f"{entry_id}:{license_reason}")

    if bool(entry.get("rights_blocked")):
        reasons.append(f"{entry_id}:rights_blocked_flag")

    chain = entry.get("intended_chain")
    if not isinstance(chain, list) or not chain:
        reasons.append(f"{entry_id}:intended_chain_empty")
    else:
        unknown = [step for step in chain if str(step) not in ALLOWED_CHAIN_STEPS]
        if unknown:
            reasons.append(f"{entry_id}:intended_chain_invalid:{','.join(unknown)}")

    role = str(entry.get("material_role") or "").strip().lower()
    if role not in ALLOWED_MATERIAL_ROLES:
        reasons.append(f"{entry_id}:material_role_not_allowed:{role}")

    duration_ok, duration_reason = _duration_in_short_chain_window(entry.get("duration_seconds"))
    if not duration_ok and duration_reason:
        reasons.append(f"{entry_id}:{duration_reason}")

    resolved, path_reason = _resolve_source_path(project_root, str(entry.get("source_path") or ""))
    if path_reason:
        reasons.append(f"{entry_id}:{path_reason}")
    elif check_file_exists and resolved is not None and not resolved.is_file():
        reasons.append(f"{entry_id}:source_file_missing")

    if bool(entry.get("quarantine_recommended")):
        reasons.append(f"{entry_id}:quarantine_recommended")

    return reasons


def validate_manifest_structure(data: dict[str, Any]) -> list[str]:
    """Schema/type errors only (no filesystem or rights outcomes)."""
    errors: list[str] = []
    missing_top = sorted(REQUIRED_TOP_LEVEL_KEYS - set(data))
    if missing_top:
        errors.append(f"missing_top_level_keys:{','.join(missing_top)}")
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version_must_be:{SCHEMA_VERSION}")
    if str(data.get("stage") or "") != STAGE_LABEL:
        errors.append(f"stage_must_be:{STAGE_LABEL}")
    if not isinstance(data.get("rights_policy"), dict):
        errors.append("rights_policy_must_be_object")
    if not isinstance(data.get("blocking_flags"), dict):
        errors.append("blocking_flags_must_be_object")

    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries_must_be_non_empty_list")
        return errors

    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry_{index}_must_be_object")
            continue
        entry_id = str(entry.get("id") or "")
        if not entry_id:
            errors.append(f"entry_{index}:id_required")
            continue
        if entry_id in seen_ids:
            errors.append(f"duplicate_entry_id:{entry_id}")
        seen_ids.add(entry_id)

        missing_entry = sorted(REQUIRED_ENTRY_KEYS - set(entry))
        if missing_entry:
            errors.append(f"{entry_id}:missing_keys:{','.join(missing_entry)}")

        license_status = str(entry.get("license_status") or "").strip().lower()
        if license_status not in ALLOWED_LICENSE_STATUSES:
            errors.append(f"{entry_id}:license_status_invalid:{license_status}")

        chain = entry.get("intended_chain")
        if not isinstance(chain, list) or not chain:
            errors.append(f"{entry_id}:intended_chain_empty")
        else:
            unknown = [step for step in chain if str(step) not in ALLOWED_CHAIN_STEPS]
            if unknown:
                errors.append(f"{entry_id}:intended_chain_invalid:{','.join(map(str, unknown))}")

        role = str(entry.get("material_role") or "").strip().lower()
        if role not in ALLOWED_MATERIAL_ROLES:
            errors.append(f"{entry_id}:material_role_not_allowed:{role}")

        lifecycle = str(entry.get("lifecycle_state") or "").strip().lower()
        if lifecycle not in ALLOWED_LIFECYCLE_STATES:
            errors.append(f"{entry_id}:lifecycle_not_allowed:{lifecycle}")

        _, duration_reason = _duration_in_short_chain_window(entry.get("duration_seconds"))
        if duration_reason:
            errors.append(f"{entry_id}:{duration_reason}")

    return errors


def validate_manifest(
    data: dict[str, Any],
    *,
    project_root: Path | None = None,
    check_file_exists: bool = True,
) -> list[str]:
    """Structure + per-entry runtime blockers (paths, rights, quarantine)."""
    root = project_root or project_root_from_here()
    errors = validate_manifest_structure(data)
    if errors and "entries_must_be_non_empty_list" in errors:
        return errors

    policy = data.get("rights_policy") if isinstance(data.get("rights_policy"), dict) else {}
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        errors.extend(
            entry_blocking_reasons(
                entry,
                project_root=root,
                policy=policy,
                check_file_exists=check_file_exists,
            )
        )
    return errors


def evaluate_short_chain_gate(
    data: dict[str, Any],
    *,
    project_root: Path | None = None,
    check_file_exists: bool = True,
) -> ShortChainGateResult:
    root = project_root or project_root_from_here()
    result = ShortChainGateResult(ok=True)

    structure_errors = validate_manifest_structure(data)
    if structure_errors:
        result.ok = False
        result.errors = structure_errors
        return result

    policy = data.get("rights_policy") if isinstance(data.get("rights_policy"), dict) else {}
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id") or "")
        blockers = entry_blocking_reasons(
            entry, project_root=root, policy=policy, check_file_exists=check_file_exists
        )
        if blockers:
            result.blocked_entry_ids.append(entry_id)
        else:
            result.approved_entry_ids.append(entry_id)

    blocking_flags = data.get("blocking_flags") or {}
    if result.approved_entry_ids:
        result.ok = True
        return result

    if bool(blocking_flags.get("no_approved_entries")):
        result.ok = True
        result.warnings.append("no_approved_entries_acknowledged")
        return result

    result.ok = False
    result.errors.append("no_approved_short_chain_entries")
    return result


def summarize_manifest(
    data: dict[str, Any],
    *,
    project_root: Path | None = None,
    check_file_exists: bool = False,
) -> dict[str, Any]:
    root = project_root or project_root_from_here()
    gate = evaluate_short_chain_gate(data, project_root=root, check_file_exists=check_file_exists)
    entries = [entry for entry in (data.get("entries") or []) if isinstance(entry, dict)]
    policy = data.get("rights_policy") if isinstance(data.get("rights_policy"), dict) else {}

    return {
        "schema_version": data.get("schema_version"),
        "stage": data.get("stage"),
        "entry_count": len(entries),
        "approved_entry_ids": gate.approved_entry_ids,
        "blocked_entry_ids": gate.blocked_entry_ids,
        "approved_count": len(gate.approved_entry_ids),
        "blocked_count": len(gate.blocked_entry_ids),
        "gate_ok": gate.ok,
        "blocking_flags": data.get("blocking_flags") or {},
        "rights_policy": policy,
        "duration_window_sec": {"min": DURATION_MIN_SEC, "max": DURATION_MAX_SEC},
    }
