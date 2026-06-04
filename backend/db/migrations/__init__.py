"""
backend.db.migrations

Schema migration files for FeiShark DB Governance Phase 2B+.

- Use ordered 00NN_name.sql for DDL (preferred for pure schema).
- .py supported for data/complex but governance prefers .sql + repositories later.
- Applied idempotently by backend.db.apply_migrations (called from init_db).
- Checksummed in schema_migrations table for integrity.
- Never edit applied migrations; add new numbered file only.

See stage60-db-governance-plan.md
"""
# This makes the dir importable as package if/when db.py is split to package in future phases.
