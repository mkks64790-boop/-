# Stage60 Bugfix Small Debt-Repaying Fixes Report

Stage: `Stage60 Bugfix - Small Debt-Repaying Fixes`
Status: BLOCKED - external RVC training environment only
Workspace: `D:\FeiSharkStudio-v2`

Read declaration: I first read `docs/agent-md/handoff/stage-60-governance-memory-snapshot.md`, then read `docs/agent-md/handoff/stage-60-bugfix-task-handoff.md`, `docs/agent-md/architect/stage-60-bugfix-small-debt-fixes-prompt.md`, the Architecture Constitution, ADR 0001/0002/0003, the Stage60 governance plans, the governance sprint report/review, the Stage59C-4b report, the architect prompt template, and the worker report template. This work follows the Constitution and Stage60 governance mode.

## 1. Scope

Allowed scope: small isolated backend bug fixes and tests, preparatory for Stage60A dependency inventory and facade boundary review.

Out of scope and not performed:

- No real UVR/RVC/GPU/ffmpeg execution.
- No C-4c continuation.
- No new user-facing features.
- No new service files created by this task.
- No `backend/db.py` migration/backfill/schema changes.
- No router split, facade introduction, or service consolidation.
- No `git add` or commit.

## 2. Files Changed

Files intentionally changed by this Stage60 bugfix task:

- `backend/vocal_separator.py`
- `backend/self_check.py`
- `backend/services/stage59_execution_guard_service.py`
- `backend/services/stage59_artifact_persistence_service.py`
- `backend/services/stage59_job_artifact_promotion_service.py`
- `tests/unit/test_vocal_separator_import.py`
- `tests/unit/test_self_check_train_preflight.py`
- `tests/unit/test_stage59c3_execution_guard_service.py`
- `tests/unit/test_stage59c4a_artifact_persistence_contract.py`
- `tests/unit/test_stage59c4b_file_backed_promotion.py`

Current working tree also contains pre-existing / other-agent Stage59C-4b and Stage60 governance changes. I did not revert or commit them.

## 3. What Was Done

Fix 1: `backend/vocal_separator.py` import blocker.

- Problem: `AUDIO_PIPELINE_DIR` used `PROJECT_ROOT` before `PROJECT_ROOT` was defined, causing `NameError` during `backend.main` import.
- Root cause: a workspace-bundled AudioPipeline fallback was inserted above the project root definition.
- Minimal change: define `PROJECT_ROOT` before `AUDIO_PIPELINE_DIR`.
- Test: `tests/unit/test_vocal_separator_import.py`.

Fix 2: execution guard invalid `max_items` handling.

- Problem: `validate_caps(max_items="not-a-number", ...)` raised instead of returning a structured guard error.
- Root cause: `int(max_items)` was outside defensive parsing.
- Minimal change: parse `max_items` inside `try/except` and return `max_items_invalid`.
- Test: `test_validate_caps_rejects_invalid_max_items_without_exception`.

Fix 3: Stage59 runtime path exact run-id segment validation.

- Problem: path validation used substring matching, so `run` could incorrectly match `run_evil`.
- Root cause: `_validate_planned_path_under_sandbox` checked `safe_prefix in norm` rather than exact `startswith(".../<safe_run_id>/")`.
- Minimal change: add `safe_runtime_run_id`, use it in planned paths, validation, and promotion path checks.
- Tests: exact segment rejection and sanitized run-id promotion coverage.

Fix 4: self-check separation of code contract vs external runtime readiness.

- Problem: `check_train_preflight_structure` and `check_train_material_routing` failed when the external RVC train environment was missing dependencies, even though endpoint shape and material routing were correct.
- Root cause: code-structure checks depended on top-level runtime `ok` / `submission_allowed`, which includes external environment readiness.
- Minimal change: structure check now validates schema shape; route check uses `material_decision.submission_allowed` for material routing. Runtime dependency failure remains in `check_train_environment_ready`.
- Test: `tests/unit/test_self_check_train_preflight.py`.

## 4. Debt Delta

- Debt added: 1 small reusable helper inside an existing Stage59 service, 2 new focused unit test files, and small tests in 3 existing test files.
- Debt reduced: 4 immediate risks reduced: import-time crash, unstructured guard exception, unsafe runtime path segment matching, and self-check false negatives that mixed external environment failures into code-contract checks.
- Net debt assessment: negative for immediate operational risk; neutral for long-term architecture because Stage59 services are still intentionally not consolidated in this bugfix round.
- Quantification: new service files by this task = 0; `backend/db.py` changes = 0; real engine executions = 0; direct `get_connection()` reductions = 0; full pytest after changes = 288 passed.

