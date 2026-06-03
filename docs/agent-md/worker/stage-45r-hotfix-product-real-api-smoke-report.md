# Stage 45R Hotfix B：产品侧真实 API smoke 返工报告

> Stage45RC 返工说明：本报告记录的是上一轮真实 API smoke 状态，后端重启后 `GET /api/separation/eval/run = 405`、`POST /api/separation/eval/run = 501`。最终按钮门禁与 smoke 结论以 `docs/agent-md/worker/stage-45rc-product-post501-gate-and-smoke-honesty-report.md` 为准。

## 是否完成

已完成返工。

本轮不再用 mock `/api/separation/eval/*` 声称验收通过，新增真实 API smoke，并修正 Factory 分离质量实验室对真实 run detail 的解析。

## mock smoke 是否仍存在

不存在。

上一轮的 `frontend/playwright_stage45rb_separation_quality_lab_smoke.cjs` 是 mock smoke，且文件名未标 mock。本轮已删除，避免继续被误当最终验收。

## 修改文件

- `frontend/factory.html`
- `frontend/js/factory/main.js`
- `frontend/css/app.css`
- `frontend/playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs`
- `docs/agent-md/worker/stage-45r-hotfix-product-real-api-smoke-report.md`
- `docs/agent-md/worker/stage-45rb-separation-quality-product-report.md`

## 真实 API smoke 结果

已通过：

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
node frontend\playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
```

真实 API 结果：

```json
{
  "sourceCount": 4,
  "runCount": 1,
  "runId": "stage45r_20260602_171704_201ec7ff",
  "itemHasReport": true,
  "noiseRisk": "high",
  "postProbeStatus": 404
}
```

浏览器结果：

- `playerAudioCount = 3`
- `missingUrlCount = 0`
- `pageErrors = []`
- `unsafeCalls = []`
- desktop/mobile 均无横向溢出
- 截图：`output/playwright/stage45rb_separation_quality_lab_real_api.png`

## 真实后端是否重启

产品 Agent 未重启后端。本次使用当前运行中的真实后端：

```text
http://127.0.0.1:8000
```

真实接口均由该后端返回。

## 真实候选音乐数量

真实 `GET /api/separation/eval/sources` 返回 4 首候选音乐。

页面候选区显示真实 D 盘候选路径，没有使用 `D:\FeiSharkStudio-test\candidate.wav` 这类假路径。

## 真实 run_id

```text
stage45r_20260602_171704_201ec7ff
```

页面 run 列表真实渲染该 run_id。

## 播放器是否真实渲染

是。

real API smoke 在真实页面检测到：

```text
playerAudioCount = 3
```

同时产品侧已修正规则：如果后端没有提供浏览器可访问的 artifact URL，不会再显示“等待分离产物”糊弄，而是明确显示：

```text
后端缺少播放 URL
```

## 指标是否真实渲染

是。

UI 已从真实结构读取：

```text
manifest.items[].report.metrics
manifest.items[].report.noise_risk
manifest.items[].report.suspected_causes
manifest.items[].report.next_step
```

页面显示：

- `noise_risk = high`
- `suspected_causes` 包含 `duration mismatch`
- `next_step = Do not start training...`
- `duration mismatch：original_excerpt: 45s；vocal: 26.807s；instrumental: 26.807s`
- `BLOCK_TRAINING：noise_risk=high`

指标不再全是“等待数据”。

## POST run 按钮策略

真实后端当前：

```text
GET /api/separation/eval/run -> 404
POST /api/separation/eval/run -> 404
```

因此产品侧按钮置灰，文案为：

```text
后端未开放浏览器执行分离，请让地基开放安全 POST 或用 CLI 执行
```

本轮 smoke 未触发 POST run。

## 是否触发训练/RVC

否。

Smoke 监听结果：

```json
{
  "unsafeCalls": [],
  "postPayloads": []
}
```

没有触发训练、RVC 推理、cover job 或 `/api/process/*`。
