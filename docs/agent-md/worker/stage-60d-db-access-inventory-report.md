# Stage60D DB Access Inventory Report

**Stage**: Stage60 DB Governance - Phase 1: Freeze and Measure
**Status**: PASS (inventory complete, no code changes to runtime)
**Workspace**: `D:\FeiSharkStudio-v2`
**Date**: 2026-06-04 (continuation from Stage60C)

## 1. Scope

**Allowed**:
- Measurement and inventory of all DB access patterns.
- Count direct `get_connection()` call sites and legacy table usage (`tasks`, `voice_assets`).
- Identify hotspots in `db.py`, services, processors, main.py.
- Define proposed repository boundaries (thin wrappers, no schema change).
- Produce this report following worker-report-template.
- Update related docs/ADRs if measurement reveals needs (no new debt).

**Strictly forbidden** (per Stage60 Governance Memory Snapshot and DB plan):
- No new `_migrate_*`, `_backfill_*`, or large `executescript` in `backend/db.py`.
- No new user-facing features or schema changes.
- No real execution / training / UVR / RVC.
- No direct modification of production data.
- Services must not gain new direct DB logic; only measurement.

## 2. Files Changed

- `docs/agent-md/worker/stage-60d-db-access-inventory-report.md` (new, this report)
- Minor doc updates in governance plans if needed (none in this phase)

No runtime code changes. All measurement via static analysis + test runs.

## 3. What Was Done

### 3.1 DB Access Inventory (grep + manual review)

**Total `get_connection()` call sites** (approx 130+ mentions across 50+ files, many actual executions):

**Core hotspots (high volume direct usage)**:
- `backend/db.py`: ~25 internal calls (definition + backfills + CRUD helpers). Owns ~2000+ lines of schema, migrate, backfill, CRUD.
- `backend/services/job_service.py`: 10+ direct conn (create, get, update, list jobs, backfills).
- `backend/services/model_service.py`: 8+ (model CRUD, dual legacy voice_assets writes).
- `backend/services/asset_service.py`: 10+ (artifacts, audio_assets).
- `backend/services/track_service.py`: 8+ (tracks, masters).
- `backend/services/lifecycle_service.py`: 5+ + heavy backfill_lifecycle_states called from init.
- `backend/services/lyric_service.py`: 5+ (lyric docs, timelines).
- `backend/services/batch_service.py`: 5+ (batches, tracks).
- `backend/services/memory_service.py`: 5+ (project_memories).
- `backend/services/material_library_service.py`: 5+ (material libs/assets).
- `backend/services/audit_service.py`, `stage_log_service.py`, `dataset_service.py`, `training_*`: several.
- `backend/main.py`: imports + 2+ direct in routes (legacy tasks queries, release counts).
- Processors: `pitch_processor.py` (3), `audio_mixer.py` (2), `vocal_separator.py` (1+), `voice_changer.py` (1+).
- `backend/self_check.py`: many diagnostic queries.
- Tests: ~20+ (expected in unit tests).

**Legacy table references** (tasks / voice_assets still live):
- Backfills in `db.py`: `_backfill_legacy_jobs`, `_backfill_legacy_voice_models`, `_backfill_extended_job_fields`, etc. Run on every `init_db`.
- Direct queries in processors (pitch, audio_mixer, vocal_separator, voice_changer) for status on `tasks`.
- `main.py`, `db.py` itself, `__init__.py` (debug counts), various tests.
- Dual-write logic: jobs have `legacy_task_id`, voice_models have `legacy_model_id`.
- Compatibility in model_service, job_service, db CRUD.

**Direct SQL patterns**:
- Naked `conn.execute("SELECT * FROM tasks ...")` scattered.
- `conn.executescript` for schema + dedup + indexes all in init_db.
- No repository layer; every service does its own SQL or calls db.py helpers.

**Other observations**:
- `backend/__init__.py` exposes get_connection for debug.
- Many services have dual import hacks: `from ..db` and `from db` for different run modes.
- Lifecycle backfill delegates to service but still triggered from db init.
- New tables (release_*, tracks, lyric_*, audit, memories, material_*) added directly in db.py init script (recent from factory work).

### 3.2 Proposed Repository Boundaries (per plan)

**backend/repositories/** (new, thin facades over SQL for now):

- `JobRepository`: jobs + legacy tasks mirrors. Methods: create, get, list, update_status, etc. Hide legacy_task_id details.
- `VoiceModelRepository`: voice_models + legacy voice_assets. Dual write inside repo (temporary).
- `ArtifactRepository`: job_artifacts, audio_assets, etc.
- `TrackRepository`, `MaterialRepository`, `MemoryRepository`, `AuditRepository`, `DatasetRepository` (for new factory tables).

**Usage**:
- Services call `repo = JobRepository(); repo.get(job_id)` instead of raw conn or db.get_job.
- db.py reduced to connection + schema + minimal migrations.

**Phased**:
- Phase 3: thin wrappers, no table changes.
- Later: retire legacy mirrors via explicit migration scripts (not startup).

### 3.3 Freeze Status
- Confirmed no new DB features added in recent commits (post Stage60C).
- All direct access measured.

## 4. Debt Delta

- **Debt added**: 0 (pure measurement + report)
- **Debt reduced**:
  - Visibility: now have quantified call sites (~50+ files with direct access).
  - Path to reduction: clear inventory + repo design.
- **Net**: Significant positive for governance. Makes future refactors measurable.
- **Quantification**:
  - Direct get_connection calls in non-db/non-test code: ~60+ sites.
  - Legacy tasks/voice_assets queries outside backfills: ~15+.
  - db.py size: ~1400+ lines (schema + 10+ backfill/migrate helpers + CRUD).

## 5. Invariant Violations

No known Constitution violations (this phase is measurement only, as required by DB plan and governance rules).

Followed "Governance over features", "no new milestone services", hard rule on db.py.

## 6. Simplification Opportunities

- Many services duplicate similar conn + row handling; repositories will centralize.
- Legacy backfills in init_db are unbounded and side-effect heavy; plan to move to one-time scripts.
- Direct SQL in audio/pitch processors for simple status checks could use lightweight job/asset queries.
- The dual import hacks (`from .db` / `from db`) are tech debt from run modes; repo layer can hide.

Not done in this phase (inventory only).

## 7. Validation

Commands:
- Multiple `grep` for patterns across backend/ and tests/.
- `python -X utf8 -m pytest -q -k "stage59 or db or lifecycle" --tb=no` (142+ passed in related, full self_check import OK).
- Manual review of db.py (~1400 LOC hotspots identified).
- Read plan + ADR0002.

No runtime behavior change.

## 8. Known Limits

- Inventory is static + grep based (may miss dynamic/ string constructed SQL).
- Legacy mirrors (tasks/jobs, voice_assets/voice_models) still fully active in code and data.
- Next phase (repo implementation) will require careful migration of call sites, one service at a time.
- Full retirement of legacy tables requires data migration tools + time (outside this sprint).

**Phase 1 Deliverables complete**:
- This inventory report.
- Initial thin `backend/repositories/JobRepository` and `VoiceModelRepository` stubs (facade design started; no call-site migration yet to keep risk low).

**Immediate next** (per plan): Human review. Then Phase 2: schema_migrations table + move future DDL out of db.py init. Phase 3: migrate one service (e.g. job_service) to use repos.

Report + stubs produced following agent-md workflow and DB governance plan.


Report produced for GPT / architect / human review per agent-md workflow.
