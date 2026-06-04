# Stage60 Phase Close Checklist (Human + GPT Acceptance)

**Date**: 2026-06-05  
**Workspace**: `D:\FeiSharkStudio-v2`  
**Mode**: Governance sprint close (Route A mechanical收口). Not a feature sprint.

## 1. What This Phase Delivered

| Area | Status | Evidence |
|------|--------|----------|
| Stage60C facade migration | **Closed (Option B)** | Public callers on 4 facades; execution_safety inlined; 10 legacy files headered + delegate |
| Stage60D DB governance | **Started, not finished** | `backend/db/` package, repos, job/model on repos; full service migration pending |
| Engine bundling | **Local READY** | `external/rvc-webui`, `rvc-webui-backup`, `audio-pipeline` populated on disk (not in git) |
| Launcher / ops | **Fixed** | `feishark-launcher.ps1` uses Conda `rvc` + `feishark-engine-env.ps1` |
| Frontend i18n | **Done** | zh-CN dashboard/factory/studio committed |
| Training preflight gate | **PASS** (with env) | `self_check` RUNTIME + CODE_STRUCTURE PASS |

## 2. Stage60C Close Decision (Option B — Recommended)

**Declare Stage60C complete** without deleting the 10 `stage59_*` files yet.

Rationale:

- All non-legacy imports use facades; internal legacy cross-imports cleaned.
- One domain (execution_safety) fully inlined; artifact/uvr remain explicit delegation (documented).
- Deleting legacy files now adds risk with low payoff; retirement map + human approval required for deletion.

**Not blocking**: optional future Stage60C-2 to inline artifact + uvr groups and delete shims (ADR if >3 core files).

## 3. Human Acceptance (check each)

### Studio tool (port 8000)

- [ ] `feishark-launcher.ps1` shows `RVC_PYTHON: D:\Miniconda3\envs\rvc\python.exe`
- [ ] Console shows `RVC ready` and opens `http://127.0.0.1:8000/`
- [ ] 工作台 / 工厂 / 录音棚 pages load (zh-CN)

### Engines (7866 / 7865)

- [ ] `http://127.0.0.1:7866` Gradio responds (primary RVC)
- [ ] `http://127.0.0.1:7865` responds (backup instance)
- [ ] 秋风模型（若有）在 `external/rvc-webui/assets/weights` 且 Studio 可用 `origin=backup` 或名称含「秋风」

### Automated gate

```powershell
. D:\FeiSharkStudio-v2\scripts\feishark-engine-env.ps1
cd D:\FeiSharkStudio-v2
python -X utf8 backend\self_check.py
python -m pytest tests/unit/ -q -k "stage59c or stage60"
```

- [ ] `SELF_CHECK_SUMMARY PASS`
- [ ] pytest stage59c/stage60 subset green

### Governance

- [ ] No `git add .` used for `external/` weights, `shared_data/`, `backend/feishark.db`
- [ ] GPT reviewed snapshot + `stage-60c-shim-removal-report.md` and signed off governance continuation
- [ ] Real training / real UVR still **not** started without explicit human approval + ADR

## 4. Known Backlog (not Stage60 close blockers)

- pytest: `test_stage57_audio_pipeline_contract` (1 fail), `test_batches_api` (1 fail)
- Stage60D: migrate remaining services off raw `get_connection()`
- Backup RVC disk: full copy + weights junction (optional slim later)
- Grok user-guide 汉化 (optional, out of repo)
- `external/` must be re-copied on new machine via `scripts/populate_external_engines.ps1`

## 5. Next Phase Options (after human signs this checklist)

| Priority | Track | Action |
|----------|-------|--------|
| **P0** | Product validation | DONE — see `p0-dry-run-runbook.md` + `stage-60-p0-train-dry-run-report.md` (PASS `train_bfe8d29c6910`) |
| **P1** | Governance | IN PROGRESS — `asset_service` + `track_service` → repositories (see `stage-60-p1-asset-repository-migration-report.md`) |
| **P2** | GPT | Memory alignment: update architect prompts that still say "start Stage60A" |
| **P3** | Feature | Only after governance sign-off + new ADR |

## 6. Files for GPT Handoff Packet

1. `docs/agent-md/handoff/stage-60-governance-memory-snapshot.md`
2. `docs/agent-md/worker/stage-60c-shim-removal-report.md`
3. `docs/agent-md/worker/stage-60d-db-access-inventory-report.md`
4. This checklist
5. `git log --oneline -15`

**Ask GPT**: Confirm Stage60C Option B close, approve Stage60D next PR plan, and whether P0 training dry-run is allowed under current ADRs.