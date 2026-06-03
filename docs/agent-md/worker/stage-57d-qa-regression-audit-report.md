# Stage57D QA Regression Audit Report

Date: 2026-06-03

Role: FeiShark Stage57D QA regression and risk audit sub-agent

Scope: read-only audit of `D:\FeiSharkStudio-v2`, except this report file.

## Conclusion

Current acceptance status: **not clean for handoff**.

Backend unit/API regression is broadly healthy: full pytest passed, isolated self-check passed, live backend `8000` is online, Stage56D `task_2594c7de4629` is completed, its final artifact downloads, and its Studio URL opens.

Main blockers/risks:

- Worktree is very dirty and mixes real code/report changes with runtime garbage.
- Raw `python -m backend.self_check` is not read-only; it writes synthetic smoke jobs unless isolated.
- Raw Stage47 Playwright smoke writes screenshots and failed in this audit because Factory model assets were read before initialization finished.
- RVC WebUI `7866` is offline now, despite Stage56D historical smoke having completed when RVC was online.
- Database contains many smoke/stage records, including stale pending jobs, that can pollute UI counts and ordering.
- Exact product label "AI 翻唱" was not found in the Dashboard body text, although the protected cover creation form/button is visible.

## Commands Run

### Git/worktree audit

Command:

```powershell
git rev-parse --show-toplevel
git status --short
```

Result: root is `D:/FeiSharkStudio-v2`; worktree is dirty.

Observed modified tracked files include backend core/services, frontend pages/modules, CSS, tests, and one prior report:

- `backend/db.py`, `backend/main.py`, `backend/model_trainer.py`, `backend/pitch_processor.py`, `backend/self_check.py`, `backend/vocal_separator.py`
- `backend/services/asset_service.py`, `job_service.py`, `preflight_service.py`, `track_service.py`
- `backend/strategies/train_multi_clean_strategy.py`, `train_single_long_strategy.py`
- `frontend/index.html`, `frontend/factory.html`, `frontend/studio.html`, `frontend/css/app.css`, major frontend JS modules
- `tests/conftest.py`
- `docs/agent-md/worker/stage-36b-studio-render-mode-ux-report.md`

Observed untracked code/report/test additions include:

- New backend services: `engine_manager_service.py`, `material_library_service.py`, `memory_service.py`, `separation_eval_service.py`, `training_gpu_service.py`, `training_observer_service.py`, `training_recovery_service.py`, `training_runtime_guard.py`, `training_tuning_service.py`
- New verify scripts: `backend/verify_stage40...` through `verify_stage45r...`
- Many new Stage37-56 architect/handoff/worker reports.
- New Playwright smoke scripts for Stage36B through Stage50.
- New API/unit tests for engine, memory, Stage43/44/45R/49/50/51/53/54/55, training recovery/GPU/runtime guard.

Observed local runtime garbage:

- `backend/feishark.db-shm`
- `backend/feishark.db-wal`

Risk: `.gitignore` ignores `*.db` and `backend/feishark.db`, but `backend/feishark.db-shm` and `backend/feishark.db-wal` still show as untracked. These should be ignored, not committed.

### Diff summary

Command:

```powershell
Get-Content .gitignore
git diff --stat
git diff --name-status
git ls-files feishark.db backend/feishark.db backend/feishark.db-shm backend/feishark.db-wal
```

Result:

- Tracked diff size: `26 files changed, 10219 insertions(+), 1296 deletions(-)`.
- Git emitted many `LF will be replaced by CRLF` warnings for modified files.
- `backend/feishark.db-shm` and `backend/feishark.db-wal` are not tracked but are visible in `git status`.

### Full pytest

