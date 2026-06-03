# Stage 46C：分离质量与训练解锁看板

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本轮不要重做大 UI，不要发挥新页面。目标是在 Factory 的“分离质量实验室”里，把 UVR 修复验收和训练是否可恢复讲清楚。

## 当前业务状态

Stage46A 已确认 UVR 时长缩短根因。Stage46B 将由地基修复 runner。产品侧必须能看懂：

```text
15/30/45 秒对照 run
duration_ratio
duration_mismatch
BLOCK_TRAINING
是否允许恢复训练
```

## 必须修改

### 1. 增加“训练解锁状态”卡片

在 Factory 分离质量实验室顶部或指标区附近新增一个紧凑卡片。

必须显示：

```text
当前状态：训练锁定 / 可尝试恢复
原因：duration mismatch high / 三段对照均通过
当前 run_id
duration_ratio
BLOCK_TRAINING
```

规则：

- 如果任一选中 run 或最新 run 的 `block_training=true`，显示“训练锁定”。
- 如果 `duration_mismatch_risk=high`，显示“禁止恢复训练”。
- 如果后端未来返回 `block_training=false` 且 ratio 正常，显示“可进入短训练冒烟，不等于正式放开”。

### 2. 增加 15/30/45 对照 run 表格

基于真实 `GET /api/separation/eval/runs` 和 run detail。

表格字段：

```text
run_id
clip_seconds
original duration
vocal duration
instrumental duration
duration_ratio
risk
```

要求：

- 能显示 Stage46A/46B 产生的 15、30、45 秒 run。
- ratio < 0.95 用红色/危险态。
- ratio >= 0.95 用绿色/通过态。
- 不要只显示“completed”，必须显示 duration 证据。

### 3. 保持播放器和指标区不倒退

必须继续满足：

```text
真实 D:\测试音乐候选能显示
真实 run 能显示
三轨播放器 playerAudioCount=3
noise_risk / suspected_causes / next_step 能显示
POST=501 时按钮置灰
postPayloads=[]
unsafeCalls=[]
```

### 4. 不要让 UI 误导用户恢复训练

文案必须明确：

```text
BLOCK_TRAINING=false 只代表分离时长门槛通过。
恢复训练还需要短训练 smoke 另行验收。
```

## 禁止事项

```text
禁止 mock /api/separation/eval/* 后声称真实通过。
禁止触发训练、RVC、cover job。
禁止启用浏览器执行分离按钮，除非后端明确 browser_execute_enabled=true。
禁止把 completed 当成质量通过。
```

## 必测

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
node frontend\playwright_stage45rb_separation_quality_lab_real_api_smoke.cjs
```

如果需要，新增：

```text
frontend\playwright_stage46c_separation_unlock_dashboard_smoke.cjs
```

但最终验收必须用真实 API。

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-46c-separation-quality-unlock-dashboard-report.md
```

报告必须包含：

```text
是否完成
真实 run 数量
15/30/45 对照是否显示
训练解锁状态显示结果
当前 BLOCK_TRAINING
播放器是否仍为 3 个
POST 按钮是否仍置灰
postPayloads 是否为空
是否触发训练/RVC：必须为否
测试结果
```
