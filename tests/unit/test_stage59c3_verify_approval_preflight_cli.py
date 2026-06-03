"""Stage59C-3 approval preflight CLI tests."""

from __future__ import annotations

from pathlib import Path

from backend.services.stage59_approval_audit_service import clear_audit_store
from backend.services.stage59_execution_policy_service import REAL_RUNNER_NOT_ENABLED_REASON
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


def setup_function() -> None:
    clear_audit_store()


def test_approval_preflight_pass_without_confirm():
    code = verify_main(
        [
            "--approval-preflight",
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


def test_approval_preflight_with_token_pass():
    code = verify_main(
        [
            "--approval-preflight",
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


def test_requested_real_execute_blocked():
    code = verify_main(
        [
            "--approval-preflight",
            "--requested-mode",
            "real_execute",
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
    assert code == 1