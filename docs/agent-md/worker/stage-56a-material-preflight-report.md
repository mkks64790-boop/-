# Stage56A Material And Preflight Audit Report

Generated at: 2026-06-03

## Scope

- Project root: `D:\FeiSharkStudio-v2`
- Architect prompt read: `docs\agent-md\architect\stage-56-rvc-short-cover-smoke-and-engine-sequencing-prompt.md`
- This audit did not run RVC cover jobs, UVR, or training.
- This audit did not intentionally modify third-party `D:\RVC\RVCv2`.
- Default live API checked: `http://127.0.0.1:8000`

## Executive Conclusion

Recommendation: **do not allow the Stage56 RVC smoke yet**.

Blocking reasons:

- `GET /api/training/gpu-status` on the live default backend returned HTTP 404, so the required GPU-status API gate is not available from the current runtime.
- `GET /api/training/observer/latest` on the live default backend returned HTTP 404, so the required training-observer API gate is not readable from the current runtime.
- A legal 20-60 second project-local file exists, but it is an instrument-only public-domain separation benchmark, not a clearly suitable short vocal or cover-source candidate for meaningful RVC cover smoke.

Partial passes:

- Physical GPU appears idle enough for a short smoke: `NVIDIA GeForce RTX 5060`, total `8151 MB`, used `2664 MB`, free `5232 MB`, GPU utilization `0%`.
- Model `v_d4d7e1c1 / 朱朱_stage47_single_long` is registered with `usable=true`, `pth_exists=true`, `index_exists=true`.
- `GET /api/preflight/cover?model_id=v_d4d7e1c1` returned `ok=true` on the live default backend.

Important caution:

- The current `run_cover_preflight()` implementation probes RVC runtime model loadability and can call model/index sync helpers. This audit made the requested cover-preflight API call once, then stopped further preflight calls after confirming the side-effect risk in code.

## API Audit

| Check | Result | Evidence |
| --- | --- | --- |
| `GET /api/health` | PASS | Returned `status=ok`, `version=2.2.0`, RVC engine online at `http://127.0.0.1:7866`, `rvc_root=D:\RVC\RVCv2`. |
| `GET /api/training/gpu-status` | FAIL | Returned HTTP 404 on `http://127.0.0.1:8000/api/training/gpu-status`. |
| `GET /api/training/observer/latest` | FAIL | Returned HTTP 404 on `http://127.0.0.1:8000/api/training/observer/latest`. |
| `GET /api/models/v_d4d7e1c1` | PASS | Returned model detail with `usable=true`, `source_job_id=train_7f4d6b4e611e`, source job status completed, `pth_exists=true`, `index_exists=true`. |
| `GET /api/preflight/cover?model_id=v_d4d7e1c1` | PASS | Returned `ok=true` and no errors. |

Runtime interpretation:

- The current default backend appears stale relative to the Stage54/55 code because `backend\main.py` contains the training GPU and observer routes, but the process at port 8000 returns 404 for both.
- I did not start a replacement backend because the intermediate instruction required quick report landing and no long-running actions.

## GPU Audit

Command:

```powershell
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu --format=csv,noheader,nounits
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits
```

Observed:

- GPU: `NVIDIA GeForce RTX 5060`
- Memory: total `8151 MB`, used `2664 MB`, free `5232 MB`
- Utilization: `0%`
- Running GPU-visible processes included a long-running `D:\Miniconda3\envs\rvc\python.exe` process, plus normal desktop/Codex/browser processes.

Conclusion:

- Physical GPU state is likely idle enough for a short smoke.
- The formal Stage56 API gate is still blocked because `/api/training/gpu-status` is not available on the live default backend.

## Model Audit

Model: `v_d4d7e1c1 / 朱朱_stage47_single_long`

API evidence from `GET /api/models/v_d4d7e1c1`:

- `voice_model_id`: `v_d4d7e1c1`
- `legacy_model_id`: `v_d4d7e1c1`
- `model_name`: `朱朱_stage47_single_long`
- `source_job_id`: `train_7f4d6b4e611e`
- `source_job_current_stage`: `train_register_model`
- `status`: `ready`
- `usable`: `true`
- `pth_exists`: `true`
- `index_exists`: `true`

