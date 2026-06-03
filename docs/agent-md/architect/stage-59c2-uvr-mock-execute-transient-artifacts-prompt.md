# FeiShark Stage59C-2 Agent Prompt: UVR Mock Execute + Transient Artifacts + Stage49 A/B Contract

Project root: `D:\FeiSharkStudio-v2`

You are Grok acting as the Stage59C-2 worker/coordinator agent for FeiShark Studio. Use extreme honesty mode:

- First list all known technical limits, assumptions, and impossible paths.
- Then implement runnable code with error handling and validation.
- If any part needs real UVR, RVC, GPU, ffmpeg, manual approval, or extra tooling, mark it as `requires_manual_approval` or `requires_extra_tooling`.
- Do not claim real UVR has run. This stage is still a mock execute / contract stage.

## Accepted Baseline

The current accepted chain is:

- Stage59A: explicit asset lifecycle foundation.
- Stage59B: short-chain manifest schema, rights gate, whitelist verifier.
- Stage59C-0: UVR A/B dry-run planner only.
- Stage59C-1: execute readiness harness, safe manifest path resolver, runner contract, `--readiness`, mock artifact contracts.
- Hotfix after Stage59C-1: invalid `runner_mode` no longer causes API 500.

Current local commits include:

- `426d0a3 Stage59C-1: add UVR execute readiness harness`
- `a2abb42 Stage59C-1: validate UVR runner mode`

Do not depend on remote push state. Work locally in `D:\FeiSharkStudio-v2`.

## Non-Negotiable Safety Boundaries

- Do not run real UVR.
- Do not call RVC WebUI or `http://127.0.0.1:7866`.
- Do not run RVC inference, RVC training, CUDA/GPU jobs, ffmpeg mixing, or long audio processing.
- Do not import or call `vocal_separator`, `voice_changer`, `model_trainer`, `audio_mixer`, `ffmpeg`, `gradio_client`, or `requests` for Stage59C-2 execute paths.
- Do not write raw `.wav`, `.mp3`, `.flac`, `.m4a`, `.aac`, `.ogg` audio files.
- Do not commit `.pth`, `.index`, DB files, raw `shared_data` assets, generated audio, or local caches.
- Do not use destructive git commands.
- The worktree is dirty from earlier stages. Stage and commit only Stage59C-2 files.

## Goal

Build Stage59C-2 as a safe mock execute bridge:

1. Convert an approved Stage59 manifest entry into a mock UVR execute result.
2. Register or expose transient artifact metadata for future `uvr_vocal` and `uvr_instrumental`.
3. Connect that metadata to a Stage49-compatible A/B listening contract.
4. Prove real execute is still blocked unless a later stage adds manual approval and real runner integration.
5. Keep all outputs metadata-only. No physical audio files should be created.

This stage is not real UVR execution. It is the last safety layer before a future real execute stage.

## Required Multi-Agent Split

If your environment supports subagents, split the work like this. If not, implement the same sections yourself and state that subagents were unavailable.

Agent A: Mock Execute Service

- Owns a new service, suggested path:
  - `backend/services/stage59_uvr_mock_execute_service.py`
- Inputs:
  - `entry_id`
  - safe manifest path
  - `clip_seconds`
  - `skip_file_exists`
  - optional `job_id` or mock `stage59_run_id`
- Must call the existing Stage59C-1 readiness path first.
- If readiness fails, return a blocked result with the original blocked reason.
- If readiness passes, return:
  - `ok=true`
  - `mode="mock_execute"`
  - `real_execute_allowed=false`
  - `audio_files_written=false`
  - `artifact_records` for `uvr_vocal` and `uvr_instrumental`
  - `lifecycle_state="transient"`
  - `material_entry_id`
  - `source_path`
  - `metadata_only=true`
- Must not create files.
- Must not call any real engine.

Agent B: Transient Artifact Store Contract

- Inspect existing artifact/job services and DB helpers before editing.
- Preferred implementation:
  - If a safe existing `job_artifacts` registration path exists, create metadata-only transient rows without file existence requirements.
  - If existing artifact APIs require physical files, do not force them. Create a Stage59-specific in-memory or pure JSON contract service instead, and document `requires_later_db_integration=true`.
- Suggested service:
  - `backend/services/stage59_transient_artifact_service.py`
