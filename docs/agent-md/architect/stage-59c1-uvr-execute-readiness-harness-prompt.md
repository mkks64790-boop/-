# FeiShark Stage59C-1 Agent Prompt: UVR A/B Execute Readiness Harness + Safety Gate

Project root: `D:\FeiSharkStudio-v2`

You are the worker/coordinator agent for FeiShark Studio. Use extreme honesty mode:

- First list all known technical limits, assumptions, and impossible paths.
- Then implement a runnable code structure with error handling and validation.
- If something cannot be done without real UVR/RVC/GPU/manual approval, mark it as `requires_manual_approval` or `requires_extra_tooling`.
- Do not hide skipped work behind vague wording.

## Current Accepted Baseline

Stage59A and Stage59B are accepted. Stage59C-0 is accepted only as dry-run planner:

- `backend/services/short_chain_manifest_service.py` has `build_short_chain_whitelist()`.
- `backend/services/short_chain_uvr_service.py` has dry-run planning and `execute_blocked_by_stage59c0`.
- `backend/verify_stage59_uvr_ab.py` verifies UVR A/B dry-run only.
- `backend/main.py` exposes:
  - `GET /api/stage59/short-chain/uvr-ab/contract`
  - `POST /api/stage59/short-chain/uvr-ab/plan`
  - `POST /api/stage59/short-chain/uvr-ab/execute` hard-blocked with 403.
- Latest architect validation: `python -m pytest -q` passed with `193 passed, 2 warnings`.

Important: Stage59C-0 did not run real UVR. Do not claim UVR execution is complete.

## Non-Negotiable Safety Boundaries

- Do not run real UVR separation.
- Do not call RVC WebUI, including `http://127.0.0.1:7866`.
- Do not run RVC inference, RVC training, ffmpeg mixing, CUDA/GPU jobs, or long audio processing.
- Do not write raw `.wav`, `.mp3`, `.flac`, `.m4a`, `.aac`, `.ogg` files into tracked repo paths.
- Do not commit `.pth`, `.index`, DB files, raw `shared_data` assets, or generated audio.
- Do not use `git reset --hard`, `git checkout --`, or any destructive cleanup.
- The worktree is dirty from many previous stages. Do not stage unrelated files. Use `git add` only on files you created or intentionally changed for Stage59C-1.

## Goal

Build the Stage59C-1 readiness harness for future real UVR A/B execution, while still keeping real execution disabled by default.

This stage should answer:

1. Is the manifest entry allowed to enter UVR A/B?
2. Is the requested manifest path safe?
3. Would the future runner know exactly what to execute?
4. Can API/CLI prove that real execution is blocked unless a future explicit approval gate is added?
5. Can tests prove no real engine, subprocess, GPU, RVC, ffmpeg, job artifact write, or raw audio write is triggered?

## Required Multi-Agent Split

If your environment supports subagents, split the work like this. If it does not, perform the same sections yourself and state that subagents were unavailable.

Agent A: Manifest and Path Safety

- Owns `backend/services/short_chain_manifest_service.py` and a new or existing Stage59 path safety helper.
- Add a safe manifest path resolver that accepts only:
  - the default `shared_data/materials/stage59/short_chain_manifest.json`;
  - files under `docs/agent-md/evidence/`;
  - files under `shared_data/materials/stage59/`.
