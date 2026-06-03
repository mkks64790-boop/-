# Stage 45R Hotfix Backend Duration Artifact Contract Report

## Completion Status

Completed.

This hotfix closed the backend contract gaps left by Stage45RA:

- Separation eval artifacts now have browser-usable URLs.
- Duration mismatch is explicitly detected and returned in API detail.
- Existing latest run `stage45r_20260602_171704_201ec7ff` now reports `BLOCK_TRAINING=true`.
- Browser-triggered execution is explicitly disabled with structured `501`, not a confusing `404`.

## Modified Files

- `backend/services/separation_eval_service.py`
  - Added artifact URL contract generation.
  - Added safe artifact resolver restricted to `shared_data/separation_eval/runs`.
  - Added duration mismatch contract:
    - `duration_mismatch`
    - `duration_ratio`
    - `duration_ratio_max`
    - `duration_mismatch_risk`
    - `duration_mismatch_next_step`
  - Updated noise risk classification so duration mismatch can force `noise_risk=high`.
  - Backfilled existing run detail/report/manifest snapshots when run detail is requested.

- `backend/main.py`
  - Added artifact playback/download endpoint:
    - `GET /api/separation/eval/runs/{run_id}/items/{item_index}/artifacts/{artifact_key}`
  - Added structured disabled POST endpoint:
    - `POST /api/separation/eval/run`

- `backend/verify_stage45r_separation_quality_audit.py`
  - Added latest-run contract checks.
  - Checks artifact URLs for original/vocal/instrumental.
  - Prints duration mismatch contract.
  - Prints `BLOCK_TRAINING=true` when mismatch exists.

- `tests/api/test_stage45r_separation_eval_api.py`
  - Added tests for artifact URLs, safe download, missing artifact 404, POST policy, and duration mismatch contract.

- `docs/agent-md/worker/stage-45r-hotfix-backend-duration-artifact-contract-report.md`
  - Added this report.

## Artifact URL Playback / Download

Implemented endpoint pattern:

```text
GET /api/separation/eval/runs/{run_id}/items/{item_index}/artifacts/original
GET /api/separation/eval/runs/{run_id}/items/{item_index}/artifacts/vocal
GET /api/separation/eval/runs/{run_id}/items/{item_index}/artifacts/instrumental
```

Safety behavior:

- Only fixed artifact keys are allowed: `original`, `original_excerpt`, `vocal`, `instrumental`.
- Files are resolved only under `shared_data/separation_eval/runs`.
- Missing run/item/artifact returns `404`.
- Response content type is `audio/wav`.
- No request path is used directly, so path traversal is blocked.

Verification result from latest run:

- Item 1 original/vocal/instrumental: `200`, readable, `audio/wav`
- Item 2 original/vocal/instrumental: `200`, readable, `audio/wav`
- Item 3 original/vocal/instrumental: `200`, readable, `audio/wav`

Artifact URL playable/downloadable: yes.

## Duration Mismatch Detection

Latest run:

```text
stage45r_20260602_171704_201ec7ff
```

Detected contract:

- Item 1: `duration_mismatch=true`, `duration_ratio=0.5957`, `duration_mismatch_risk=high`
- Item 2: `duration_mismatch=true`, `duration_ratio=0.5957`, `duration_mismatch_risk=high`
- Item 3: `duration_mismatch=true`, `duration_ratio=0.5957`, `duration_mismatch_risk=high`

Meaning:

- `original_excerpt.wav` is `45.0s`.
- `vocal.wav` and `instrumental.wav` are about `26.807s`.
- Difference is greater than 5%, therefore risk is high.

Duration mismatch detected: yes.

## BLOCK_TRAINING

`BLOCK_TRAINING=true`

Reason:

- The separation layer does not preserve the 45s excerpt duration.
- This is a training/cover blocking contract issue until UVR runner trimming is inspected or fixed.

## POST Run Strategy

Final strategy: structured disabled endpoint.

`POST /api/separation/eval/run` returns:

- HTTP `501`
- `code=separation_eval_execute_disabled`
- Message says execution is CLI-only for safety.

Reason:

- Product side should not expose a browser one-click UVR execution path yet.
- This avoids accidental GPU/UVR load and keeps the Stage45R audit command explicit.

## Safety Confirmation

- `train.py` started: no
- RVC inference called: no
- D: test music moved/deleted/overwritten: no
- Recursive full-D scan performed: no
- Duration mismatch silently ignored: no

## Test Results

- `python -m pytest -q`
  - PASS: `64 passed, 2 warnings`

- `python -m backend.self_check`
  - PASS: `SELF_CHECK_SUMMARY PASS`

- `python backend\verify_stage45r_separation_quality_audit.py`
  - PASS: `STAGE45R_AUDIT_SUMMARY PASS`
  - Artifact URL checks all returned `200`, readable, `audio/wav`
  - Printed `BLOCK_TRAINING=true`

- `python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/separation/eval/runs/stage45r_20260602_171704_201ec7ff').json())"`
  - PASS
  - Response includes `artifact_urls`, `duration_mismatch=true`, `duration_ratio=0.5957`, `duration_mismatch_risk=high`, and `block_training=true`.

## Remaining Risks

- This hotfix does not fix the UVR runner trimming bug; it makes the bug explicit and blocks training.
- The next backend step should inspect AudioPipeline `run_uvr5_split.py` STFT/ISTFT chunking and output length preservation.
- Product-side A/B listening should use the new artifact URLs, but training should remain blocked while duration mismatch is high.
