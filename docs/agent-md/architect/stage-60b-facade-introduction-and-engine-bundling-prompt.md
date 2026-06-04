# Stage60B: Facade Introduction + RVC/AudioPipeline Bundling (Governance-Only Bounded Implementation)

**Project root**: `D:\FeiSharkStudio-v2`

**Read this first (non-negotiable)**:
`docs/agent-md/handoff/stage-60-governance-memory-snapshot.md`

Then:
- `docs/agent-md/handoff/stage-60b-facade-and-bundling-handoff.md`
- This prompt
- The Stage60A inventory report + its review (they are the source of truth for what to implement)
- `docs/governance/stage60-training-engine-bundling-plan.md`
- All previous required reading from Stage60A (Constitution, ADRs, governance plans, etc.)

**Declaration required at top of your worker report**: "I read the memory snapshot first, followed by the Stage60A inventory report and review, the bundling plan, and all listed governance documents. This work stays strictly within governance boundaries."

## Stage Boundary (Hard)
- This is **bounded implementation** after pure inventory.
- Introduce the 4 durable facades proposed in Stage60A.
- Complete the workspace self-contained bundling for RVC (main + 秋风RVC backup) + AudioPipeline.
- Keep **all existing behavior 100% identical**.
- No real UVR/RVC/GPU execution or training on real materials (use the existing dry/mock/real-smoke-plan paths only for verification).
- No deletion of old stage59_* shims (that is Stage60C).
- No db.py changes.
- No new user features.

## Goal
Take the Stage60A inventory output and turn the **proposals** into working (but transitional) code:

1. Create the 4 durable facade modules exactly as proposed:
   - `short_chain_service.py`
   - `execution_safety_service.py`
   - `artifact_lifecycle_service.py`
   - `uvr_smoke_service.py`

   Old `stage59_*` modules become thin delegates during this phase.

2. Complete the RVC + AudioPipeline bundling so that:
   - `external/rvc-webui` (primary, port 7866) + `external/rvc-webui-backup` (for 秋风RVC / Qiufeng backup, port 7865) + `external/audio-pipeline` become the preferred, complete, self-contained locations inside the workspace.
   - User's prepared materials + the 秋风RVC model (enabled as backup in studio) can be used reliably without depending on scattered external D:\ installs.
   - Launcher reliably starts both RVC instances from the workspace external dirs.
   - engine_manager surfaces `rvc_webui_backup` as a first-class engine.
   - Model import and metadata can record primary vs backup origin.
   - voice_changer / model_trainer / vocal_separator prefer the workspace external paths (with env override still winning).
   - Backward compatibility is preserved for anyone who still has external installs.

3. Make sure the "freeze gate" tests from Stage60A all pass (plus any new bundling-specific tests).

4. Produce a full worker report with Debt Delta, Invariant Violations, Simplification Opportunities, etc.

## Required Deliverables
- The 4 facade Python modules (with delegation logic so old code paths continue to work).
- Updates to:
  - `feishark-launcher.ps1` (start main + backup from external/ if present)
  - `backend/services/engine_manager_service.py` (first-class rvc_webui_backup engine)
  - Path resolution in `voice_changer.py`, `model_trainer.py`, `vocal_separator.py`
  - Model import / registration to support origin metadata for backup models
  - `scripts/setup_training_engines.ps1` (make it actually useful for dropping complete RVC deployments into external/)
  - `.gitignore` (fix the space typos in external patterns, properly cover backup binaries)
- A small resolver if it helps (e.g. `backend/engine_paths.py`) — keep it minimal and non-service if possible.
- All Stage60A freeze-gate tests + new bundling tests passing.
- Worker report at:
  `docs/agent-md/worker/stage-60b-facade-and-bundling-report.md`

## Validation (Run and Record)
Use the exact freeze-gate list from the Stage60A report, plus:
- Full `python -m pytest -q`
- `python -X utf8 backend\self_check.py` (CODE_STRUCTURE must PASS; runtime will still be limited until external/ engines are populated)
- Engine scan showing both primary and backup RVC
- Launcher dry checks
- `git ls-files` raw asset scan (must stay clean)
- The Stage59C-4b real-smoke-plan CLI (still must return real_execute_allowed=false)
- Manual verification that existing cover/train flows are unaffected

## How to Work
- Base every facade and bundling change on the exact proposals in the Stage60A report.
- For the 秋风RVC backup: make it first-class where it makes sense (engine listing, model origin, launcher, path resolution), but keep training on primary only unless a later ADR says otherwise.
- Prefer workspace `external/...` paths, but keep the old hard-coded fallbacks + env var overrides so nothing breaks for other users.
- Every change must be small, reviewable, and covered by tests.
- Document any temporary delegation patterns clearly in comments.
- Be extremely honest in the Debt Delta section about what new temporary complexity (if any) the transitional facades introduce.

## Success Criteria
- The 4 facades exist and old code still works.
- A user with complete RVC-WebUI (main + 秋风 backup) and AudioPipeline can copy them into `external/` and have stable, self-contained training + inference with their prepared materials.
- All freeze-gate tests pass.
- No behavior change for legacy external setups.
- Report is complete and follows the template.
- No Constitution violations (0 new milestone services in this phase, real execution still blocked, etc.).

**Do not commit.** Leave everything for human + reviewer inspection.

After this phase, the next logical step will be human-approved Stage60C (shim deletion) or direct use of the now-stable bundled engines for training.

Begin.