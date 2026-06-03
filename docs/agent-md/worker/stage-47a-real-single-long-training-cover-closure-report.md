# Stage 47A Real Single Long Training + Cover Closure Report

## 1. Completion Status

- Status: PASS with runtime refresh note.
- Scope executed: real long dry vocal -> single-file training -> model registration -> trained-model cover smoke -> final artifact download -> Studio-readable contract.
- Source desktop files were not deleted, moved, renamed, or overwritten.
- Existing model `朱朱_recovered_e90` was not overwritten.
- No source-code changes were made in Stage47A. The only file added by this stage is this report.

## 2. Preflight Results

- FastAPI: online at `http://127.0.0.1:8000`.
- RVC WebUI: online at `http://127.0.0.1:7866`.
- RVC process: `D:\Miniconda3\envs\rvc\python.exe infer-web.py --pycmd D:\Miniconda3\envs\rvc\python.exe --port 7866 --noautoopen`.
- Compute slot before Stage47A train: free (`has_active_compute_jobs=False`).
- Latest Stage45R fixed UVR run: `stage45r_20260602_193728_d0f83e7c`, `BLOCK_TRAINING=false`.
- Disk free space observed before execution:
  - C: about 114 GB free.
  - D: about 278 GB free.
- Long dry vocal:
  - Path: `C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3`
  - Size: `108400926` bytes
  - Duration: `2709.9951s` / `45分10秒`
  - Train preflight: PASS
  - Material profile: `single_long_candidate`
  - Recommended route: `single_long_preprocess`
- Short dry vocal:
  - Path: `C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3`
  - Duration: `932.702s` / about `15分33秒`
  - Classification from existing routing: not a compliant single-long candidate.
- Cover music source:
  - Original: `D:\测试音乐\如愿-孔老师.wav`
  - Original duration: `260.000s`
  - Smoke clip created for bounded cover acceptance: `D:\FeiSharkStudio-v2\shared_data\stage47\stage47_cover_smoke_60s_ruyuan.wav`
  - Clip duration: `60.000s`

## 3. Training Closure

- Training API path: `POST /api/train`
- Training job id: `train_7f4d6b4e611e`
- Voice name: `朱朱_stage47_single_long`
- Strategy: `single_long_preprocess`
- Training config: `fast_preview · 30 epochs · batch 6 · 40k · f0=on · index=on`
- Train.py started: yes, through existing FeiShark job/service/API path.
- Train command preview:
  - `D:\Miniconda3\envs\rvc\python.exe D:\RVC\RVCv2\infer\modules\train\train.py -se 10 -te 30 -bs 6 -e feishark_v_d4d7e1c1 -sr 40k -v v2 -f0 1 -l 1 -c 0 -sw 1 -g 0`
- Stage flow observed:
  - `train_upload` completed
  - `train_preflight` completed
  - `train_dataset_prepare` completed
  - `train_preprocess` completed
  - `train_pitch_extract` completed
  - `train_feature_extract` completed
  - `train_core` completed
  - `train_index` completed
  - `train_register_model` completed
- Elapsed:
  - Created: `2026-06-02 11:54:15`
  - Completed/updated: `2026-06-02 12:12:48`
  - Approx elapsed: `18m33s`
- Generated model:
  - `model_id`: `v_d4d7e1c1`
  - `model_name`: `朱朱_stage47_single_long`
  - Usable: true
  - Origin: `trained_local`
  - Source job: `train_7f4d6b4e611e`
- Model artifacts:
  - PTH: `D:\FeiSharkStudio-v2\shared_data\jobs\train_7f4d6b4e611e\artifacts\train_register_model\朱朱_stage47_single_long.pth`
  - PTH size: `55229665`
  - Index: `D:\FeiSharkStudio-v2\shared_data\jobs\train_7f4d6b4e611e\artifacts\train_register_model\朱朱_stage47_single_long.index`
  - Index size: `292128899`
- Runtime-synced artifacts:
  - `D:\RVC\RVCv2\assets\weights\朱朱_stage47_single_long.pth`
  - `D:\RVC\RVCv2\assets\indices\朱朱_stage47_single_long.index`
- Checkpoint inspection:
  - Exp name: `feishark_v_d4d7e1c1`
  - Highest epoch: `30`
  - Feature count: `552`
  - Index feasible: true

## 4. Cover Smoke Closure

- Cover was run through existing API path:
  - `POST /api/upload_task`
  - `POST /api/process/{task_id}?model_id=v_d4d7e1c1`
- Valid cover smoke job id: `task_b2272d133fff`
- Model used: `v_d4d7e1c1` / `朱朱_stage47_single_long`
- Cover input:
  - `D:\FeiSharkStudio-v2\shared_data\stage47\stage47_cover_smoke_60s_ruyuan.wav`
  - Uploaded job input: `D:\FeiSharkStudio-v2\shared_data\jobs\task_b2272d133fff\input\task_b2272d133fff.wav`
