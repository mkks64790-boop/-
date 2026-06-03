# FeiShark Stage59C-3 Agent Prompt: Real UVR Approval Gate + Execution Framework Hardening

Project root: `D:\FeiSharkStudio-v2`

You are Grok acting as the Stage59C-3 worker/coordinator agent for FeiShark Studio. Use extreme honesty mode:

- First list all known technical limits, assumptions, and impossible paths.
- Then implement runnable code with error handling and validation.
- If any part needs real UVR, RVC, GPU, ffmpeg, manual approval, or extra tooling, mark it as `requires_manual_approval` or `requires_extra_tooling`.
- Do not claim real UVR has run. Stage59C-3 is an approval gate and execution framework hardening stage, not a default real execution stage.

## Accepted Baseline

Current accepted chain:

- Stage59A: explicit asset lifecycle foundation.
- Stage59B: short-chain manifest schema, rights gate, whitelist verifier.
- Stage59C-0: UVR A/B dry-run planner.
- Stage59C-1: readiness harness, safe manifest path resolver, runner contract, invalid `runner_mode` hotfix.
- Stage59C-2: mock execute, in-memory transient artifacts, Stage49-compatible listening contract.

Recent local commits:

- `24ed42f Stage59C-2: add UVR mock execute artifact bridge`
- `a2abb42 Stage59C-1: validate UVR runner mode`
- `426d0a3 Stage59C-1: add UVR execute readiness harness`

Do not depend on remote push state. Work locally in `D:\FeiSharkStudio-v2`.

## Non-Negotiable Safety Boundaries

- Do not run real UVR by default.
- Do not call RVC WebUI or `http://127.0.0.1:7866`.
- Do not run RVC inference, RVC training, CUDA/GPU jobs, ffmpeg mixing, or long audio processing.
- Do not import/call `vocal_separator`, `voice_changer`, `model_trainer`, `audio_mixer`, `ffmpeg`, `gradio_client`, or `requests` from the new Stage59C-3 execution-policy path.
- Do not write raw `.wav`, `.mp3`, `.flac`, `.m4a`, `.aac`, `.ogg` audio files.
- Do not commit `.pth`, `.index`, DB files, raw `shared_data` assets, generated audio, or local caches.
- Do not use destructive git commands.
- The worktree is dirty from earlier stages. Stage and commit only Stage59C-3 files.

## Goal

Build the framework layer that makes future real UVR execution controllable and auditable.

Stage59C-3 must answer:

1. Can the backend distinguish dry-run, readiness, mock-execute, approval-preflight, and real-execute request modes cleanly?
2. Can real execute be blocked unless every explicit approval condition is met?
3. Can the system explain exactly why real execute is blocked?
4. Can caps, disk safety, timeout policy, sandbox paths, and cleanup contracts be validated without running real UVR?
5. Can your future manual test prove the system is ready for a tiny real UVR smoke stage, without actually running it now?

This stage should improve the overall framework, not just add one endpoint.

## Required Architecture

Implement or refactor toward the following service layers.

### 1. Execution Policy Service

Suggested file:

- `backend/services/stage59_execution_policy_service.py`

Responsibilities:

- Define supported modes:
  - `dry_run`
  - `readiness`
  - `mock_execute`
  - `approval_preflight`
  - `real_execute`
- Define approval requirements:
  - `confirm_execute=true`
  - `approval_token` present and structurally valid
  - `entry_id` required
  - manifest path must pass `resolve_safe_manifest_path`
  - entry must be whitelist-approved
  - intended chain must include `uvr_ab`
  - `clip_seconds` must be capped to a strict allowed range
  - max items must be exactly `1`
  - disk preflight must pass
  - sandbox preflight must pass
  - timeout policy must be present
  - real runner availability must be explicitly configured, but still blocked in this stage
- Return a structured policy result:
  - `ok`
  - `mode`
  - `real_execute_allowed`
  - `blocked`
  - `blocked_reasons`
  - `approval_requirements`
  - `caps`
  - `safety`
  - `next_allowed_stage`

