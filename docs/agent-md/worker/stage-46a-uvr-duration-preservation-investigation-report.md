# Stage 46A UVR Duration Preservation Investigation Report

## Completion Status

Completed.

This stage investigated why UVR separation turns a 45s input excerpt into ~26.807s vocal/instrumental stems. No training was started, no RVC inference was called, and no D: test-music files were moved, deleted, renamed, or overwritten.

## Safety Confirmation

- `train.py` started: no
- RVC inference called: no
- D: test music modified: no
- Full recursive D: scan performed: no
- External `C:\Users\ASUS\AudioPipeline` modified: no
- Silent padding used as a fake fix: no

## Existing Blocking Fact

Latest Stage45R quality run before this investigation:

```text
stage45r_20260602_171704_201ec7ff
```

Observed:

```text
original_excerpt.wav = 45.0s
vocal.wav            = 26.807s
instrumental.wav     = 26.807s
duration_ratio       = 0.5957
duration_mismatch    = true
duration_risk        = high
BLOCK_TRAINING       = true
```

## Controlled Comparison Runs

All comparison runs used one approved candidate from `D:\测试音乐`, with `limit=1`, and explicit capped clip lengths.

| Input clip | Run id | Original duration | Vocal duration | Instrumental duration | Ratio | Risk |
|---:|---|---:|---:|---:|---:|---|
| 15s | `stage45r_20260602_191113_e7227402` | `15.0s` | `8.928s` | `8.928s` | `0.5952` | high |
| 30s | `stage45r_20260602_191133_a85edf70` | `30.0s` | `17.868s` | `17.868s` | `0.5956` | high |
| 45s | `stage45r_20260602_191152_04d2c1ba` | `45.0s` | `26.807s` | `26.807s` | `0.5957` | high |

Conclusion from comparison:

- The mismatch is systematic and proportional.
- This is not a 45-second boundary-only issue.
- The ratio is stable at about `0.595`.

## Root Cause Candidate Ranking

### 1. Highest confidence: UVR runner crops each 5s STFT chunk from ~430 frames to 256 frames

Evidence path:

- `D:\FeiSharkStudio-v2\backend\vocal_separator.py`
- `C:\Users\ASUS\AudioPipeline\run_uvr5_split.py`

Critical lines observed:

```python
model_frames = 256
chunk_seconds = 5
frames_per_chunk = int(chunk_seconds * sr / hop_length)
```

At `sr=44100`, `hop_length=512`, and `chunk_seconds=5`:

```text
frames_per_chunk = int(5 * 44100 / 512) = 430
```

Then the runner does:

```python
if real.shape[1] > model_frames:
    real = real[:, :model_frames]
    imag = imag[:, :model_frames]
```

That means each 5s chunk is truncated from about 430 time frames to 256 time frames before model inference.

Expected ratio:

```text
256 / 430 = 0.5953
```

Measured ratios:

```text
15s -> 0.5952
30s -> 0.5956
45s -> 0.5957
```

This matches the observed duration loss almost exactly.

### 2. Secondary issue: ISTFT output does not force original sample length

The runner calls:

```python
librosa.istft(vocal_spec, hop_length=hop_length, win_length=n_fft, window='hann', center=True)
```

It does not pass `length=len(audio)`. Even after fixing chunk cropping, duration preservation should explicitly force or verify final length.

This is likely not the primary cause of the `0.595` ratio, but it is a contract hardening issue.

### 3. Lower likelihood: FeiShark artifact copy/rename logic

The FeiShark wrapper copies/normalizes output names after runner execution. The shortened duration is already present in the runner output, and the original excerpt itself is correctly clipped to the requested duration.

So the copy/rename/artifact layer is not the root cause.

### 4. Lower likelihood: ffmpeg trimming parameters

The generated `original_excerpt.wav` durations are correct:

- `15.0s`
- `30.0s`
- `45.0s`

Therefore ffmpeg clipping is not the cause.

### 5. Model replacement is not the first fix

The evidence points to runner chunk framing/truncation before any model-quality judgment. Switching UVR model or moving to MDX23C may be useful later for quality, but it should not be the first duration-preservation fix.

## Recommended Fix Strategy

### Real fix

Update the UVR runner logic so it never crops real source time frames away.

Preferred approach:

1. Process STFT in model-sized windows:

```text
frames_per_chunk = model_frames
```

2. For each chunk:

- If `actual_frames < model_frames`, pad to `model_frames`.
- Run inference.
- Append only `actual_frames` frames from the output.
- Never pass a chunk larger than `model_frames` and then crop it.

3. Reconstruct with duration preservation:

```python
librosa.istft(..., length=len(audio))
```

4. Add a post-run hard check:

```text
abs(output_duration - input_duration) / input_duration <= 0.05
```

If the check fails, keep `BLOCK_TRAINING=true`.

### Safe implementation boundary

Do not directly hand-edit `C:\Users\ASUS\AudioPipeline` as the durable fix.

Safer next implementation:

- Update FeiShark-controlled `backend/vocal_separator.py` runner template.
- Let FeiShark regenerate `run_uvr5_split.py`.
- Or copy the runner into a FeiShark-controlled location and call that explicitly.

### Temporary fallback

Allowed:

- Continue exposing A/B playback for review.
- Continue reporting `duration_mismatch=true`.
- Keep training and formal cover blocked.

Not allowed:

- Padding 26.807s stems with silence to 45s and declaring the issue fixed.
- Resuming training while duration mismatch remains high.

## Can Training Resume?

No.

`BLOCK_TRAINING` remains `true`.

Reason:

- The separation layer systematically loses about 40% of source duration.
- Until UVR output duration is preserved, training and formal cover outputs would be based on corrupted stems.

## Tests Run

- `python backend\verify_stage45r_separation_quality_audit.py --execute --limit 1 --clip-seconds 15`
  - PASS
  - Run id: `stage45r_20260602_191113_e7227402`
  - Output ratio: `0.5952`

- `python backend\verify_stage45r_separation_quality_audit.py --execute --limit 1 --clip-seconds 30`
  - PASS
  - Run id: `stage45r_20260602_191133_a85edf70`
  - Output ratio: `0.5956`

- `python backend\verify_stage45r_separation_quality_audit.py --execute --limit 1 --clip-seconds 45`
  - PASS
  - Run id: `stage45r_20260602_191152_04d2c1ba`
  - Output ratio: `0.5957`

- `python -m pytest -q`
  - PASS: `64 passed, 2 warnings`

- `python -m backend.self_check`
  - PASS: `SELF_CHECK_SUMMARY PASS`

- `python backend\verify_stage45r_separation_quality_audit.py`
  - PASS: `STAGE45R_AUDIT_SUMMARY PASS`
  - Latest run still reports `BLOCK_TRAINING=true`

## Final Engineering Judgment

Most likely root cause:

```text
The UVR runner uses 5-second chunks but crops each chunk to the model's fixed 256-frame input window, causing systematic duration shrinkage of about 256/430 = 0.595.
```

Recommended next stage:

```text
Patch the FeiShark-controlled UVR runner template to process model_frames-sized windows, preserve actual frame counts, and force/verify output length.
```

Training recovery remains blocked until a new 15/30/45 comparison run shows duration ratios close to `1.0`.
