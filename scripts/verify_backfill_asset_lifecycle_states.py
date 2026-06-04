#!/usr/bin/env python
"""
One-time verifier / runner for retired _backfill_asset_lifecycle_states.

Phase 4: Backfill Retirement and Legacy Cleanup.

Delegates to lifecycle_service.backfill_lifecycle_states(conn) which uses
should_backfill_lifecycle_state + inference to patch active->transient/test_data etc.

Retired from init_db startup.

Usage:
  python -X utf8 scripts/verify_backfill_asset_lifecycle_states.py --dry-run
  python -X utf8 scripts/verify_backfill_asset_lifecycle_states.py --run

Note: you can also call backend.services.lifecycle_service.backfill_lifecycle_states directly
from tests or ad-hoc (it already returns stats).
"""
from __future__ import annotations

import argparse
import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from backend.db import get_connection, _backfill_asset_lifecycle_states, DB_PATH
    from backend.services.lifecycle_service import backfill_lifecycle_states
except ImportError:
    from db import get_connection, _backfill_asset_lifecycle_states, DB_PATH  # type: ignore
    from services.lifecycle_service import backfill_lifecycle_states  # type: ignore


def count_table(conn, table: str) -> int:
    try:
        if table == "material_assets":
            # may not exist in very old DBs
            try:
                row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
            except Exception:
                return 0
        else:
            row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
        return int(row["c"]) if row else 0
    except Exception:
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args(argv)
    do_run = args.run and not args.report
    if do_run:
        args.dry_run = False

    print(f"[verify_backfill_asset_lifecycle_states] DB_PATH={DB_PATH}")
    print("[verify_backfill_asset_lifecycle_states] RETIRED from init_db().")

    conn = get_connection()
    try:
        print("  counts before:")
        for t in ("job_artifacts", "audio_assets", "voice_models", "material_assets"):
            c = count_table(conn, t)
            print(f"    {t}={c}")

        if do_run:
            print("[verify_backfill_asset_lifecycle_states] EXECUTING (via delegate)...")
            # direct public also available; use the retired wrapper for parity
            stats = backfill_lifecycle_states(conn)
            conn.commit()
            print(f"  stats from backfill: {stats}")
            print("  counts after (re-query):")
            for t in ("job_artifacts", "audio_assets", "voice_models", "material_assets"):
                c = count_table(conn, t)
                print(f"    {t}={c}")
            print("[verify_backfill_asset_lifecycle_states] Done. (uses should_backfill heuristic; safe re-run)")
        else:
            print("DRY-RUN. --run to apply lifecycle inference backfill.")
            # Optionally show what would change by calling with dry? but the func mutates; we skip to be pure.
            print("  (To preview impact, temporarily use the public backfill_lifecycle_states in a test DB copy.)")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
