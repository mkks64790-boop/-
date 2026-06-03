# Stage58 Final Coordinator Acceptance Report

Date: 2026-06-03
Scope: user-state data cleanup, test-noise hiding, real-material quality acceptance
Workspace: D:\FeiSharkStudio-v2

## Verdict

PASS after coordinator fixes.

Stage58 is accepted for the current development boundary: the default user-facing API and UI no longer expose the known historical stage/smoke/test noise, while QA can still opt in with `include_test_data=true` / `include_smoke=true` or the frontend "show test records" toggle.

## Extreme Honesty Boundary

Known technical limits:
- This stage does not physically delete user data, DB rows, audio outputs, model files, or shared_data assets. It only default-hides test-like records and keeps an explicit QA escape hatch.
- This stage does not prove UVR/RVC audio quality. It only classifies available materials and verifies that bad smoke/test materials are not treated as user-facing evidence.
- This stage does not start RVC 7866, run long training, run UVR, or consume GPU.
- `shared_data/materials/stage58/material_manifest.json` is local evidence under ignored shared data. It is not a GitHub-safe artifact unless copied into a docs-safe manifest without raw audio paths.
- Rights and ownership for user-provided voice files cannot be proven by code. Manual confirmation is still required before real training/public output.
- Historical stage names are detected by heuristics. The filter is now stricter, but a future manual archive/promote state is still needed for perfect classification.

Assumptions:
- `stage47_real...` and `stage56_actual...` are protected acceptance evidence and remain visible by default.
- Older `stageXX_...`, smoke, playwright, self_check, separation_eval, test, tmp, and training-stage artifacts are QA noise unless explicitly included.
- Keeping old `/api/models` as an array is required for backward compatibility with existing frontend and tests.
- The browser UI should remain clean by default and reveal historical test records only through a deliberate toggle.

Impossible paths in this stage:
- It is not possible to guarantee "production-quality voice clone" without a real RVC/UVR/VST run and human listening review.
- It is not possible to determine copyright/rights status from filenames or metadata alone.
- It is not possible to distinguish every old stage artifact from a valid user artifact purely by regex forever. Stage59+ should add explicit asset states.

## Runnable Code Structure

Backend:
- `backend/services/smoke_filter.py`
  - Central filter contract: `explain_test_data_filter_reason(row, kind=...)`.
  - Error posture: metadata parsing falls back to `{}`; unknown rows return no reason instead of crashing.
  - Coordinator fix: machine stage prefixes now require `stageNN_`, `stageNN-`, or exact `stageNN`; human voice names like `Stage50 Voice...` are not hidden by name alone.
  - Coordinator fix: protected real-stage names are narrowed to current accepted `stage47` / `stage56` evidence so old `stage26_real_long_*` is hidden by default.
- `backend/services/job_service.py`
  - `/api/jobs` and `/api/jobs/summary` default-hide test jobs and jobs tied to hidden test models.
  - Returns `hidden_test_count` for full-list visibility, not page-local guesses.
- `backend/services/model_service.py`
  - `list_models(...)` keeps old array semantics.
  - New `hidden_test_model_count(...)` calculates model noise count with the same unavailable/test-data parameters.
- `backend/main.py`
  - Existing `/api/models` remains backward-compatible as an array.
  - New `/api/models/summary` returns `model_count`, `usable_count`, `hidden_test_count`, `hidden_test_model_count`, and include flags.
  - `/api/batches`, `/api/batches/{id}/tracks`, and `/api/factory/summary` expose default-hidden QA counts.

Frontend:
- `frontend/js/jobs.js`
  - Reads backend `hidden_test_count` before falling back to client-side page diff.
- `frontend/js/models.js`
  - Reads `/api/models` and `/api/models/summary` in parallel.
  - Keeps old list compatibility and uses summary for accurate hidden model count.
- `frontend/js/factory/main.js`
  - Combines hidden batch, track, and model counts for the Factory "show test records" toggle.
- `frontend/js/studio.js`
  - Uses backend job hidden count for cover-product library visibility.

Tests:
- `tests/api/test_stage58_user_noise_filter_api.py`
  - Verifies jobs/models/batches/tracks/factory summary default-hide test noise.
  - Verifies `/api/models/summary` hidden-count contract.
  - Verifies old `stage26_real_long_*` is hidden while human `Stage50 Voice...` naming is not falsely hidden.

## Error Handling

- Backend metadata parsing is defensive: invalid JSON does not break filtering.
- `/api/models` retains existing try/except downgrade behavior and returns an empty list on model-loading failure.
- Frontend model summary calls use `.catch(() => null)` so old or not-yet-restarted backends do not break the page.
- Frontend hidden-count rendering falls back to page-local filtering if a backend count is missing.
- Isolated self-check uses a copied DB and ignores temp cleanup lock errors, so smoke writes do not pollute the real DB.

## Validation Results

Commands run:
- `python -m pytest -q`
  - Result: `114 passed, 2 warnings`
- `node frontend\playwright_stage58_user_noise_ui_smoke.cjs`
  - Result: pass on Dashboard / Factory / Studio
- `python backend\verify_stage58_material_quality.py`
  - Result: `STAGE58_MATERIAL_QUALITY PASS`
  - Evidence: `entries=17`, `verified_usable=10`, `quarantine_recommended=6`
- Isolated DB self-check through copied `backend/feishark.db`
  - Result: `CODE_STRUCTURE_SUMMARY PASS`, `RUNTIME_ENVIRONMENT_SUMMARY PASS`, `SELF_CHECK_SUMMARY PASS`
- Backend compile:
  - Result: pass for `backend/main.py`, `backend/db.py`, `backend/self_check.py`, and Stage58 service files
- Frontend ESM syntax check:
  - Result: pass for `frontend/js/jobs.js`, `frontend/js/models.js`, `frontend/js/factory/main.js`, `frontend/js/studio.js`

Live API after restart:
- `/api/jobs?limit=100`: `items_count=22`, `hidden_test_count=416`, known noise hits empty
- `/api/jobs/summary`: `hidden_test_count=416`, known noise hits empty
- `/api/models`: `items_count=3`, known noise hits empty
- `/api/models/summary`: `model_count=3`, `hidden_test_model_count=54`, known noise hits empty
- `/api/batches?limit=50`: `items_count=0`, `hidden_test_count=80`, known noise hits empty
- `/api/factory/summary`: `batch_count=0`, `track_count=0`, `hidden_test_batch_count=80`, `hidden_test_track_count=138`, known noise hits empty

Service state:
- `http://127.0.0.1:8000/api/health`: ok, `needs_restart=false`
- `127.0.0.1:8000` listener: one owning process on port 8000
- RVC 7866: offline by design for this stage

## Remaining Risks

- UI is cleaner by default, but the product still needs a formal asset lifecycle: user asset, QA evidence, quarantined artifact, archived test record, release candidate.
- Material quality PASS is not listening-quality PASS. Real audio acceptance still needs UVR/RVC A/B runs and human review.
- The current regex filter is good enough for Stage58 but should not become the permanent source of truth.
- `shared_data` remains local and ignored; raw audio should not be pushed to GitHub.

## Next Stage Recommendation

Stage59 should be a product/backend joint stage:
- Build explicit user asset states instead of relying only on regex hiding.
- Add "promote to user asset" and "archive as QA/test evidence" operations.
- Keep test records hidden by default, but make QA drawers searchable.
- Prepare the real-material short-chain validation path: UVR A/B first, then fresh RVC cover only after the user explicitly starts 7866.

