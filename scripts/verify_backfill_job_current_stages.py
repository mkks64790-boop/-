#!/usr/bin/env python
"""
One-time verifier / runner for retired _backfill_job_current_stages.

Phase 4: Backfill Retirement and Legacy Cleanup.

Inferred missing current_stage from logs or status heuristics. Per-row + subquery, retired from startup.

Usage:
  python -X utf8 scripts/verify_backfill_job_current_stages.py --dry-run
  python -X utf8 scripts/verify_backfill_job_current_stages.py --run
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
    from backend.db import get_connection, _backfill_job_current_stages, DB_PATH
except ImportError:
    from db import get_connection, _backfill_job_current_stages, DB_PATH  # type: ignore


def count_jobs(conn) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
        return int(row["c"]) if row else 0
    except Exception:
        return 0


def count_jobs_missing_stage(conn) -> int:
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE COALESCE(current_stage, '') = ''"
        ).fetchone()
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

    print(f"[verify_backfill_job_current_stages] DB_PATH={DB_PATH}")
    print("[verify_backfill_job_current_stages] RETIRED from init_db() -- one-time only (was heavy).")

    conn = get_connection()
    try:
        before_jobs = count_jobs(conn)
        before_missing = count_jobs_missing_stage(conn)
        print(f"  before: jobs={before_jobs}, missing_current_stage={before_missing}")

        if do_run:
            print("[verify_backfill_job_current_stages] EXECUTING retired stage inference backfill...")
            _backfill_job_current_stages(conn)
            conn.commit()
            after_missing = count_jobs_missing_stage(conn)
            print(f"  after:  jobs={before_jobs}, missing_current_stage={after_missing}")
            filled = max(0, before_missing - after_missing)
            print(f"  estimate_filled={filled}")
            print("[verify_backfill_job_current_stages] Done.")
        else:
            print("DRY-RUN. --run to apply inference (may query job_stage_logs per row).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