- Required behavior:
  - stable artifact ids, for example `stage59c2_{entry_id}_uvr_vocal`
  - artifact types: `uvr_vocal`, `uvr_instrumental`
  - lifecycle: `transient`
  - path fields are planned paths only, not existing files
  - download/playback disabled until real file exists
- Add tests proving no physical file is required.

Agent C: API + CLI Contract

- Owns:
  - `backend/main.py`
  - `backend/verify_stage59_uvr_ab.py`
  - API/CLI tests
- Add CLI mode:
  - `python backend\verify_stage59_uvr_ab.py --mock-execute --manifest <allowed-path> --entry-id <id> --skip-file-exists`
- Add API route, suggested:
  - `POST /api/stage59/short-chain/uvr-ab/mock-execute`
- Keep:
  - `/execute` returning 403
  - real runner blocked
  - invalid `runner_mode` handled without 500
- The mock execute route must return metadata-only artifact records and must include `real_execute_allowed=false`.
- Invalid manifest paths must return 400.
- Non-whitelisted entry ids must return 422.

Agent D: Stage49 A/B Listening Contract

- Inspect existing Stage49 listening review routes/tests before editing.
- Add a bridge contract that lets the product layer understand:
  - source material side A
  - mock `uvr_vocal` side B
  - mock `uvr_instrumental` side C if useful
  - playback disabled because files are metadata-only
  - next action requires real UVR execute
- Suggested service:
  - `backend/services/stage59_listening_bridge_service.py`
- Suggested API route:
  - `GET /api/stage59/short-chain/uvr-ab/mock-execute/{run_id}/listening-contract`
  - or include `listening_contract` directly in mock execute response if a separate route is overkill.
- Keep this backend-only unless existing frontend tests require a small contract check.

Agent E: QA Audit

- Owns report files only.
- Verify:
  - no forbidden imports/calls in Stage59C-2 paths
  - no raw audio files added to Git
  - `/execute` still 403
  - `--mock-execute` is metadata-only
  - `--runner real` still blocked
  - invalid `runner_mode` still returns 422 or blocked, not 500
  - full pytest passes

Coordinator Responsibilities

- Integrate all work.
- Preserve all Stage59B, Stage59C-0, and Stage59C-1 behavior.
- Do not rewrite large unrelated modules.
- Keep changes backend-first.
- Write final reports.
- Commit only Stage59C-2 files if all validation passes.

## Expected Files

Create or update only as needed:

- `backend/services/stage59_uvr_mock_execute_service.py`
- `backend/services/stage59_transient_artifact_service.py`
- `backend/services/stage59_listening_bridge_service.py`
- `backend/services/short_chain_uvr_service.py`
- `backend/services/stage59_uvr_runner_contract.py`
- `backend/verify_stage59_uvr_ab.py`
- `backend/main.py`
- `tests/unit/test_stage59c2_uvr_mock_execute_service.py`
- `tests/unit/test_stage59c2_transient_artifact_contract.py`
- `tests/unit/test_stage59c2_listening_bridge_contract.py`
- `tests/unit/test_stage59c2_verify_mock_execute_cli.py`
- `tests/api/test_stage59c2_uvr_mock_execute_api.py`
- `docs/agent-md/worker/stage-59c2-uvr-mock-execute-report.md`
- `docs/agent-md/worker/stage-59c2-qa-audit-report.md`

Do not edit frontend files in this stage unless absolutely required for an existing backend contract test.

## Acceptance Criteria

Stage59C-2 is accepted only if all are true:

- Existing Stage59B tests pass.
- Existing Stage59C-0 tests pass.
- Existing Stage59C-1 tests pass.
- New Stage59C-2 unit/API/CLI tests pass.
- CLI `--mock-execute` returns PASS for the redacted manifest with `--skip-file-exists`.
- API `/mock-execute` returns metadata-only transient artifact records.
- A Stage49-compatible listening contract is present or clearly documented as inline in the mock execute response.
- No audio files are physically written.
- No real UVR/RVC/GPU/ffmpeg/subprocess is called.
- `/execute` remains 403.
- `--runner real` remains blocked.
- Invalid `runner_mode` does not return 500.
- Full `python -m pytest -q` passes.

## Required Validation Commands

Run from `D:\FeiSharkStudio-v2`:

