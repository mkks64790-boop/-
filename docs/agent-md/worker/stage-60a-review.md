# Stage60A Dependency Inventory and Facade Boundary Review - Governance Reviewer Report

**Stage**: Stage60A - Dependency Inventory and Facade Boundary Review  
**Date**: 2026-06-04  
**Reviewer**: Grok (following `governance-reviewer-prompt.md` and memory snapshot)  
**Worker Report**: `docs/agent-md/worker/stage-60a-dependency-inventory-facade-boundary-review-report.md` (Status: PASS - governance inventory complete; external runtime limits documented)  
**Prompt Used**: `docs/agent-md/architect/stage-60a-dependency-inventory-facade-boundary-review-prompt.md`  
**Handoffs Used**: memory snapshot + stage-60a-dependency-inventory-handoff.md

## 1. Verdict: Pass

The GPT-side work is **accepted**. It delivered a high-quality, complete, read-only inventory that precisely matches the requirements in the memory snapshot and the Stage60A prompt.

This is exactly the kind of disciplined governance output the Constitution and plans call for: thorough analysis, explicit freeze lists, concrete proposals, test gates, and honest documentation of limits (especially the external RVC/AudioPipeline situation and the user's 秋风RVC backup + prepared materials).

No behavior was changed. No real execution occurred. The working tree was not dirtied beyond writing the required report.

## 2. Constitution Compliance

**Strong compliance.**

- Started with the memory snapshot (explicit declaration in report).
- Followed full required reading list (Constitution, ADRs 0001-0003, all 4 governance plans including the bundling plan, prior reports/reviews, templates).
- No new milestone services, no db.py changes, no main.py expansion, no real UVR/RVC workloads.
- All changes were documentation/analysis only (the report + embedded graphs/proposals).
- Properly treated the bundling requirement (main RVC + 秋风RVC backup + AudioPipeline into `external/`) as part of the inventory, not as feature work.
- Debt Delta, Invariant Violations, and Simplification Opportunities sections are present and substantive.

The report correctly notes that `external/` currently does not exist in the workspace, so current paths fall back to the user's scattered D:\RVC... and C:\Users\ASUS\AudioPipeline installs. This directly addresses the user's pain point about uncertain external setups and desire for self-contained, stable training.

## 3. Debt Delta

**Excellent (negative at planning/governance level).**

**Debt added**: Only the report file itself (necessary deliverable).

**Debt reduced**:
- Full static inventory of all 10 stage59_* services + adjacent modules + core interactions + engine boundaries.
- Public interfaces explicitly frozen (detailed lists for manifest, execution, artifact, listening, real-smoke-plan, main.py Stage59 routes/models, engine/model/pre-flight contracts, etc.).
- Clear identification of the external engine fragility (primary + backup RVC paths, AudioPipeline, launcher support for 7866/7865, gaps in engine_manager for first-class backup engine).
- Specific proposal for bundling complete engines into workspace `external/rvc-webui` (main) + `external/rvc-webui-backup` (Qiufeng/秋风RVC) + `external/audio-pipeline`, with env overrides, model origin metadata, primary-vs-backup routing, etc.
- 106 direct `get_connection(` calls counted for later DB governance.
- Precise "freeze gate" test list defined so Stage60B can proceed safely.

**Quantification** (from report):
- 10 milestone Stage59 services inventoried.
- 9 Stage59 API endpoints + 5 Pydantic models frozen.
- Clear facade split proposed (4 durable services).
- External engine debt now bounded and actionable.
- Net: strong reduction in "we don't know the shape" risk for the next migration phase.

## 4. Invariant Violations

**None.**

- No new services.
- No db.py or schema work.
- No main.py behavior or router changes.
- No real execution (only read-only probes).
- No raw assets added.
- The work stayed strictly within the "inventory and proposal" boundary defined in the prompt and memory snapshot.

The report even calls out minor existing issues (e.g. .gitignore typos with spaces in external patterns) for later small fixes instead of fixing them here.

## 5. Simplification Opportunities

The report surfaces good ones and correctly defers execution:

- Replace 10 stage59_* with 4 facades after approval + test freeze.
- Extract Stage59 routes from main.py only after facades.
- Centralize RVC/UVR path resolution (stop duplicated constants in voice_changer, model_trainer, vocal_separator, engine_manager).
- Make backup RVC (秋风/Qiufeng) first-class in engine_manager + model metadata + list_rvc_models (instead of relying only on URL fallbacks).
- Fix .gitignore for external/ binaries.
- Add read-only mode to self_check (current one mutates the ignored runtime DB).
- Do DB repository inventory after facade work (106 get_connection calls are widespread).

**Additional reviewer note**: The bundling proposal for complete engines in `external/` (to support user's prepared materials + stable main + 秋风RVC backup) is one of the highest-value simplifications identified. Once the engines live inside the workspace with proper launcher + path resolver support, a huge class of "works on my machine" and deletion-risk debt disappears. This should be treated as a priority follow-up item (can start as a small contained infra task even before full facade code moves).

## 6. Blocking Issues

**None.**

- Report is complete and follows the template.
- All required artifacts are present (Mermaid graphs, detailed freeze lists, facade proposals, bundling integration details for 秋风RVC, exact test gate).
- Validations were run (pytest 288 passed; self_check structure PASS with documented runtime FAIL due to missing external engines; engine scan correctly shows current external paths; no raw assets).
- Scope respected perfectly.
- The "external directory missing" observation is accurate and actionable.

## 7. Non-Blocking Issues

- Working tree remains dirty with pre-existing changes (C-4b, previous bugfix, bundling prep edits to launcher/paths/self_check, etc.). The report correctly documents this and only wrote the required report file.
- Some validation commands in the prompt had PowerShell wildcard issues (GPT handled by expanding them — good).
- The report notes that `model_trainer` should stay on primary only for training (backup as inference-only) unless a later ADR says otherwise — prudent.
- `.gitignore` has the space typos in external patterns (as noted) — should be a tiny follow-up fix.
- No diagrams beyond Mermaid (fine for this phase).

## 8. Required Fixes Before Merge / Next Actions

**Verdict: Pass. No blocking fixes.**

**Recommended immediate actions**:

1. **Human approval**: Review this inventory + the worker report. Approve the proposed facade boundaries and the bundling direction for main RVC + 秋风RVC backup + AudioPipeline into `external/`.

2. **Clean commits** (after approval):
   - Commit the Stage60A report + any supporting graphs as a clean "Stage60A: dependency inventory and facade boundary review (governance only)" commit.
   - Keep pre-existing dirty changes (C-4b, bugfix, bundling prep) for separate handling or squashing later.

3. **Proceed to implementation**:
   - Next major step: Stage60B — actual introduction of the 4 durable facades (short_chain_service, execution_safety_service, artifact_lifecycle_service, uvr_smoke_service) as thin facades + thin delegates.
   - Prioritize or parallelize the **RVC/AudioPipeline bundling** work:
     - Make `external/rvc-webui` and `external/rvc-webui-backup` (for 秋风RVC) + `external/audio-pipeline` the primary targets.
     - Update launcher to reliably start both on 7866/7865 from workspace.
     - Improve engine_manager to expose `rvc_webui_backup` as first-class.
     - Add origin metadata on import-rvc / voice_models for primary vs backup.
     - Centralize path resolution.
     - Once engines are complete inside workspace, the user's prepared materials can be used for stable training without external fragility.

4. **Create the next prompt**:
   I will prepare a Stage60B (or "Stage60A+ Bundling + Facade Introduction") prompt + handoff that takes this inventory as input and produces the actual (minimal, test-gated) facade code + bundling completion.

5. **Training timeline reminder** (per memory snapshot + Constitution):
   - You can continue using dry/mock/plan modes and the existing training paths for your prepared materials once the bundling is in place.
   - Full real UVR (short-chain) + production RVC training on separated material should wait until after the facade work + human sign-off on the governance debt repayment, to avoid re-introducing the very service sprawl we are trying to eliminate.

The inventory is solid. This is the right foundation. Now we can move from analysis to bounded, safe execution while giving you the stable self-contained RVC (main + 秋风 backup) setup you need for your materials.

**Reviewer sign-off**: Pass. Ready for human approval and Stage60B planning/implementation.

*This review written to `docs/agent-md/worker/stage-60a-review.md` per the agent-md workflow.*