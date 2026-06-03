# Stage 39B：checkpoint 恢复入口 UX（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本阶段只做前端 UI/UX 和浏览器 smoke。不要启动真实训练，不要修改后端训练主链。目标是在训练失败详情页里给用户一个清晰、安全的“从 checkpoint 恢复登记模型”入口。

## 启动前必须阅读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-39-checkpoint-recovery-plan.md
D:\FeiSharkStudio-v2\frontend\js\jobs.js
D:\FeiSharkStudio-v2\frontend\js\models.js
D:\FeiSharkStudio-v2\frontend\css\app.css
D:\FeiSharkStudio-v2\frontend\index.html
```

## 依赖后端契约

Stage 39A 提供：

```text
GET /api/jobs/{job_id}/training-recovery
POST /api/jobs/{job_id}/training-recovery/register
```

产品可以先按该契约开发。若接口暂不可用，UI 要显示“恢复能力待后端就绪”，不能报错刷屏。

## 必做任务

### 1. 失败任务详情增加恢复卡

对 `job_type=train` 且失败在 `train_core` 的任务，加载：

```text
GET /api/jobs/{job_id}/training-recovery
```

如果 `can_recover=true`，展示：

```text
可恢复 checkpoint
推荐实验：feishark_v_62f76886
最高 epoch：90
特征数：552
状态：可构建 index / 可登记模型
```

如果发现多个候选，默认高亮推荐项，但允许展开查看其它候选。

### 2. 增加安全确认按钮

按钮文案：

```text
从 e90 checkpoint 恢复登记模型
```

点击后必须二次确认：

```text
这不会重新训练，只会用已有 checkpoint 构建 index 并登记模型。确认继续？
```

确认后调用：

```text
POST /api/jobs/{job_id}/training-recovery/register
```

### 3. 成功后刷新模型库和任务详情

恢复成功后：

- toast：`模型已从 checkpoint 恢复登记`
- 刷新任务详情
- 刷新模型面板
- 提供 CTA：`去模型库查看` / `送入 AI 翻唱`

### 4. 禁止误导

- 不要把 checkpoint recovery 写成“继续训练”。
- 不要说“恢复后一定完美”，只说“可用于后续试听/翻唱验证”。
- 如果后端返回 `dry_run` 或 `can_recover=false`，按钮禁用并显示原因。

## 必测项

```powershell
$tmp = Join-Path $env:TEMP 'feishark_jobs_check.mjs'; Copy-Item -LiteralPath 'frontend\js\jobs.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
node --check frontend\playwright_stage39b_checkpoint_recovery_ux_smoke.cjs
node frontend\playwright_stage39b_checkpoint_recovery_ux_smoke.cjs
```

浏览器 smoke 要验证：

- `train_010253ec08f0` 显示 checkpoint 恢复卡。
- 推荐候选是 `feishark_v_62f76886`，不是 `feishark_v_2860bda4`。
- 按钮有二次确认。
- 成功或接口不可用都有明确提示，不刷屏。

截图输出：

```text
D:\FeiSharkStudio-v2\output\playwright\stage39b_checkpoint_recovery_ux.png
```

## 完成后写报告

使用：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-39b-checkpoint-recovery-ux-report-template.md
```

