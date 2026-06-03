# Stage58D QA Audit Report

审计时间：2026-06-03
审计范围：`D:\FeiSharkStudio-v2` 当前工作树与已运行的 `http://127.0.0.1:8000` FastAPI 服务。
边界：只读审计；未启动训练、未启动 RVC 7866、未提交 UI 表单、未删除 `shared_data` 资产。仅写入本报告。

## 总结结论

Stage58 当前不能按“用户态干净 + 真实素材可信”收口。Stage58A 已开始过滤 `/api/jobs`、`/api/jobs/summary`、`/api/models` 的测试噪声，但过滤还不完整：`/api/batches` 仍默认返回 80 个 stage/smoke 批次，Factory 默认统计直接展示这些数据；Studio 默认载入 Stage47 短 smoke 成品；Dashboard/Factory 的模型入口仍可见 stage 模型。素材库 manifest 已存在并区分素材类型，但 DB/API 把“用户本地、人工权利确认待定”的干声标为 `clean_dry_vocal` 并给出训练 route hint，可信度边界不够硬。

风险评级：**不建议最终验收通过**。应先修 `/api/batches`/tracks 过滤、Studio 默认入口、素材权利 gating，再跑最终命令清单。

## 关键失败点

### P0 - Factory 用户列表仍被测试批次污染

证据：
- DB：`release_batches=80`，`batches_smoke=80`；`tracks=138`，`tracks_smoke=137`。
- API：`GET /api/batches` 返回 50 items，`has_stage=True`、`has_smoke=True`、`has_test=True`。
- Playwright/Chrome 只读 DOM：Factory 首屏显示 `批次 80`、`曲目 138`，并出现 `stage41 recovered model smoke`、`Stage41 recovered smoke`、`short_smoke.wav`、`task_stage41_ce1b32f2`。
- 代码证据：`backend/services/batch_service.py:list_batches()` 没有 `include_smoke/include_test_data` 或过滤逻辑；`backend/main.py:/api/batches` 直接返回 `list_batches()`。

风险：
- 用户打开 Factory 默认看到的不是产品批量工作台，而是历史 stage/playwright/smoke 垃圾。
- 当前 Stage58A 后端过滤覆盖 jobs/models，但没有覆盖 batches/tracks，验收会漏掉最大污染源。

修复建议：
1. 给 `release_batches`、`tracks` 增加统一 test-data 识别与默认隐藏。
2. `/api/batches` 返回 `hidden_test_count/include_test_data`，保留显式“显示测试记录”开关。
3. Factory 默认列表和统计使用过滤后的用户态数据，测试抽屉默认收起。

### P0 - Studio 默认载入 smoke 成品，真实素材验收不可信

证据：
- Playwright/Chrome 只读 DOM：Studio 默认载入 `task_b2272d133fff / art_f99f7e4afb10`，页面文案包含 `Stage47 短 smoke / 完整 cover`、`浏览器 smoke 记录，不是人工验收`。
- DB artifact：`art_f99f7e4afb10` metadata 中 `listening_review.notes` 为 `stage49 browser smoke...`，verdict 仍是 `unreviewed`。
- Studio 资源库还暴露大量 `stage26_real_long_1780063446 · task_*` 和 `test_sep_001`。

风险：
- 默认 Studio 入口会让用户把 smoke 成品误认为当前正式工作对象。
- “浏览器 smoke 记录”不应作为真实人工试听或发布候选依据。

修复建议：
1. Studio 默认只加载明确非测试、非 smoke、已有人审或真实验收标记的成品。
2. smoke/stage 成品只能在显式测试模式或 QA 抽屉中显示。
3. `unreviewed + smoke note` 不得触发任何正式可用、候选成品、发布候选 UI。

### P1 - Jobs 过滤有进步，但仍有 stale pending 测试残留默认可见

证据：
- DB：`jobs=438`；`jobs_smoke_stage_test=399`；`jobs_pending_any=11`；`jobs_pending_smoke_stage_test=10`。
- stale pending 测试任务包括 `smoke_retry_ba451022`、`stage45r_eval_a904bce4d24b`、`stage45r_eval_1987cd899406`、`stage45r_eval_a7cc23e60d89`、`stage45r_eval_72e712476a64`、`stage45r_eval_a7a180d4d334`、`stage45r_eval_942cb831b343`、`stage45r_eval_bd99cca85a78`、`stage45r_eval_12212e18a3d0`、`stage45r_eval_a1b032f385ec`。
- API：`GET /api/jobs` still contains `stage45r_eval_* pending` in the first 50, while `GET /api/jobs/summary` is filtered.

