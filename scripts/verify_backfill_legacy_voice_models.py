#!/usr/bin/env python
"""
One-time verifier / runner for retired _backfill_legacy_voice_models.

Phase 4: Backfill Retirement and Legacy Cleanup.

Populated voice_models from legacy voice_assets. Now one-time only.

Usage:
  python -X utf8 scripts/verify_backfill_legacy_voice_models.py --dry-run
  python -X utf8 scripts/verify_backfill_legacy_voice_models.py --run
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
    from backend.db import get_connection, _backfill_legacy_voice_models, DB_PATH
except ImportError:
    from db import get_connection, _backfill_legacy_voice_models, DB_PATH  # type: ignore


def count_voice_assets(conn) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM voice_assets").fetchone()
        return int(row["c"]) if row else 0
    except Exception:
        return 0


def count_voice_models(conn) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM voice_models").fetchone()
        return int(row["c"]) if row else 0
    except Exception:
        return 0


def count_voice_models_with_legacy(conn) -> int:
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM voice_models WHERE legacy_model_id IS NOT NULL AND legacy_model_id != ''"
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

    print(f"[verify_backfill_legacy_voice_models] DB_PATH={DB_PATH}")
    print("[verify_backfill_legacy_voice_models] RETIRED from init_db().")

    conn = get_connection()
    try:
        before_assets = count_voice_assets(conn)
        before_models = count_voice_models(conn)
        before_legacy = count_voice_models_with_legacy(conn)
        print(f"  before: voice_assets={before_assets}, voice_models={before_models}, with_legacy={before_legacy}")

        if do_run:
            print("[verify_backfill_legacy_voice_models] EXECUTING retired backfill (INSERT OR IGNORE)...")
            _backfill_legacy_voice_models(conn)
            conn.commit()
            after_models = count_voice_models(conn)
            after_legacy = count_voice_models_with_legacy(conn)
            added = max(0, after_legacy - before_legacy)
            print(f"  after:  voice_models={after_models}, with_legacy={after_legacy}")
            print(f"  estimate_added={added}")
            print("[verify_backfill_legacy_voice_models] Done.")
        else:
            print("DRY-RUN. --run to execute.")
        if before_assets > 0 and before_legacy == 0:
            print("NOTE: assets present without voice_models mirrors; consider --run.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