Important: in Stage59C-3, even if all approval fields are supplied, actual real UVR execution must remain blocked with a clear reason such as `real_uvr_runner_not_enabled_stage59c3`.

### 2. Caps and Sandbox Service

Suggested file:

- `backend/services/stage59_execution_guard_service.py`

Responsibilities:

- Validate hard caps:
  - max entries: `1`
  - allowed clip seconds: `20 <= clip_seconds <= 60`
  - default clip seconds: `45`
  - no batch execution
  - no unbounded source file scanning
- Validate sandbox plan:
  - planned temp root under `shared_data/stage59_runtime/<run_id>/`
  - no path traversal
  - no real files created in this stage
  - cleanup plan present
- Validate disk preflight in metadata-only mode:
  - read free-space info if safe and cheap
  - otherwise return `disk_check_mode="metadata_only"`
  - do not create probe files unless they are temp files and cleaned in the same test
- Return:
  - `caps_ok`
  - `sandbox_ok`
  - `disk_ok`
  - `cleanup_required=true`
  - `files_created=false`

### 3. Approval Audit Service

Suggested file:

- `backend/services/stage59_approval_audit_service.py`

Responsibilities:

- Create metadata-only audit records for:
  - approval preflight requested
  - real execute blocked
  - mock execute accepted
  - unsafe manifest rejected
  - pending/non-whitelisted entry rejected
- Do not require a DB if the existing audit service is not safe to write without side effects.
- If DB integration is not used, return `requires_later_db_integration=true`.
- The audit record should include:
  - `audit_id`
  - `stage`
  - `event_type`
  - `entry_id`
  - `mode`
  - `decision`
  - `blocked_reasons`
  - `real_execute_allowed`
  - timestamp

### 4. API Contract

Update `backend/main.py`.

Add endpoint:

- `POST /api/stage59/short-chain/uvr-ab/approval-preflight`

Request body:

- `entry_id: str`
- `manifest_path: str | None`
- `skip_file_exists: bool = false`
- `clip_seconds: int = 45`
- `confirm_execute: bool = false`
- `approval_token: str | None = None`
- `requested_mode: "approval_preflight" | "real_execute" = "approval_preflight"`
- `max_items: int = 1`

Behavior:

- `approval_preflight` returns 200 if the framework validates, but must include `real_execute_allowed=false` in Stage59C-3.
- `real_execute` must return 403 with `real_uvr_runner_not_enabled_stage59c3`, even if approval fields are valid.
- Invalid manifest path returns 400.
- Non-whitelisted entry returns 422.
- Invalid request mode returns 422.
- `/execute` must still return 403.
- `/mock-execute` from Stage59C-2 must keep passing.

### 5. CLI Contract

Update `backend/verify_stage59_uvr_ab.py`.

Add flags:

- `--approval-preflight`
- `--confirm-execute`
- `--approval-token <token>`
- `--max-items 1`
- optional `--requested-mode approval_preflight|real_execute`

Expected CLI behavior:

- `--approval-preflight` with no confirmation should PASS as a framework preflight but report missing approval fields and `real_execute_allowed=false`.
- `--approval-preflight --confirm-execute --approval-token stage59-local-approval --entry-id ...` should PASS as approved preflight, but still report `real_execute_allowed=false` and `real_uvr_runner_not_enabled_stage59c3`.
- `--approval-preflight --requested-mode real_execute ...` must FAIL/blocked with expected reason.
- `--mock-execute`, `--readiness`, and `--dry-run` must still work.

### 6. Reports

Write:

- `docs/agent-md/worker/stage-59c3-approval-gate-framework-report.md`
- `docs/agent-md/worker/stage-59c3-qa-audit-report.md`

The reports must state plainly:

- No real UVR was run.
- No audio files were written.
- Real execute is still blocked.
- This stage prepares the future tiny real smoke, it does not perform it.

## Required Tests

Create/update as needed:

- `tests/unit/test_stage59c3_execution_policy_service.py`
- `tests/unit/test_stage59c3_execution_guard_service.py`
- `tests/unit/test_stage59c3_approval_audit_service.py`
- `tests/unit/test_stage59c3_verify_approval_preflight_cli.py`
- `tests/api/test_stage59c3_approval_preflight_api.py`