风险：
- stale pending 任务虽然 `compute_ready=0`，不会被调度器直接吃掉，但仍会污染排队/列表/状态判断。
- `/api/jobs` 和 summary 口径不一致，UI 可能显示“summary 干净、列表脏”。

修复建议：
1. 扩展 `smoke_filter.py` 对 `stage45r_eval_*` pending 这类 separation eval job_id 的过滤。
2. 给 stale pending 测试任务单独做非破坏性归档状态或 QA-only 标记，不物理删除。
3. 为 `/api/jobs` 增加断言：默认列表不得包含 `stage45r_eval_*`、`smoke_*`、`self_check`、`playwright`。

### P1 - 模型入口仍默认展示阶段模型

证据：
- DB：`voice_models=128`；`models_smoke_stage_test=124`。
- API：`GET /api/models` 已降到 6 items，但仍有 `stage8_multi_success4`、`stage26_real_long_*`、`朱朱_stage47_single_long`。
- Dashboard DOM：cover 模型下拉默认显示 `stage8_multi_success4`、`stage26_real_long_1780063060`、`stage26_real_long_1780063446`、`朱朱_stage47_single_long`。
- Factory DOM：`已读取 6 个模型资产，其中 6 个可用于翻唱；Stage47 实训模型 1 个。`

风险：
- stage 模型可以是验收素材，但默认混在用户可用模型中会让产品看起来仍是测试台。
- `stage47` 可被保护为真实闭环证据，但必须贴上“验收样本/非正式发布”标签，而不是普通模型。

修复建议：
1. 模型过滤区分 `qa_evidence_model` 与 `user_available_model`。
2. 默认 cover 模型选择器仅展示用户正式模型或手动确认模型。
3. Stage47/Stage26 只进 QA/历史验收抽屉，除非用户显式开启。

### P1 - 素材验收 manifest 存在，但权利与训练 gating 不够硬

证据：
- Manifest 存在：`shared_data/material_library/manifests/material_manifest.json`。
- Manifest 区分用户干声、cover source、public-domain voice、public-domain separation benchmark、synthetic benchmark。
- Manifest 对用户干声写明 `user_provided_local_pending_manual_rights_confirmation`，且 intended use 要求人工权利确认前不得训练/发布。
- API/DB：用户干声 `朱朱干声.mp3`、`朱朱干声唱.mp3` 被标为 `material_role=dry_vocal`、`material_profile=clean_dry_vocal`、`quality_state=probe_ok`、`route_hint=training_baseline_multi_clean_direct`、`license_status=user_provided_local`。

风险：
- `probe_ok/clean_dry_vocal` 是音频探测通过，不等于权利/训练/发布可用。
- 当前标签容易让 agent 把“人工确认待定”的素材当成正式训练材料。

修复建议：
1. 增加 `rights_confirmed` 或 `manual_rights_confirmation_required` 字段，并让训练入口强制检查。
2. `user_provided_local_pending_manual_rights_confirmation` 不得自动 route 到正式训练，只能显示为候选。
3. UI 中把 `probe_ok` 改写为“格式探测通过”，不要写成“正式可用”。

### P2 - 安全边界当前未被本审计破坏，但环境有外部长任务

证据：
- `netstat`：`127.0.0.1:8000` 正在监听；`7866` 未监听。
- `/api/health`：RVC `online=false`，base_url `http://127.0.0.1:7866`。
- FeiShark DB：`compute_mutex.owner_task_id=''`；active compute status rows 为 0。
- 进程：存在 `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`。
- 进程：存在外部 `ffmpeg`/Python 长任务，但命令行不属于 `D:\FeiSharkStudio-v2`；本审计未触碰外部项目。
- `shared_data` 未删除；只发现 `shared_data/material_library/quarantine` 目录，无删除/归档动作证据。

风险：
- QA 机器上同时跑外部长任务会干扰“没有误启动长任务”的判断。对 FeiShark 可判定为未发现 7866/训练/GPU 长任务，但不能声明整机完全空闲。

## 已执行验证

通过：
- `python -m py_compile backend\main.py backend\db.py backend\services\smoke_filter.py backend\services\model_service.py backend\services\job_service.py backend\services\batch_service.py backend\services\material_library_service.py backend\self_check.py`
- ESM syntax check via temporary UTF-8 `.mjs` copies for `frontend\js\main.js`、`frontend\js\jobs.js`、`frontend\js\models.js`、`frontend\js\cover.js`、`frontend\js\factory\main.js`、`frontend\js\studio.js`
- `python -m pytest tests\api\test_stage58_user_noise_filter_api.py -q` -> `3 passed, 2 warnings`
- `python -m pytest tests\api\test_stage57_backend_contracts_api.py tests\api\test_stage53_material_library_api.py tests\unit\test_training_runtime_guard.py -q` -> `14 passed, 2 warnings`
- Playwright via installed Chrome channel, read-only：Dashboard / Factory / Studio core selectors present; no console errors.

