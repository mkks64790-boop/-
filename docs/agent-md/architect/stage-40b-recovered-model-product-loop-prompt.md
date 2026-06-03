# Stage 40B：恢复模型产品闭环（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本阶段是一个大任务：把恢复出来的模型从 Dashboard、模型库、翻唱入口、Factory/Studio 路径全部串起来，让用户知道“这个失败训练已经救回来了，并且下一步能用它干什么”。

## 启动前必须阅读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-40-real-recovery-product-closure-plan.md
D:\FeiSharkStudio-v2\frontend\js\jobs.js
D:\FeiSharkStudio-v2\frontend\js\models.js
D:\FeiSharkStudio-v2\frontend\js\cover.js
D:\FeiSharkStudio-v2\frontend\js\factory\main.js
D:\FeiSharkStudio-v2\frontend\css\app.css
```

## 前置条件

最好等 Stage 40A 完成真实恢复后再做最终联调。

如果 Stage 40A 尚未完成，可以先实现兼容 UI，但 smoke 必须支持真实后端模式：

```text
train_010253ec08f0 恢复后应出现恢复模型
模型名建议：朱朱_recovered_e90
```

## 必做任务

### 1. Dashboard 恢复成功态

恢复成功后，任务详情不应再像普通失败任务一样吓人。需要显示：

```text
已从 checkpoint 恢复
来源实验：feishark_v_62f76886
恢复 epoch：90
模型：朱朱_recovered_e90
```

按钮：

```text
去模型库查看
送入 AI 翻唱
复制模型 ID
```

失败日志仍保留，但降级为“历史事故记录”，不要挡住主操作。

### 2. 模型库恢复来源标识

模型面板中，对 metadata `recovered_from_checkpoint=true` 的模型显示专属标签：

```text
checkpoint 恢复
e90
来源任务 train_010253ec08f0
```

点击模型详情时显示：

```text
从失败训练恢复登记，已完成 index/model register，可用于翻唱验证。
```

### 3. 一键送入翻唱入口

从恢复成功卡点击“送入 AI 翻唱”后：

- 自动选中恢复模型。
- 跳转或滚动到 AI 一键翻唱创建入口。
- 显示 toast：`已选择恢复模型，可上传歌曲进行翻唱验证`。
- 不自动提交 cover job，用户仍需选择歌曲确认。

### 4. Factory/Studio 来源链路

如果恢复模型被用于 Factory 或 cover job，后续任务详情要能显示：

```text
音色来源：checkpoint 恢复模型
来源训练：train_010253ec08f0
恢复实验：feishark_v_62f76886 / e90
```

先做到 UI 读取和展示，不强求本阶段跑完整翻唱。

### 5. 浏览器真机验收

新增：

```text
frontend/playwright_stage40b_recovered_model_product_loop_smoke.cjs
```

验证：

- Dashboard 能看到恢复成功态或可恢复态。
- 模型库能看到恢复模型标签。
- “送入 AI 翻唱”能选中模型。
- 不会自动提交真实 cover job。
- 移动端 1024px 以下恢复卡不撑爆。

## 必测项

```powershell
$tmp = Join-Path $env:TEMP 'feishark_jobs_check.mjs'; Copy-Item -LiteralPath 'frontend\js\jobs.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
$tmp = Join-Path $env:TEMP 'feishark_models_check.mjs'; Copy-Item -LiteralPath 'frontend\js\models.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
node --check frontend\playwright_stage40b_recovered_model_product_loop_smoke.cjs
node frontend\playwright_stage40b_recovered_model_product_loop_smoke.cjs
```

## 完成后写报告

使用：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-40b-recovered-model-product-loop-report-template.md
```

## 本大任务对当前阶段的好处

```text
把后端恢复能力变成用户看得懂、点得动的产品闭环。
让“训练失败”不再是死胡同，而是可恢复、可继续使用的状态。
打通模型库、翻唱入口、Factory/Studio 的模型来源叙事。
为下一步真实翻唱验收准备干净入口。
```

