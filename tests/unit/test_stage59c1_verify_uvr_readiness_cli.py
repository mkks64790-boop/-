"""
Stage59C-1 — verify_stage59_uvr_ab.py --readiness CLI tests.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.services.stage59_uvr_runner_contract import REAL_RUNNER_BLOCKED_REASON
from backend.verify_stage59_uvr_ab import main as verify_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _redacted_manifest() -> Path:
    return (
        _repo_root()
        / "docs"
        / "agent-md"
        / "evidence"
        / "stage59-short-chain-manifest.redacted.json"
    )


def _run_script(argv: list[str]) -> subprocess.CompletedProcess[str]:
    script = _repo_root() / "backend" / "verify_stage59_uvr_ab.py"
    return subprocess.run(
        [sys.executable, str(script), *argv],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_readiness_pass_redacted_manifest():
    code = verify_main(
        [
            "--readiness",
            "--manifest",
            str(_redacted_manifest()),
            "--entry-id",
            "stage59_redacted_cover_source",
            "--skip-file-exists",
            "--project-root",
            str(_repo_root()),
        ]
    )
    assert code == 0


def test_readiness_subprocess_pass_message():
    result = _run_script(
        [
            "--readiness",
            "--manifest",
            str(_redacted_manifest()),
            "--entry-id",
            "stage59_redacted_cover_source",
            "--skip-file-exists",
            "--project-root",
            str(_repo_root()),
        ]
    )
    assert result.returncode == 0
    assert "STAGE59_UVR_AB PASS" in result.stdout
    assert "real_execute_allowed=false" in result.stdout


def test_readiness_requires_entry_id():
    code = verify_main(
        [
            "--readiness",
            "--manifest",
            str(_redacted_manifest()),
            "--skip-file-exists",
            "--project-root",
            str(_repo_root()),
        ]
    )
    assert code == 1


def test_readiness_real_runner_blocked():
    code = verify_main(
        [
            "--readiness",
            "--runner",
            "real",
            "--manifest",
            str(_redacted_manifest()),
            "--entry-id",
            "stage59_redacted_cover_source",
            "--skip-file-exists",
            "--project-root",
            str(_repo_root()),
        ]
    )
    assert code == 1


def test_unsafe_manifest_path_exit_1():
    root = _repo_root()
    code = verify_main(
        [
            "--readiness",
            "--manifest",
            str(root / "backend" / "feishark.db"),
            "--entry-id",
            "stage59_redacted_cover_source",
            "--project-root",
            str(root),
        ]
    )
    assert code == 1


def test_dry_run_still_compatible():
    code = verify_main(
        [
            "--dry-run",
            "--manifest",
            str(_redacted_manifest()),
            "--skip-file-exists",
            "--project-root",
            str(_repo_root()),
        ]
    )
    assert code == 0


def test_execute_still_blocked_with_readiness_reason():
    code = verify_main(
        [
            "--readiness",
            "--execute",
            "--manifest",
            str(_redacted_manifest()),
            "--entry-id",
            "stage59_redacted_cover_source",
            "--skip-file-exists",
            "--project-root",
            str(_repo_root()),
        ]
    )
    assert code == 1


def test_readiness_json_output(capsys: pytest.CaptureFixture[str]):
    code = verify_main(
        [
            "--readiness",
            "--json",
            "--manifest",
            str(_redacted_manifest()),
            "--entry-id",
            "stage59_redacted_cover_source",
            "--skip-file-exists",
            "--project-root",
            str(_repo_root()),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["real_execute_allowed"] is False
    assert payload["readiness"]["artifact_contracts"]


def test_runner_real_on_dry_run_path_blocked():
    result = _run_script(
        [
            "--runner",
            "real",
            "--manifest",
            str(_redacted_manifest()),
            "--skip-file-exists",
            "--project-root",
            str(_repo_root()),
        ]
    )
    assert result.returncode == 1
    assert REAL_RUNNER_BLOCKED_REASON in result.stdout + result.stderr