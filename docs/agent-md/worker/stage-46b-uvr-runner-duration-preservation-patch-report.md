# Stage 46B UVR Runner Duration Preservation Patch Report

## Completion Status

Completed.

The UVR runner duration preservation bug was patched in the FeiShark-controlled runner template. The previous systematic shrinkage (`45s -> 26.807s`, ratio ~`0.595`) is no longer reproduced in the 15s/30s/45s real UVR checks.

## Modified Files

- `backend/vocal_separator.py`
  - Updated `_RUNNER_SCRIPT` so time chunking uses `model_frames=256` directly.
  - Removed the old `chunk_seconds=5 -> ~430 frames -> crop to 256 frames` behavior.
  - Added a hard runtime guard if any time chunk exceeds `model_frames`.
  - Added `librosa.istft(..., length=len(audio))` for waveform length preservation.
  - Added post-UVR duration preservation validation in `split_audio()`.
  - Added audio duration helpers and explicit `duration mismatch` failure message.

- `tests/unit/test_uvr_runner_duration_contract.py`
  - Added template contract tests to prevent reintroducing time-frame cropping.
  - Added duration mismatch guard tests.

- `docs/agent-md/worker/stage-46b-uvr-runner-duration-preservation-patch-report.md`
  - Added this report.

## Safety Confirmation

- `train.py` started: no
- RVC inference called: no
- D: test music moved/deleted/overwritten: no
- Recursive D: scan performed: no
- Silent padding used as fake fix: no

## External AudioPipeline Boundary

I did not manually edit:

```text
C:\Users\ASUS\AudioPipeline\run_uvr5_split.py
```

During real UVR execution, FeiShark regenerated that runner through `_ensure_runner_script()` from the patched template in `backend/vocal_separator.py`. This is the intended FeiShark-controlled generation path.

## Patch Summary

Old behavior:

```text
chunk_seconds = 5
frames_per_chunk = int(5 * 44100 / 512) = 430
model_frames = 256
real = real[:, :model_frames]
```

This discarded about 40% of each time chunk.

New behavior:

```text
frames_per_chunk = model_frames
actual_frames is recorded before padding
last short chunk is padded only for inference
only actual_frames are appended back
ISTFT reconstructs to length=len(audio)
```

The fix preserves real STFT time frames instead of padding silence over a shortened stem.

## Real 15/30/45s Verification

All checks used one approved candidate from:

```text
D:\测试音乐
```

| Input clip | Run id | Original duration | Vocal duration | Instrumental duration | Ratio | Pass >= 0.95 |
|---:|---|---:|---:|---:|---:|---|
| 15s | `stage45r_20260602_193645_40e23d95` | `15.0s` | `15.0s` | `15.0s` | `1.0` | yes |
| 30s | `stage45r_20260602_193705_68741142` | `30.0s` | `30.0s` | `30.0s` | `1.0` | yes |
| 45s | `stage45r_20260602_193728_d0f83e7c` | `45.0s` | `45.0s` | `45.0s` | `1.0` | yes |

Duration mismatch status:

- 15s: `duration_mismatch=false`, risk `low`
- 30s: `duration_mismatch=false`, risk `low`
- 45s: `duration_mismatch=false`, risk `low`

## BLOCK_TRAINING Final Status

Latest verify output:

```text
run_id=stage45r_20260602_193728_d0f83e7c
duration_contract item=1 mismatch=false ratio=1.0 risk=low
BLOCK_TRAINING=false
```

Interpretation:

- The duration-preservation blocker is cleared for the latest real 45s UVR check.
- This does not mean all audio-quality risks are cleared.

## Subjective Audio Quality Risk

No human A/B listening was performed in this backend stage.

Metrics still show source-level clipping risk on the selected test track:

- `original_excerpt` clipping risk remains `high`.
- Vocal/instrumental stem clipping risk is `low`.
- Duration is now preserved.

Risk statement:

```text
The duration contract is fixed, but product-side A/B listening is still required before resuming broader training/cover acceptance.
```

## Tests Run

- `python -m pytest -q tests\unit\test_uvr_runner_duration_contract.py`
  - PASS: `3 passed`

- `python backend\verify_stage45r_separation_quality_audit.py --execute --limit 1 --clip-seconds 15`
  - PASS
  - Run id: `stage45r_20260602_193645_40e23d95`
  - Ratio: `1.0`

- `python backend\verify_stage45r_separation_quality_audit.py --execute --limit 1 --clip-seconds 30`
  - PASS
  - Run id: `stage45r_20260602_193705_68741142`
  - Ratio: `1.0`

- `python backend\verify_stage45r_separation_quality_audit.py --execute --limit 1 --clip-seconds 45`
  - PASS
  - Run id: `stage45r_20260602_193728_d0f83e7c`
  - Ratio: `1.0`

- `python -m pytest -q`
  - PASS: `67 passed, 2 warnings`

- `python -m backend.self_check`
  - PASS: `SELF_CHECK_SUMMARY PASS`

- `python backend\verify_stage45r_separation_quality_audit.py`
  - PASS: `STAGE45R_AUDIT_SUMMARY PASS`
  - Latest run reports `BLOCK_TRAINING=false`

## Remaining Risks

- Product-side A/B playback still needs to confirm perceived separation quality.
- Source clipping remains visible in metrics for the selected test track.
- Older Stage45R runs still contain historical mismatch artifacts; use the latest fixed run ids above for duration-preservation acceptance.