- Cover status: completed.
- Stage flow observed:
  - `upload` completed
  - `cover_preflight` completed
  - `cover_split` completed
  - `cover_pitch` completed
  - `cover_voice` completed
  - `cover_mix` completed
- Duration contract:
  - Input duration: `60.000s`
  - UVR vocal duration: `60.000s`
  - UVR instrumental duration: `60.000s`
  - UVR ratio: `1.000`
  - Final master duration: `60.100s`
  - Requirement `ratio >= 0.95`: PASS
- Final artifact:
  - Artifact id: `art_f99f7e4afb10`
  - Path: `D:\FeiSharkStudio-v2\shared_data\jobs\task_b2272d133fff\artifacts\cover_mix\final_master.wav`
  - Size: `5300864`
  - Download API: `/api/jobs/task_b2272d133fff/artifacts/art_f99f7e4afb10/download`
  - Download check: `200`, `content-type=audio/wav`, `5300864` bytes
- Studio-readable:
  - `can_open_studio=true`
  - Studio URL: `/studio?job_id=task_b2272d133fff&artifact_id=art_f99f7e4afb10`
  - Studio page check: `200`, page contains `studio.js`

## 5. Runtime Refresh Note

- First cover smoke attempt after training used job `task_152f8fe607ae`.
- That attempt produced `cover_split` duration `35.747s` from a `60.000s` input, ratio about `0.596`, which failed the Stage47A duration requirement.
- Investigation showed the repository already contained the Stage46B duration-preservation guard in `backend\vocal_separator.py`, but the running FastAPI process had not loaded it yet.
- Action taken: restarted only the FeiShark FastAPI server on port `8000`; RVC WebUI on `7866` was left running.
- After runtime refresh, `task_b2272d133fff` passed the UVR duration contract with ratio `1.000`.

## 6. Validation Results

- `python -m pytest -q`
  - Result: PASS
  - Summary: `67 passed, 2 warnings in 30.72s`
- `python -m backend.self_check`
  - Result: PASS
  - Summary: `SELF_CHECK_SUMMARY PASS`
  - Re-run after cleanup: PASS
- `python backend\verify_stage45r_separation_quality_audit.py`
  - Result: PASS
  - Summary: `STAGE45R_AUDIT_SUMMARY PASS`
  - Latest run contract: `BLOCK_TRAINING=false`
- Additional validation:
  - `python backend\verify_stage11_train_flow.py`
  - Result: PASS
  - Summary: `stage11 verification PASS`
- Extra non-required validation note:
  - `python backend\smoke_stage9.py` was attempted in parallel with `verify_stage11_train_flow.py`.
  - Result: FAIL due to my unsafe parallel validation causing compute-slot contention and a later smoke train timeout.
  - Cleanup: stale smoke job `train_b4937e58233e` was marked failed and compute slot was released.
  - Final compute state after cleanup: `has_active_compute_jobs=False`.

## 7. Files / Data Created

- Report:
  - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-47a-real-single-long-training-cover-closure-report.md`
- Training job workspace:
  - `D:\FeiSharkStudio-v2\shared_data\jobs\train_7f4d6b4e611e`
- New registered model files:
  - `D:\FeiSharkStudio-v2\shared_data\weights\朱朱_stage47_single_long.pth`
  - `D:\FeiSharkStudio-v2\shared_data\weights\朱朱_stage47_single_long.index`
- Cover smoke clip:
  - `D:\FeiSharkStudio-v2\shared_data\stage47\stage47_cover_smoke_60s_ruyuan.wav`
- Valid cover job workspace:
  - `D:\FeiSharkStudio-v2\shared_data\jobs\task_b2272d133fff`
- Valid final cover output:
  - `D:\FeiSharkStudio-v2\shared_data\jobs\task_b2272d133fff\artifacts\cover_mix\final_master.wav`

## 8. Remaining Risks

- The first cover attempt proved that after backend code changes, a stale FastAPI process can keep old UVR behavior alive. Operationally, Stage46B/Stage47 acceptance should include a backend restart or runtime version guard before real cover validation.
- `smoke_stage9.py` is not stable when run concurrently with another training verification; it can queue behind compute jobs and time out. Future smoke runs should be serialized or made queue-aware.
- The valid cover acceptance used a 60-second smoke clip from `如愿-孔老师.wav`, not the full 260-second song. This matches the Stage47A allowance for 45-90 second smoke, but it is not a full-song formal cover acceptance.
- `build_training_command_preview()` returned `starts_train_py=False` even though the command clearly invokes `train.py`; this appears to be a reporting/preview metadata inconsistency, not a runtime failure.
