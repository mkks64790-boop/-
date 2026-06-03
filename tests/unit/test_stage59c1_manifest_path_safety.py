"""
Stage59C-1 — safe manifest path resolver tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.short_chain_manifest_service import (
    DEFAULT_MANIFEST_REL,
    ManifestPathSafetyError,
    default_manifest_path,
    resolve_safe_manifest_path,
)


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    evidence = root / "docs" / "agent-md" / "evidence"
    evidence.mkdir(parents=True)
    stage59 = root / "shared_data" / "materials" / "stage59"
    stage59.mkdir(parents=True)
    (evidence / "manifest.redacted.json").write_text("{}", encoding="utf-8")
    (stage59 / "short_chain_manifest.json").write_text("{}", encoding="utf-8")
    (stage59 / "local_manifest.json").write_text("{}", encoding="utf-8")
    return root


def test_default_manifest_path_allowed(project_root: Path):
    resolved = resolve_safe_manifest_path(None, project_root=project_root)
    assert resolved == default_manifest_path(project_root)


def test_evidence_manifest_allowed(project_root: Path):
    rel = "docs/agent-md/evidence/manifest.redacted.json"
    resolved = resolve_safe_manifest_path(rel, project_root=project_root)
    assert resolved == (project_root / rel).resolve()


def test_stage59_materials_manifest_allowed(project_root: Path):
    rel = "shared_data/materials/stage59/local_manifest.json"
    resolved = resolve_safe_manifest_path(rel, project_root=project_root)
    assert resolved == (project_root / rel).resolve()


def test_default_relative_path_allowed(project_root: Path):
    resolved = resolve_safe_manifest_path(DEFAULT_MANIFEST_REL, project_root=project_root)
    assert resolved == project_root / DEFAULT_MANIFEST_REL


def test_rejects_path_traversal(project_root: Path):
    with pytest.raises(ManifestPathSafetyError) as exc:
        resolve_safe_manifest_path(
            "docs/agent-md/evidence/../../backend/feishark.db",
            project_root=project_root,
        )
    assert exc.value.reason == "manifest_path_traversal"


def test_rejects_outside_allowed_prefix(project_root: Path):
    uploads = project_root / "shared_data" / "uploads" / "manifest.json"
    uploads.parent.mkdir(parents=True, exist_ok=True)
    uploads.write_text("{}", encoding="utf-8")
    with pytest.raises(ManifestPathSafetyError) as exc:
        resolve_safe_manifest_path(
            "shared_data/uploads/manifest.json",
            project_root=project_root,
        )
    assert exc.value.reason == "manifest_path_not_allowed"


def test_rejects_absolute_outside_project(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ManifestPathSafetyError) as exc:
        resolve_safe_manifest_path(outside, project_root=root)
    assert exc.value.reason == "manifest_path_outside_project"