# Stage60 Stage59 Service Inventory and Consolidation Plan

Status: Draft for Governance Sprint
Date: 2026-06-04
Scope: planning only, no runtime UVR/RVC work

## Goal

Stop Stage59 service sprawl before C-4c or any real UVR runner work continues.

The target is not to delete safety gates. The target is to move milestone-named
services into durable domain abstractions so future stages extend stable modules
instead of adding more `stageXX_*_service.py` files.

## Current Inventory

Stage59-specific modules found in `backend/services`:

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

Adjacent Stage59-heavy shared modules:

- `short_chain_manifest_service.py`
- `short_chain_uvr_service.py`
- `verify_stage59_uvr_ab.py`
- Stage59 route block and request models in `backend/main.py`

## Proposed Durable Abstractions

### 1. `short_chain_service.py`

Owns:

- manifest loading and safe path resolution
- rights gate
- entry whitelist
- chain stage eligibility
- dry-run plan shape

Absorb from:

- `short_chain_manifest_service.py`
- `short_chain_uvr_service.py`

Do not change behavior in the first pass. Create a compatibility facade if needed.

### 2. `execution_approval_service.py`

Owns:

- approval token validation
- explicit confirmation policy
- caps and timeout policy
- sandbox and disk preflight
- audit record adapter

Absorb from:

- `stage59_execution_policy_service.py`
- `stage59_execution_guard_service.py`
- `stage59_approval_audit_service.py`

Future-proof name must not include `stage59`.

### 3. `artifact_contract_service.py`

Owns:

- transient artifact contract
- file-backed promotion plan
- lifecycle and cleanup policy
- listening bridge metadata for non-playable artifacts

Absorb from:

- `stage59_artifact_persistence_service.py`
- `stage59_job_artifact_promotion_service.py`
- `stage59_transient_artifact_service.py`
- `stage59_listening_bridge_service.py`

### 4. `uvr_smoke_service.py`

Owns:

- mock UVR smoke execution contract
- real-smoke plan only
- future real runner adapter boundary

Absorb from:

- `stage59_uvr_mock_execute_service.py`
- `stage59_real_smoke_plan_service.py`
- `stage59_uvr_runner_contract.py`

This module must keep real execution disabled by default until a later ADR.

## Consolidation Phases

### Phase A: Facade First

Create durable modules that import and wrap current Stage59 implementations.

Acceptance:

- no behavior change
- all existing tests pass
- old import paths still work
- no new user-facing feature

### Phase B: Move Internals

Move implementation from `stage59_*` files into durable modules.

Acceptance:

- Stage59 files become thin compatibility shims
- service count with milestone prefix drops materially
- route/API contract remains unchanged

### Phase C: Remove Shims

Remove milestone-named shims after tests and downstream imports are updated.

Acceptance:

- no `stage59_*_service.py` files remain except archived docs/tests if needed
- `verify_stage59_uvr_ab.py` may remain as a historical verifier until C-4 series closes

## Hard Rules

- No real UVR/RVC execution during this consolidation.
- No raw audio/model/DB files may be tracked.
- No new `stage60_*_service.py` replacement sprawl.
- Any cross-cutting code move touching more than three core files requires an ADR update.

## Suggested First PR

First governance PR should only add facades and update imports for tests, not remove old files.

Candidate title:

`Stage60A: introduce durable short-chain, approval, artifact, and uvr-smoke facades`

## Debt Delta Target

- Stage60A may add facade files temporarily, but must document them as migration scaffolding.
- Stage60B must reduce milestone-named service files.
- No Feature Sprint resumes until Stage60A has a passing report.