Command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider
```

Result: **PASS**

Output summary:

```text
99 passed, 2 warnings in 38.20s
```

Warnings:

- FastAPI `on_event` deprecation warnings in `backend/main.py`.

### Self-check

Raw recommended command was **not run directly**:

```powershell
python -m backend.self_check
```

Reason: current `backend/self_check.py` calls `init_db()`, creates synthetic `smoke_busy_*` / `smoke_retry_*` jobs, mutates status rows, and calls `/api/memory/rescan`. That violates this read-only audit if run against the real DB.

Replacement command used a read-only backup of the live SQLite DB into a temporary DB, then ran the same `backend.self_check.main()` against the temporary DB:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
# copy backend/feishark.db through sqlite backup into %TEMP%
# patch backend.db.DB_PATH and backend.self_check.DB_PATH to temp DB
# run backend.self_check.main()
```

Result: **PASS**

Output summary:

```text
CODE_STRUCTURE_SUMMARY PASS
RUNTIME_ENVIRONMENT_SUMMARY PASS
SELF_CHECK_SUMMARY PASS
```

Notable self-check details:

- `cover artifact uniqueness`: PASS for `task_2594c7de4629`
- `final artifact priority`: PASS for `task_2594c7de4629`
- `download final artifact`: PASS, HTTP 200, `audio/wav`
- `download artifact item`: PASS, HTTP 200, `cover_master`
- `cover preflight usable model`: PASS for model files; external RVC offline was tolerated by the check.

### JS syntax checks

Naive direct command failed for browser ES modules because the repo is CommonJS:

```powershell
node --check frontend/js/api.js
```

Result: **FAIL as a command shape**, not accepted as a JS syntax failure:

```text
SyntaxError: Unexpected token 'export'
```

Corrected binary-preserving module checks:

```powershell
cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\api.js','rb').read())"" | node --input-type=module --check"
cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\ui.js','rb').read())"" | node --input-type=module --check"
cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\main.js','rb').read())"" | node --input-type=module --check"
cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\cover.js','rb').read())"" | node --input-type=module --check"
cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\diagnostics.js','rb').read())"" | node --input-type=module --check"
cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\jobs.js','rb').read())"" | node --input-type=module --check"
cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\models.js','rb').read())"" | node --input-type=module --check"
cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\studio.js','rb').read())"" | node --input-type=module --check"
cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\train.js','rb').read())"" | node --input-type=module --check"
cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\factory\main.js','rb').read())"" | node --input-type=module --check"
node --check frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
```

Result: **PASS**

All checked frontend modules and the Stage47 CJS smoke script exited `0`.

### Live service and process check

Command:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
Get-NetTCPConnection -LocalPort 7866 -State Listen
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'FeiSharkStudio-v2|RVC|infer-web|uvicorn|gradio|7866|8000' }
Invoke-WebRequest http://127.0.0.1:8000/api/health
Invoke-WebRequest http://127.0.0.1:7866/
```

Result:

- `8000`: **online**, listener PID `8832`, command `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level warning`.
- PID `3952` is a Python shim parent process for PID `8832`, not a second `8000` listener.
- `7866`: **offline**, no listener.
- `GET /api/health`: HTTP 200, reports RVC base URL `http://127.0.0.1:7866`, `online=false`.
- `GET http://127.0.0.1:7866/`: connection failed.

Additional live API checks:

```powershell
GET http://127.0.0.1:8000/api/engines
GET http://127.0.0.1:8000/api/training/gpu-status
GET http://127.0.0.1:8000/api/training/observer/latest
```

Result:

- `/api/engines`: HTTP 200, RVC `offline`, UVR `online`, SVC fallback `not_configured`.
- `/api/training/gpu-status`: HTTP 200, CUDA acceleration available on GPU 0.
- `/api/training/observer/latest`: HTTP 200, latest observer `train_7f4d6b4e611e`, model `v_d4d7e1c1 / 朱朱_stage47_single_long`, usable.

### Stage56D `task_2594c7de4629`

Commands:

```powershell
# read-only SQLite query against backend/feishark.db
SELECT * FROM jobs WHERE job_id='task_2594c7de4629';
SELECT * FROM tasks WHERE task_id='task_2594c7de4629';
SELECT * FROM job_artifacts WHERE job_id='task_2594c7de4629';
SELECT * FROM job_stage_logs WHERE job_id='task_2594c7de4629';

Invoke-WebRequest http://127.0.0.1:8000/api/jobs/task_2594c7de4629
Invoke-WebRequest http://127.0.0.1:8000/api/jobs/task_2594c7de4629/artifacts
Invoke-WebRequest http://127.0.0.1:8000/api/jobs/task_2594c7de4629/artifacts/art_423574fb9c3c/download
Invoke-WebRequest "http://127.0.0.1:8000/studio?job_id=task_2594c7de4629&artifact_id=art_423574fb9c3c"
```

