# Stage60 Training Engine Bundling Plan (Infra Stability & Simplification)

**Status**: Proposed addition to Stage60 governance (prep for Stage60A)  
**Date**: 2026-06  
**Related**: stage60-db-governance-plan.md, stage60-stage59-service-consolidation-plan.md, memory snapshot, Constitution (simplification opportunities, complexity compression)

## Problem
Current RVC and AudioPipeline (UVR) engines are referenced via brittle external absolute paths:
- `model_trainer.py`: FEISHARK_RVC_DIR or hardcoded D:\RVC\RVCv2 etc. RVC_PYTHON fallbacks to conda/venv outside project.
- `vocal_separator.py`: FEISHARK_AUDIO_PIPELINE or D:\AudioPipeline etc. for UVR5 via subprocess + onnx model.

This leads to:
- "Works on my machine" issues (user reports current setups incomplete/uncertain).
- Risk of accidental deletion or path breakage when moving machines/folders.
- Previous agents deployed externally (scattered installs).
- Unstable training: materials ready but engines not reliably integrated.
- Violates "self-contained workspace" for long-term training stability (user has prepared materials in shared_data/).

From code checks:
- RVC dir may exist partially (e.g. D:\RVC\RVCv2 present but runtime/python.exe missing).
- No workspace-relative defaults.
- .gitignore already ignores *.pth, venv/, some rvc logs – good start, but no external/ handling.

This is technical debt (external dependency sprawl) that increases training fragility, contrary to Constitution "复杂度必须被主动压缩" and "Simplification Opportunities" in reports.

## Goal (Governance-aligned)
Make RVC (for model training + voice conversion) and AudioPipeline/UVR (for separation in cover/training data prep) **self-contained inside the project workspace**.

