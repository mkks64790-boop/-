# Stage 56B RVC Cover Smoke Report

Generated at: 2026-06-03 04:07:49 +08:00

## Result

Status: `blocked`

Actual RVC cover smoke run: `no`

Submitted cover job: `no`

Job ID: `N/A`

Reason: no 20-60 second legal short material that is also suitable as an RVC cover source was quickly confirmed inside the allowed project locations. Per the Stage56 boundary, no network song, broad D-drive scan, long training, or repeated hard run was attempted.

## Preflight Evidence

- Live services: FastAPI responded at `http://127.0.0.1:8000/api/health`; RVC WebUI responded at `http://127.0.0.1:7866`; RVC root is `D:\RVC\RVCv2`.
- Live backend route drift: the already-running FastAPI process returned `404` for `/api/training/gpu-status` and `/api/training/observer/latest`, while current source exposes those routes. I did not restart the service because other agents may be working.
- Current-source GPU check via TestClient: `gpu_acceleration_available=true`, `device_mode=cuda`, selected GPU `[0]`, torch `2.11.0+cu128`, GPU `NVIDIA GeForce RTX 5060`, utilization observed at `0-2%`, memory observed around `2743/8151 MB` used by `nvidia-smi`.
- Training observer via current source: latest completed training observer read `train_b78378f2068e`; model `v_d4d7e1c1` itself is sourced from `train_7f4d6b4e611e`.
- Model `v_d4d7e1c1`: `usable=true`, `.pth` exists at `D:\FeiSharkStudio-v2\shared_data/weights/朱朱_stage47_single_long.pth`, `.index` exists at `D:\FeiSharkStudio-v2\shared_data/weights/朱朱_stage47_single_long.index`.
- Cover preflight via current source: `ok=true`; RVC service online, runtime sync ok, model choice ok, model load probe ok.
- Running compute jobs: no `processing` train or cover jobs found. Existing pending cover jobs were historical/stale and not requeued.

## Material Check

Allowed locations checked:

- `shared_data\material_library`
- `shared_data\separation_eval\input`

Findings:

- `shared_data\separation_eval\input` does not exist.
- `shared_data\material_library\authorized_dry_vocals\user\朱朱干声唱.mp3`: user local backup, rights pending, `2709.995s`, too long for short smoke.
- `shared_data\material_library\authorized_dry_vocals\user\朱朱干声.mp3`: user local backup, rights pending, `932.702s`, too long for short smoke.
- `shared_data\material_library\cover_source_candidates\user\归不了岸的船.mp3`: user local cover-source candidate, manual rights confirmation pending, `180.036s`, too long; not used.
- `shared_data\material_library\authorized_dry_vocals\public_domain_voice\jimmy_wales_voice_cc0.ogg`: CC0, `9.533s`, too short and speech only.
- `shared_data\material_library\authorized_dry_vocals\public_domain_voice\librivox_abou_hunt_py_public_domain.mp3`: Public Domain, `108.991s`, too long and speech only.
- `shared_data\material_library\separation_benchmarks\public_domain\acoustic_guitar_sample_public_domain.ogg`: Public Domain, `48.878s`, but manifest classifies it as instrument-only separation/waveform smoke material, not an RVC cover source; not used.
- `shared_data\material_library\separation_benchmarks\synthetic\synthetic_vowel_tone_mix_8s.wav`: generated synthetic, `8.000s`, too short and not a real cover source.

Conclusion: no eligible 20-60 second legal vocal/cover-source material was confirmed, so no cover job was submitted.

## Cover Artifact Evidence

Because no cover job was submitted:

- `cover_upload`: not created.
- `cover_preflight`: passed as standalone preflight only; no job-bound log.
- `cover_split` / `cover_infer` / `cover_mix`: not run.
- `cover_master`: not generated.
- Download URL: `N/A`.
- Studio URL: `N/A`.
- Audio size/duration/sample rate: `N/A`.

Note: current backend stage naming uses `cover_voice` for RVC inference, while the Stage56 prompt asks for `cover_infer`; this was not modified because no smoke job was run.

## Engine Roadmap State

- RVC: engine and model preflight are ready, but real short cover smoke is blocked on a lawful 20-60 second vocal/cover-source asset.
- UVC/SVC: not developed, not connected, not trained in this stage.
- VST: not connected to a real plugin host; remains a future Studio post-processing/export direction.

## Modified Files

- `docs\agent-md\worker\stage-56b-rvc-cover-smoke-report.md`

No backend, frontend, RVC third-party source, historical job, model, or audio asset was modified by this Stage56B pass.

## Verification Commands

- `python -m py_compile backend\main.py backend\services\training_observer_service.py backend\services\training_gpu_service.py backend\services\preflight_service.py` -> pass.
- `python -m pytest tests\api\test_stage55_training_observer_api.py -q` -> `2 passed`.
- `python -m pytest tests\api\test_stage54_training_gpu_api.py -q` -> `2 passed`.
- `python -m pytest -q` -> `99 passed`.
- `python -m backend.self_check` -> `CODE_STRUCTURE_SUMMARY PASS`, `RUNTIME_ENVIRONMENT_SUMMARY PASS`, `SELF_CHECK_SUMMARY PASS`.
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\jobs.js','rb').read())"" | node --input-type=module --check"` -> pass.
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\cover.js','rb').read())"" | node --input-type=module --check"` -> pass.
- `frontend\js\studio.js` syntax check was not run because Studio was not modified.

## Next Step

Place or identify one rights-confirmed 20-60 second project-local vocal/cover-source file under `shared_data\material_library\cover_source_candidates\user` or `shared_data\separation_eval\input`, then rerun exactly one short cover smoke with model `v_d4d7e1c1`. If live HTTP API checks are required, restart or reload the FastAPI backend after coordinating with other agents so the running service picks up the Stage54/55 routes.
