# Stage60 Governance Sprint Prompt: Governance Only - No New Features

Project root: `D:\FeiSharkStudio-v2`

## Stage Boundary

This stage is governance only. Do not add user-facing features. Do not run real
UVR/RVC/GPU/ffmpeg workloads. Do not continue C-4c.

## Required Reading

1. `docs/ARCHITECTURE_CONSTITUTION.md`
2. `docs/adr/0001-stage60-governance-sprint-and-process-upgrade.md`
3. `docs/adr/0002-stage60-debt-audit-stage59-db-legacy.md`
4. `docs/governance/stage60-stage59-service-consolidation-plan.md`
5. `docs/governance/stage60-db-governance-plan.md`
6. `docs/governance/stage60-main-router-split-plan.md`
7. `docs/governance/stage60-legacy-retirement-map.md`
8. `docs/agent-md/architect/governance-reviewer-prompt.md`
9. `docs/agent-md/worker/worker-report-template.md`

## Goals

- Make Constitution and ADR mandatory for future work.
- Freeze feature expansion until governance debt is visible and planned.
- Create executable plans for Stage59 service consolidation.
- Create DB governance and migration/repository direction.
- Create main.py router split direction.
- Create legacy retirement roadmap.
- Upgrade agent-md reporting so agents must report debt and violations.

## Allowed Changes

- Documentation under `docs/`
- Agent prompt/report templates under `docs/agent-md/`
- Governance inventory scripts only if read-only and explicitly scoped

## Forbidden Changes

- No real UVR/RVC execution.
- No C-4c real runner work.
- No new product UI.
- No new runtime service unless it is a read-only governance verifier and has an ADR.
- No new large migration/backfill in `backend/db.py`.
- No `git add .`.
- No raw audio/model/DB files.

## Required Deliverables

- Constitution exists and is readable.
- ADR 0001 exists.
- ADR 0002 or equivalent debt audit exists.
- Governance plans exist under `docs/governance/`.
- Worker report template requires Debt Delta, Invariant Violations, Simplification Opportunities.
- Governance Reviewer prompt exists.
- Worker report for this stage exists.

## Required Validation

Run:

```powershell
python -m pytest -q
git diff --check
git ls-files | Select-String -Pattern '(\.wav|\.mp3|\.flac|\.m4a|\.aac|\.ogg|\.pth|\.index|\.sqlite|\.db)$'
```

If only docs changed after the previous full test, note that in the report.

## Report

Write:

`docs/agent-md/worker/stage-60-governance-sprint-report.md`

The report must follow:

`docs/agent-md/worker/worker-report-template.md`
