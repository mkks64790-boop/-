#!/usr/bin/env python
"""
One-time verifier / runner for retired _backfill_extended_job_fields.

Phase 4: Backfill Retirement and Legacy Cleanup.

This backfill historically did blanket UPDATEs on jobs for post-migrate columns.
Retired from every-startup.

Usage:
  python -X utf8 scripts/verify_backfill_extended_job_fields.py --dry-run
  python -X utf8 scripts/verify_backfill_extended_job_fields.py --run

Defaults safe verify. --run will execute (unconditional UPDATE for defaults).
See db.py for RETIRED header + inventory report for docs.
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
    from backend.db import get_connection, _backfill_extended_job_fields, DB_PATH
except ImportError:
    from db import get_connection, _backfill_extended_job_fields, DB_PATH  # type: ignore


def count_jobs(conn) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
        return int(row["c"]) if row else 0
    except Exception:
        return 0


def count_jobs_needing_backfill(conn) -> int:
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c FROM jobs
            WHERE COALESCE(job_kind, '') = ''
               OR COALESCE(track_id, '') = ''
               OR COALESCE(resource_class, '') = ''
               OR COALESCE(depends_on_json, '') = ''
            """
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

    print(f"[verify_backfill_extended_job_fields] DB_PATH={DB_PATH}")
    print("[verify_backfill_extended_job_fields] RETIRED from init_db() -- one-time only.")

    conn = get_connection()
    try:
        before_jobs = count_jobs(conn)
        before_needing = count_jobs_needing_backfill(conn)
        print(f"  before: jobs={before_jobs}, rows_needing_fill={before_needing}")

        if do_run:
            print("[verify_backfill_extended_job_fields] EXECUTING retired blanket update...")
            _backfill_extended_job_fields(conn)
            conn.commit()
            after_jobs = count_jobs(conn)
            after_needing = count_jobs_needing_backfill(conn)
            print(f"  after:  jobs={after_jobs}, rows_needing_fill={after_needing}")
            print("[verify_backfill_extended_job_fields] Done.")
        else:
            print("[verify_backfill_extended_job_fields] DRY-RUN/VERIFY. Use --run to apply.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
