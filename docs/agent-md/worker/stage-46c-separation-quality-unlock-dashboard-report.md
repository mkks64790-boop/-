# Stage 46C：分离质量与训练解锁看板报告

## 是否完成

已完成。

本轮在 Factory 的“分离质量实验室”内新增训练解锁状态卡和 15/30/45 秒对照 run 表格，没有新开页面，也没有触发训练、RVC 或 cover job。

## 真实 run 数量

真实 `GET /api/separation/eval/runs` 返回：

```text
7
```

Smoke 锚定的历史 run 仍可读取：

```text
stage45r_20260602_171704_201ec7ff
```

## 15/30/45 对照是否显示

是。

页面表格显示真实 duration 证据：

```text
15s：0.5952 high / 1.0000 low
30s：0.5956 high / 1.0000 low
45s：0.5957 high / 1.0000 low
```

表格字段包含：

- `run_id`
- `clip_seconds`
- `original duration`
- `vocal duration`
- `instrumental duration`
- `duration_ratio`
- `risk`

ratio `< 0.95` 的旧风险行用危险态展示，ratio `>= 0.95` 的修复后行用通过态展示。

## 训练解锁状态显示结果

当前最新 run：

```text
stage45r_20260602_193728_d0f83e7c
```

看板显示：

```text
可尝试短训练冒烟
```

原因：

```text
三段对照均通过；仍需短训练 smoke 另行验收。
```

页面保留约束文案：

```text
BLOCK_TRAINING=false 只代表分离时长门槛通过；恢复训练还需要短训练 smoke 另行验收。
```

## 当前 BLOCK_TRAINING

当前最新 run：

```text
BLOCK_TRAINING=false
duration_ratio=1.0000
```

旧风险 run 仍在表格中可见：

```text
BLOCK_TRAINING=true
duration_ratio=0.595x
duration_mismatch_risk=high
```

## 播放器是否仍为 3 个

是。

```json
{
  "playerAudioCount": 3,
  "missingUrlCount": 0
}
```

## POST 按钮是否仍置灰

是。

真实 POST 状态：

```text
POST /api/separation/eval/run = 501
```

按钮文案：

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

## 是否触发训练/RVC

否。

```json
{
  "unsafeCalls": []
}
```

没有触发训练、RVC、cover job、`/api/process/*`。

## 测试结果

已通过：

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
node frontend\playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
```

最新 smoke 摘要：

```json
{
  "sourceCount": 4,
  "runCount": 7,
  "runId": "stage45r_20260602_171704_201ec7ff",
  "postStatus": 501,
  "playerAudioCount": 3,
  "durationRiskRows": 4,
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
