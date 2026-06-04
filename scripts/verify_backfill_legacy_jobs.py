#!/usr/bin/env python
"""
One-time verifier / runner for retired _backfill_legacy_jobs.

Phase 4: Backfill Retirement and Legacy Cleanup.

This backfill historically populated the canonical `jobs` table from legacy `tasks`
on every startup. It is now retired from init_db().

Usage (from project root):
  python -X utf8 scripts/verify_backfill_legacy_jobs.py --dry-run
  python -X utf8 scripts/verify_backfill_legacy_jobs.py --run
  python -X utf8 scripts/verify_backfill_legacy_jobs.py --report

Defaults to --dry-run (verify only, no writes).
Supports --run to actually execute the retired backfill (safe: INSERT OR IGNORE).
Prints before/after counts, affected estimate.

Must not lose data: only adds missing mirrors; existing canonical rows untouched.
For old installs that predate jobs canonical table.

See:
- backend/db.py : _backfill_legacy_jobs (now with RETIRED docstring)
- docs/agent-md/worker/stage-60d-db-access-inventory-report.md (Phase 4 section)
- docs/governance/stage60-legacy-retirement-map.md
"""
from __future__ import annotations

import argparse
import os
import sys

# Support running from project root or backend/ (compat with dual import style in codebase)
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from backend.db import get_connection, _backfill_legacy_jobs, DB_PATH
except ImportError:
    from db import get_connection, _backfill_legacy_jobs, DB_PATH  # type: ignore


def count_tasks(conn) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()
        return int(row["c"]) if row else 0
    except Exception:
        return 0


def count_jobs(conn) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
        return int(row["c"]) if row else 0
    except Exception:
        return 0


def count_jobs_with_legacy(conn) -> int:
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE legacy_task_id IS NOT NULL AND legacy_task_id != ''"
        ).fetchone()
        return int(row["c"]) if row else 0
    except Exception:
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify / one-time run retired legacy_jobs backfill.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Default: verify only (no DB write).")
    parser.add_argument("--run", action="store_true", help="Actually execute the backfill (idempotent).")
    parser.add_argument("--report", action="store_true", help="Only print counts and exit (implies dry).")
    args = parser.parse_args(argv)

    do_run = args.run and not args.report
    if do_run:
        args.dry_run = False

    print(f"[verify_backfill_legacy_jobs] DB_PATH={DB_PATH}")
    print("[verify_backfill_legacy_jobs] RETIRED from init_db() -- one-time use only.")

    conn = get_connection()
    try:
        before_tasks = count_tasks(conn)
        before_jobs = count_jobs(conn)
        before_legacy = count_jobs_with_legacy(conn)

        print(f"  before: tasks={before_tasks}, jobs={before_jobs}, jobs_with_legacy={before_legacy}")

        if do_run:
            print("[verify_backfill_legacy_jobs] EXECUTING retired backfill (INSERT OR IGNORE from tasks)...")
            _backfill_legacy_jobs(conn)
            conn.commit()
            after_tasks = count_tasks(conn)
            after_jobs = count_jobs(conn)
            after_legacy = count_jobs_with_legacy(conn)
            added_estimate = max(0, after_legacy - before_legacy)
            print(f"  after:  tasks={after_tasks}, jobs={after_jobs}, jobs_with_legacy={after_legacy}")
            print(f"  estimate_added_legacy_mirrors={added_estimate}")
            print("[verify_backfill_legacy_jobs] Done. (idempotent; re-runnable safely)")
        else:
            print("[verify_backfill_legacy_jobs] DRY-RUN / VERIFY only. No changes.")
            print("  To execute: add --run (after reviewing report)")

        # Simple health: if tasks > 0 but legacy mirrors ==0 , suggest run
        if before_tasks > 0 and before_legacy == 0:
            print("[verify_backfill_legacy_jobs] NOTE: legacy tasks exist with no mirrored jobs. Consider --run on this DB.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
