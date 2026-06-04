"""
Stage59C-2 — verify_stage59_uvr_ab.py --mock-execute CLI tests.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.services.artifact_lifecycle_service import clear_transient_store
from backend.services.uvr_smoke_service import REAL_RUNNER_BLOCKED_REASON
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


@pytest.fixture(autouse=True)
def _clear_store():
    clear_transient_store()
    yield
    clear_transient_store()


def test_mock_execute_pass_redacted():
    code = verify_main(
        [
            "--mock-execute",
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


def test_mock_execute_subprocess_stdout():
    script = _repo_root() / "backend" / "verify_stage59_uvr_ab.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--mock-execute",
            "--manifest",
            str(_redacted_manifest()),
            "--entry-id",
            "stage59_redacted_cover_source",
            "--skip-file-exists",
            "--project-root",
            str(_repo_root()),
        ],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "mode=mock_execute" in result.stdout
    assert "audio_files_written=false" in result.stdout


def test_readiness_runner_real_still_blocked():
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


def test_mock_execute_json_output(capsys: pytest.CaptureFixture[str]):
    code = verify_main(
        [
            "--mock-execute",
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
    assert payload["listening_contract"]["real_execute_required"] is True
    assert payload["real_execute_allowed"] is False


def test_runner_real_on_mock_execute_path_blocked_via_readiness_branch():
    result = subprocess.run(
        [
            sys.executable,
            str(_repo_root() / "backend" / "verify_stage59_uvr_ab.py"),
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
        ],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert REAL_RUNNER_BLOCKED_REASON in result.stdout + result.stderr