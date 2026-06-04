# Stage60 Bugfix Task Handoff (for GPT Architect / Agent)

**Use this as the task-specific handoff. First action for any agent: read the master memory snapshot.**

## 1. Master Memory Snapshot (MUST READ FIRST)
`docs/agent-md/handoff/stage-60-governance-memory-snapshot.md`

This file defines the current governance mode, rules, consolidation direction, API preference, and explicitly recommends the next major task as **Stage60A: dependency inventory and facade boundary review**.

## 2. Specific Task for This Round
**Task**: Small debt-repaying bug fixes (governance-only, preparatory for Stage60A).

**Main Instruction Prompt** (execute this as the core task):
`docs/agent-md/architect/stage-60-bugfix-small-debt-fixes-prompt.md`

This prompt has been updated to list the memory snapshot as the #1 required read.

## 3. Scope Reminder (from Memory Snapshot + Prompt)
- Governance-only sprint continuation.
- Only small, isolated fixes (ideally 1-3 files each).
- Focus on hotspots from governance plans (legacy tasks/voice_assets access, direct get_connection calls, lifecycle inconsistencies, etc.).
- Goal: reduce immediate risk/inconsistency so that the upcoming Stage60A inventory and facade work is cleaner.
- Do **not** do big refactors, facade introduction, service consolidation, or DB restructuring — those are for Stage60A proper.
- Produce full worker report using the template, with Debt Delta, Invariant Violations, Simplification Opportunities.
- Reference this handoff and the memory snapshot in your thinking and report.

## 4. Output Deliverables
- Code changes for the small fixes + tests.
- `docs/agent-md/worker/stage-60-bugfix-small-debt-fixes-report.md` (following worker-report-template.md)
- Run all validation commands listed in the bugfix prompt.
- Do **not** git add or commit (leave for human).

## 5. After Completion
- Share the full worker report + `git status --porcelain` + `git diff --stat` (and key diffs if small) with the coordinator / Grok.
- Grok will review (following governance-reviewer-prompt), then collaborate to create the actual **Stage60A architect prompt and plan**, based directly on the recommendations in the memory snapshot (dependency graph, interface freeze, facade boundaries, required tests, etc.).

## 6. Alignment
This task respects:
- Current governance mode (no features, no new milestone services, no real engine work).
- The explicit "Next Recommended Task" in the memory snapshot.
- Small fixes now = better foundation for inventory/facade work later.

Human coordinator will provide the memory snapshot + this handoff + the bugfix prompt to the executing agent.

---
*This handoff was prepared after the agent read and internalized the master Stage60 Governance Memory Snapshot.*
