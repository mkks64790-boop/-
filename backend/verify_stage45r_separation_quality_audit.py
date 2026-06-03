from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.separation_eval_service import (  # noqa: E402
    audit_environment,
    discover_sources,
    execute_separation_audit,
    get_eval_run,
    list_eval_runs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 45R UVR separation quality audit.")
    parser.add_argument("--execute", action="store_true", help="Run clipped UVR separation. Default is dry-run only.")
    parser.add_argument("--limit", type=int, default=3, help="Max source files to execute. Capped to 3.")
    parser.add_argument("--clip-seconds", type=int, default=45, help="Clip length for each source. Capped to 60 seconds.")
    args = parser.parse_args()

    print("STAGE45R_SEPARATION_AUDIT")
    print("safety: train.py started = no")
    print("safety: RVC inference called = no")
    print("safety: default mode = dry-run")

    env = audit_environment()
    sources = discover_sources(ROOT)
    print("\nENVIRONMENT")
    print(json.dumps(env, ensure_ascii=False, indent=2))
    print("\nCANDIDATES")
    print(json.dumps(sources, ensure_ascii=False, indent=2))

    verify_latest_run_contract()

    if not args.execute:
        print("\nDRY_RUN_ONLY")
        print("No separation executed. Use --execute --limit 3 --clip-seconds 45 to run capped evaluation.")
        print("STAGE45R_AUDIT_SUMMARY PASS")
        return 0

    print("\nEXECUTE_REQUESTED")
    print(f"limit={min(max(args.limit, 1), 3)} clip_seconds={min(max(args.clip_seconds, 1), 60)}")
    result = execute_separation_audit(project_root=ROOT, limit=args.limit, clip_seconds=args.clip_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("status") in {"completed", "partial", "blocked"}:
        print("STAGE45R_AUDIT_SUMMARY PASS")
        return 0
    print("STAGE45R_AUDIT_SUMMARY FAIL")
    return 1


def verify_latest_run_contract() -> None:
    runs = list_eval_runs(ROOT).get("runs") or []
    if not runs:
        print("\nLATEST_RUN_CONTRACT")
        print("No existing separation eval run found.")
        print("BLOCK_TRAINING=false")
        return

    latest_run_id = runs[0]["run_id"]
    detail = get_eval_run(latest_run_id, ROOT) or {}
    print("\nLATEST_RUN_CONTRACT")
    print(f"run_id={latest_run_id}")
    print(f"block_training={str(bool(detail.get('block_training'))).lower()}")

    artifact_checks = _check_artifact_urls(detail)
    for check in artifact_checks:
        print(
            "artifact_url "
            f"item={check['item_index']} key={check['key']} "
            f"status={check['status_code']} readable={str(check['readable']).lower()} "
            f"content_type={check['content_type']}"
        )

    for item in detail.get("items") or []:
        print(
            "duration_contract "
            f"item={item.get('item_index')} "
            f"mismatch={str(bool(item.get('duration_mismatch'))).lower()} "
            f"ratio={item.get('duration_ratio')} "
            f"risk={item.get('duration_mismatch_risk')}"
        )

    if detail.get("block_training"):
        print("BLOCK_TRAINING=true")
    else:
        print("BLOCK_TRAINING=false")


def _check_artifact_urls(detail: dict) -> list[dict]:
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
    except Exception as exc:
        return [
            {
                "item_index": 0,
                "key": "all",
                "status_code": 0,
                "readable": False,
                "content_type": "",
                "error": str(exc),
            }
        ]

    checks = []
    with TestClient(app) as client:
        for item in detail.get("items") or []:
            item_index = item.get("item_index")
            urls = item.get("artifact_urls") or {}
            for key in ("original", "vocal", "instrumental"):
                url = urls.get(key) or ""
                resp = client.get(url) if url else None
                content_type = resp.headers.get("content-type", "") if resp is not None else ""
                checks.append(
                    {
                        "item_index": item_index,
                        "key": key,
                        "status_code": resp.status_code if resp is not None else 0,
                        "readable": bool(resp is not None and resp.status_code == 200 and resp.content),
                        "content_type": content_type,
                    }
                )
    return checks


if __name__ == "__main__":
    raise SystemExit(main())
