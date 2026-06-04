# Stage60 Bugfix Small Debt-Repaying Fixes - Governance Reviewer Report

**Stage**: Stage60 Bugfix - Small Debt-Repaying Fixes  
**Date**: 2026-06-04  
**Reviewer**: Grok (following governance-reviewer-prompt.md)  
**Worker Report Reviewed**: `docs/agent-md/worker/stage-60-bugfix-small-debt-fixes-report.md` (Status: BLOCKED - external RVC training environment only)  
**Task Prompt**: `docs/agent-md/architect/stage-60-bugfix-small-debt-fixes-prompt.md` (and associated handoffs + memory snapshot)  
**Related Prior**: Stage60 Governance Sprint, memory snapshot, bundling plan for RVC/AudioPipeline integration, user's 秋风RVC backup model discussion.

## 1. Verdict: Pass

The work is accepted as a valid, scoped Stage60 governance bugfix task. It delivered small, isolated, defensive improvements that reduce immediate operational risks without violating governance boundaries.

The "BLOCKED" status in the report is honest and expected (external RVC env incomplete, as discussed in prior context around bundling complete RVC + 秋风RVC backup into workspace/external/). This is not a task failure but an acknowledged limit outside the bugfix scope.

All blocking rules from the reviewer prompt are satisfied:
- No real UVR/RVC/GPU execution enabled.
- No raw assets tracked.
- No new large db.py changes.
- No new milestone service created by *this task* (0 new service files).
- Report contains all required sections (Debt Delta, Invariant Violations, Simplification Opportunities) + honest validation.
- No endpoint contract changes without tests.

## 2. Constitution Compliance

**Compliant.** This task operated strictly within Stage60 governance-only mode.

- Followed mandatory reading: memory snapshot first (as required), Constitution, ADRs 0001-0003, governance plans, prior reports/reviews, templates.
- Declared compliance at top of report.
- Changes were minimal and isolated (existing Stage59 services + self_check + vocal_separator + tests). No cross-3+ core file structural changes without prior ADR (the fixes are bug repairs, not new architecture).
- No violation of hard invariants:
  - No new stage59_/stage60_ service files.
  - No db.py backfill/migration additions.
  - Job core (pipelines/strategies) untouched.
  - Real execution kept strictly blocked (`real_execute_allowed=false` throughout, verified by CLI in report).
  - No expansion of main.py for new business logic (any main.py diffs are pre-existing from prior sessions).
- The vocal_separator.py fix directly supports the user's request for workspace-bundled engines (external/audio-pipeline fallback) by fixing the import order bug introduced during bundling prep. This is a positive debt reduction for training stability.
- Self-check improvement separates "code contract/structure" from "external runtime readiness" - excellent for governance, prevents false negatives when RVC env (including 秋风RVC backup) is incomplete.

The task explicitly avoided consolidation/facades (reserved for Stage60A per memory snapshot and plans).

## 3. Debt Delta (Reviewer Assessment)

**Matches report; positive for risk reduction.**

**Debt added (minimal, acceptable):**
- Small helper in stage59_execution_guard_service (the try/except for max_items).
- 2 new unit test files + additions to 3 existing tests.
- Minor comments in vocal_separator for bundling context.

**Debt reduced (clear operational wins):**
- Eliminated import-time NameError in vocal_separator (critical for bundling external engines into workspace without crashing imports).
- Prevented unstructured exceptions in execution guard on bad input (now returns proper guard error).
- Fixed unsafe substring path matching for run-id in Stage59 artifact/promotion paths (prevents potential security/ sandbox escape in planned paths).
- Improved self_check to not conflate code shape with missing external RVC deps (torch, fairseq, faiss, sklearn, CUDA) - directly relevant to user's "秋风RVC as backup" and incomplete external setup. Structure checks now pass even if runtime env fails.
- Overall pytest count increased (282 → 288), indicating net test coverage gain.

**Net debt assessment**: Negative (good) for immediate risks and testability. Neutral-to-positive for long-term because changes are localized and the report correctly defers Stage59 consolidation to Stage60A/B. Ties nicely into the bundling plan (external RVC/AudioPipeline integration for stable training with prepared materials + backup model).

**Quantification** (from report + verification):
- New service files by *this task*: 0
- db.py changes: 0
- Real engine executions: 0 (CLI confirmed real_smoke_plan still forces false)
- Direct get_connection reductions: 0 (not in scope)
- Full pytest: 288 passed, 2 warnings
- Self-check: CODE_STRUCTURE_SUMMARY PASS (improved)

## 4. Invariant Violations

**None.**

