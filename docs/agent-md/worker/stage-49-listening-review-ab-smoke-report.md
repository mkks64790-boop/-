# Stage 49 Listening Review A/B Smoke Report

## Status

PASS.

## Scope

Stage49 added a small, real acceptance layer for listening review. It did not trigger training, RVC inference, UVR separation, or cover generation.

The goal was to let Studio record whether a generated artifact sounds usable after A/B listening.

## Backend

Added artifact-level listening review storage through `job_artifacts.metadata_json`.

New APIs:

- `GET /api/jobs/{job_id}/source-audio/download`
- `GET /api/jobs/{job_id}/artifacts/{artifact_id}/review`
- `PATCH /api/jobs/{job_id}/artifacts/{artifact_id}/review`

Review schema:

- `verdict`: `unreviewed`, `needs_work`, `usable`, `release_candidate`, or `rejected`
- `overall_score`: 1-5 or null
- `vocal_score`: 1-5 or null
- `noise_score`: 1-5 or null
- `mix_score`: 1-5 or null
- `notes`: trimmed text
- `reviewed_at`
- `schema=stage49_listening_review_v1`

## Frontend

Studio Inspector now includes `试听验收 A/B`.

- A track: current final artifact in the main Studio player.
- B track: original job source audio through `/source-audio/download`.
- Review verdict and four score sliders can be saved.
- Saved review is loaded back from artifact metadata.

## Validation

Commands run:

```powershell
python -m pytest tests\api\test_stage49_listening_review_api.py -q
python -m pytest tests\api\test_track_studio_versions_api.py -q
node frontend\playwright_stage49_listening_review_smoke.cjs
node frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
python -m pytest -q
python -m backend.self_check
```

Results:

- Stage49 API tests: `3 passed`.
- Track Studio versions regression: `6 passed`.
- Stage49 browser smoke: PASS.
- Stage47 browser regression: PASS.
- Full pytest: `74 passed, 2 warnings`.
- Self-check: `SELF_CHECK_SUMMARY PASS`.

## Real Smoke Note

The Stage49 browser smoke saved a non-human review note on the Stage47 artifact:

```text
stage49 browser smoke only - not a human quality verdict
```

This proves persistence only. It is not a quality judgment.
