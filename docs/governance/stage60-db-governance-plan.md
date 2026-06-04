# Stage60 DB Governance Plan

Status: Draft for Governance Sprint
Date: 2026-06-04
Scope: planning only

## Problem

`backend/db.py` is doing too much:

- schema creation
- startup migrations
- legacy backfills
- direct CRUD helpers
- compatibility mirrors between `tasks` and `jobs`
- compatibility mirrors between `voice_assets` and `voice_models`
- cleanup and recovery helpers

This makes every future feature risky because startup side effects and data model
compatibility logic live in one large file.

## Hard Rule

No new large `_migrate_*`, `_backfill_*`, or long `executescript` blocks may be
added to `backend/db.py`.

Small bug fixes are allowed. New schema evolution must go through a migration or
repository abstraction plan.

## Target Architecture

### `backend/db/connection.py`

Owns only:

- database path resolution
- connection creation
- row factory
- pragma setup

### `backend/db/schema.py`

Owns only:

- current create-table DDL
- schema version table
- schema snapshot helpers

### `backend/db/migrations/`

Owns:

- ordered migration files
- idempotent migration application
- migration history table

Initial migration table:

- `schema_migrations(id TEXT PRIMARY KEY, applied_at TEXT, checksum TEXT)`

### `backend/repositories/`

Owns data access for:

- `JobRepository`
- `VoiceModelRepository`
- `ArtifactRepository`
- `TrackRepository`
- `MaterialRepository`

Services should depend on repositories, not call `get_connection()` directly.

## Current Hotspots

High-priority cleanup targets:

- `backend/db.py` startup backfills around legacy jobs/models/lifecycle
- direct `get_connection()` usage in `backend/main.py`
- direct legacy `tasks` reads in `pitch_processor.py`, `audio_mixer.py`, `voice_changer.py`, `vocal_separator.py`
- model dual-write code in `backend/db.py` and `backend/services/model_service.py`
- job direct SQL in `backend/services/job_service.py`

## Migration Plan

### Phase 1: Freeze and Measure

- Add no new DB features.
- Create a DB access inventory report.
- Count direct `get_connection()` call sites.
- Count direct `tasks` and `voice_assets` references.
- Define repository boundaries.

### Phase 2: Introduce Schema Versioning

- Add `schema_migrations`.
- Move only new future migrations into ordered files.
- Keep old startup migrations working until retired.

### Phase 3: Repository Facades

- Create repositories as thin wrappers over existing SQL.
- Migrate service call sites one domain at a time.
- Do not change table shape in this phase.

### Phase 4: Backfill Retirement

- Move historical backfills out of startup. **COMPLETED** (Phase 4 sub-agent).
- Add explicit verifier scripts for one-time backfills. **DONE** (5 scripts in scripts/verify_backfill_*.py).
- Startup must not perform unbounded data rewrites. **ACHIEVED** (init_db now minimal).

## Acceptance Criteria

- New database changes no longer require editing the middle of `backend/db.py`.
- New service code does not call `get_connection()` directly unless an ADR allows it.
- Startup time and backfill side effects are measurable.
- Legacy mirrors have a documented retirement path.

## Immediate Stage60 Deliverable

Produce a first implementation prompt for `Stage60A DB Access Inventory`, not a
schema rewrite. The first code stage should be measurement and facade design.
