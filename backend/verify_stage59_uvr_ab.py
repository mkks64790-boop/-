#!/usr/bin/env python3
"""
Stage59C-0/59C-1 verifier — short-chain UVR A/B dry-run and readiness harness.

Default: dry-run PASS without UVR/RVC/GPU/subprocess.
--readiness: mock runner contract (metadata-only artifacts).
--mock-execute: 59C-2/4a transient artifact + persistence contract (metadata-only).
--artifact-contract: with --mock-execute, print persistence contract fields.
--approval-preflight: 59C-3 approval gate (real execute still blocked).
--execute and --runner real: blocked in this stage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.short_chain_manifest_service import (  # noqa: E402
    SCHEMA_VERSION,
    ManifestPathSafetyError,
    build_short_chain_whitelist,
    default_manifest_path,
    evaluate_short_chain_gate,
    load_manifest,
    project_root_from_here,
    resolve_safe_manifest_path,
    validate_manifest_structure,
)
from backend.services.short_chain_uvr_service import (  # noqa: E402
    STAGE59C0_EXECUTE_BLOCK_REASON,
    evaluate_uvr_ab_readiness,
    plan_dry_run,
    select_uvr_ab_entries,
)
from backend.services.execution_safety_service import (  # noqa: E402
    REAL_RUNNER_NOT_ENABLED_REASON,
    evaluate_execution_policy,
)
from backend.services.uvr_smoke_service import evaluate_real_smoke_plan  # noqa: E402
from backend.services.uvr_smoke_service import mock_execute_uvr_ab  # noqa: E402
from backend.services.uvr_smoke_service import (  # noqa: E402
    REAL_RUNNER_BLOCKED_REASON,
    RunnerMode,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage59 short-chain UVR A/B verifier (dry-run/readiness; no separation)."
    )
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
        help="Gate/whitelist without requiring audio files on disk",
    )
    parser.add_argument(
        "--entry-id",
        type=str,
        default=None,
        help="Optional single manifest entry id filter (required for --readiness)",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Plan only (default: true)",
    )
    parser.add_argument(
        "--readiness",
        action="store_true",
        help="59C-1 mock runner readiness harness (metadata-only)",
    )
    parser.add_argument(
        "--mock-execute",
        action="store_true",
        help="59C-2 mock execute + transient artifact metadata (no audio files)",
    )
    parser.add_argument(
        "--artifact-contract",
        action="store_true",
        help="With --mock-execute: include persistence-ready artifact contract output",
    )
    parser.add_argument(
        "--approval-preflight",
        action="store_true",
        help="59C-3 approval gate preflight (metadata-only; no real UVR)",
    )
    parser.add_argument(
        "--real-smoke-plan",
        action="store_true",
        help="59C-4b real UVR smoke plan only (no UVR execution)",
    )
    parser.add_argument(
        "--confirm-execute",
        action="store_true",
        help="Explicit execute confirmation for approval preflight",
    )
    parser.add_argument(
        "--approval-token",
        type=str,
        default=None,
        help="Approval token (e.g. stage59-local-approval)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=1,
        help="Max manifest entries to process (must be 1)",
    )
    parser.add_argument(
        "--requested-mode",
        choices=["approval_preflight", "real_execute"],
        default="approval_preflight",
        help="Requested execution mode for approval preflight",
    )
    parser.add_argument(
        "--runner",
        choices=[RunnerMode.MOCK.value, RunnerMode.REAL.value],
        default=RunnerMode.MOCK.value,
        help="Runner mode for --readiness (real is blocked)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Request UVR execution (blocked)",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    root = args.project_root or project_root_from_here()
    check_files = not args.skip_file_exists

    try:
        manifest_path = resolve_safe_manifest_path(args.manifest, project_root=root)
    except ManifestPathSafetyError as exc:
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": exc.reason,
                "manifest": str(args.manifest or ""),
                "exit_code": 1,
            },
            text=f"STAGE59_UVR_AB FAIL {exc.reason}",
        )
        return 1

    if args.readiness:
        return _run_readiness(args, manifest_path=manifest_path, root=root, check_files=check_files)

    if args.mock_execute:
        return _run_mock_execute(args, manifest_path=manifest_path, root=root, check_files=check_files)

    if args.approval_preflight:
        return _run_approval_preflight(
            args,
            manifest_path=manifest_path,
            root=root,
            check_files=check_files,
        )

    if args.real_smoke_plan:
        return _run_real_smoke_plan(
            args,
            manifest_path=manifest_path,
            root=root,
            check_files=check_files,
        )

    try:
        data = load_manifest(manifest_path)
    except FileNotFoundError:
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": "manifest_missing",
                "manifest": str(manifest_path),
                "exit_code": 2,
            },
            text=f"STAGE59_UVR_AB FAIL manifest_missing={manifest_path}",
        )
        return 2
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": "manifest_read_error",
                "error": str(exc),
                "exit_code": 1,
            },
            text=f"STAGE59_UVR_AB FAIL manifest_read_error={exc}",
        )
        return 1

    schema_errors = validate_manifest_structure(data)
    if schema_errors:
        return _fail_validation(
            args,
            manifest_path=manifest_path,
            schema_errors=schema_errors,
            reason="schema",
        )

    gate = evaluate_short_chain_gate(data, project_root=root, check_file_exists=check_files)
    whitelist = build_short_chain_whitelist(
        data, project_root=root, check_file_exists=check_files
    )
    manifest_ids = {
        str(entry.get("id"))
        for entry in (data.get("entries") or [])
        if isinstance(entry, dict) and entry.get("id")
    }

    if args.entry_id:
        if args.entry_id not in manifest_ids:
            return _fail_validation(
                args,
                manifest_path=manifest_path,
                gate_errors=[f"entry_id_not_in_manifest:{args.entry_id}"],
                reason="entry_id_not_in_manifest",
            )
        if args.entry_id not in whitelist:
            return _fail_validation(
                args,
                manifest_path=manifest_path,
                gate_errors=[f"entry_id_not_approved:{args.entry_id}"],
                reason="entry_id_not_in_whitelist",
            )

    if not whitelist:
        if not gate.ok and gate.errors and not _is_no_approved_failure(gate.errors):
            return _fail_validation(
                args,
                manifest_path=manifest_path,
                gate_errors=gate.errors,
                reason="rights_or_gate",
            )
        return _fail_no_approved(args, manifest_path=manifest_path, gate=gate)

    if not gate.ok and gate.errors:
        return _fail_validation(
            args,
            manifest_path=manifest_path,
            gate_errors=gate.errors,
            reason="rights_or_gate",
        )

    uvr_entries = select_uvr_ab_entries(
        data, whitelist=whitelist, entry_id_filter=args.entry_id
    )
    entry_ids = [str(entry["id"]) for entry in uvr_entries]

    if args.entry_id and not entry_ids:
        if args.entry_id not in manifest_ids:
            reason = "entry_id_not_in_manifest"
        elif args.entry_id in whitelist:
            reason = "entry_id_not_uvr_ab_eligible"
        else:
            reason = "entry_id_not_in_whitelist"
        return _fail_validation(
            args,
            manifest_path=manifest_path,
            gate_errors=[f"{reason}:{args.entry_id}"],
            reason=reason,
        )

    if not entry_ids:
        return _fail_no_approved(
            args,
            manifest_path=manifest_path,
            gate=gate,
            detail="no_uvr_ab_eligible_approved_entries",
        )

    if args.execute or not args.dry_run or args.runner == RunnerMode.REAL.value:
        blocked_reason = (
            REAL_RUNNER_BLOCKED_REASON
            if args.runner == RunnerMode.REAL.value and not args.execute
            else STAGE59C0_EXECUTE_BLOCK_REASON
        )
        return _fail_execute_blocked(
            args,
            manifest_path=manifest_path,
            entry_ids=entry_ids,
            reason=blocked_reason,
        )

    plan = plan_dry_run(
        entry_ids,
        manifest_path,
        project_root=root,
        check_file_exists=check_files,
    )

    payload = {
        "status": "PASS",
        "mode": "dry_run",
        "schema_version": SCHEMA_VERSION,
        "manifest": str(manifest_path),
        "approved_entry_ids": sorted(whitelist),
        "uvr_ab_entry_ids": entry_ids,
        "gate_warnings": gate.warnings,
        "plan": plan,
        "exit_code": 0,
        "safety": plan.get("safety"),
        "real_execute_allowed": False,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("STAGE59_UVR_AB")
        print(f"manifest={manifest_path}")
        print("dry_run=true execute=false")
        print(f"uvr_ab_entries={json.dumps(entry_ids, ensure_ascii=False)}")
        print(f"planned_count={plan.get('planned_count', 0)}")
        if gate.warnings:
            print("warnings=" + json.dumps(gate.warnings, ensure_ascii=False))
        print("STAGE59_UVR_AB PASS")
    return 0


def _run_readiness(
    args: argparse.Namespace,
    *,
    manifest_path: Path,
    root: Path,
    check_files: bool,
) -> int:
    if not args.entry_id:
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": "entry_id_required_for_readiness",
                "exit_code": 1,
            },
            text="STAGE59_UVR_AB FAIL entry_id_required_for_readiness",
        )
        return 1

    if args.execute:
        return _fail_execute_blocked(
            args,
            manifest_path=manifest_path,
            entry_ids=[args.entry_id],
            reason=STAGE59C0_EXECUTE_BLOCK_REASON,
        )

    readiness = evaluate_uvr_ab_readiness(
        args.entry_id,
        manifest_path=manifest_path,
        project_root=root,
        runner_mode=args.runner,
        check_file_exists=check_files,
    )
    if not readiness.get("ok"):
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": readiness.get("blocked_reason", "readiness_blocked"),
                "manifest": str(manifest_path),
                "readiness": readiness,
                "exit_code": 1,
            },
            text=f"STAGE59_UVR_AB FAIL {readiness.get('blocked_reason')}",
        )
        return 1

    payload = {
        "status": "PASS",
        "mode": "readiness",
        "schema_version": SCHEMA_VERSION,
        "manifest": str(manifest_path),
        "entry_id": args.entry_id,
        "runner_mode": readiness.get("runner_mode", args.runner),
        "readiness": readiness,
        "real_execute_allowed": False,
        "exit_code": 0,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("STAGE59_UVR_AB")
        print(f"manifest={manifest_path}")
        print("mode=readiness real_execute_allowed=false")
        print(f"entry_id={args.entry_id}")
        contracts = readiness.get("artifact_contracts") or []
        print(f"artifact_contracts={len(contracts)}")
        print("STAGE59_UVR_AB PASS")
    return 0


def _run_mock_execute(
    args: argparse.Namespace,
    *,
    manifest_path: Path,
    root: Path,
    check_files: bool,
) -> int:
    if not args.entry_id:
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": "entry_id_required_for_mock_execute",
                "exit_code": 1,
            },
            text="STAGE59_UVR_AB FAIL entry_id_required_for_mock_execute",
        )
        return 1

    if args.execute:
        return _fail_execute_blocked(
            args,
            manifest_path=manifest_path,
            entry_ids=[args.entry_id],
            reason=STAGE59C0_EXECUTE_BLOCK_REASON,
        )

    if args.runner == RunnerMode.REAL.value:
        return _fail_execute_blocked(
            args,
            manifest_path=manifest_path,
            entry_ids=[args.entry_id],
            reason=REAL_RUNNER_BLOCKED_REASON,
        )

    result = mock_execute_uvr_ab(
        args.entry_id,
        manifest_path=manifest_path,
        project_root=root,
        check_file_exists=check_files,
    )
    if not result.get("ok"):
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": result.get("blocked_reason", "mock_execute_blocked"),
                "manifest": str(manifest_path),
                "mock_execute": result,
                "exit_code": 1,
            },
            text=f"STAGE59_UVR_AB FAIL {result.get('blocked_reason')}",
        )
        return 1

    contract = result.get("artifact_persistence_contract") or {}
    payload = {
        "status": "PASS",
        "mode": "mock_execute",
        "schema_version": SCHEMA_VERSION,
        "manifest": str(manifest_path),
        "entry_id": args.entry_id,
        "run_id": result.get("run_id"),
        "mock_execute": result,
        "artifact_records": result.get("artifact_records"),
        "artifact_persistence_contract": contract,
        "listening_contract": result.get("listening_contract"),
        "real_execute_allowed": False,
        "audio_files_written": False,
        "exit_code": 0,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("STAGE59_UVR_AB")
        print(f"manifest={manifest_path}")
        print("mode=mock_execute real_execute_allowed=false audio_files_written=false")
        print(f"entry_id={args.entry_id}")
        print(f"run_id={result.get('run_id')}")
        records = result.get("artifact_records") or []
        print(f"artifact_records={len(records)}")
        if args.artifact_contract:
            print("artifact_contract:")
            for art in contract.get("artifacts") or records:
                print(
                    f"  id={art.get('artifact_id')} lifecycle={art.get('lifecycle_state')} "
                    f"metadata_only={art.get('metadata_only')} file_exists={art.get('file_exists')} "
                    f"playback_enabled={art.get('playback_enabled')}"
                )
            promo = result.get("promotion_plan") or {}
            print(f"promotion_can_promote={promo.get('can_promote', False)}")
        print("STAGE59_UVR_AB PASS")
    return 0


def _run_approval_preflight(
    args: argparse.Namespace,
    *,
    manifest_path: Path,
    root: Path,
    check_files: bool,
) -> int:
    if not args.entry_id:
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": "entry_id_required_for_approval_preflight",
                "exit_code": 1,
            },
            text="STAGE59_UVR_AB FAIL entry_id_required_for_approval_preflight",
        )
        return 1

    result = evaluate_execution_policy(
        args.entry_id,
        manifest_path=manifest_path,
        project_root=root,
        clip_seconds=45,
        check_file_exists=check_files,
        confirm_execute=args.confirm_execute,
        approval_token=args.approval_token,
        requested_mode=args.requested_mode,
        max_items=args.max_items,
    )

    if args.requested_mode == "real_execute":
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": REAL_RUNNER_NOT_ENABLED_REASON,
                "policy": result,
                "exit_code": 1,
                "real_execute_allowed": False,
            },
            text=f"STAGE59_UVR_AB FAIL {REAL_RUNNER_NOT_ENABLED_REASON}",
        )
        return 1

    if not result.get("ok"):
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": result.get("blocked_reasons", ["policy_blocked"]),
                "policy": result,
                "exit_code": 1,
            },
            text=f"STAGE59_UVR_AB FAIL {result.get('blocked_reasons')}",
        )
        return 1

    payload = {
        "status": "PASS",
        "mode": "approval_preflight",
        "schema_version": SCHEMA_VERSION,
        "manifest": str(manifest_path),
        "entry_id": args.entry_id,
        "policy": result,
        "real_execute_allowed": False,
        "real_execute_block_reason": REAL_RUNNER_NOT_ENABLED_REASON,
        "exit_code": 0,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("STAGE59_UVR_AB")
        print(f"manifest={manifest_path}")
        print("mode=approval_preflight real_execute_allowed=false")
        print(f"entry_id={args.entry_id}")
        if result.get("blocked_reasons"):
            print(f"warnings={json.dumps(result['blocked_reasons'], ensure_ascii=False)}")
        print(f"approval_complete={result.get('approval_complete', False)}")
        print("STAGE59_UVR_AB PASS")
    return 0


def _run_real_smoke_plan(
    args: argparse.Namespace,
    *,
    manifest_path: Path,
    root: Path,
    check_files: bool,
) -> int:
    if not args.entry_id:
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": "entry_id_required_for_real_smoke_plan",
                "exit_code": 1,
            },
            text="STAGE59_UVR_AB FAIL entry_id_required_for_real_smoke_plan",
        )
        return 1

    result = evaluate_real_smoke_plan(
        args.entry_id,
        manifest_path=manifest_path,
        project_root=root,
        clip_seconds=45,
        check_file_exists=check_files,
        confirm_execute=args.confirm_execute,
        approval_token=args.approval_token,
        max_items=args.max_items,
    )
    if not result.get("ok"):
        _emit(
            args,
            {
                "status": "FAIL",
                "reason": result.get("blocked_reasons", ["real_smoke_plan_blocked"]),
                "plan": result,
                "exit_code": 1,
                "real_execute_allowed": False,
                "audio_files_written": False,
            },
            text=f"STAGE59_UVR_AB FAIL {result.get('blocked_reasons')}",
        )
        return 1

    payload = {
        "status": "PASS",
        "mode": "real_smoke_plan",
        "schema_version": SCHEMA_VERSION,
        "manifest": str(manifest_path),
        "entry_id": args.entry_id,
        "plan": result,
        "real_execute_allowed": False,
        "audio_files_written": False,
        "exit_code": 0,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("STAGE59_UVR_AB")
        print(f"manifest={manifest_path}")
        print("mode=real_smoke_plan real_execute_allowed=false audio_files_written=false")
        print(f"entry_id={args.entry_id}")
        print(f"approval_complete={result.get('approval_complete', False)}")
        print(f"planned_sandbox={result.get('planned_sandbox')}")
        print(f"blocked_reasons={json.dumps(result.get('blocked_reasons', []), ensure_ascii=False)}")
        print("STAGE59_UVR_AB PASS")
    return 0


def _is_no_approved_failure(errors: list[str]) -> bool:
    return any("no_approved_short_chain_entries" in err for err in errors)


def _fail_validation(
    args: argparse.Namespace,
    *,
    manifest_path: Path,
    reason: str,
    schema_errors: list[str] | None = None,
    validation_errors: list[str] | None = None,
    gate_errors: list[str] | None = None,
) -> int:
    errors = schema_errors or validation_errors or gate_errors or []
    _emit(
        args,
        {
            "status": "FAIL",
            "reason": reason,
            "manifest": str(manifest_path),
            "schema_errors": schema_errors or [],
            "validation_errors": validation_errors or [],
            "gate_errors": gate_errors or [],
            "errors": errors,
            "exit_code": 1,
        },
        text=f"STAGE59_UVR_AB FAIL {reason}",
    )
    return 1


def _fail_no_approved(
    args: argparse.Namespace,
    *,
    manifest_path: Path,
    gate: object,
    detail: str = "no_approved_entries",
) -> int:
    warnings = getattr(gate, "warnings", [])
    blocked = getattr(gate, "blocked_entry_ids", [])
    _emit(
        args,
        {
            "status": "FAIL",
            "reason": detail,
            "manifest": str(manifest_path),
            "gate_warnings": warnings,
            "blocked_entry_ids": blocked,
            "exit_code": 3,
        },
        text=f"STAGE59_UVR_AB FAIL {detail}",
    )
    return 3


def _fail_execute_blocked(
    args: argparse.Namespace,
    *,
    manifest_path: Path,
    entry_ids: list[str],
    reason: str | None = None,
) -> int:
    blocked = reason or STAGE59C0_EXECUTE_BLOCK_REASON
    _emit(
        args,
        {
            "status": "FAIL",
            "reason": blocked,
            "manifest": str(manifest_path),
            "uvr_ab_entry_ids": entry_ids,
            "exit_code": 1,
            "real_execute_allowed": False,
        },
        text=f"STAGE59_UVR_AB FAIL {blocked}",
    )
    return 1


def _emit(args: argparse.Namespace, payload: dict, *, text: str) -> None:
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text)


if __name__ == "__main__":
    raise SystemExit(main())
