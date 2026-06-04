# Stage60 main.py Router Split Plan

Status: Draft for Governance Sprint
Date: 2026-06-04
Scope: planning only

## Problem

`backend/main.py` has grown into a mixed entrypoint:

- app setup
- imports
- Pydantic request models
- route handlers
- queue dispatch
- compatibility shims
- direct DB access
- Stage59 route block

This makes product changes and governance changes collide in one file.

## Target Shape

Keep `backend/main.py` responsible only for:

- FastAPI app creation
- middleware/static setup
- startup hooks
- router registration
- root health/status endpoints if needed

Move route groups into `backend/routers/`.

## Proposed Routers

- `backend/routers/jobs.py`
- `backend/routers/models.py`
- `backend/routers/tracks.py`
- `backend/routers/studio.py`
- `backend/routers/factory.py`
- `backend/routers/training.py`
- `backend/routers/diagnostics.py`
- `backend/routers/stage59_short_chain.py`
- `backend/routers/materials.py`
- `backend/routers/memory.py`

Request/response models should move into:

- `backend/schemas/`

Shared dependencies should move into:

- `backend/dependencies.py`

## Split Order

### Phase 1: Stage59 Router Extraction

Reason: Stage59 is already isolated and route-heavy.

Move:

- `Stage59UvrAb*Request`
- `/api/stage59/short-chain/uvr-ab/*`
- `_resolve_stage59_manifest_or_400`

Acceptance:

- API paths unchanged
- tests unchanged except imports if necessary
- no real UVR/RVC execution

### Phase 2: Jobs and Artifacts Router

Move:

- `/api/jobs`
- `/api/jobs/{job_id}`
- artifacts
- stage logs
- retry/requeue/cancel

Acceptance:

- job list/detail contracts unchanged
- artifact download sandbox tests pass

### Phase 3: Training and Model Routers

Move:

- training presets/observer/recovery
- model import/rescan/detail/list

Acceptance:

- training observer tests pass
- model lifecycle tests pass

### Phase 4: Product Routers

Move:

- tracks
- studio effects
- factory
- material library
- memory lab

Acceptance:

- browser smoke tests and API tests pass

## Rules

- Router extraction must not change endpoint paths.
- Router extraction must not introduce new feature behavior.
- Any router split touching service logic must be rejected unless an ADR covers it.
- Do not move all routers in one PR. Split by domain.

## Suggested First PR

`Stage60B: extract Stage59 short-chain router without behavior changes`

Validation:

```powershell
python -m pytest tests\api\test_stage59c*.py tests\unit\test_stage59c*.py -q
python -m pytest -q
```
