# Stage 45RC：产品侧 POST 501 禁用策略返工

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本轮是严格返工，不是新功能发挥。

## 验收打回事实

架构师重启 FastAPI 后，用真实后端重新验收：

```text
GET  /api/separation/eval/run -> 405 Method Not Allowed
POST /api/separation/eval/run -> 501 separation_eval_execute_disabled
```

但是 Factory 页面真实浏览器 smoke 输出：

```json
{
  "runButtonDisabled": false,
  "runButtonText": "只裁剪 45 秒短片段，不跑整首歌",
  "postPayloads": [
    "{\"limit\":1,\"clip_seconds\":45}"
  ]
}
```

这说明你上一轮报告里的“按钮置灰、本轮 smoke 未触发 POST run”不成立。后端明确禁用浏览器执行分离时，前端还启用了按钮并发出了 POST，这一项必须修正。

## 必须修改

### 1. 修正浏览器执行入口探测

修改：

```text
frontend/js/factory/main.js
```

当前 `refreshSeparationPostAvailability()` 使用 `GET /api/separation/eval/run`，只把 `404` 当禁用。这不够。

要求：

- 不允许用 GET 探测 POST 能力。
- 必须以真实 POST 的响应为准，或使用后端明确提供的能力字段。
- 当前后端 `POST /api/separation/eval/run` 返回 `501` 时，必须设置：

```text
state.separationPostUnavailable = "后端未开放浏览器执行分离，请用 CLI 执行短片段质检。"
```

- 按钮必须置灰。
- 按钮文案必须明确显示后端禁用浏览器执行。
- 不允许在 `501` 状态下继续触发 POST run。

### 2. 修正错误处理

当前 `handleSeparationEvalRun()` 只特殊处理 `404`。

要求：

- `405`、`501`、`503` 都必须视为后端未开放或暂不可用。
- 失败后不要显示“已提交”。
- 失败后按钮进入禁用文案，而不是恢复成“只裁剪 45 秒短片段”。

### 3. 修正真实 smoke

修改：

```text
frontend/playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
```

要求：

- smoke 必须探测真实 `POST /api/separation/eval/run`，而不是 `GET`。
- 如果 POST 返回 `501`：
  - `runButtonDisabled` 必须为 `true`。
  - `postPayloads` 必须为空。
  - 文案必须包含“后端未开放”或“CLI”。
- 如果 POST 返回 `200/202`：
  - 才允许按钮启用。
  - payload 必须固定 `limit=1`、`clip_seconds=45`。
- 报告不得再写“POST 是 404”这种旧服务结果。

### 4. 保留已修好的真实数据渲染

不要破坏以下已通过项：

```text
真实 D:\测试音乐候选数量 = 4
真实 run_id = stage45r_20260602_171704_201ec7ff
playerAudioCount = 3
noise_risk = high
duration mismatch 显示 45s -> 26.807s
BLOCK_TRAINING 显示
desktop/mobile 无横向溢出
unsafeCalls = []
```

## 禁止事项

```text
禁止 mock /api/separation/eval/* 后声称真实通过。
禁止在 POST=501 时启用按钮。
禁止触发训练、RVC、cover job、/api/process/*。
禁止删除或移动 D:\测试音乐。
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
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-45rc-product-post501-gate-and-smoke-honesty-report.md
```

报告必须包含：

```text
是否完成
真实 POST /api/separation/eval/run 状态码
按钮是否置灰
按钮文案
postPayloads 是否为空
播放器是否仍为 3 个
指标是否仍显示 high / duration mismatch / BLOCK_TRAINING
是否触发训练/RVC：必须为否
测试结果
```