未执行：
- 未运行 full `python -m pytest -q`，避免在并发 agent 修改期间把全量失败误归因；最终验收必须补跑。
- 未运行原生命令 `python -m backend.self_check`，因为它会写 synthetic smoke jobs；只验证了临时 DB copy 可建立。
- 未运行 UVR/RVC/训练/7866/长 GPU 任务。
- 未运行 `backend/verify_stage45r_separation_quality_audit.py`，需主控确认不会触发长 UVR 后再跑。

## 后续 A/B/C 改动后的复跑要求

如果后端过滤 agent 继续改 A：复跑 `/api/jobs`、`/api/jobs/summary`、`/api/models`、`/api/batches`、`/api/tracks` 默认响应，断言无 `smoke/stage/test/playwright/self_check/stage45r_eval` 污染；同时新增 batches/tracks 后端测试。

如果前端 UI agent 继续改 B：用 Playwright 打开 Dashboard/Factory/Studio，确认默认页面不铺满测试记录；“显示测试记录”必须是显式开关，默认 off。

如果素材验收 agent 继续改 C：复核 `material_manifest.json`、`/api/material-library/summary`、`/api/material-library/items`、训练 preflight；必须证明 pending manual rights material 不会被自动标成正式训练/发布可用。

## 最终验收命令清单

安全前置：

```powershell
netstat -ano | Select-String -Pattern ':7866|:8000'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'FeiSharkStudio-v2|uvicorn|rvc|train|ffmpeg' } | Select-Object ProcessId,Name,CommandLine
```

后端与测试：

```powershell
python -m pytest -q
python -m pytest tests\api\test_stage58_user_noise_filter_api.py -q
python -m pytest tests\api\test_stage53_material_library_api.py tests\api\test_stage57_backend_contracts_api.py -q
python -m py_compile backend\main.py backend\db.py backend\self_check.py backend\services\smoke_filter.py backend\services\job_service.py backend\services\model_service.py backend\services\batch_service.py backend\services\material_library_service.py
```

前端 JS syntax：

```powershell
$files = @('frontend\js\main.js','frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js')
$tmp = Join-Path $env:TEMP ('feishark_jscheck_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  foreach ($f in $files) {
    $dest = Join-Path $tmp (([IO.Path]::GetFileNameWithoutExtension($f)) + '.mjs')
    [IO.File]::Copy((Resolve-Path $f), $dest, $true)
    node --check $dest
  }
} finally {
  Remove-Item -LiteralPath $tmp -Recurse -Force
}
```

Playwright：

```powershell
node frontend\playwright_stage42b_three_page_product_shell_smoke.cjs
node frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
node frontend\playwright_stage50_review_routing_product_smoke.cjs
```

隔离 DB self_check，不允许直接写真实 DB：

```powershell
@'
import os, shutil, tempfile
from pathlib import Path
import backend.db as db
import backend.self_check as sc

src = Path("backend/feishark.db").resolve()
with tempfile.TemporaryDirectory(prefix="feishark_selfcheck_") as td:
    tmp = Path(td) / "feishark.db"
    shutil.copy2(src, tmp)
    db.DB_PATH = str(tmp)
    sc.DB_PATH = str(tmp)
    raise SystemExit(sc.main())
'@ | python -
```

Stage verify scripts：

```powershell
python backend\verify_stage43_studio_entry_contract.py
python backend\verify_stage44_training_preset_runtime_contract.py
python backend\verify_stage45r_separation_quality_audit.py
```

注意：`verify_stage45r_separation_quality_audit.py` 必须先确认只读/短任务模式；不得在最终验收中启动长 UVR。

## 修复顺序

1. P0：给 `/api/batches`、tracks 和 Factory 统计补默认测试过滤。
2. P0：Studio 默认入口改为非测试、非 smoke、可审计的用户态成品；Stage47 smoke 只进 QA 抽屉。
3. P1：修 `stage45r_eval_* pending` 默认列表泄漏。
4. P1：模型入口区分 QA evidence model 与 user available model。
5. P1：素材库增加权利确认 gating，`probe_ok` 不得等同正式可用。
6. P2：最终验收前冻结并记录 FeiShark scoped 进程快照。