## 5. Invariant Violations

No known Constitution violations.

- No new milestone-named service was created by this task.
- No new migration/backfill/schema logic was added to `backend/db.py`.
- No real UVR/RVC/GPU/ffmpeg execution was enabled.
- No user-facing feature or UI change was added.
- No router split or facade migration was attempted without ADR.

## 6. Simplification Opportunities

- Stage59 service consolidation remains for Stage60A/B; this task intentionally did not introduce durable facades.
- `safe_runtime_run_id` overlaps conceptually with the execution guard's private `_normalize_run_id`; consolidating those helpers should wait for Stage60A dependency inventory to avoid cross-cutting refactor drift.
- `self_check.py` still mutates local ignored runtime DB state through synthetic smoke jobs. A later governance task should add a read-only/temp-DB self-check mode.
- External RVC training environment repair was not attempted; installing or changing CUDA/Python dependencies is outside this governance bugfix scope.

## 7. Validation

Focused tests:

```powershell
python -m pytest tests\unit\test_self_check_train_preflight.py tests\unit\test_vocal_separator_import.py tests\unit\test_stage59c3_execution_guard_service.py tests\unit\test_stage59c4a_artifact_persistence_contract.py tests\unit\test_stage59c4b_file_backed_promotion.py -q --tb=short
# 16 passed, 2 warnings
```

Compile check:

```powershell
python -m py_compile backend\vocal_separator.py backend\services\stage59_execution_guard_service.py backend\services\stage59_artifact_persistence_service.py backend\services\stage59_job_artifact_promotion_service.py
# exit 0
```

Prompt command note:

```powershell
python -m pytest tests/unit/test_lifecycle*.py tests/api/test_*.py -q --tb=short
# PowerShell passed the wildcard literally; pytest returned:
# ERROR: file or directory not found: tests/unit/test_lifecycle*.py
```

Equivalent expanded lifecycle/API regression:

```powershell
$targets = @((Get-ChildItem -LiteralPath 'tests\unit' -Filter 'test_lifecycle*.py').FullName) + @((Get-ChildItem -LiteralPath 'tests\api' -Filter 'test_*.py').FullName); python -m pytest @targets -q --tb=short
# 128 passed, 2 warnings
```

Full regression:

```powershell
python -m pytest -q
# 288 passed, 2 warnings
```

Self check:

```powershell
python -X utf8 backend\self_check.py
# CODE_STRUCTURE_SUMMARY PASS
# RUNTIME_ENVIRONMENT_SUMMARY FAIL
# SELF_CHECK_SUMMARY FAIL
# exit 1
```

Self-check runtime blocker details:

- `D:\RVC\RVCv2\venv\Scripts\python.exe` cannot import `fairseq` because `torch` is missing.
- `faiss` missing.
- `sklearn` missing.
- train GPU torch CUDA check reports `No module named 'torch'`.
- train GPU selection reports `selected=[0]; device_count=0`.

Tracked raw asset scan:

```powershell
git ls-files | Select-String -Pattern '(\.wav|\.mp3|\.flac|\.m4a|\.aac|\.ogg|\.pth|\.index|\.sqlite|\.db)$'
# no output
```

Stage59C-4b CLI, because this task touched C-4b artifact contract/promotion files:

```powershell
python backend\verify_stage59_uvr_ab.py --real-smoke-plan --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
# STAGE59_UVR_AB PASS
# real_execute_allowed=false
# audio_files_written=false
```

## 8. Known Limits

- Required `self_check.py` does not fully pass in this local environment because external RVC training dependencies are missing. I did not install or modify external RVC/CUDA dependencies.
- The working tree remains dirty with pre-existing Stage59C-4b and Stage60 governance changes from prior agents.
- This bugfix does not reduce Stage59 service file count; that belongs to Stage60A/B after dependency inventory.

## 9. Next Recommended Step

Run a Governance Reviewer pass on this report and diff. If accepted, proceed to `Stage60A: dependency inventory and facade boundary review`; separately decide whether to repair the external RVC training environment before requiring `RUNTIME_ENVIRONMENT_SUMMARY PASS` as a merge gate.
