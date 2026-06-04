# Stage60A: Dependency Inventory and Facade Boundary Review (Governance Only - No New Features)

**Project root**: `D:\FeiSharkStudio-v2`

**Critical**: This is **Stage60A**, the first execution phase after the governance sprint and bugfix. **Strictly governance-only**. Do not implement new user-facing features, do not run real UVR/RVC/GPU workloads, do not create new milestone-named services.

## First Action (Mandatory - Memory Snapshot is the Source of Truth)
**Before reading anything else, read this file as the primary handoff**:
- `docs/agent-md/handoff/stage-60-governance-memory-snapshot.md`

This snapshot defines the current mode, rules, consolidation targets (execution_safety_service, artifact_lifecycle_service, etc.), API direction (/api/short-chain/...), and explicitly sets the goal for this Stage60A.

After the memory snapshot, read:
- `docs/agent-md/handoff/stage-60a-dependency-inventory-handoff.md` (this task's handoff)
- This architect prompt
- The full set of required reading below

**You must declare at the top of your worker report**: "I read the Stage60 Governance Memory Snapshot first, followed by [list all required files]. This work strictly follows the Constitution and governance mode."

## Required Reading (Read in This Order)
1. `docs/agent-md/handoff/stage-60-governance-memory-snapshot.md` (PRIMARY - do this first)
2. `docs/ARCHITECTURE_CONSTITUTION.md`
3. `docs/adr/0001-stage60-governance-sprint-and-process-upgrade.md`
4. `docs/adr/0002-stage60-debt-audit-stage59-db-legacy.md`
5. `docs/adr/0003-stage59-consolidation-proposal.md`
6. `docs/governance/stage60-stage59-service-consolidation-plan.md`
7. `docs/governance/stage60-db-governance-plan.md`
8. `docs/governance/stage60-main-router-split-plan.md`
9. `docs/governance/stage60-legacy-retirement-map.md`
10. `docs/governance/stage60-training-engine-bundling-plan.md` (user requirement: integrate complete RVC-WebUI (main + 秋风RVC backup) + AudioPipeline into workspace/external/ for stable training with prepared materials)
11. `docs/agent-md/worker/stage-60-governance-sprint-report.md`
12. `docs/agent-md/worker/stage-60-governance-review.md`
13. `docs/agent-md/worker/stage-60-bugfix-small-debt-fixes-report.md` (and its review)
14. `docs/agent-md/worker/worker-report-template.md`
15. `docs/agent-md/architect/prompt-template.md`
16. Current key files for inventory: `backend/main.py`, `backend/services/` (all stage59_* + related), `backend/voice_changer.py`, `backend/vocal_separator.py`, `backend/model_trainer.py`, `backend/services/engine_manager_service.py`, `feishark-launcher.ps1`, existing tests for Stage59.

## Stage Boundary (Hard - Governance Only)
- **Only** perform read-only dependency inventory, analysis, and proposal work.
- **Do not** write new feature code, do not enable real UVR/RVC execution, do not modify production behavior.
- **Do not** create new `stage59_*` or `stage60_*` service files.
- **Do not** make changes to `backend/db.py` (migrations/backfills).
- **Do not** expand `main.py` with new logic.
- **Do not** run any real engines or training on user's prepared materials yet (use dry/mock where possible for analysis).
- The goal is **inventory and proposal only** to enable safe facade introduction in follow-up work (Stage60B etc.).

Current working tree still contains pre-existing Stage59C-4b code + Stage60 governance artifacts + recent bundling prep changes. Do not revert them; analyze the current state.

## Goal
Execute the exact recommendation from the memory snapshot:

"Start `Stage60A: dependency inventory and facade boundary review`.

The first task should output:
- dependency graph of Stage59 modules
- interface freeze list
- proposed facade boundaries
- exact tests required before any import migration
- worker report using `worker-report-template.md`"

**Additionally incorporate** the user's concrete requirement (from conversation): Support bundling complete RVC-WebUI (primary + 秋风RVC as backup, enabled in studio) + AudioPipeline into the workspace under `external/` for self-contained, stable training (no fragile external D:\ deploys, protects prepared materials in shared_data/, launcher integration).

## Required Deliverables
Produce a complete **worker report** at:
`docs/agent-md/worker/stage-60a-dependency-inventory-facade-boundary-review-report.md`

The report **must** use the template and include all required sections (especially Debt Delta, Invariant Violations, Simplification Opportunities).

In addition to the memory snapshot requirements, the report + any supporting artifacts must deliver:

### 1. Dependency Graph of Stage59 Modules
- Create (or update) a clear graph (textual + suggested diagram format, e.g. Mermaid or simple list) of:
  - All current `stage59_*_service.py` and related (approval_audit, artifact_persistence, execution_guard, execution_policy, job_artifact_promotion, listening_bridge, real_smoke_plan, transient_artifact, uvr_mock_execute, uvr_runner_contract, short_chain_manifest, short_chain_uvr, verify_stage59_uvr_ab, etc.).
  - Cross dependencies with core (job_service, asset_service, model_service, lifecycle_service, engine_manager_service, vocal_separator, voice_changer, model_trainer, main.py routes, track_service, preflight_service, etc.).
  - External engine dependencies (RVC-WebUI main + 秋风RVC backup, AudioPipeline/UVR).
  - Data flow for key paths: short-chain UVR A/B, cover, train (single long / multi clean), studio effects, material registration.
- Highlight tight coupling, circular risks, and "sacred" core (job execution, state machine).

### 2. Interface Freeze List
- For each major Stage59 module and related core, list the **current public interface** that must be frozen before any facade/migration:
  - Functions, classes, Pydantic models, API endpoints (especially /api/stage59/short-chain/uvr-ab/* and /api/train, /api/cover, model import).
  - Key contracts (artifact contracts, execution guards, lifecycle states, listening contracts, promotion rules).
- Explicitly call out interfaces involving RVC model loading (including backup 秋风RVC), UVR separation, path sandboxing for run-ids, approval tokens.

### 3. Proposed Facade Boundaries
- Propose the 4 durable abstractions from the consolidation plan, with concrete boundaries:
  1. `short_chain_service.py` (manifest, rights gate, eligibility, dry-run/plan shape) – absorb short_chain_manifest + short_chain_uvr.
  2. `execution_safety_service.py` (or execution_approval) – caps, policy, guard, approval, audit, sandbox preflight.
  3. `artifact_lifecycle_service.py` (or artifact_contract) – persistence contracts, transient, file-backed promotion (including C-4b real-smoke-plan), listening bridge, cleanup.
  4. `uvr_smoke_service.py` – mock + real-smoke-plan + future real runner adapter (keep real disabled by default).
- For the **RVC + AudioPipeline bundling** (user priority):
  - Propose how to integrate `external/rvc-webui` (main) + `external/rvc-webui-backup` (for 秋风RVC) + `external/audio-pipeline`.
  - Suggested: small `engine_paths.py` or updates in engine_manager_service + voice_changer + vocal_separator + model_trainer + launcher.
  - Make workspace-relative paths the new default (after env override).
  - Interface for "primary vs backup RVC" (e.g. model selection in studio, fallback bases in voice_changer).
  - Setup scripts and .gitignore updates as part of the boundary.
- Show proposed import structure (old stage59_* become thin delegates/facades during transition).
- Keep all existing behavior identical during inventory phase (no behavior change).

### 4. Exact Tests Required Before Any Import Migration
- List precise tests (existing + new) that must pass green before any code move:
  - All current Stage59C* unit + api tests.
  - Full pytest.
  - Self-check (note current RUNTIME_ENVIRONMENT limitations due to external RVC).
  - Specific contract tests: artifact persistence, execution guard, promotion paths, run-id sandboxing, real-smoke-plan CLI.
  - Engine scan / list_rvc_models / list_engines tests (including backup 秋风RVC).
  - Cover/train preflight + material routing (structure vs runtime separation).
  - Launcher smoke for main + backup RVC startup.
  - Any new tests for the bundling paths (e.g. external/ resolution, multiple RVC instances on 7866/7865).
- Recommend a "freeze gate": all listed tests must be passing + have coverage before Stage60B moves internals.

### 5. Worker Report
- Follow `worker-report-template.md` exactly.
- Include:
  - Scope (inventory + proposal only, explicit bundling for RVC main + 秋风 backup + AudioPipeline).
  - Files analyzed (list key ones read).
  - What was produced (the graph, freeze list, facade proposals, test list, bundling integration plan).
  - **Debt Delta**: quantify (e.g. "external engine debt now inventoried and proposed for elimination via bundling").
  - **Invariant Violations**: declare none (or minimal with explanation).
  - **Simplification Opportunities**: note any additional ones discovered during inventory.
  - Validation: run the commands below and include output.
  - Known Limits.
  - Next Recommended Step (e.g. Stage60B implementation of facades after human approval of this inventory).

## Validation Commands (Must Run and Record Full Output)
```powershell
cd D:\FeiSharkStudio-v2

# 1. Full regression (must stay green)
python -m pytest -q

# 2. Self check (note runtime limitations)
python -X utf8 backend\self_check.py

# 3. Stage59 specific (including C-4b touched areas)
python -m pytest tests/unit/test_stage59c* tests/api/test_stage59* -q --tb=short

# 4. Engine / RVC model scanning (must surface main + 秋风RVC backup)
python -c "
from backend.services.engine_manager_service import scan_engines, list_rvc_models
print(scan_engines('.', 'shared_data/weights', force=True))
print(list_rvc_models('.', 'shared_data/weights', limit=20, registered='all'))
"

# 5. Launcher / bundling path check (dry)
python -c "
import os
print('RVC_DIR candidates would prefer external now')
print('Check external/rvc-webui and backup dirs exist or not')
"

# 6. Asset scan (must be clean)
git ls-files | Select-String -Pattern '(\.wav|\.mp3|\.flac|\.m4a|\.aac|\.ogg|\.pth|\.index|\.sqlite|\.db)$' | Select-Object -First 5

# 7. Git status (show only analysis changes; do not stage)
git status --porcelain
git diff --stat
```

**Do not** actually start real RVC webui instances or run training on real materials during this inventory unless using completely dry/mock paths.

## How to Work (Extreme Honesty + Governance Discipline)
- Inventory first: actually read the source of all listed Stage59 modules + related core + engine files.
- For bundling: analyze current path resolution in voice_changer.py, model_trainer.py, vocal_separator.py, engine_manager_service.py, launcher.ps1, main.py model import.
- Propose concrete, minimal facade code structure (but **do not implement** the facades in this task – only propose + show example thin delegate).
- Document the "秋风RVC as backup" usage (how it is currently enabled in studio, which ports/instances, how model loading switches).
- Be explicit about risks of moving imports before tests freeze.
- If during inventory you discover something that should be a small bugfix instead, note it in Known Limits and recommend a follow-up tiny governance task (do not do it here).
- Output must be usable as input for a future Stage60B prompt.

## Report Location and Format
`docs/agent-md/worker/stage-60a-dependency-inventory-facade-boundary-review-report.md`

Must follow the worker-report-template exactly, with the governance sections.

After finishing, the report + any supporting files (graph as .md or .mmd, proposed facade example code snippets, updated test list) are the deliverables.

**Do not** `git add` or commit. Leave the tree for human review.

## Success Criteria for This Stage60A
- Memory snapshot requirements fully met.
- Clear, actionable dependency graph + freeze list + facade proposals (including explicit RVC main + 秋风 backup + AudioPipeline bundling into external/).
- Precise, runnable list of tests that form the "migration gate".
- Worker report is complete, honest, contains all required sections, and references the memory snapshot + bundling plan.
- No behavior change, no real execution, zero new milestone services.
- Full validation commands executed and results recorded.
- Report ends with concrete next step recommendation (likely "human approves inventory → Stage60B facade implementation prompt").

**Violations of this prompt or the memory snapshot will make the output invalid and require re-work.**

---

**Begin only after reading the memory snapshot first.**

Produce the report and supporting analysis. Good luck – this is the foundation for making training (with your prepared materials + 秋风RVC backup) stable inside the workspace.