Filesystem evidence:

- `D:\FeiSharkStudio-v2\shared_data\weights\朱朱_stage47_single_long.pth`
  - Size: `55229665` bytes
- `D:\FeiSharkStudio-v2\shared_data\weights\朱朱_stage47_single_long.index`
  - Size: `292128899` bytes

Conclusion:

- Model asset gate is PASS for engineering availability.
- This does not assert final voice quality or commercial readiness.

## Cover Preflight Audit

Endpoint:

```text
GET http://127.0.0.1:8000/api/preflight/cover?model_id=v_d4d7e1c1
```

Observed result:

- `ok=true`
- Required backend modules existed.
- RVC service reported online.
- Model pth check passed.
- RVC runtime/model choice/load probe returned pass.

Conclusion:

- Cover preflight gate is PASS on the currently running default backend.
- Because the implementation can sync model/index files into the RVC runtime, future audits should treat this endpoint as not purely read-only unless the implementation is changed.

## Material Audit

Search boundary:

- Checked only `D:\FeiSharkStudio-v2\shared_data\material_library`
- Checked only `D:\FeiSharkStudio-v2\shared_data\separation_eval\input`
- Did not scan the rest of D drive.
- Did not download songs.

`shared_data\separation_eval\input` result:

- Directory missing: `D:\FeiSharkStudio-v2\shared_data\separation_eval\input`

Audio files quickly found in `shared_data\material_library`:

| Path | Duration | Rights/source note | Stage56A judgment |
| --- | ---: | --- | --- |
| `shared_data\material_library\authorized_dry_vocals\public_domain_voice\jimmy_wales_voice_cc0.ogg` | `9.53s` | CC0 per Stage53-A report | Too short for 20-60s gate. Speech, not singing. |
| `shared_data\material_library\authorized_dry_vocals\public_domain_voice\librivox_abou_hunt_py_public_domain.mp3` | `108.99s` | Public Domain per Stage53-A report | Too long for 20-60s gate. Speech, not singing. |
| `shared_data\material_library\authorized_dry_vocals\user\朱朱干声.mp3` | `932.70s` | User-provided local dry vocal, manual rights boundary | Too long. Training candidate only with manual confirmation, not short smoke. |
| `shared_data\material_library\authorized_dry_vocals\user\朱朱干声唱.mp3` | `2709.99s` | User-provided local dry vocal, manual rights boundary | Too long. Do not use for short smoke. |
| `shared_data\material_library\cover_source_candidates\user\归不了岸的船.mp3` | `180.04s` | Manual-review-only cover source candidate per Stage53 report | Too long and manual-review-only. Do not use by default. |
| `shared_data\material_library\separation_benchmarks\public_domain\acoustic_guitar_sample_public_domain.ogg` | `48.88s` | Public Domain per Stage53-A report | Duration/legal gate PASS, but instrument-only; weak RVC cover-smoke material. |
| `shared_data\material_library\separation_benchmarks\synthetic\synthetic_vowel_tone_mix_8s.wav` | `8.00s` | Internal synthetic | Too short. |

Material conclusion:

- There is one legal 20-60s project-local file: `shared_data\material_library\separation_benchmarks\public_domain\acoustic_guitar_sample_public_domain.ogg`.
- It should be treated as `not_training_candidate` and only as a waveform/separation/connectivity benchmark, not a meaningful RVC vocal-cover source.
- No clearly legal 20-60s vocal or song cover-source candidate was quickly confirmed.

## Final Gate Decision

Stage56 RVC smoke should remain **blocked / needs_backend_refresh + needs_material_confirmation**.

Allow smoke only after all of these are true:

- Restart or refresh the live backend so `GET /api/training/gpu-status` returns a real status instead of 404.
- Confirm `GET /api/training/observer/latest` returns the latest completed training observer, ideally `train_7f4d6b4e611e`.
- Provide or explicitly approve a 20-60 second project-local vocal or cover-source clip with rights suitable for internal RVC smoke.
- If using the existing public-domain guitar sample anyway, label the run as connectivity-only and do not draw voice-quality conclusions.

## Files Modified

- `docs\agent-md\worker\stage-56a-material-preflight-report.md`

No code files were modified.
