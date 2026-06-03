# FeiShark Stage59C-4a Agent Prompt: Persist UVR A/B Artifacts Before Tiny Real Smoke

Project root: `D:\FeiSharkStudio-v2`

You are Grok acting as the Stage59C-4a worker/coordinator agent for FeiShark Studio. Use extreme honesty mode:

- First list all known technical limits, assumptions, and impossible paths.
- Then implement runnable code with error handling and validation.
- If any part needs real UVR, RVC, GPU, ffmpeg, manual approval, DB migration, or extra tooling, mark it as `requires_manual_approval`, `requires_later_db_integration`, or `requires_extra_tooling`.
- Do not claim real UVR has run. Stage59C-4a is a persistence-contract stage before tiny real smoke.

## Accepted Baseline

Current accepted chain:

- Stage59A: explicit asset lifecycle foundation.
- Stage59B: short-chain manifest schema, rights gate, whitelist verifier.
- Stage59C-0: UVR A/B dry-run planner.
- Stage59C-1: readiness harness, safe manifest path resolver, runner contract, invalid `runner_mode` hotfix.
- Stage59C-2: mock execute, in-memory transient artifacts, Stage49-compatible listening contract.
- Stage59C-3: approval preflight, caps, sandbox, audit framework; real execute still blocked.

Current repository hygiene:

- `main` should be clean and synced before this stage starts.
- Do not rely on untracked files.
- Do not use `git add .`.

## Non-Negotiable Safety Boundaries

- Do not run real UVR.
- Do not run RVC, call RVC WebUI, or call `http://127.0.0.1:7866`.
- Do not run RVC inference, RVC training, CUDA/GPU jobs, ffmpeg mixing, or long audio processing.
- Do not write raw `.wav`, `.mp3`, `.flac`, `.m4a`, `.aac`, `.ogg` files.
- Do not commit `.pth`, `.index`, DB files, raw `shared_data` assets, generated audio, local caches, or screenshots.
- Do not use destructive git commands.
- Do not broaden this stage into router split or frontend redesign.

## Goal

Fix the biggest remaining Stage59 technical debt before any tiny real UVR smoke:

1. Replace the Stage59C-2 in-memory-only artifact contract with a persistence-ready artifact contract.
2. Define how future real `uvr_vocal` and `uvr_instrumental` files enter the canonical `job_artifacts` read path.
3. Keep mock artifacts metadata-only and non-playable.
4. Make Stage49 listening contract point at stable artifact identifiers instead of process-local memory only.
5. Prepare cleanup/lifecycle rules for real smoke outputs.
6. Preserve all safety gates from Stage59C-3.

This stage is **not** real UVR execution. It is the artifact persistence bridge that makes real smoke safe to observe and clean up later.

## Core Design Rule

Do not force fake file paths into `job_artifacts` if the existing artifact registration requires physical files. That would corrupt the asset model.

Instead, implement one of these two paths after inspecting existing code:

### Preferred Path A: Metadata-Only Artifact Contract Table/Service

If existing DB schema can safely hold metadata-only artifacts without file existence, add a narrow service that writes metadata-only records with explicit `file_exists=false` and `metadata_only=true`.

### Preferred Path B: Persistence-Ready Contract Without DB Write

If DB schema or helper functions require physical files, keep DB untouched and implement a stable persistence-ready contract service with:

- stable `artifact_id`
- future `job_artifact_kind`
- planned storage path
- file existence policy
- lifecycle policy
- cleanup policy
- Stage49 listening bridge compatibility
- `requires_later_db_integration=true`

Path B is acceptable if and only if the report clearly explains why DB write is blocked by physical-file requirements.

## Required Architecture

### 1. Artifact Persistence Contract Service

Suggested file:

- `backend/services/stage59_artifact_persistence_service.py`

Responsibilities:

- Define artifact kinds:
  - `uvr_vocal`
  - `uvr_instrumental`
- Define lifecycle:
  - default `transient`
  - never `active` for mock or smoke intermediate stems
- Define metadata fields:
  - `artifact_id`
  - `run_id`
  - `entry_id`
  - `artifact_type`
  - `lifecycle_state`
  - `metadata_only`
  - `file_exists`
  - `planned_path`
  - `canonical_store`
  - `download_enabled`
  - `playback_enabled`
  - `cleanup_required`
  - `promotable_to_job_artifact`
  - `requires_later_db_integration`
- Add validator:
  - mock artifacts must be metadata-only
  - real smoke artifacts may require `file_exists=true` before DB promotion
  - no artifact path may escape `shared_data/stage59_runtime/<run_id>/`

### 2. Job Artifact Promotion Plan Service

Suggested file:

- `backend/services/stage59_job_artifact_promotion_service.py`

Responsibilities:

