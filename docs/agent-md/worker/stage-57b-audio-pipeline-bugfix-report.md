# Stage57B Audio Pipeline Bugfix Report

Generated at: 2026-06-03

## Scope

- Project root: `D:\FeiSharkStudio-v2`
- Reviewed cover pipeline stages: `cover_split`, `cover_pitch`, `cover_voice`, `cover_mix`
- No long training was run.
- No new real cover job was submitted.
- Existing Stage56 evidence was read only, especially `task_2594c7de4629` and the known pitch error:
  `ValueError: operands could not be broadcast together with shapes (1944,) (2048,) (1944,)`
- Did not modify `D:\RVC\RVCv2` or `D:\AudioPipeline`.

## Bugs Found

- Stage56 pitch fallback was still too broad for an operational contract: it matched any pitch error containing `operands could not be broadcast together` and `(2048`, so unrelated pitch failures involving `2048` could be mislabeled as safe fallback.
- The fallback contract had no direct unit test coverage for success shape, `fallback` field, missing source protection, or unknown-error rejection.
- `CoverStrategy` could mark a stage completed after calling artifact registration even if no expected artifacts were registered. The completed stage log also did not carry artifact IDs, making stage/artifact mismatch harder to detect.
- Cover audio modules used top-level `from db import ...` inside package-imported code. In isolated or package contexts this can load a separate `db` module and bypass the patched `backend.db` state.
- `merge_master_audio()` marked success based on computed array length, not on a post-write `final_master.wav` WAV probe. A bad/missing output or wrong sample rate could pass until later artifact quality reads.

## Fixes

- Tightened `backend/pitch_processor.py` fallback matching to only the known short-frame numpy broadcast shape: `(N,) (2048,) (N,)` with `0 < N < 2048`.
- Hardened pitch fallback copy so the source must be an existing file and input/output paths cannot be identical.
- Added package-safe DB imports in `pitch_processor`, `vocal_separator`, `voice_changer`, and `audio_mixer`.
- Added `EXPECTED_COVER_STAGE_ARTIFACTS` enforcement in `backend/strategies/cover_strategy.py`; incomplete artifact registration now logs stage failure instead of completed.
- Added artifact IDs to each completed cover stage log detail.
- Added an audio mixer WAV probe for `final_master.wav` existence, duration, and `44100` sample-rate contract before marking the task successful.
- Added `tests/unit/test_stage57_audio_pipeline_contract.py` covering:
  - known pitch frame-broadcast fallback only,
  - fallback success and `fallback=copy_original_vocal`,
  - unknown pitch error rejection,
  - missing source protection,
  - RVC stage uses `vocal_fixed.wav`,
  - stage log/artifact type consistency,
  - final master duration/sample-rate quality summary.

## Not Fixed

- Did not replace the current pedalboard-based cover mixer with ffmpeg; the audited code path is still `merge_master_audio()`.
- Did not modify `backend/services/asset_service.py` because it was outside the allowed write scope.
- Did not change UVR separation logic beyond safe DB import; the existing duration-preservation contract was validated by its existing tests.
- Did not run a real RVC cover quality smoke or create new production artifacts.
- Did not touch third-party RVC or AudioPipeline code.

## Validation

- `python -m py_compile backend\pitch_processor.py backend\vocal_separator.py backend\voice_changer.py backend\audio_mixer.py backend\strategies\cover_strategy.py`
  - Result: pass
- `python -m pytest tests\unit\test_stage57_audio_pipeline_contract.py -q`
  - Result: `5 passed`
- `python -m pytest tests\unit\test_uvr_runner_duration_contract.py tests\api\test_stage51_artifact_quality_gate_api.py -q`
  - Result: `7 passed`

Observed warnings were only FastAPI `on_event` deprecation warnings from existing code.

## Risks

- The pitch fallback remains a pragmatic bypass for one known AudioPipeline short-frame bug; it does not improve pitch quality for that case.
- `asset_service.register_cover_stage_outputs()` still owns the production artifact filename/type map. Because it was outside this stage's write scope, Stage57B only enforced counts and tested the strategy contract.
- Final audio quality is still a metadata/quality-gate scan, not a listening verdict. A real short singing cover smoke is still needed for subjective quality.
