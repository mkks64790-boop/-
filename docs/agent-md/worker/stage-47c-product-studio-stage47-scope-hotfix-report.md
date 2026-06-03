# Stage 47C Product Studio Stage47 Scope Hotfix Report

## Status

PASS.

## Scope

This hotfix closed the Stage47 Studio scope labeling gap found during architect validation.

Real Stage47 closure facts:

- Training job: `train_7f4d6b4e611e`
- Model: `v_d4d7e1c1` / `朱朱_stage47_single_long`
- Cover job: `task_b2272d133fff`
- Artifact: `art_f99f7e4afb10`
- Studio URL: `/studio?job_id=task_b2272d133fff&artifact_id=art_f99f7e4afb10`

No training, RVC inference, or cover processing was triggered by this hotfix.

## Changes

- `frontend/js/studio.js`
  - Added robust Stage47 Studio hints for the known real closure IDs.
  - `isStage47StudioJob()` now checks model id, generated model fields, model source lineage, artifact names, artifact download URL, and metadata.
  - Studio now labels the real Stage47 artifact as `Stage47 短 smoke / 完整 cover`.

- `backend/main.py`
  - Job detail now falls back to registered voice model metadata when job metadata lacks model source fields.
  - `/api/jobs/task_b2272d133fff` now returns:
    - `voice_model_origin_kind=trained_local`
    - `voice_model_source_job_id=train_7f4d6b4e611e`
    - `voice_model_source_summary` from the registered model lineage.

## Validation

Commands run:

```powershell
node frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
node frontend\playwright_stage48b_memory_lab_smoke.cjs
python -m pytest -q
python -m backend.self_check
```

Results:

- Stage47 browser smoke: PASS.
- Memory Lab browser smoke: PASS.
- Pytest: `71 passed, 2 warnings`.
- Backend self-check: `SELF_CHECK_SUMMARY PASS`.
- ESM syntax check for key frontend modules: PASS.

## Notes

FastAPI was restarted after the backend patch. RVC WebUI on port `7866` was not touched.
