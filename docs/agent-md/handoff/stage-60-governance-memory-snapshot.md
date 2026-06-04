# Stage60 Governance Memory Snapshot for Grok

Project root: `D:\FeiSharkStudio-v2`

Use this file as the first handoff before any next Grok task.

## Current Mode

The project is now in **Stage60 Governance Sprint**.

This is governance-only:

- Do not implement new user-facing features.
- Do not continue C-4c.
- Do not run or enable real UVR/RVC/GPU/ffmpeg workloads.
- Do not create new `stage59_*` or `stage60_*` service files.
- Do not use `git add .`.

## Product North Star

FeiShark Studio is a local AI music workstation:

- One-click AI cover: source song -> UVR separation -> RVC voice conversion -> mix output.
- Single long-file training: one 30-50 minute clean vocal -> native RVC preprocessing -> feature extraction -> training.
- Multi-file training: already cleaned short clips -> skip slicing -> feature extraction -> training.
- Studio page later supports review, versions, and post-processing.

The product is not a remote web wrapper.

## Current Technical Baseline

Canonical backend paths:

- `jobs`
- `voice_models`
- `job_artifacts`
- `job_stage_logs`

Legacy paths to retire:

- `tasks -> jobs`
- `voice_assets -> voice_models`
- `shared_data/outputs/{task_id}` as primary discovery

Stage59C-4b already exists as a safety gate:

- real-smoke plan only
- file-backed artifact promotion planning
- `real_execute_allowed=false`
- `/execute` remains blocked
- full regression previously passed: `282 passed, 2 warnings`

## Mandatory Reading Order

1. `docs/ARCHITECTURE_CONSTITUTION.md`
2. `docs/adr/0001-stage60-governance-sprint-and-process-upgrade.md`
3. `docs/adr/0002-stage60-debt-audit-stage59-db-legacy.md`
4. `docs/adr/0003-stage59-consolidation-proposal.md`
5. `docs/governance/stage60-stage59-service-consolidation-plan.md`
6. `docs/governance/stage60-db-governance-plan.md`
7. `docs/governance/stage60-main-router-split-plan.md`
8. `docs/governance/stage60-legacy-retirement-map.md`
9. `docs/agent-md/architect/governance-reviewer-prompt.md`
10. `docs/agent-md/worker/worker-report-template.md`

## Governance Rules

- Governance over features.
- Human is final governance owner.
- Cross-cutting changes touching more than 3 core files require ADR first.
- Every worker report must include:
  - `Debt Delta`
  - `Invariant Violations`
  - `Simplification Opportunities`
- No new milestone-named services.
- No real UVR/RVC/GPU without explicit human approval and a separate ADR.

## Confirmed Consolidation Direction

Stage59 service sprawl must be consolidated.

Target services:

- `execution_safety_service`
  - guards
  - policy
  - approval
  - audit

- `artifact_lifecycle_service`
  - persistence contract
  - transient records
  - promotion plan
  - listening contract
  - smoke-plan artifact contract

Keep and reuse:

- `short_chain_manifest_service.py`
- `short_chain_uvr_service.py`

Old `stage59_*` files:

- first become thin delegate wrappers
- then all imports migrate to the new services
- then old wrappers are deleted after tests pass

## API Direction

Preferred new API path:

- `/api/short-chain/uvr-ab/...`

Old path:

- `/api/stage59/short-chain/uvr-ab/...`

Human confirmation still needed:

- keep old path as deprecated alias for one cycle, or remove immediately?

## Next Recommended Task

Start `Stage60A: dependency inventory and facade boundary review`.

Do not write feature code in Stage60A. The first task should output:

- dependency graph of Stage59 modules
- interface freeze list
- proposed facade boundaries
- exact tests required before any import migration
- worker report using `worker-report-template.md`

## Current Workspace Caution

The working tree contains both:

- Stage59C-4b source/tests/docs from the previous safety-gate stage
- Stage60 governance docs/templates

Do not accidentally commit ignored runtime files:

- `backend/feishark.db`
- `shared_data/`

Do not stage raw audio/model/DB assets.

## Post-Stage60C / During Stage60D Current State (Recovered via Strict Review + Multi-Plan Work)

**Shim removal (Stage60C) status (strictly reviewed + fixes applied):**
- All public callers (main.py routes/services, verify CLI, tests) migrated to durable facades: `short_chain_service`, `execution_safety_service`, `artifact_lifecycle_service`, `uvr_smoke_service`.
- Legacy `stage59_*_service.py` (10 files): all carry "Legacy thin shim / shim/impl holder" headers directing to facades.
- Execution safety group (approval_audit, execution_guard, execution_policy): **fully inlined** into `execution_safety_service.py`. Old 3 files are now small pure reexports. Facade owns the code.
- Artifact lifecycle + UVR smoke groups: delegation via facade reexports from (headered) legacy impl files. Internal cross-imports among legacy files cleaned to always prefer facades (0 remaining direct stage59-to-stage59 after final review fixes).
- Facade tests (`test_stage60b_facades.py`), C4b smoke plan tests, identity "is" checks, and `verify_stage59_uvr_ab.py --real-smoke-plan` all green. Governance hard guards (`real_execute_allowed=false`, `audio_files_written=false`) intact.
- Bundling for training infra (primary RVC + 秋风RVC backup on 7865 + AudioPipeline): complete in code (engine_paths.py prioritizes `external/`, feishark-launcher.ps1 dual launch, voice_changer supports origin="backup" or "秋风" in name + root= sync, engine_manager lists both). `external/` dirs + `scripts/setup_training_engines.ps1` + .gitignore rules present. User action required to copy complete engines (per "准备好了素材" + "秋风rvc作为备用" + "整合完整的进入工作区").
- No new milestone-named services. No real UVR/RVC. Behavior 100% identical for existing paths.

**Parallel Stage60D DB Governance (started by other plan, per git):**
- Commits include "Stage60D DB Governance: parallel ABCD complete (A restructure, B migrations, C repos+2services, D backfill retirement+verifiers)", "Stage60D: DB Governance Phase 1 - access inventory report + initial thin repositories stubs (Job, VoiceModel)".
- Work on `backend/db.py`, thin repos, backfill retirement in progress (uncommitted at some handoffs).
- Align with `docs/governance/stage60-db-governance-plan.md`.

**Memory for next agent/GPT:**
- Use this snapshot + the full `docs/agent-md/worker/stage-60c-shim-removal-report.md` (contains 4-section + Debt Delta + Invariants + Simplification + what "this agent" vs "other plan" each did + review fixes) as primary handoff.
- Current mode remains governance-only. "不能贪快". Human final owner.
- Next focus likely: finish/declare Stage60C (more inlining + legacy delete vs accept current state), complete DB governance, populate external/ + validate training with prepared materials + 秋风 backup, then decide feature sprint only after governance sign-off + new ADR.

**Key files changed in Stage60C window (recovered):**
- Facades: backend/services/{short_chain,execution_safety,artifact_lifecycle,uvr_smoke}_service.py (reexports + one full inlining).
- Legacy: all 10 backend/services/stage59_*_service.py (headers + selective pure shims).
- Callers: backend/main.py, backend/verify_stage59_uvr_ab.py, tests/*stage59c* + test_stage60b*, engine paths/voice_changer/launcher for bundling.
- Reports: docs/agent-md/worker/stage-60c-shim-removal-report.md (this reviewed version), related handoff/architect prompts.

Re-read the full reviewed report before any next action.