- Reject absolute or relative paths escaping `D:\FeiSharkStudio-v2`.
- Reject path traversal like `..\..\`.
- Add unit tests for allowed and rejected manifest paths.

Agent B: Runner Contract and Mock Harness

- Owns `backend/services/short_chain_uvr_service.py` or a new `backend/services/stage59_uvr_runner_contract.py`.
- Add a runner contract that models future UVR execution without importing or calling UVR:
  - `UvrAbRunnerRequest`
  - `UvrAbRunnerPlan`
  - `UvrAbArtifactContract`
  - `MockUvrAbRunner`
  - `RealUvrAbRunnerAdapter` that always returns blocked/not implemented in this stage.
- The mock runner may return metadata-only artifact contracts for `uvr_vocal` and `uvr_instrumental`, but must not create audio files.
- Include error handling for missing entry id, non-whitelisted entry id, no `uvr_ab` in `intended_chain`, unsafe manifest path, invalid clip seconds, and real runner requested.

Agent C: CLI and API Contract

- Owns `backend/verify_stage59_uvr_ab.py`, `backend/main.py`, and API/CLI tests.
- Keep existing dry-run behavior compatible.
- Add an explicit readiness mode, for example:
  - CLI: `python backend\verify_stage59_uvr_ab.py --readiness --manifest <path> --entry-id <id> --skip-file-exists`
  - API: either extend `/plan` with `readiness=true` or add `/api/stage59/short-chain/uvr-ab/readiness`.
- `/execute` must remain blocked for real execution.
- If a mock readiness route is added, it must clearly return `real_execute_allowed=false`.
- API must not accept arbitrary local manifest paths after Agent A's resolver is added.

Agent D: QA and Regression Audit

- Owns report files only.
- Verify no Stage59C-1 path imports or calls:
  - `subprocess`
  - `vocal_separator`
  - `voice_changer`
  - `model_trainer`
  - `audio_mixer`
  - `ffmpeg`
  - `gradio_client`
  - `requests` to `127.0.0.1:7866`
- Verify no tracked raw audio was added.
- Verify the final `git status` includes only Stage59C-1 intended files plus existing unrelated dirty files.

Coordinator Responsibilities

- Integrate subagent outputs.
- Preserve compatibility with Stage59B and Stage59C-0 tests.
- Run the validation commands below.
- Write the final worker report.
- Commit only Stage59C-1 files if all validation passes.

## Required Files

Create or update as needed:

- `backend/services/short_chain_manifest_service.py`
- `backend/services/short_chain_uvr_service.py`
- Optional: `backend/services/stage59_uvr_runner_contract.py`
- `backend/verify_stage59_uvr_ab.py`
- `backend/main.py`
- `tests/unit/test_stage59c1_manifest_path_safety.py`
- `tests/unit/test_stage59c1_uvr_runner_contract.py`
- `tests/unit/test_stage59c1_verify_uvr_readiness_cli.py`
- `tests/api/test_stage59c1_uvr_readiness_api.py`
- `docs/agent-md/worker/stage-59c1-uvr-execute-readiness-report.md`
- `docs/agent-md/worker/stage-59c1-qa-audit-report.md`

Do not edit frontend files in this stage unless a test fixture absolutely requires it.

## Acceptance Criteria

Stage59C-1 is accepted only if all criteria are true:

- Existing Stage59B tests still pass.
- Existing Stage59C-0 tests still pass.
- New Stage59C-1 tests prove safe path resolution, readiness contract, mock runner behavior, and real runner blocking.
- CLI readiness mode returns PASS for the redacted manifest with `--skip-file-exists`.
- CLI real execution or real runner mode returns a clear blocked result.
- API readiness returns metadata-only plans and states `real_execute_allowed=false`.
- `/execute` still returns 403.
- No real UVR/RVC/ffmpeg/GPU/subprocess is called.
- No raw audio file is added to Git.
- Full `python -m pytest -q` passes.

## Required Validation Commands

Run these from `D:\FeiSharkStudio-v2`:

```powershell
python -m pytest tests\unit\test_stage59_short_chain_manifest.py -q
python -m pytest tests\api\test_stage59_uvr_ab_api.py -q
python -m pytest tests\unit\test_stage59c0_manifest_whitelist.py tests\unit\test_stage59c0_short_chain_uvr_service.py tests\unit\test_stage59c0_verify_uvr_ab_cli.py -q
python -m pytest tests\unit\test_stage59c1_manifest_path_safety.py tests\unit\test_stage59c1_uvr_runner_contract.py tests\unit\test_stage59c1_verify_uvr_readiness_cli.py -q
python -m pytest tests\api\test_stage59c1_uvr_readiness_api.py -q
python backend\verify_stage59_short_chain_manifest.py --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --skip-file-exists
python backend\verify_stage59_uvr_ab.py --dry-run --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --skip-file-exists
python backend\verify_stage59_uvr_ab.py --readiness --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python -m pytest -q
git status -sb
```

If you choose a different CLI flag than `--readiness`, document the exact command and add tests for it.

## Final Report Format

Write `docs/agent-md/worker/stage-59c1-uvr-execute-readiness-report.md` with:

1. Score from 1 to 5.
2. What changed.
3. What stayed intentionally blocked.
4. Exact validation commands and outputs.
5. Blocking and non-blocking issues.
6. Git add/commit list.
7. Next recommended stage.

Write `docs/agent-md/worker/stage-59c1-qa-audit-report.md` with:

1. Forbidden import/call scan.
2. Raw audio Git scan.
3. API/CLI contract audit.
4. Remaining risks.

## Commit Rule

If and only if all validations pass:

```powershell
git add backend\services\short_chain_manifest_service.py `
  backend\services\short_chain_uvr_service.py `
  backend\services\stage59_uvr_runner_contract.py `
  backend\verify_stage59_uvr_ab.py `
  backend\main.py `
  tests\unit\test_stage59c1_manifest_path_safety.py `
  tests\unit\test_stage59c1_uvr_runner_contract.py `
  tests\unit\test_stage59c1_verify_uvr_readiness_cli.py `
  tests\api\test_stage59c1_uvr_readiness_api.py `
  docs\agent-md\worker\stage-59c1-uvr-execute-readiness-report.md `
  docs\agent-md\worker\stage-59c1-qa-audit-report.md

git commit -m "Stage59C-1: add UVR execute readiness harness"
```

If optional files are not created, remove them from `git add`.

Do not push if network/TLS fails. Report the local commit hash instead.

