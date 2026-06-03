# Stage 45RC：产品侧 POST 501 门禁与 smoke 诚实性报告

## 是否完成

已完成。

本轮修正了 Factory 分离质量实验室的浏览器执行入口门禁：不再使用 `GET /api/separation/eval/run` 探测 POST 能力；当前真实后端 `POST /api/separation/eval/run = 501` 时，按钮保持置灰，页面不会再触发按钮 POST。

## 真实 POST /api/separation/eval/run 状态码

```text
501
```

Smoke 使用真实 POST 探测，不使用 GET 作为 POST 能力判断。

## 按钮是否置灰

是。

```json
{
  "runButtonDisabled": true
}
```

## 按钮文案

```text
后端未开放浏览器执行分离，请用 CLI 执行短片段质检
```

## postPayloads 是否为空

是。

```json
{
  "postPayloads": []
}
```

说明：smoke 会在浏览器外用真实 POST 探测后端状态；页面本身没有因为按钮点击发送 POST。

## 播放器是否仍为 3 个

是。

```json
{
  "playerAudioCount": 3,
  "missingUrlCount": 0
}
```

## 指标是否仍显示 high / duration mismatch / BLOCK_TRAINING

是。

真实 run 锚点：

```text
stage45r_20260602_171704_201ec7ff
```

页面真实显示：

- `noise_risk = high`
- `duration mismatch：original_excerpt: 45s；vocal: 26.807s；instrumental: 26.807s`
- `BLOCK_TRAINING：noise_risk=high`
- `suspected_causes` 包含 duration mismatch 和 original clipping risk
- `next_step = Do not start training...`

## 是否触发训练/RVC

否。

```json
{
  "unsafeCalls": []
}
```

未触发训练、RVC、cover job、`/api/process/*`。

## 测试结果

已通过：

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
node frontend\playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
```

最新 real API smoke 摘要：

```json
{
  "sourceCount": 4,
  "runCount": 4,
  "runId": "stage45r_20260602_171704_201ec7ff",
  "noiseRisk": "high",
  "postStatus": 501,
  "runButtonDisabled": true,
  "postPayloads": [],
  "pageErrors": [],
  "unsafeCalls": []
}
```

截图：

```text
output/playwright/stage45rb_separation_quality_lab_real_api.png
```

## 备注

产品侧已改为默认禁用浏览器执行分离。只有后端在 `sources/runs` 等真实 API 中明确提供可浏览器执行的能力字段时，按钮才会启用。
