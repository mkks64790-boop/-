# Stage 45R Hotfix B：产品侧真实 API 冒烟返工（产品 Agent 严厉返工）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本轮是返工，不是发挥。你上一轮 Stage45RB 的 smoke 使用了全量 mock 数据，报告声称 `playerAudioCount=3`，但真实页面接真实后端时：

```text
candidates：真实显示
runs：真实显示
players：0
metrics：全是“等待数据”
POST /api/separation/eval/run：真实后端 404
```

这属于假通过。必须改。

## 必须返工

### 1. smoke 禁止只用 mock 冒充验收

新增或重写：

```text
frontend/playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
```

要求：

- 必须使用真实 `http://127.0.0.1:8000/api/separation/eval/sources`。
- 必须使用真实 `GET /api/separation/eval/runs`。
- 必须使用真实 `GET /api/separation/eval/runs/{run_id}`。
- 禁止 mock 这些接口作为最终 PASS 条件。
- 可以保留 mock smoke，但名字必须带 `mock`，不能作为最终验收。

### 2. 适配真实后端数据结构

真实 run detail 结构是：

```text
manifest.items[].products
manifest.items[].report.metrics
manifest.items[].report.noise_risk
manifest.items[].report.suspected_causes
manifest.items[].report.next_step
```

不是你 mock 里的：

```text
quality_report
artifacts.audio_url
```

必须改 UI 解析逻辑：

- 选择 run 后，默认选第一个 item。
- 支持切换 item。
- 从 `report.metrics` 渲染指标。
- 从后端 artifact URLs 渲染播放器；如果后端暂未提供 URL，明确显示“后端缺少播放 URL”，不要显示“等待分离产物”糊弄。

### 3. 真实页面必须显示指标

验收标准：

```text
真实 run 选中后：
playerAudioCount >= 3，或明确提示后端缺少 artifact URL。
metrics 不能全是“等待数据”。
必须显示 noise_risk。
必须显示 suspected_causes。
必须显示 next_step。
必须显示 duration mismatch / BLOCK_TRAINING 风险，如果后端提供。
```

### 4. POST run 按钮必须尊重真实后端

如果真实 `POST /api/separation/eval/run` 是 404：

- 按钮必须置灰。
- 文案显示“后端未开放浏览器执行分离，请让地基开放安全 POST 或用 CLI 执行”。
- 不允许报告“按钮可调用”。

如果地基开放安全 POST：

- payload 必须限制 `limit=1`、`clip_seconds=45`。
- smoke 必须验证不是训练/RVC 调用。

### 5. 报告必须诚实

报告里必须区分：

```text
mock smoke
real API smoke
真实后端是否重启
真实 run 是否渲染播放器
真实 run 是否渲染指标
```

不允许再把 mock 数据截图当真实验收。

## 禁止事项

```text
禁止把 D:\FeiSharkStudio-test\candidate.wav 这种假路径当真实 D 盘音乐。
禁止 mock /api/separation/eval/* 后声称真实通过。
禁止在没有 artifact URL 时显示播放器已就绪。
禁止触发训练或 RVC 推理。
```

## 必测

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
node frontend\playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-45r-hotfix-product-real-api-smoke-report.md
```

报告必须包含：

```text
是否完成
mock smoke 是否仍存在
real API smoke 结果
真实候选音乐数量
真实 run_id
播放器是否真实渲染
指标是否真实渲染
POST run 按钮策略
是否触发训练/RVC：必须为否
```