- Report explicitly declares and the diff confirms: no new milestone services, no db.py structural debt, no real workloads enabled, no user features added, no unauthorized router changes.
- All changes are bug repairs/hardening in pre-existing code.
- The path validation fix in Stage59 services actually strengthens the sandbox invariants from prior C-4 work.
- Self-check change improves governance observability without changing runtime behavior.

The "external RVC training environment" blocker is called out but is a pre-existing condition (user's current RVC + AudioPipeline setup, including 秋风RVC backup), not introduced by this task.

## 5. Simplification Opportunities

**Report identifies them accurately; additional notes:**

- Correctly notes that Stage59 consolidation is for Stage60A after inventory.
- The `safe_runtime_run_id` helper could be unified later with execution guard logic - good call to defer.
- Self-check still does some synthetic DB work; read-only mode is a valid future governance item.
- External RVC repair (full bundling of main + 秋风RVC backup into external/rvc-webui* + audio-pipeline) is correctly left out of this bugfix (as per prompt scope) but is now a clear candidate for the bundling plan + Stage60A.

**Additional reviewer observation**: The vocal_separator fix is a direct enabler for the `stage60-training-engine-bundling-plan.md` (workspace self-contained engines). This bugfix round effectively "paid" a small debt that the bundling prep exposed. When we do the joint Stage60A planning (per user's choice 2), we should include the full bundling (main + 秋风 backup) as a simplification item in the dependency inventory.

No missed major simplifications in scope.

## 6. Blocking Issues

**None.**

- No real execution.
- No raw assets (scan clean).
- No db.py debt added.
- No new milestone service.
- Report is complete with all sections, honest limits, and correct next step (reviewer pass → Stage60A).
- Tests cover the claimed fixes; full regression green.
- The BLOCKED status is appropriate and well-documented (external env); not a blocker for accepting *this* fix set.

## 7. Non-Blocking Issues

- Working tree is dirty with pre-existing C-4b/Stage60 changes + my earlier bundling prep edits (main.py, launcher, model_trainer, voice_changer, README, prompt-template, .gitignore). The report correctly notes this and did not touch/commit them. Recommend cleaning (separate commits for prior work + this bugfix) after review.
- Self-check still fails on RUNTIME_ENVIRONMENT (expected per report and user's incomplete external RVC setup with 秋风RVC). The code-structure improvement is valuable.
- Minor: The prompt command note in report shows a PowerShell wildcard issue - non-blocking, just documentation.
- The fixes are good but small; the real value for user's "秋风RVC as backup + prepared materials + stable training" will come from completing the bundling plan in Stage60A.
- No whitespace or style issues beyond the usual CRLF warnings on Windows.

## 8. Required Fixes Before Merge / Recommendations

**No blocking fixes required. Accept the changes.**

**Recommended next actions (non-blocking):**

1. **Human/Governance Reviewer sign-off**: Accept this report + the 4 fixes. The work is clean governance bugfix.

2. **Clean working tree**: After acceptance, stage/commit the *specific* files from this task separately from the pre-existing C-4b/Stage60/bundling prep changes. Suggested commit message:
   ```
   Stage60 Bugfix: small debt-repaying fixes (import order, guard validation, path segment, self-check separation)
   
   - vocal_separator.py: fix PROJECT_ROOT ordering for external bundling support
   - self_check.py: separate code structure checks from external RVC runtime readiness
   - stage59_execution_guard/artifact/job_artifact_promotion: defensive improvements + tests
   - New/updated focused unit tests
   - Full pytest 288 passed; real_execute remains blocked
   ```

3. **Proceed to Stage60A planning** (as recommended in memory snapshot and this report):
   - Now that GPT bugfix is reviewed, user shares this + the bugfix report with me.
   - We jointly draft the Stage60A architect prompt (dependency inventory + facade boundaries).
   - Explicitly include the `stage60-training-engine-bundling-plan.md` (main RVC + 秋风RVC backup + AudioPipeline) as part of the inventory and a simplification deliverable.
   - Goal: get the complete engines self-contained in `external/` so training with prepared materials + backup model is stable, without scattered external deploys.

4. **External RVC env**: Separately decide (post this acceptance) whether to fully bundle/repair the RVC (including 秋风 backup) + AudioPipeline before making RUNTIME_ENVIRONMENT_SUMMARY a hard gate. The bundling plan + setup script I prepared earlier are ready to use here.

5. **Optional polish**: Consider adding a small note in the bugfix report or self_check about the bundling context for 秋风RVC.

This bugfix round did exactly what was asked: small, safe, preparatory fixes while respecting the full governance process. It even helped unblock the bundling work for the user's RVC + 秋风 backup + materials use case.

**Reviewer sign-off**: Pass. Ready for Stage60A.

*Review artifact written to `docs/agent-md/worker/stage-60-bugfix-review.md` for the permanent record, following the workflow in memory snapshot and agent-md rules.*
