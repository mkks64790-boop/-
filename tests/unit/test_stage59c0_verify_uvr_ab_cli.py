"""
Stage59C-0 — verify_stage59_uvr_ab.py CLI contract (dry-run only).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.services.short_chain_manifest_service import SCHEMA_VERSION
from backend.services.short_chain_uvr_service import STAGE59C0_EXECUTE_BLOCK_REASON, plan_dry_run
from backend.verify_stage59_uvr_ab import main as verify_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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


def _uvr_entry(entry_id: str, rel_path: str, *, license_status: str = "approved") -> dict:
    return {
        "id": entry_id,
        "material_id": "",
        "source_path": rel_path,
        "material_role": "separation_eval_candidate",
        "lifecycle_state": "active",
        "intended_chain": ["preflight", "uvr_ab"],
        "license_status": license_status,
        "duration_seconds": 45.0,
        "rights_blocked": False,
        "quarantine_recommended": False,
    }


def _run_script(argv: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    root = _repo_root()
    script = root / "backend" / "verify_stage59_uvr_ab.py"
    return subprocess.run(
        [sys.executable, str(script), *argv],
        cwd=cwd or root,
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_dry_run_pass_redacted_template_skip_files():
    root = _repo_root()
    manifest = root / "docs" / "agent-md" / "evidence" / "stage59-short-chain-manifest.redacted.json"
    code = verify_main(
        [
            "--manifest",
            str(manifest),
            "--skip-file-exists",
            "--project-root",
            str(root),
        ]
    )
    assert code == 0


def test_dry_run_pass_local_manifest(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    rel = "shared_data/materials/stage59/uvr.wav"
    _write_wav(root / rel)
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_uvr", rel)]
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert verify_main(["--manifest", str(manifest_path), "--project-root", str(root)]) == 0
    plan = plan_dry_run(["sc59_uvr"], manifest_path, project_root=root)
    assert plan["planned_count"] == 1
    assert plan["execute_allowed"] is False


def test_manifest_missing_exit_2(tmp_path: Path):
    missing = tmp_path / "shared_data" / "materials" / "stage59" / "missing.json"
    assert verify_main(
        [
            "--manifest",
            str(missing.relative_to(tmp_path)),
            "--project-root",
            str(tmp_path),
        ]
    ) == 2


def test_no_approved_entries_exit_3(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    rel = "shared_data/materials/stage59/pending.wav"
    _write_wav(root / rel)
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_pending", rel, license_status="pending")]
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert verify_main(["--manifest", str(manifest_path), "--project-root", str(root)]) == 3


def test_execute_blocked_exit_1(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    rel = "shared_data/materials/stage59/uvr.wav"
    _write_wav(root / rel)
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_uvr", rel)]
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    code = verify_main(
        ["--manifest", str(manifest_path), "--project-root", str(root), "--execute"]
    )
    assert code == 1


def test_execute_blocked_subprocess_message(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    rel = "shared_data/materials/stage59/uvr.wav"
    _write_wav(root / rel)
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_uvr", rel)]
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_script(
        [
            "--manifest",
            str(manifest_path),
            "--project-root",
            str(root),
            "--execute",
        ],
        cwd=root,
    )
    assert result.returncode == 1
    assert STAGE59C0_EXECUTE_BLOCK_REASON in result.stdout + result.stderr


def test_entry_id_filter_pass(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    rel = "shared_data/materials/stage59/uvr.wav"
    _write_wav(root / rel)
    manifest = _base_manifest()
    manifest["entries"] = [
        _uvr_entry("sc59_a", rel),
        _uvr_entry("sc59_b", rel),
    ]
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    code = verify_main(
        [
            "--manifest",
            str(manifest_path),
            "--project-root",
            str(root),
            "--entry-id",
            "sc59_b",
        ]
    )
    assert code == 0


def test_entry_id_not_in_whitelist_exit_1(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    rel = "shared_data/materials/stage59/pending.wav"
    _write_wav(root / rel)
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_pending", rel, license_status="pending")]
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    code = verify_main(
        [
            "--manifest",
            str(manifest_path),
            "--project-root",
            str(root),
            "--entry-id",
            "sc59_pending",
        ]
    )
    assert code == 1


def test_json_output_contains_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    root = tmp_path / "proj"
    root.mkdir()
    rel = "shared_data/materials/stage59/uvr.wav"
    _write_wav(root / rel)
    manifest = _base_manifest()
    manifest["entries"] = [_uvr_entry("sc59_uvr", rel)]
    manifest_path = root / "shared_data" / "materials" / "stage59" / "short_chain_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    code = verify_main(
        [
            "--manifest",
            str(manifest_path),
            "--project-root",
            str(root),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
    assert payload["plan"]["planned_count"] == 1


def test_schema_invalid_exit_1(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    manifest_path = root / "shared_data" / "materials" / "stage59" / "bad.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"stage": "stage59"}), encoding="utf-8")
    assert verify_main(["--manifest", str(manifest_path), "--project-root", str(root)]) == 1


def test_verifier_does_not_import_separation_or_subprocess():
    source = (_repo_root() / "backend" / "verify_stage59_uvr_ab.py").read_text(encoding="utf-8")
    assert "import subprocess" not in source
    assert "separation_eval_service" not in source
    assert "voice_changer" not in source
    assert "vocal_separator" not in source
    assert "short_chain_uvr_service" in source


def test_subprocess_redacted_dry_run_pass():
    root = _repo_root()
    manifest = root / "docs" / "agent-md" / "evidence" / "stage59-short-chain-manifest.redacted.json"
    result = _run_script(
        [
            "--manifest",
            str(manifest),
            "--skip-file-exists",
            "--project-root",
            str(root),
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STAGE59_UVR_AB PASS" in result.stdout