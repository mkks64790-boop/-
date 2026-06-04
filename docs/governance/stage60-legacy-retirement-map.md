# Stage60 Legacy Retirement Map

Status: Draft for Governance Sprint
Date: 2026-06-04
Scope: planning only

## Goal

Retire legacy dual paths without breaking current local projects.

Legacy support is allowed only as a temporary compatibility layer with a measured
exit path.

## Canonical Tables

Canonical read/write paths:

- `jobs`
- `voice_models`
- `job_artifacts`
- `job_stage_logs`
- `audio_assets`
- `tracks`
- `material_assets`

Legacy paths:

- `tasks`
- `voice_assets`
- `shared_data/outputs/{task_id}` as primary output discovery

## Retirement Timeline

### Stage60: Inventory and Freeze

- No new feature may write new legacy-only data.
- Existing dual-write code remains for compatibility.
- Add inventory docs and migration script plan.
- Add tests proving canonical reads still work when legacy rows are absent.

### Stage61: Read-Through Compatibility

- Canonical tables become primary.
- Legacy tables are read only as fallback.
- Add warnings or metadata flags when fallback was used.
- New UI/API flows must not depend on legacy-only rows.

### Stage62: Migration Tooling

- Create explicit migration scripts:
  - `backend/scripts/migrate_tasks_to_jobs.py`
  - `backend/scripts/migrate_voice_assets_to_voice_models.py`
  - `backend/scripts/verify_legacy_retirement_readiness.py`
- Scripts must support dry-run and report mode.
- No destructive deletes in the first migration pass.

### Stage63: Disable New Legacy Writes

- Remove or guard new writes to `tasks` and `voice_assets`.
- Keep read fallback for existing local data.
- Add tests that new jobs/models can be created without legacy mirror writes.

### Stage64: Archive Legacy Tables

- Stop default UI/API exposure of legacy-only rows.
- Keep manual recovery tooling.
- Actual table deletion requires a separate ADR and user approval.

## Migration Script Requirements

All migration scripts must:

- support `--dry-run`
- support `--report <path>`
- avoid destructive deletes by default
- print row counts before and after
- report unresolved conflicts
- never copy raw audio/model files into git-tracked docs

## Current Known Compatibility Hotspots

- `backend/db.py` creates and writes both `tasks` and `jobs`.
- `backend/db.py` creates and writes both `voice_assets` and `voice_models`.
- `backend/main.py` still reads `tasks` in at least one compatibility path.
- older runtime modules still query `tasks` directly:
  - `pitch_processor.py`
  - `audio_mixer.py`
  - `voice_changer.py`
  - `vocal_separator.py`
- `model_service.py` still mirrors `voice_assets`.

## Stop Conditions

Do not disable legacy writes until:

- current user data has a dry-run migration report
- training and cover job creation works from canonical tables only
- model import/rescan works from canonical `voice_models`
- rollback path is documented

## First Executable Task

`Stage60C: legacy access inventory and canonical-read tests`

No deletion. No schema rewrite. Measurement and compatibility tests only.
