"""
Stage59C-0 — manifest gate whitelist for 59C dry-run runners.

Proves only approved_entry_ids from evaluate_short_chain_gate enter the runner
whitelist; pending, restricted, unknown, quarantine, and archived entries stay out.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.short_chain_manifest_service import (
    SCHEMA_VERSION,
    build_short_chain_whitelist,
    evaluate_short_chain_gate,
)


def _base_manifest() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-06-03T00:00:00",
        "stage": "stage59",
        "rights_policy": {"require_license_approved": True},
        "blocking_flags": {"allow_blocked_entries_in_manifest": True},
        "entries": [],
    }


def _write_wav(path: Path, *, seconds: float = 1.0, sample_rate: int = 44100) -> None:
    import struct
    import wave

    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, int(sample_rate * seconds))
    silent = struct.pack("<h", 0) * frame_count
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(silent)


def _entry(
    entry_id: str,
    rel_path: str,
    *,
    license_status: str = "approved",
    lifecycle_state: str = "active",
    quarantine_recommended: bool = False,
    rights_blocked: bool = False,
) -> dict:
    return {
        "id": entry_id,
        "material_id": "",
        "source_path": rel_path,
        "material_role": "cover_source",
        "lifecycle_state": lifecycle_state,
        "intended_chain": ["preflight", "uvr_ab", "rvc_cover"],
        "license_status": license_status,
        "duration_seconds": 45.0,
        "rights_blocked": rights_blocked,
        "quarantine_recommended": quarantine_recommended,
    }


def _materials_dir(root: Path) -> Path:
    return root / "shared_data" / "materials" / "stage59"


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    materials = _materials_dir(root)
    for name in (
        "approved.wav",
        "pending.wav",
        "restricted.wav",
        "unknown.wav",
        "quarantine.wav",
        "archived.wav",
    ):
        _write_wav(materials / name)
    return root


def _mixed_manifest(root: Path) -> dict:
    rel = "shared_data/materials/stage59"
    return {
        **_base_manifest(),
        "entries": [
            _entry("sc59_approved", f"{rel}/approved.wav"),
            _entry("sc59_pending", f"{rel}/pending.wav", license_status="pending"),
            _entry("sc59_restricted", f"{rel}/restricted.wav", license_status="restricted"),
            _entry("sc59_unknown", f"{rel}/unknown.wav", license_status="unknown"),
            _entry(
                "sc59_quarantine",
                f"{rel}/quarantine.wav",
                quarantine_recommended=True,
            ),
            _entry("sc59_archived", f"{rel}/archived.wav", lifecycle_state="archived"),
        ],
    }


def test_whitelist_contains_only_approved_entry_ids(project_root: Path):
    manifest = _mixed_manifest(project_root)
    gate = evaluate_short_chain_gate(manifest, project_root=project_root, check_file_exists=True)
    whitelist = build_short_chain_whitelist(manifest, project_root=project_root, check_file_exists=True)

    assert gate.approved_entry_ids == ["sc59_approved"]
    assert whitelist == frozenset({"sc59_approved"})
    assert gate.blocked_entry_ids == [
        "sc59_pending",
        "sc59_restricted",
        "sc59_unknown",
        "sc59_quarantine",
        "sc59_archived",
    ]


@pytest.mark.parametrize(
    "entry_id,license_status,lifecycle,quarantine",
    [
        ("sc59_pending", "pending", "active", False),
        ("sc59_restricted", "restricted", "active", False),
        ("sc59_unknown", "unknown", "active", False),
        ("sc59_quarantine", "approved", "active", True),
        ("sc59_archived", "approved", "archived", False),
    ],
)
def test_blocked_entry_cannot_enter_runner_whitelist(
    project_root: Path,
    entry_id: str,
    license_status: str,
    lifecycle: str,
    quarantine: bool,
):
    rel = "shared_data/materials/stage59/approved.wav"

    manifest = _base_manifest()
    manifest["entries"] = [
        _entry("sc59_ok", rel),
        _entry(
            entry_id,
            rel,
            license_status=license_status,
            lifecycle_state=lifecycle,
            quarantine_recommended=quarantine,
        ),
    ]
    whitelist = build_short_chain_whitelist(
        manifest, project_root=project_root, check_file_exists=True
    )

    assert "sc59_ok" in whitelist
    assert entry_id not in whitelist
    gate = evaluate_short_chain_gate(manifest, project_root=project_root, check_file_exists=True)
    assert entry_id in gate.blocked_entry_ids
    assert entry_id not in gate.approved_entry_ids


def test_runner_rejects_blocked_id_not_in_whitelist(project_root: Path):
    """Simulates 59C dry-run: runner may only process ids present in gate whitelist."""
    manifest = _mixed_manifest(project_root)
    whitelist = build_short_chain_whitelist(
        manifest, project_root=project_root, check_file_exists=True
    )
    all_ids = {str(e["id"]) for e in manifest["entries"]}

    for blocked_id in (
        "sc59_pending",
        "sc59_restricted",
        "sc59_unknown",
        "sc59_quarantine",
        "sc59_archived",
    ):
        assert blocked_id in all_ids
        assert blocked_id not in whitelist

    assert whitelist <= frozenset({"sc59_approved"})


def test_whitelist_matches_gate_approved_ids_only(project_root: Path):
    manifest = _mixed_manifest(project_root)
    gate = evaluate_short_chain_gate(manifest, project_root=project_root, check_file_exists=True)
    whitelist = build_short_chain_whitelist(
        manifest, project_root=project_root, check_file_exists=True
    )

    assert whitelist == frozenset(gate.approved_entry_ids)
    assert whitelist.isdisjoint(frozenset(gate.blocked_entry_ids))


def test_rights_blocked_entry_excluded_from_whitelist(project_root: Path):
    rel = "shared_data/materials/stage59/approved.wav"
    manifest = _base_manifest()
    manifest["entries"] = [
        _entry("sc59_rights_blocked", rel, rights_blocked=True),
    ]
    whitelist = build_short_chain_whitelist(
        manifest, project_root=project_root, check_file_exists=True
    )

    assert whitelist == frozenset()
    gate = evaluate_short_chain_gate(manifest, project_root=project_root, check_file_exists=True)
    assert gate.blocked_entry_ids == ["sc59_rights_blocked"]


def test_redacted_template_whitelist_excludes_pending(project_root: Path):
    redacted = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "agent-md"
        / "evidence"
        / "stage59-short-chain-manifest.redacted.json"
    )
    data = json.loads(redacted.read_text(encoding="utf-8"))
    whitelist = build_short_chain_whitelist(
        data, project_root=project_root, check_file_exists=False
    )

    assert whitelist == frozenset({"stage59_redacted_cover_source"})
    assert "stage59_redacted_pending_dry_vocal" not in whitelist