```powershell
python -m pytest tests\unit\test_stage59_short_chain_manifest.py -q
python -m pytest tests\api\test_stage59_uvr_ab_api.py -q
python -m pytest tests\unit\test_stage59c0_manifest_whitelist.py tests\unit\test_stage59c0_short_chain_uvr_service.py tests\unit\test_stage59c0_verify_uvr_ab_cli.py -q
python -m pytest tests\unit\test_stage59c1_manifest_path_safety.py tests\unit\test_stage59c1_uvr_runner_contract.py tests\unit\test_stage59c1_verify_uvr_readiness_cli.py -q
python -m pytest tests\api\test_stage59c1_uvr_readiness_api.py -q
python -m pytest tests\unit\test_stage59c2_uvr_mock_execute_service.py tests\unit\test_stage59c2_transient_artifact_contract.py tests\unit\test_stage59c2_listening_bridge_contract.py tests\unit\test_stage59c2_verify_mock_execute_cli.py -q
python -m pytest tests\api\test_stage59c2_uvr_mock_execute_api.py -q
python backend\verify_stage59_short_chain_manifest.py --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --skip-file-exists
python backend\verify_stage59_uvr_ab.py --dry-run --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --skip-file-exists
python backend\verify_stage59_uvr_ab.py --readiness --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python backend\verify_stage59_uvr_ab.py --mock-execute --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python backend\verify_stage59_uvr_ab.py --readiness --runner real --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
python -m pytest -q
git status -sb
```

For the `--runner real` command, a non-zero exit is expected if the reason is `real_uvr_runner_requires_manual_approval`.

## Forbidden Scan

Run a grep/rg scan and include the result in the QA report:

```powershell
rg -n "subprocess|Popen|vocal_separator|voice_changer|model_trainer|audio_mixer|ffmpeg|gradio_client|127\.0\.0\.1:7866|requests" `
  backend\services\stage59_uvr_mock_execute_service.py `
  backend\services\stage59_transient_artifact_service.py `
  backend\services\stage59_listening_bridge_service.py `
  backend\verify_stage59_uvr_ab.py

git ls-files | Select-String -Pattern "(\.wav|\.mp3|\.flac|\.m4a|\.aac|\.ogg|\.pth|\.index|\.sqlite|\.db)$"
```

The Stage59C-2 service paths must not contain forbidden runtime imports/calls. Existing legacy imports elsewhere in `backend/main.py` are not Stage59C-2 violations unless the new route calls them.

## Final Report Format

Write `docs/agent-md/worker/stage-59c2-uvr-mock-execute-report.md`:

1. Score from 1 to 5.
2. What changed.
3. What stayed blocked.
4. Mock execute response shape.
5. Transient artifact contract.
6. Stage49 listening bridge shape.
7. Exact validation commands and outputs.
8. Blocking and non-blocking issues.
9. Git add / commit list.
10. Next recommended stage.

Write `docs/agent-md/worker/stage-59c2-qa-audit-report.md`:

1. Forbidden import/call scan.
2. Raw audio/model/DB Git scan.
3. API/CLI contract audit.
4. Regression test audit.
5. Remaining risks.

## Commit Rule

If and only if all validations pass:

```powershell
git add backend\services\stage59_uvr_mock_execute_service.py `
  backend\services\stage59_transient_artifact_service.py `
  backend\services\stage59_listening_bridge_service.py `
  backend\services\short_chain_uvr_service.py `
  backend\services\stage59_uvr_runner_contract.py `
  backend\verify_stage59_uvr_ab.py `
  backend\main.py `
  tests\unit\test_stage59c2_uvr_mock_execute_service.py `
  tests\unit\test_stage59c2_transient_artifact_contract.py `
  tests\unit\test_stage59c2_listening_bridge_contract.py `
  tests\unit\test_stage59c2_verify_mock_execute_cli.py `
  tests\api\test_stage59c2_uvr_mock_execute_api.py `
  docs\agent-md\worker\stage-59c2-uvr-mock-execute-report.md `
  docs\agent-md\worker\stage-59c2-qa-audit-report.md

git commit -m "Stage59C-2: add UVR mock execute artifact bridge"
```

If optional files are not created, remove them from `git add`.

Do not push if network/TLS fails. Report the local commit hash.

## Next Stage After This

If Stage59C-2 passes, the next stage should be `Stage59C-3 real execute approval gate`, not direct real UVR. That later stage must add explicit manual approval, hard caps, disk safety, process timeout, and artifact cleanup before any real engine can run.

