# ADR 0003 (Draft): Stage59 Services Consolidation Proposal

Status: Draft for review (Stage60 Governance)
Date: 2026-06
Related:

- `docs/ARCHITECTURE_CONSTITUTION.md`
- `docs/adr/0002-stage60-debt-audit-stage59-db-legacy.md`
- `docs/governance/stage60-stage59-service-consolidation-plan.md`

## Problem

Stage59 created a useful safety chain for short-chain UVR A/B work, but it also
created too many milestone-named modules. This violates the new Constitution
principle that milestone experiments must be consolidated into durable
abstractions.

Current Stage59-specific modules:

- `stage59_approval_audit_service.py`
- `stage59_artifact_persistence_service.py`
- `stage59_execution_guard_service.py`
- `stage59_execution_policy_service.py`
- `stage59_job_artifact_promotion_service.py`
- `stage59_listening_bridge_service.py`
- `stage59_real_smoke_plan_service.py`
- `stage59_transient_artifact_service.py`
- `stage59_uvr_mock_execute_service.py`
- `stage59_uvr_runner_contract.py`

Adjacent Stage59-heavy modules:

- `short_chain_manifest_service.py`
- `short_chain_uvr_service.py`
- `verify_stage59_uvr_ab.py`
- Stage59 request models and routes in `backend/main.py`

## Decision Proposal

Consolidate Stage59 work into durable modules that can support future local
engine workflows without keeping `stage59_` service sprawl.

Target modules:

1. `short_chain_service.py`
   - manifest loading
   - rights gate
   - whitelist
   - chain eligibility

2. `execution_safety_service.py`
   - caps
   - approval policy
   - sandbox policy
   - disk preflight
   - audit adapter

3. `artifact_lifecycle_service.py`
   - artifact contracts
   - transient lifecycle
   - file-backed promotion plan
   - listening bridge metadata
   - cleanup policy

4. `uvr_smoke_service.py`
   - UVR A/B mock execution
   - real-smoke plan only
   - future real runner adapter boundary

## Migration Approach

Phase 1:

- Add durable facade modules.
- Keep old Stage59 modules as compatibility shims.
- Do not change endpoint behavior.
- Do not run real UVR/RVC/GPU.

Phase 2:

- Move implementation into durable modules.
- Update imports in `main.py`, tests, and verifiers.
- Keep tests green.

Phase 3:

- Delete or archive milestone-named shims after all imports are migrated.
- Consider renaming `/api/stage59/...` only after a separate API compatibility ADR.

## Consequences

Benefits:

- Lower cognitive load.
- Removes milestone-specific service growth pattern.
- Makes safety and artifact logic reusable for normal cover/train flows.
- Creates a controlled path toward real UVR/RVC without new service explosions.

Costs:

- Short-term refactor work before visible features resume.
- Temporary facade modules may briefly increase file count.
- Requires careful import migration and tests.

## Acceptance Criteria

- No new feature behavior.
- All existing Stage59C tests pass.
- Full `python -m pytest -q` passes.
- `stage59_*` service count decreases by the end of consolidation.
- Worker report shows negative or neutral Debt Delta.

## Open Questions

- Should API paths remain `/api/stage59/...` for compatibility, or should they
  be generalized later under `/api/short-chain/...`?
- Should `artifact_lifecycle_service.py` merge with the existing
  `asset_service.py`, or stay separate until DB repositories exist?
- Should audit persistence remain in memory until DB governance work creates a
  repository boundary?
