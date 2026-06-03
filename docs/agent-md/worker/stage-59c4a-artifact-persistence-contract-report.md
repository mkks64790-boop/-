# Stage59C-4a Artifact Persistence Contract Report

Date: 2026-06-04
Workspace: `D:\FeiSharkStudio-v2`
Status: PASS, persistence-ready contract only. No real UVR was run.

## 1. Score

4 / 5

- Safety: 5/5. No UVR, RVC, GPU, ffmpeg, subprocess runner, or audio writes.
- Contract: 4/5. Mock UVR artifacts now have stable persistence-ready records.
- Persistence: 3/5. DB write is intentionally deferred because fake metadata must not be forced into `job_artifacts`.
- Readiness for real smoke: 4/5. Stage59C-4b can now promote only file-backed transient stems after existence checks.

## 2. What Changed

Added a metadata-only artifact persistence layer for future UVR A/B stems:

- `backend/services/stage59_artifact_persistence_service.py`
- `backend/services/stage59_job_artifact_promotion_service.py`
- Updated `stage59_transient_artifact_service.py`
- Updated `stage59_uvr_mock_execute_service.py`
- Updated `stage59_listening_bridge_service.py`
- Updated `backend/verify_stage59_uvr_ab.py`
- Updated `backend/main.py`

The mock execute response now includes:

- stable `artifact_id`
- `artifact_type` as `uvr_vocal` / `uvr_instrumental`
- `lifecycle_state=transient`
- `metadata_only=true`
- `file_exists=false`
- `playback_enabled=false`
- `download_enabled=false`
- planned sandbox path under `shared_data/stage59_runtime/<run_id>/`
- dry promotion plan showing `can_promote=false` until real files exist

## 3. DB Write Decision

DB write is intentionally deferred.

Reason: existing job artifact registration expects physical files. Stage59C-4a still has no real UVR output files. Writing fake metadata into `job_artifacts` would corrupt the canonical artifact model and make the UI think non-existent stems are playable or downloadable.

Current contract marks:

- `requires_later_db_integration=true`
- `db_write_policy=deferred_until_physical_file_exists`
- `promotable_to_job_artifact=false` for mock metadata

Future Stage59C-4b may promote only after real smoke creates file-backed transient stems and file checks pass.

## 4. Stage49 Listening Bridge

The Stage49-compatible listening contract now references stable artifact ids and explicit non-playable metadata:

- `artifact_ref`
- `job_artifact_ref`
- `can_play=false`
- `can_review=false`
- `reason=metadata_only_artifact`

This keeps frontend/product behavior honest: the bridge exists, but audio playback is disabled until real files exist.

## 5. Validation Results

Commands run:

```powershell
python -m pytest tests\unit\test_stage59c4a_artifact_persistence_contract.py tests\unit\test_stage59c4a_job_artifact_promotion_plan.py tests\unit\test_stage59c4a_listening_contract_artifact_refs.py tests\unit\test_stage59c4a_verify_artifact_contract_cli.py -q
# 7 passed

python -m pytest tests\api\test_stage59c4a_artifact_contract_api.py -q
# 3 passed

python backend\verify_stage59_uvr_ab.py --mock-execute --artifact-contract --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
# PASS, artifact_records=2, promotion_can_promote=False

python backend\verify_stage59_uvr_ab.py --approval-preflight --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
# PASS, real_execute_allowed=false

python backend\verify_stage59_uvr_ab.py --approval-preflight --requested-mode real_execute --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
# Expected FAIL, real_uvr_runner_not_enabled_stage59c3

python -m pytest -q
# 273 passed, 2 warnings
```

## 6. Blocking Issues

None for Stage59C-4a.

## 7. Non-Blocking Issues

- Real DB promotion still requires Stage59C-4b file-backed smoke outputs.
- `main.py` remains large and should be split later, but not before the tiny real smoke path is proven.
- Some older comments/reports have encoding noise, but runtime behavior is unaffected.

## 8. Next Stage

Recommended next stage:

`Stage59C-4b: tiny real UVR smoke behind approval gate`

Constraints for C-4b:

- one approved manifest entry only
- 20-45 second cap
- explicit approval token
- sandbox under `shared_data/stage59_runtime/<run_id>/`
- timeout and failure cleanup
- no RVC/GPU unless separately approved
- promote artifacts only after real files exist and pass checks

