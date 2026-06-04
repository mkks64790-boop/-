# Stage59C-4b Real-Smoke Plan Report

Date: 2026-06-04
Workspace: `D:\FeiSharkStudio-v2`
Status: PASS

## 1. Scope

This stage adds the C-4b safety bridge before any true UVR execution:

- plan-only real-smoke readiness service
- file-backed UVR artifact contracts
- file-backed promotion plan
- transient lifecycle registration for `uvr_vocal` and `uvr_instrumental`
- API and CLI contract for `real-smoke-plan`

No real UVR, RVC, GPU, ffmpeg, or audio separation was run.

## 2. Technical Limits

- True UVR runner is still not integrated.
- `real_execute_allowed` remains `false`.
- `/api/stage59/short-chain/uvr-ab/execute` remains blocked.
- A real local manifest and a real approved source file are required before any future smoke can run.
- Redacted manifest tests still use `--skip-file-exists` only for contract validation.

## 3. Changed Files

- `backend/services/stage59_real_smoke_plan_service.py`
- `backend/services/stage59_artifact_persistence_service.py`
- `backend/services/stage59_job_artifact_promotion_service.py`
- `backend/services/lifecycle_service.py`
- `backend/verify_stage59_uvr_ab.py`
- `backend/main.py`
- `tests/unit/test_stage59c4b_real_smoke_plan_service.py`
- `tests/unit/test_stage59c4b_file_backed_promotion.py`
- `tests/unit/test_stage59c4b_verify_real_smoke_plan_cli.py`
- `tests/api/test_stage59c4b_real_smoke_plan_api.py`

## 4. Validation

Focused validation:

```powershell
python -m pytest tests\unit\test_stage59c4a_artifact_persistence_contract.py tests\unit\test_stage59c4a_job_artifact_promotion_plan.py tests\unit\test_stage59c4b_real_smoke_plan_service.py tests\unit\test_stage59c4b_file_backed_promotion.py tests\unit\test_stage59c4b_verify_real_smoke_plan_cli.py tests\api\test_stage59c4a_artifact_contract_api.py tests\api\test_stage59c4b_real_smoke_plan_api.py -q
# 17 passed, 2 warnings
```

CLI validation:

```powershell
python backend\verify_stage59_uvr_ab.py --real-smoke-plan --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
# PASS, real_execute_allowed=false, audio_files_written=false
```

Real execute block validation:

```powershell
python backend\verify_stage59_uvr_ab.py --approval-preflight --requested-mode real_execute --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
# Expected FAIL: real_uvr_runner_not_enabled_stage59c3
```

Full validation:

```powershell
python -m pytest -q
# 282 passed, 2 warnings
```

Forbidden tracked asset scan:

```powershell
git ls-files | Select-String -Pattern '(\.wav|\.mp3|\.flac|\.m4a|\.aac|\.ogg|\.pth|\.index|\.sqlite|\.db)$'
# no output
```

## 5. Git Status

Working tree contains only Stage59C-4b source, tests, and md artifacts. No raw audio/model/DB assets were tracked.