Result: **PASS**

Evidence:

- Job status: `完成`
- Current stage: `cover_mix`
- Model: `v_d4d7e1c1`
- Input metadata: `stage56_librivox_public_domain_voice_30s.mp3`, `smoke=true`
- Final artifact: `art_423574fb9c3c`
- Final artifact type: `cover_master`
- Final artifact file: `D:\FeiSharkStudio-v2\shared_data\jobs\task_2594c7de4629\artifacts\cover_mix\final_master.wav`
- Final artifact size: `2646044`
- Download URL: HTTP 200, `audio/wav`, `2646044` bytes
- Studio URL: HTTP 200

Risk note: stage logs show an earlier `cover_pitch` failure:

```text
ValueError: operands could not be broadcast together with shapes (1944,) (2048,) (1944,)
```

The same job later completed `cover_pitch`, `cover_voice`, and `cover_mix`. This is acceptable as completion evidence, but the retained failed stage log can confuse UI/audit readers unless explained.

### Stage47 / Studio Playwright smoke

Raw recommended command was **not run directly**:

```powershell
node frontend/playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
```

Reason: the script writes screenshots to `output/playwright`, which is outside the only allowed writable report file.

Replacement command used the same script but monkey-patched screenshot writes to no-op:

```powershell
# node wrapper:
# patch fs.mkdirSync("output/playwright") to no-op
# patch page.screenshot() to return an empty Buffer
# require("./frontend/playwright_stage47_e2e_acceptance_dashboard_smoke.cjs")
```

Result: **FAIL**

Failure:

```text
Factory does not tag real Stage47 model; Factory Stage47 model facts are incomplete
```

Important detail:

- The script's real API section succeeded:
  - training job: `train_7f4d6b4e611e`
  - model: `v_d4d7e1c1 / 朱朱_stage47_single_long`
  - cover job: `task_b2272d133fff`
  - artifact: `art_f99f7e4afb10`
  - Studio ready: `true`
- Dashboard rendered Stage47 data correctly.
- Studio rendered playable/downloadable artifact correctly.
- Factory initially showed `已读取 0 个模型资产...Stage47 实训模型 0 个`.

Follow-up read-only browser check waited 12 seconds on Factory:

```powershell
GET /factory#factoryModelAssetsDrawer through Playwright
wait 12000ms
read #factoryModelAssetsSummary and #factoryModelAssetsList
```

Result: Factory eventually showed:

```text
已读取 6 个模型资产，其中 6 个可用于翻唱；Stage47 实训模型 1 个。
朱朱_stage47_single_long
pth：存在
index：存在
cover：可用
source train_7f4d6b4e611e
```

Interpretation: current Stage47 smoke is flaky/too impatient because Factory loads model assets late in `refreshAll()`. Product data exists and eventually renders, but the smoke command does not reliably pass.

### Stale smoke / UI pollution DB audit

Command:

```sql
SELECT status, COUNT(*) FROM jobs GROUP BY status;
SELECT job_type, status, COUNT(*) FROM jobs GROUP BY job_type, status;
SELECT status, COUNT(*) FROM tasks GROUP BY status;
SELECT status, COUNT(*) FROM jobs
WHERE lower(job_id) LIKE '%smoke%'
   OR lower(metadata_json) LIKE '%smoke%'
   OR lower(job_id) LIKE 'stage%'
GROUP BY status;
```

Result:

All jobs:

- `失败`: 159
- `完成`: 151
- `已取消`: 113
- `pending`: 11
- `??`: 4

Smoke/stage-like jobs:

- `完成`: 137
- `失败`: 125
- `已取消`: 107
- `pending`: 10

