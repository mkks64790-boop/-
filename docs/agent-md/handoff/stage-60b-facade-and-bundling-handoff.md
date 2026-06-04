# Stage60B: Facade Introduction + Engine Bundling Handoff

**Master memory snapshot is still the first thing to read.**

## 1. Master Memory Snapshot (READ FIRST)
`docs/agent-md/handoff/stage-60-governance-memory-snapshot.md`

## 2. This Task's Context
You just completed (or are reviewing) the Stage60A inventory report:
`docs/agent-md/worker/stage-60a-dependency-inventory-facade-boundary-review-report.md`

Plus its review:
`docs/agent-md/worker/stage-60a-review.md`

The inventory produced:
- Clear dependency graph
- Frozen interface list
- Proposed 4 durable facades (short_chain_service, execution_safety_service, artifact_lifecycle_service, uvr_smoke_service)
- Exact test freeze gate
- Detailed proposal for bundling complete RVC-WebUI (main on 7866) + 秋风RVC backup (on 7865) + AudioPipeline into `external/` inside the workspace

**User's concrete goal**: Make training stable and self-contained. User has prepared materials ready. Current external RVC/AudioPipeline setups (including the 秋风RVC model enabled as backup in studio) are uncertain/fragile. We want the complete engines living inside the project tree so nothing gets accidentally deleted and training is reliable.

## 3. Task Scope (Governance-Only, Bounded Implementation)
This is the first *implementation* step after pure inventory.

**Allowed**:
- Introduce the 4 durable facade modules as thin facades (old stage59_* modules become thin delegates or the facades delegate to old code during transition).
- Complete the workspace bundling for engines:
  - Make `external/rvc-webui` (primary/main) and `external/rvc-webui-backup` (for 秋风RVC) + `external/audio-pipeline` the preferred, complete, self-contained locations.
  - Update path resolution, launcher (start both instances reliably), engine_manager (expose backup as first-class), model metadata (origin primary vs backup), list_rvc_models, voice_changer (choose correct instance for backup models), etc.
  - Improve setup script if needed so user can drop their complete RVC deployments (main + 秋风) into external/ and have everything "just work".
- Update .gitignore for the new external/ structure (fix the space typos noted in inventory).
- Add any minimal supporting files (e.g. a small `engine_paths.py` resolver if it reduces duplication).
- Write focused tests and update the freeze-gate tests so they pass.
- Produce a proper worker report.

**Strictly forbidden**:
- No new user-facing features.
- No real UVR/RVC execution or training on real materials (dry/mock only for testing the new paths).
- No changes to `backend/db.py`.
- No expansion of core job execution (pipelines/strategies) beyond what's needed for facade delegation.
- Do not delete old stage59_* files yet (that is Stage60C).
- Keep all existing behavior identical for existing flows.

## 4. Main Prompt
`docs/agent-md/architect/stage-60b-facade-introduction-and-engine-bundling-prompt.md` (create if not present — base it on the Stage60A inventory output + bundling plan).

## 5. Expected Deliverables
- The 4 facade modules (with old modules delegating).
- Completed bundling so that launcher starts main (7866) and backup (7865) from workspace external/ dirs, paths resolve correctly, engine_manager lists backup as first-class, models can be imported with origin metadata, Studio can use 秋风RVC as backup stably.
- All freeze-gate tests passing + new bundling tests.
- Updated documentation (README, launcher comments, setup script).
- Worker report at `docs/agent-md/worker/stage-60b-facade-and-bundling-report.md` (full template with Debt Delta etc.).

## 6. Success Criteria
- `external/rvc-webui` + `external/rvc-webui-backup` + `external/audio-pipeline` are the primary, complete locations.
- User's prepared materials + 秋风RVC backup model work reliably inside the workspace.
- No behavior change for existing users who still have external installs (backward compat via env + fallbacks).
- All required tests green.
- Report honest on debt (we are compressing Stage59 services while solving a real user pain point for stable training).

After this, the tree should be much cleaner for actual training use, while we continue the governance consolidation.

Human will review the report + changes, then we decide on Stage60C (shim deletion) or direct training usage.