- Inspect existing artifact services/DB helpers before implementation.
- Provide a dry promotion plan for future real smoke outputs:
  - `can_promote`
  - `blocked_reasons`
  - `required_file_checks`
  - `target_job_artifact_fields`
  - `lifecycle_state=transient`
  - `cleanup_on_failure=true`
- If existing `register_job_artifact()` requires actual files, do not write DB in C-4a.
- Add a function that can later be used after real smoke:
  - `build_job_artifact_promotion_plan(...)`
- Do not call it with real files in this stage.

### 3. Stage49 Listening Contract Update

Update:

- `backend/services/stage59_listening_bridge_service.py`

Responsibilities:

- Contract should reference stable artifact ids and artifact persistence contract.
- Keep `playback_enabled=false` until `file_exists=true`.
- Include:
  - `artifact_ref`
  - `job_artifact_ref`
  - `can_play=false`
  - `can_review=false`
  - `reason="metadata_only_artifact"`
- Make it obvious to frontend/product that this is not a playable audio result yet.

### 4. Mock Execute Integration

Update:

- `backend/services/stage59_uvr_mock_execute_service.py`
- `backend/services/stage59_transient_artifact_service.py` if still needed

Responsibilities:

- Keep mock execute behavior compatible.
- Add persistence-ready artifact contract fields to mock execute response.
- Do not remove old fields unless tests prove no caller needs them.
- Set:
  - `metadata_only=true`
  - `file_exists=false`
  - `download_enabled=false`
  - `playback_enabled=false`
  - `requires_later_db_integration` according to actual inspected DB capability.

### 5. API Contract

Update `backend/main.py` only as needed.

Suggested additions:

- Add or extend an endpoint:
  - `GET /api/stage59/short-chain/uvr-ab/mock-execute/{run_id}/artifact-contract`
- Or include the artifact persistence contract directly inside existing mock execute and listening contract responses.

Required API behavior:

- `/mock-execute` still returns 200 for approved redacted manifest.
- `/mock-execute` response includes stable artifact contract.
- `/listening-contract` response points at stable artifact ids.
- `/execute` still 403.
- `/approval-preflight` still real-execute blocked.

### 6. CLI Contract

Update `backend/verify_stage59_uvr_ab.py`.

Add optional flag:

- `--artifact-contract`

Expected behavior:

- Works with `--mock-execute`.
- Prints or returns JSON showing:
  - artifact ids
  - lifecycle `transient`
  - `metadata_only=true`
  - `file_exists=false`
  - `playback_enabled=false`
  - promotion blocked until real files exist

If you decide not to add a new CLI flag, document why and make sure `--mock-execute --json` contains the artifact contract.

## Required Tests

Create/update as needed:

- `tests/unit/test_stage59c4a_artifact_persistence_contract.py`
- `tests/unit/test_stage59c4a_job_artifact_promotion_plan.py`
- `tests/unit/test_stage59c4a_listening_contract_artifact_refs.py`
- `tests/unit/test_stage59c4a_verify_artifact_contract_cli.py`
- `tests/api/test_stage59c4a_artifact_contract_api.py`

Tests must cover:

- mock artifact contract is metadata-only and non-playable
- artifact ids are stable for the same run/entry/type
- planned paths stay under `shared_data/stage59_runtime/<run_id>/`
- promotion to `job_artifacts` is blocked when files do not exist
- promotion plan allows future file-backed artifacts only after file checks
- lifecycle is `transient`
- listening bridge references artifact ids, not only raw paths
- `/execute` still 403
- approval preflight still blocks real execute
- no audio files are written
- existing C0-C3 tests still pass

## Required Validation Commands

Run from `D:\FeiSharkStudio-v2`:

```powershell
python -m pytest tests\unit\test_stage59_short_chain_manifest.py -q
python -m pytest tests\api\test_stage59_uvr_ab_api.py -q
python -m pytest tests\unit\test_stage59c1_manifest_path_safety.py tests\unit\test_stage59c1_uvr_runner_contract.py tests\unit\test_stage59c1_verify_uvr_readiness_cli.py -q
python -m pytest tests\api\test_stage59c1_uvr_readiness_api.py -q
python -m pytest tests\unit\test_stage59c2_uvr_mock_execute_service.py tests\unit\test_stage59c2_transient_artifact_contract.py tests\unit\test_stage59c2_listening_bridge_contract.py tests\unit\test_stage59c2_verify_mock_execute_cli.py -q
python -m pytest tests\api\test_stage59c2_uvr_mock_execute_api.py -q
python -m pytest tests\unit\test_stage59c3_execution_policy_service.py tests\unit\test_stage59c3_execution_guard_service.py tests\unit\test_stage59c3_approval_audit_service.py tests\unit\test_stage59c3_verify_approval_preflight_cli.py -q
python -m pytest tests\api\test_stage59c3_approval_preflight_api.py -q
python -m pytest tests\unit\test_stage59c4a_artifact_persistence_contract.py tests\unit\test_stage59c4a_job_artifact_promotion_plan.py tests\unit\test_stage59c4a_listening_contract_artifact_refs.py tests\unit\test_stage59c4a_verify_artifact_contract_cli.py -q
python -m pytest tests\api\test_stage59c4a_artifact_contract_api.py -q
python backend\verify_stage59_uvr_ab.py --mock-execute --artifact-contract --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python backend\verify_stage59_uvr_ab.py --approval-preflight --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python backend\verify_stage59_uvr_ab.py --approval-preflight --requested-mode real_execute --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python -m pytest -q
git status -sb
```

