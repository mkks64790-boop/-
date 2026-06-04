# FeiShark Stage59C-4b Agent Prompt: Real-Smoke Plan + File-Backed UVR Artifact Promotion

Project root: `D:\FeiSharkStudio-v2`

Use extreme honesty mode:

- First list all known technical limits, assumptions, and impossible paths.
- Then implement runnable code with error handling and validation.
- If a part requires real UVR, RVC, GPU, ffmpeg, manual approval, a local manifest, or extra tooling, mark it explicitly.
- Do not claim real UVR has run unless the operator explicitly approved a bounded real smoke command and evidence exists.

## Accepted Baseline

- Stage59A: explicit asset lifecycle foundation.
- Stage59B: short-chain manifest schema, rights gate, whitelist verifier.
- Stage59C-0: UVR A/B dry-run planner.
- Stage59C-1: readiness harness and runner contract.
- Stage59C-2: mock execute and transient metadata artifacts.
- Stage59C-3: approval preflight, caps, sandbox, in-memory audit.
- Stage59C-4a: persistence-ready artifact contract, no DB write for fake files.

## Non-Negotiable Safety Boundaries

- Do not run real UVR in this stage.
- Do not run RVC, RVC WebUI, CUDA/GPU jobs, ffmpeg mixing, or long audio processing.
- Do not write or commit raw audio/model/DB assets.
- Do not touch `D:\TideRelease`.
- Do not use `git add .`.
- Do not broaden this stage into UI redesign or router split.

## Goal

Build the missing bridge between C-4a metadata-only contracts and a future tiny real UVR smoke:

1. Add a C-4b plan-only service for a single approved short-chain entry.
2. Keep `real_execute_allowed=false` and `audio_files_written=false`.
3. Require explicit confirmation token and physical source-file checks for real-smoke readiness.
4. Add file-backed artifact contract support for real stems created later.
5. Ensure `uvr_vocal` and `uvr_instrumental` register as `transient`, never `active`.
6. Allow promotion planning only when both real stem files exist, are non-empty, and remain under `shared_data/stage59_runtime/<run_id>/`.

## Required Implementation

- Add or update `backend/services/stage59_real_smoke_plan_service.py`.
- Update `backend/services/stage59_artifact_persistence_service.py`.
- Update `backend/services/stage59_job_artifact_promotion_service.py`.
- Update lifecycle handling in `backend/services/lifecycle_service.py`.
- Add `--real-smoke-plan` to `backend/verify_stage59_uvr_ab.py`.
- Add API endpoint `POST /api/stage59/short-chain/uvr-ab/real-smoke-plan`.
- Keep `POST /api/stage59/short-chain/uvr-ab/execute` blocked.

## Required Tests

- Unit test C-4b plan-only service.
- Unit test file-backed promotion plan.
- Unit test CLI `--real-smoke-plan`.
- API test `/real-smoke-plan`.
- Regression test that old C-4a mock contracts remain metadata-only and non-playable.

## Validation Commands

```powershell
cd D:\FeiSharkStudio-v2

python -m pytest tests\unit\test_stage59c4a_artifact_persistence_contract.py tests\unit\test_stage59c4a_job_artifact_promotion_plan.py tests\unit\test_stage59c4b_real_smoke_plan_service.py tests\unit\test_stage59c4b_file_backed_promotion.py tests\unit\test_stage59c4b_verify_real_smoke_plan_cli.py tests\api\test_stage59c4a_artifact_contract_api.py tests\api\test_stage59c4b_real_smoke_plan_api.py -q

python backend\verify_stage59_uvr_ab.py --real-smoke-plan --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists

python -m pytest -q
```

## Report Requirements

Write a worker report under `docs/agent-md/worker/` with:

- What changed.
- What remains blocked before true real UVR.
- Test results.
- Git status and exact files changed.
