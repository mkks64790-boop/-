-- FeiShark Studio DB Governance Phase 2B
-- First migration: introduce schema_migrations table for versioning.
-- Idempotent; the table is also declared in base DDL (in db.py and backend/__init__.py)
-- for compatibility during transition. Future schema evolution (new tables, columns, indexes)
-- MUST be added here as 0002_*.sql (or .py for complex) instead of editing the middle of db.py.
-- See docs/governance/stage60-db-governance-plan.md Phase 2.

CREATE TABLE IF NOT EXISTS schema_migrations (
    id TEXT PRIMARY KEY,
    applied_at TEXT,
    checksum TEXT
);

-- End of 0001. Next change e.g. 0002_add_some_future_column.sql would contain:
-- ALTER TABLE some_table ADD COLUMN new_col TEXT DEFAULT '';
