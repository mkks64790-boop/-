# Stage56D Actual RVC Connectivity Smoke Report

Generated at: 2026-06-03

## Scope

- Project root: `D:\FeiSharkStudio-v2`
- Goal: run one short RVC connectivity smoke with existing model `v_d4d7e1c1 / 朱朱_stage47_single_long`.
- Input: `shared_data/separation_eval/input/stage56_librivox_public_domain_voice_30s.mp3`
- Input caveat: Public Domain speech sample, not singing material. This run proves connectivity only, not singing quality.
- Training: not run.
- UVC/SVC: not run.
- VST: not run.
- Third-party `D:\RVC\RVCv2`: not modified.

## Result

- Final status: `completed`
- Job ID: `task_2594c7de4629`
- Model ID: `v_d4d7e1c1`
- Final artifact ID: `art_423574fb9c3c`
- Final artifact type: `cover_master`
- Download URL: `/api/jobs/task_2594c7de4629/artifacts/art_423574fb9c3c/download`
- Studio URL: `/studio?job_id=task_2594c7de4629&artifact_id=art_423574fb9c3c`

## Important Timeline

1. First attempt submitted exactly one cover job.
2. UVR/separation completed.
3. The pipeline failed at `cover_pitch` with:

```text
ValueError: operands could not be broadcast together with shapes (1944,) (2048,) (1944,)
```

4. Root cause was isolated to the optional AudioPipeline pitch-fix stage on short/boundary-frame audio, before RVC inference.
5. `backend/pitch_processor.py` was patched with a safe fallback: when this specific frame-broadcast error appears, copy `vocal.wav` to `vocal_fixed.wav`, mark `fallback=copy_original_vocal`, and continue to RVC.
6. The same job `task_2594c7de4629` was reprocessed. No second job was submitted.
7. The job then completed through `cover_voice` and `cover_mix`.

## Stage Evidence

- `upload`: completed, `stage56_librivox_public_domain_voice_30s.mp3`, `481250` bytes.
- `cover_preflight`: completed, model `v_d4d7e1c1`, RVC service online at `http://127.0.0.1:7866`.
- `cover_split`: completed, duration `30.0s`, elapsed `27.49s`.
- `cover_pitch`: completed after fallback, duration `30.0s`, warning retained.
- `cover_voice`: completed, output `vocal_transformed.wav`, duration `29.98s`, elapsed `2.40s`.
- `cover_mix`: completed, output `final_master.wav`, duration `30.0s`, elapsed `4.40s`.

## Final Artifact ffprobe

```json
{
  "codec_name": "pcm_s16le",
  "sample_rate": "44100",
  "channels": 1,
  "duration": "30.000000",
  "size": "2646044"
}
```

## Generated Artifacts

- `cover_split / cover_vocal`: `shared_data/jobs/task_2594c7de4629/artifacts/cover_split/vocal.wav`
- `cover_split / cover_instrumental`: `shared_data/jobs/task_2594c7de4629/artifacts/cover_split/instrumental.wav`
- `cover_pitch / cover_fixed`: `shared_data/jobs/task_2594c7de4629/artifacts/cover_pitch/vocal_fixed.wav`
- `cover_voice / cover_transformed`: `shared_data/jobs/task_2594c7de4629/artifacts/cover_voice/vocal_transformed.wav`
- `cover_mix / cover_master`: `shared_data/jobs/task_2594c7de4629/artifacts/cover_mix/final_master.wav`

## Files Modified

- `backend/pitch_processor.py`
  - Added safe fallback for AudioPipeline frame-broadcast pitch-shift failures.
  - Does not skip RVC. It only skips optional pitch correction when the short-audio pitch stage fails in this known way.
- `shared_data/separation_eval/input/stage56_librivox_public_domain_voice_30s.mp3`
  - Generated local 30-second Public Domain speech smoke input.
- `shared_data/separation_eval/input/stage56_librivox_public_domain_voice_30s.meta.md`
  - Documents rights and caveat: connectivity only, not singing quality or training.

Related subagent reports:

- `docs/agent-md/worker/stage-56a-material-preflight-report.md`
- `docs/agent-md/worker/stage-56b-rvc-cover-smoke-report.md`
- `docs/agent-md/worker/stage-56c-product-entry-smoke-report.md`

## Validation

- `python -m py_compile backend\pitch_processor.py`: passed.
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\jobs.js','rb').read())"" | node --input-type=module --check"`: passed.
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\cover.js','rb').read())"" | node --input-type=module --check"`: passed.
- `python -m pytest -q`: `99 passed`.
- `python -m backend.self_check`: `SELF_CHECK_SUMMARY PASS`.
- `GET /studio?job_id=task_2594c7de4629&artifact_id=art_423574fb9c3c`: HTTP `200`.

## Current Architecture Judgment

- RVC inference path is now proven end-to-end on a 30-second connectivity sample.
- The model can be loaded and used by the local RVC service.
- The optional pitch-fix stage is not robust enough to be a hard blocker for RVC smoke; fallback protection is now required and implemented.
- This run does not prove singing quality because the input is speech, not a song vocal.

## Next Recommendation

Stage57 should use a rights-confirmed 20-60 second singing cover-source clip and run exactly one quality-oriented RVC cover smoke. That stage should listen for:

- converted vocal intelligibility,
- electric/noise artifacts,
- timing drift after UVR and mix,
- whether pitch fallback was used,
- whether the final artifact should enter Studio listening review.

