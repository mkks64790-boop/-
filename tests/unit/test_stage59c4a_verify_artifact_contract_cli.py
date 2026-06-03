"""
Stage59C-4a — verify CLI --artifact-contract tests.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_mock_execute_artifact_contract_cli():
    manifest = (
        _repo_root()
        / "docs"
        / "agent-md"
        / "evidence"
        / "stage59-short-chain-manifest.redacted.json"
    )
    cmd = [
        sys.executable,
        str(_repo_root() / "backend" / "verify_stage59_uvr_ab.py"),
        "--mock-execute",
        "--artifact-contract",
        "--json",
        "--manifest",
        str(manifest),
        "--entry-id",
        "stage59_redacted_cover_source",
        "--skip-file-exists",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    contract = payload["artifact_persistence_contract"]
    assert contract["metadata_only"] is True
    assert contract["file_exists"] is False
    for art in contract["artifacts"]:
        assert art["lifecycle_state"] == "transient"
        assert art["playback_enabled"] is False