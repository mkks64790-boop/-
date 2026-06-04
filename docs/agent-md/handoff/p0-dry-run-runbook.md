# P0 Training Dry-Run Runbook (Stage60)

**Status**: Active  
**Governance**: Real training allowed only when human approves P0; use `smoke=true` and 1-epoch env overrides for dry-run.

## Prerequisites

1. `external/rvc-webui` populated (see `scripts/populate_external_engines.ps1`).
2. Conda `rvc` env: `D:\Miniconda3\envs\rvc\python.exe` with `torch` + `dotenv`.
3. Launcher or manual env: `scripts/feishark-engine-env.ps1` / `feishark-launcher.ps1`.
4. Sample dry vocals (default):
   - `shared_data/uploads/train_e5790874eb1e.wav`
   - `shared_data/uploads/train_def71bf124f9.wav`

## Step 1 — Environment

```powershell
cd D:\FeiSharkStudio-v2
. .\scripts\feishark-engine-env.ps1
python backend\self_check.py
```

Expect runtime checks PASS when `external/` is present.

## Step 2 — API preflight (no GPU train yet)

With API up (`feishark-launcher.ps1` or `uvicorn backend.main:app --port 8000`):

```powershell
curl "http://127.0.0.1:8000/api/preflight/train?file_count=2"
```

Or offline:

```powershell
python -c "from backend.services.preflight_service import run_train_preflight; print(run_train_preflight('multi_clip_preprocess'))"
```

Record: `ok`, `errors`, `rvc_python`, `cuda_available`.

## Step 3 — Smoke dry-run (automated)

Sets 1-epoch / small batch via env; posts `/api/train` with `smoke=true`:

```powershell
python scripts\stage60_p0_train_dry_run.py
```

Report: `docs/agent-md/worker/stage-60-p0-train-dry-run-report.md`

**PASS criteria**: job `status=完成`, `current_stage=train_register_model`, artifacts include `train_model_pth` + `train_model_index`.

## Step 4 — UI spot-check (optional)

1. Open http://127.0.0.1:8000/ → 训练页上传同样两段干声。
2. Confirm preflight green before submit.
3. Do **not** run long production training without explicit approval.

## Governance gate

| Action | Allowed |
|--------|---------|
| Preflight / self_check | Yes |
| `stage60_p0_train_dry_run.py` (smoke, 1 epoch) | Yes when P0 approved |
| Full epoch production train | Human sign-off only |

## Rollback

- Failed job: note `job_id` in report; no DB schema changes in P0.
- Re-run launcher if RVC 7866 stuck (Conda python, not empty `external/rvc-webui/venv`).