Benefits:
- All in one tree: `project/external/rvc-webui/`, `project/external/audio-pipeline/`.
- Materials (user's prepared clean vocals) stay in `shared_data/`, engines bundled, no deletion risk.
- Stable training: relative paths, versioned setup scripts, consistent across machines.
- Simplification: reduce "external install" surface, easier launcher integration, better for future real UVR/RVC enablement (post-governance).
- Debt reduction: Document and retire scattered external deps.

**Scope limits (governance only)**:
- No real UVR/RVC/GPU execution in this task (per memory snapshot and bugfix prompt).
- Read-only inventory first, then minimal path updates + scripts.
- No new stage* services.
- Large binaries/models: .gitignore + download-on-setup scripts (do not bloat repo).
- Compatible with existing env vars (override still works).
- Part of Stage60A "dependency inventory" – treat external engines as a dependency to facade/bound.

## Proposed Structure
Inside D:\FeiSharkStudio-v2\ :

external/
  rvc-webui/                  # complete RVC-WebUI for main (source + runtime + models; your primary)
    # e.g. after setup: runtime/, models/, configs/ etc. (includes support for scanning 秋风RVC etc.)
  rvc-webui-backup/ or rvc-webui-qiufeng/  # for 秋风RVC as backup (separate webui instance on e.g. port 7865; you have enabled it in studio as backup)
    # allows stable backup RVC model without relying on scattered external deploys
  audio-pipeline/             # complete AudioPipeline for UVR5
    # venv/, models/UVR-MDX-NET-Voc_FT.onnx etc.

scripts/
  setup_rvc.ps1               # clone or download complete RVC-WebUI into external/rvc-webui, setup venv if needed
  setup_audiopipeline.ps1     # setup AudioPipeline + download UVR models
  setup_training_engines.ps1  # combined

Update .env.example or docs with:
FEISHARK_RVC_DIR=external/rvc-webui
FEISHARK_RVC_PYTHON=external/rvc-webui/runtime/python.exe
FEISHARK_AUDIO_PIPELINE=external/audio-pipeline

## Implementation Phases (align with Stage60A)
**Phase 1: Inventory (in Stage60A dependency review)**
- Scan all references to RVC/AudioPipeline paths (model_trainer.py, vocal_separator.py, cover_strategy.py, voice_changer.py, launcher.ps1, preflight, etc.).
- List current fallbacks and env vars.
- Document as "external engine debt" in Stage60A output (dependency graph).
- Propose facade: e.g. a small `engine_paths.py` or update in training services (but minimal, no new service).

**Phase 2: Bundling + Path Updates (small, contained changes)**
- Update _pick_first_existing in model_trainer.py and vocal_separator.py:
  Prefer:
  1. env var (backward compat)
  2. os.path.join(PROJECT_ROOT, "external", "rvc-webui")
  3. os.path.join(PROJECT_ROOT, "external", "rvc")
  4. old hardcoded
- Same for AudioPipeline.
- Add to .gitignore:
  external/rvc-webui/venv/
  external/rvc-webui/runtime/
  external/rvc-webui/models/*.pth
  external/rvc-webui/logs/
  external/audio-pipeline/venv/
  external/audio-pipeline/models/*.onnx
  external/**/ *.log
  (keep small scripts/configs)
- Update feishark-launcher.ps1 to detect and start RVC from workspace external/ if present.
- Add setup scripts (PowerShell, since Windows primary).
- Update README.md, docs/governance/, agent-md if needed, with "For stable local training: run scripts/setup_training_engines.ps1 after clone. Place your prepared materials in shared_data/."
- Update any tests/smokes that assume paths.

**Phase 3: Validation (no real exec)**
- Dry-run path resolution.
- Use existing /api/training/gpu-status, /api/train (with mock data), verify_stage59 dry/mock.
- Confirm materials in shared_data/ are discoverable.
- Full pytest + self_check.
- Worker report with Debt Delta (reduced external fragility), no violations.

## Acceptance Criteria
- Workspace clone + run setup script → engines "just work" for training without external D:\ installs.
- User's prepared materials usable via existing APIs (/api/train for RVC models, cover for full pipeline once engines ready).
- No bloat in git (binaries ignored).
- Paths relative to PROJECT_ROOT.
- Backward compat (old env vars or external installs still work as fallback).
- Documented in one place.
- Contributes to Stage60 simplification (negative or neutral debt delta).

## Risks & Mitigations
- Large downloads: Use scripts with progress, optional (user can still use env override).
- Models licensing: Follow RVC/UVR original (user responsible for downloads).
- During governance: This task is **prep/infra only** – no execution of real workloads. Real UVR/RVC runs still blocked until post-Stage60 + ADR + human approval (per memory snapshot).
- If touches >3 core files: Will require ADR update (as per Constitution).

## Relation to User's Request
- Addresses "我手里是准备好了素材的" + "rvc跟AudioPipeline都不确定是完整的 能用的" + "让agent在本地部署的" (external fragility).
- "整合完整的进入工作区" → exactly this plan: bundle complete engines inside project tree.
- "不用担心被误删 而且后期训练也稳定" → achieved via relative paths + .gitignore + setup scripts + all-in-one workspace.
- Ties to memory snapshot: "Single long-file training... native RVC preprocessing", "One-click AI cover: source song -> UVR separation -> RVC".
- Can be inventoried in Stage60A as part of making training "stable" before resuming full feature work.

## Suggested First Step (for Stage60A or bugfix extension)
Add to Stage60A architect prompt:
- Inventory external engine deps.
- Propose this bundling as "Simplification Opportunity".
- Implement as small contained changes + scripts (scoped to this plan).
- Include in worker report Debt Delta section.

This is not "new feature" – it's debt repayment and complexity compression for the existing training north star.

## Next Actions
1. Include in Stage60A planning (after current bugfix report review).
2. Create setup scripts and path updates as minimal PRs during/after inventory.
3. Once bundled, user can reliably use prepared materials for RVC training and UVR-assisted pipelines (subject to governance approval for real runs).

**Human approval needed** for full execution, per Constitution.

This plan keeps us honest to "不能贪快" while addressing the real pain point for stable training.