Stale pending/failed smoke/stage examples:

- `stage45r_eval_a1b032f385ec` pending
- `stage45r_eval_12212e18a3d0` pending
- `stage45r_eval_bd99cca85a78` pending
- `stage45r_eval_942cb831b343` pending
- `stage45r_eval_a7a180d4d334` pending
- `stage45r_eval_72e712476a64` pending
- `stage45r_eval_a7cc23e60d89` pending
- `stage45r_eval_1987cd899406` pending
- `stage45r_eval_a904bce4d24b` pending
- `smoke_retry_ba451022` pending

Risk: default UI endpoints must keep hiding smoke/test jobs. Otherwise stale records will dominate recent lists, status chips, and review queues.

### Protected business flows visibility

Command:

```powershell
# Playwright read-only DOM check on http://127.0.0.1:8000/
# no screenshots, no form submit
```

Result: **PASS with naming caveat**

Visible forms/buttons:

- `#coverCreateForm`: visible
- `#coverCreateBtn`: `创建 cover job`
- `#singleTrainCreateForm`: visible
- `#singleTrainCreateBtn`: `创建单文件快速训练`
- `#multiTrainCreateForm`: visible
- `#multiTrainCreateBtn`: `创建多文件精训`

Caveat: the exact phrase `AI 翻唱` was not found in `document.body.innerText`; the protected cover flow is visible as `cover job`.

## Risk List

1. **Dirty worktree blocks clean acceptance.** There are many modified tracked files and many untracked stage files. This should be reviewed as a coherent Stage37-57 change set before commit.

2. **Runtime DB sidecar files are untracked garbage.** `backend/feishark.db-shm` and `backend/feishark.db-wal` should not be committed and should be ignored.

3. **Raw self-check is not read-only.** `python -m backend.self_check` writes synthetic smoke jobs and memory scan rows unless DB paths are isolated.

4. **Stage47 Playwright smoke is flaky as written.** It failed because Factory model assets had not loaded yet. A longer wait or explicit wait for `/api/models`/`Stage47 实训模型` is needed.

5. **RVC `7866` is offline now.** Historical Stage56D completion is valid, but a fresh RVC connectivity or quality smoke cannot be accepted while `7866` is offline.

6. **Smoke/stage DB pollution is significant.** There are 379 smoke/stage-like jobs, including 10 pending stale records. UI must filter these by default or users will see stale QA noise.

7. **Stage56D logs retain an earlier failure inside a completed job.** This is explainable, but UI/audit should distinguish recovered failure logs from final job status.

8. **Product wording drift.** Dashboard still exposes the three protected flows, but cover entry is labeled `cover job`, not literally `AI 翻唱`.

9. **Line ending churn risk.** `git diff` reports LF-to-CRLF warnings across many files, which can inflate diffs and hide real changes.

10. **Reports/prompts are numerous and untracked.** Earlier agents may have generated many Stage files without committing or curating them; this increases review burden.

## Recommended Next Steps

1. Separate commit candidates from garbage: commit coherent backend/frontend/tests/docs stage work, but ignore/remove `backend/feishark.db-shm` and `backend/feishark.db-wal`.

2. Add ignore coverage for SQLite sidecars: `*.db-shm`, `*.db-wal`, or explicit `backend/feishark.db-shm` / `backend/feishark.db-wal`.

3. Make `backend.self_check` support a documented read-only or temp-DB mode before using it as a QA command.

4. Patch Stage47 Playwright smoke to wait for Factory model assets to finish loading, specifically `Stage47 实训模型 1 个` or the model name `朱朱_stage47_single_long`.

5. Restart/bring up RVC WebUI `7866` only when a fresh RVC smoke is explicitly requested; do not start it as part of this read-only audit.

6. Add or verify default API/UI filters that hide smoke/test/stage QA records from user-facing job lists unless explicitly requested.

7. Decide whether the cover creation entry should use the user-facing label `AI 翻唱` again, or update acceptance language to `cover job`.

## Files Written

- `docs/agent-md/worker/stage-57d-qa-regression-audit-report.md`

