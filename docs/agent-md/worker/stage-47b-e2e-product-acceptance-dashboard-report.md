# Stage 47B 产品侧端到端验收看板报告

## 是否完成

已完成产品侧改造与真实浏览器 smoke。

- Dashboard 新增 Stage47 端到端只读验收卡。
- Factory 模型资产库新增 Stage47 实训模型识别、pth/index/source/cover 可用性展示。
- Studio 在真实 Stage47 cover artifact 载入时标注“Stage47 短 smoke / 完整 cover”，不标注为正式成品。
- 新增真实 API smoke：`frontend/playwright_stage47_e2e_acceptance_dashboard_smoke.cjs`。

## 当前真实 API 发现

运行时间：2026-06-02。

- Stage47 training job：已发现 `train_7f4d6b4e611e`。
- training status：`训练中` / `train_core`。
- Stage47 model：未发现。
- Stage47 cover job：未发现。
- Stage47 final artifact：未发现。
- Studio 是否可播放：否，原因是当前尚无 Stage47 cover artifact / playback URL。

说明：当前真实闭环还在地基训练阶段，产品 UI 只展示 running / pending，不写死成功，也不把 Stage26 或 recovered model 冒充 Stage47 新模型。

## 真实 API smoke 结果

已通过：

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
node frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
```

Smoke 结果摘要：

- realApi.trainingJobId：`train_7f4d6b4e611e`
- realApi.modelId：空
- realApi.coverJobId：空
- realApi.studioReady：`false`
- Dashboard：显示真实 training job，模型 / cover / Studio 仍为未就绪。
- Factory：显示 `Stage47 实训模型 0 个`。
- unsafeCalls：`[]`
- pageErrors：`[]`
- desktop/mobile overflow：未发现。

截图：

- `output/playwright/stage47_e2e_acceptance_dashboard.png`
- `output/playwright/stage47_e2e_acceptance_factory.png`

## 是否触发训练 / RVC / cover

否。

产品侧本轮只读取：

- `/api/jobs`
- `/api/jobs/{job_id}`
- `/api/jobs/{job_id}/artifacts`
- `/api/models`

Smoke 监听到的训练/RVC/cover危险请求为 `[]`，没有触发 `/api/train`、`/api/process/*`、`/cover-jobs`、`/api/cover`、`/rvc/infer` 或 `/infer`。

## 下一个联调点

等待地基完成 `train_7f4d6b4e611e` 后生成 Stage47 model。届时产品 smoke 会继续要求：

- Factory 模型库出现 Stage47 实训模型。
- pth/index/source training job/cover usable 字段真实展示。
- cover job 出现并有 cover_master playback URL。
- Studio 可以打开并播放，且标注“Stage47 短 smoke / 完整 cover”。