Expected:

- `--mock-execute --artifact-contract` exits 0 and shows metadata-only artifacts.
- `--requested-mode real_execute` may exit non-zero, but only with `real_uvr_runner_not_enabled_stage59c3`.
- Full pytest passes.
- `git status -sb` only shows intended Stage59C-4a files before commit, then clean after commit.

## Forbidden Scan

Run and include output summary in QA report:

```powershell
rg -n "subprocess|Popen|vocal_separator|voice_changer|model_trainer|audio_mixer|ffmpeg|gradio_client|127\.0\.0\.1:7866|requests" `
  backend\services\stage59_artifact_persistence_service.py `
  backend\services\stage59_job_artifact_promotion_service.py `
  backend\services\stage59_listening_bridge_service.py `
  backend\services\stage59_uvr_mock_execute_service.py `
  backend\verify_stage59_uvr_ab.py

git ls-files | Select-String -Pattern "(\.wav|\.mp3|\.flac|\.m4a|\.aac|\.ogg|\.pth|\.index|\.sqlite|\.db)$"
```

Existing legacy imports elsewhere in `backend/main.py` are not Stage59C-4a violations unless the new Stage59C-4a route calls them.

## Final Reports

Write:

- `docs/agent-md/worker/stage-59c4a-artifact-persistence-contract-report.md`
- `docs/agent-md/worker/stage-59c4a-qa-audit-report.md`

Report must include:

1. Score from 1 to 5.
2. Whether DB write is implemented or intentionally deferred.
3. Why fake metadata should or should not enter `job_artifacts`.
4. Exact mock artifact contract response shape.
5. Stage49 listening bridge changes.
6. Cleanup/lifecycle policy.
7. Validation commands and outputs.
8. Blocking and non-blocking issues.
9. Git add/commit list.
10. Recommendation for `Stage59C-4b tiny real UVR smoke`.

## Manual Tester Workflow For User

Your final report must include this workflow:

1. `cd D:\FeiSharkStudio-v2`
2. Run:
   - `python backend\verify_stage59_uvr_ab.py --mock-execute --artifact-contract --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists`
   - `python backend\verify_stage59_uvr_ab.py --approval-preflight --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists`
   - `python -m pytest -q`
3. Confirm:
   - `metadata_only=true`
   - `file_exists=false`
   - `playback_enabled=false`
   - `download_enabled=false`
   - `lifecycle_state=transient`
   - `real_execute_allowed=false`
4. Do not start UVR/RVC.

## Commit Rule

If and only if all validations pass:

```powershell
git add backend\services\stage59_artifact_persistence_service.py `
  backend\services\stage59_job_artifact_promotion_service.py `
  backend\services\stage59_listening_bridge_service.py `
  backend\services\stage59_transient_artifact_service.py `
  backend\services\stage59_uvr_mock_execute_service.py `
  backend\verify_stage59_uvr_ab.py `
  backend\main.py `
  tests\unit\test_stage59c4a_artifact_persistence_contract.py `
  tests\unit\test_stage59c4a_job_artifact_promotion_plan.py `
  tests\unit\test_stage59c4a_listening_contract_artifact_refs.py `
  tests\unit\test_stage59c4a_verify_artifact_contract_cli.py `
  tests\api\test_stage59c4a_artifact_contract_api.py `
  docs\agent-md\worker\stage-59c4a-artifact-persistence-contract-report.md `
  docs\agent-md\worker\stage-59c4a-qa-audit-report.md

git commit -m "Stage59C-4a: add UVR artifact persistence contract"
```

If optional files are not created, remove them from `git add`.

Do not push if network/TLS fails. Report the local commit hash.

## Next Stage After This

If Stage59C-4a passes, next stage:

`Stage59C-4b: tiny real UVR smoke behind approval gate`

That stage may execute at most one approved 20-45 second sample under sandbox, with explicit manual approval, timeout, cleanup, no RVC/GPU, and artifact promotion only after file existence checks.

