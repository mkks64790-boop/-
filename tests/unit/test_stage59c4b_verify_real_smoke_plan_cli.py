"""Stage59C-4b real-smoke plan CLI tests."""

from __future__ import annotations

from pathlib import Path

from backend.verify_stage59_uvr_ab import main as verify_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _redacted() -> Path:
    return (
        _repo_root()
        / "docs"
        / "agent-md"
        / "evidence"
        / "stage59-short-chain-manifest.redacted.json"
    )


def test_real_smoke_plan_cli_passes_as_plan_only():
    code = verify_main(
        [
            "--real-smoke-plan",
            "--confirm-execute",
            "--approval-token",
            "stage59-local-approval",
            "--manifest",
            str(_redacted()),
            "--entry-id",
            "stage59_redacted_cover_source",
            "--skip-file-exists",
            "--project-root",
            str(_repo_root()),
        ]
    )
    assert code == 0