Tests must cover:

- approval preflight missing confirmation returns structured blocked reasons
- approval preflight with token still keeps `real_execute_allowed=false`
- requested real execute is blocked
- invalid manifest path returns 400
- pending entry returns 422
- invalid requested mode returns 422
- caps reject `max_items > 1`
- caps reject clip seconds outside allowed range or clamp only if the previous Stage59 convention requires clamping
- sandbox path stays under `shared_data/stage59_runtime/<run_id>/`
- no audio files are written
- forbidden imports are absent from new Stage59C-3 services

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
python backend\verify_stage59_short_chain_manifest.py --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --skip-file-exists
python backend\verify_stage59_uvr_ab.py --dry-run --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --skip-file-exists
python backend\verify_stage59_uvr_ab.py --readiness --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python backend\verify_stage59_uvr_ab.py --mock-execute --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python backend\verify_stage59_uvr_ab.py --approval-preflight --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python backend\verify_stage59_uvr_ab.py --approval-preflight --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python backend\verify_stage59_uvr_ab.py --approval-preflight --requested-mode real_execute --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python -m pytest -q
git status -sb
```

Expected:

- All pytest commands pass.
- The `--requested-mode real_execute` command may exit non-zero, but only if the reason is `real_uvr_runner_not_enabled_stage59c3`.
- Full pytest should pass.

## Forbidden Scan

Run and include output summary in QA report:

```powershell
rg -n "subprocess|Popen|vocal_separator|voice_changer|model_trainer|audio_mixer|ffmpeg|gradio_client|127\.0\.0\.1:7866|requests" `
  backend\services\stage59_execution_policy_service.py `
  backend\services\stage59_execution_guard_service.py `
  backend\services\stage59_approval_audit_service.py `
  backend\verify_stage59_uvr_ab.py

git ls-files | Select-String -Pattern "(\.wav|\.mp3|\.flac|\.m4a|\.aac|\.ogg|\.pth|\.index|\.sqlite|\.db)$"
```

Existing legacy imports elsewhere in `backend/main.py` are not Stage59C-3 violations unless the new Stage59C-3 route calls them.

## Manual Tester Workflow For User

Your final report must include a short manual workflow for the project owner:

1. Open PowerShell.
2. `cd D:\FeiSharkStudio-v2`
3. Run the three CLI commands:
   - `--dry-run`
   - `--mock-execute`
   - `--approval-preflight --confirm-execute --approval-token stage59-local-approval`
4. Confirm all say `real_execute_allowed=false`.
5. Confirm `--requested-mode real_execute` is blocked.
6. Run full `python -m pytest -q`.
7. Do not start RVC/UVR or click real execute in any external UI.

## Commit Rule

If and only if all validations pass:

```powershell
git add backend\services\stage59_execution_policy_service.py `
  backend\services\stage59_execution_guard_service.py `
  backend\services\stage59_approval_audit_service.py `
  backend\verify_stage59_uvr_ab.py `
  backend\main.py `
  tests\unit\test_stage59c3_execution_policy_service.py `
  tests\unit\test_stage59c3_execution_guard_service.py `
  tests\unit\test_stage59c3_approval_audit_service.py `
  tests\unit\test_stage59c3_verify_approval_preflight_cli.py `
  tests\api\test_stage59c3_approval_preflight_api.py `
  docs\agent-md\worker\stage-59c3-approval-gate-framework-report.md `
  docs\agent-md\worker\stage-59c3-qa-audit-report.md

git commit -m "Stage59C-3: add real UVR approval gate framework"
```

If optional files are not created, remove them from `git add`.

Do not push if network/TLS fails. Report the local commit hash.

## Next Stage After This

If Stage59C-3 passes, the next stage should be:

`Stage59C-4: tiny real UVR smoke behind approval gate`

That later stage must run at most one approved 20-45 second sample, write only under a sandbox directory, enforce timeout, clean temp files on failure, and still avoid RVC/GPU unless explicitly approved.

