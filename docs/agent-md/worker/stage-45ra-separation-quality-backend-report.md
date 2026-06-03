# Stage 45RA Separation Quality Backend Report

## Completion Status

Completed.

This stage implemented a safe UVR separation quality audit backend path. Real training remains paused. No `train.py` was started, and no RVC inference was called.

## Modified Files

- `backend/services/separation_eval_service.py`
  - Added safe candidate discovery for the approved D: test-music locations.
  - Added dry-run environment checks for ffmpeg, ffprobe, and UVR/AudioPipeline.
  - Added capped execution flow: clip source audio first, then call the existing `vocal_separator.split_audio()` UVR path.
  - Added per-product WAV metrics and `quality_report.json` generation.
  - Added read-only run listing/detail helpers for future UI use.
  - Added subprocess encoding guards for Windows console safety.

- `backend/verify_stage45r_separation_quality_audit.py`
  - Added Stage45R CLI verifier.
  - Default mode is dry-run only.
  - Real execution requires explicit `--execute --limit 3 --clip-seconds 45`.

- `backend/main.py`
  - Added read-only API routes:
    - `GET /api/separation/eval/sources`
    - `GET /api/separation/eval/runs`
    - `GET /api/separation/eval/runs/{run_id}`
  - Did not add a browser-triggered POST execution endpoint, to avoid accidental UVR/GPU load.

- `tests/api/test_stage45r_separation_eval_api.py`
  - Added API contract tests for source discovery and run listing.
  - Added quality report shape test with generated WAV files.
  - Tests do not execute UVR, training, or RVC.

## Candidate Test Music

Discovery scanned the approved fixed directory:

- `D:\测试音乐`

It found 4 candidate files:

- `D:\测试音乐\依邦妮 - 口哨战歌 (DJ版).flac`, duration `248.415s`
- `D:\测试音乐\如愿-孔老师.wav`, duration `260.0s`
- `D:\测试音乐\水果龙仔 - 拉票专用曲 (DJ版).mp3`, duration `220.5s`
- `D:\测试音乐\画心-孔老师.wav`, duration `304.63s`

No recursive full-D scan was performed. Original user files were only read; they were not moved, deleted, renamed, or overwritten.

## Separation Execution

Executed:

```powershell
python backend\verify_stage45r_separation_quality_audit.py --execute --limit 3 --clip-seconds 45
```

Result:

- `STAGE45R_AUDIT_SUMMARY PASS`
- Run id: `stage45r_20260602_171704_201ec7ff`
- Run path: `D:\FeiSharkStudio-v2\shared_data\separation_eval\runs\stage45r_20260602_171704_201ec7ff`
- Source count executed: `3`
- Clip length requested: `45s`
- Execution status: `completed`

Output layout per source:

- `original_excerpt.wav`
- `vocal.wav`
- `instrumental.wav`
- `quality_report.json`

## Output Paths

- `D:\FeiSharkStudio-v2\shared_data\separation_eval\runs\stage45r_20260602_171704_201ec7ff\01_依邦妮_-_口哨战歌__DJ版`
- `D:\FeiSharkStudio-v2\shared_data\separation_eval\runs\stage45r_20260602_171704_201ec7ff\02_如愿-孔老师`
- `D:\FeiSharkStudio-v2\shared_data\separation_eval\runs\stage45r_20260602_171704_201ec7ff\03_水果龙仔_-_拉票专用曲__DJ版`

## Metric Summary

Sample 1: `依邦妮 - 口哨战歌 (DJ版).flac`

- Overall risk: `high`
- Cause: `original_excerpt: clipping risk is high`
- Original excerpt: `45.0s`, `44100Hz`, peak `0.0 dB`, RMS `-7.351 dB`, clipping `high`, HF ratio `0.002287`, ZCR `0.04896`, silence `0.007316`
- Vocal stem: `26.807s`, `44100Hz`, peak `-0.957 dB`, RMS `-25.518 dB`, clipping `low`, HF ratio `0.001655`, ZCR `0.230362`, silence `0.327094`
- Instrumental stem: `26.807s`, `44100Hz`, peak `-0.98 dB`, RMS `-25.531 dB`, clipping `low`, HF ratio `0.001645`, ZCR `0.21788`, silence `0.325811`

