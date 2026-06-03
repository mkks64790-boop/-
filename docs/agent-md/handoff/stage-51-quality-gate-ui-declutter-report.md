# Stage 51: Artifact Quality Gate + Dashboard Declutter

## Scope

- Do not run UVR, RVC inference, or training.
- Do not delete or overwrite the 89 historical `cover_master` artifacts.
- Add an automatic quality gate before human listening review.
- Reduce Dashboard pressure by moving historical panels below the live task workflow.

## Sub-Agent Audit Inputs

- UI audit: Dashboard was overloaded because Stage47 and Memory Lab were forced above Task Center; Factory and Studio still need later product-level cleanup.
- Material audit: local test material exists under `C:\Users\ASUS\Desktop\干声文件` and `D:\测试音乐`; the 89 existing cover masters are mostly historical smoke/short clips and should not be treated as 89 finished songs.

## Implemented

- Added `stage51_artifact_quality_v1` in `backend/services/asset_service.py`.
- Added quality verdicts: `reviewable`, `needs_manual_quality_check`, `blocked_auto`.
- Added WAV header/PCM scan for duration, level, near-silence, short-smoke detection.
- Extended `/api/reviews/artifacts` with `quality_summary`, `quality_verdict`, `quality_flags`, and `quality=` filtering.
- Extended job detail/artifact APIs with final artifact quality fields.
- Dashboard review queue now shows quality counts and excludes `blocked_auto` from the default visible list.
- Factory review routing now shows quality counts and only lists non-blocked artifacts in action groups.
- Dashboard visual order now starts with Task Center, then review queue; Stage47 and Memory Lab are pushed below the active work area.
- Updated Playwright smoke to understand Stage51 quality gate fields.

## Current Real Artifact Result

- Total `cover_master`: 89
- Reviewable: 19
- Manual QC: 0
- Auto blocked: 70
- Most blocked artifacts are under 10 seconds and are not worth manual listening review.

## Validation

- `python -m pytest tests\api\test_stage51_artifact_quality_gate_api.py -q` -> 4 passed.
- `python -m pytest tests\api\test_stage50_review_routing_api.py tests\api\test_stage51_artifact_quality_gate_api.py -q` -> 11 passed.
- `python -m pytest -q` -> 85 passed.
- `python -m backend.self_check` -> `SELF_CHECK_SUMMARY PASS`.
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\jobs.js','rb').read())"" | node --input-type=module --check"` -> pass.
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\factory\main.js','rb').read())"" | node --input-type=module --check"` -> pass.
- `node frontend\playwright_stage50_review_routing_product_smoke.cjs` -> pass, no page errors, no unsafe compute calls.
- Dashboard visual coordinate check: Task Center top `209`, review queue top `1401`, Stage47 top `2769`, Memory Lab top `3298`.

## Remaining Risks

- Quality gate checks basic duration/level only; it does not yet detect all electric-noise artifacts.
- Online "free songs" should not be used unless Public Domain, CC0, or explicitly licensed.
- Factory and Studio still need a proper product layout pass; Stage51 only fixed the highest-impact queue pollution and Dashboard ordering.
