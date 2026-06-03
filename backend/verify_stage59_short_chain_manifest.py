#!/usr/bin/env python3
"""
Stage59B verifier — short-chain manifest schema + rights gate only.

Does NOT start UVR/RVC or touch inference/training pipelines.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.short_chain_manifest_service import (
    SCHEMA_VERSION,
    default_manifest_path,
    evaluate_short_chain_gate,
    load_manifest,
    project_root_from_here,
    summarize_manifest,
    validate_manifest,
    validate_manifest_structure,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage59B short-chain manifest verifier (no UVR/RVC).")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=f"Manifest path (default: {default_manifest_path()})",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root for relative source_path resolution",
    )
    parser.add_argument(
        "--skip-file-exists",
        action="store_true",
        help="Validate schema/rights/duration only; do not require audio files on disk",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    root = args.project_root or project_root_from_here()
    manifest_path = args.manifest or default_manifest_path(root)

    try:
        data = load_manifest(manifest_path)
    except FileNotFoundError:
        print(f"STAGE59_SHORT_CHAIN FAIL manifest_missing={manifest_path}")
        print("HINT: copy docs/agent-md/evidence/stage59-short-chain-manifest.redacted.json")
        print("      to shared_data/materials/stage59/short_chain_manifest.json and fill real paths locally")
        return 2
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"STAGE59_SHORT_CHAIN FAIL manifest_read_error={exc}")
        return 1

    check_files = not args.skip_file_exists
    schema_errors = validate_manifest_structure(data)
    structure_errors = validate_manifest(data, project_root=root, check_file_exists=check_files)
    gate = evaluate_short_chain_gate(data, project_root=root, check_file_exists=check_files)
    summary = summarize_manifest(data, project_root=root, check_file_exists=check_files)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "manifest": str(manifest_path),
        "schema_errors": schema_errors,
        "validation_errors": structure_errors,
        "gate_ok": gate.ok,
        "gate_errors": gate.errors,
        "gate_warnings": gate.warnings,
        "summary": summary,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("STAGE59_SHORT_CHAIN")
        print(f"manifest={manifest_path}")
        print(f"entries={summary['entry_count']} approved={summary['approved_count']} blocked={summary['blocked_count']}")
        if gate.warnings:
            print("warnings=" + json.dumps(gate.warnings, ensure_ascii=False))
        if schema_errors or gate.errors:
            print("errors=" + json.dumps(schema_errors or gate.errors, ensure_ascii=False))

    if schema_errors:
        print("STAGE59_SHORT_CHAIN FAIL schema")
        return 1
    if not gate.ok:
        print("STAGE59_SHORT_CHAIN FAIL rights_or_gate")
        return 1

    print("STAGE59_SHORT_CHAIN PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