Sample 2: `如愿-孔老师.wav`

- Overall risk: `low`
- Cause: no obvious clipping, silence, DC offset, or high-frequency noise metric was detected.
- Original excerpt: `45.0s`, `44100Hz`, peak `-6.131 dB`, RMS `-20.999 dB`, clipping `low`, HF ratio `0.00011`, ZCR `0.055664`, silence `0.039652`
- Vocal stem: `26.807s`, `44100Hz`, peak `-6.956 dB`, RMS `-27.071 dB`, clipping `low`, HF ratio `0.022778`, ZCR `0.534071`, silence `0.711014`
- Instrumental stem: `26.807s`, `44100Hz`, peak `-6.968 dB`, RMS `-27.073 dB`, clipping `low`, HF ratio `0.022645`, ZCR `0.489428`, silence `0.711458`

Sample 3: `水果龙仔 - 拉票专用曲 (DJ版).mp3`

- Overall risk: `medium`
- Cause: `original_excerpt: peak is close to clipping`
- Original excerpt: `45.0s`, `44100Hz`, peak `-0.213 dB`, RMS `-10.035 dB`, clipping `medium`, HF ratio `0.025681`, ZCR `0.106502`, silence `0.024145`
- Vocal stem: `26.807s`, `44100Hz`, peak `-2.893 dB`, RMS `-23.015 dB`, clipping `low`, HF ratio `0.000511`, ZCR `0.243138`, silence `0.416025`
- Instrumental stem: `26.807s`, `44100Hz`, peak `-2.896 dB`, RMS `-23.028 dB`, clipping `low`, HF ratio `0.000501`, ZCR `0.230463`, silence `0.41418`

## Noise Risk Judgment

Current judgment: `medium`, with one `high` source-level clipping case.

The generated stems did not show obvious high-frequency energy spikes by the current coarse metrics. However, two original excerpts are clipped or near-clipped, and all UVR stems are shorter than the 45s source excerpts (`26.807s` output from a 45s clipped input). That duration mismatch is a backend quality risk and should be investigated before resuming real training.

## Suspected Causes

- Source-level clipping or hot mastered material may be contributing to harshness before UVR.
- Current UVR runner output length may be truncated or not preserving the full clipped excerpt duration.
- If audible electric noise still exists during A/B listening despite low high-frequency ratios, inspect UVR model/config and the generated `run_uvr5_split.py` STFT/ISTFT chunking behavior.

## Next Step

- Product Agent should expose A/B listening for `original_excerpt.wav`, `vocal.wav`, and `instrumental.wav`.
- Foundation Agent should inspect why 45s excerpts produce `26.807s` stems before training resumes.
- Do not restart real training until the separation output duration and audible quality are accepted.

## Safety Confirmation

- `train.py` started: no
- RVC inference called: no
- Original D: music files moved/deleted/overwritten: no
- Recursive full-D scan performed: no
- Browser POST execution endpoint added: no

## Test Results

- `python -m pytest -q`
  - PASS: `63 passed, 2 warnings`

- `python -m backend.self_check`
  - PASS: `SELF_CHECK_SUMMARY PASS`

- `python backend\verify_stage45r_separation_quality_audit.py`
  - PASS: `STAGE45R_AUDIT_SUMMARY PASS`
  - Dry-run only, no separation executed.

- `python backend\verify_stage45r_separation_quality_audit.py --execute --limit 3 --clip-seconds 45`
  - PASS: `STAGE45R_AUDIT_SUMMARY PASS`
  - Real clipped UVR audit executed for 3 sources.

## Remaining Risks

- The metric classifier is intentionally coarse; final noise judgment still needs human A/B listening.
- UVR stem duration mismatch must be resolved or explained before using this separation layer as a training input gate.
- The existing `vocal_separator.split_audio()` writes legacy task status rows for eval task ids; this avoids cover/train execution but leaves audit task rows in the DB for traceability.
