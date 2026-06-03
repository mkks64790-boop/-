# Stage 41B：恢复模型翻唱产品验收面板（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本阶段只做前端产品验收体验，不自动提交真实 cover job。目标是让用户能清楚完成：恢复模型 -> 选择歌曲 -> 创建翻唱 -> 打开 Studio 试听。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-41-recovered-model-cover-acceptance-plan.md
D:\FeiSharkStudio-v2\frontend\js\jobs.js
D:\FeiSharkStudio-v2\frontend\js\models.js
D:\FeiSharkStudio-v2\frontend\js\cover.js
D:\FeiSharkStudio-v2\frontend\js\studio.js
D:\FeiSharkStudio-v2\frontend\css\app.css
```

## 必做任务

### 1. 恢复模型验收入口

在 Dashboard / 模型详情中对 `v_2c1603c7` 显示：

```text
恢复模型验收
1. 选择歌曲
2. 创建 AI 翻唱
3. 完成后打开 Studio 试听
```

不要自动提交任务。

### 2. 修移动端模型详情对焦

Stage 40B smoke 中移动端模型详情仍出现旧模型详情文本。要求：

- 点击“去模型库查看”后，移动端 Models Tab 必须打开并对焦 `v_2c1603c7`。
- 模型详情必须显示 checkpoint 恢复标签、e90、来源任务。
- 补 smoke 验证。

### 3. 翻唱入口状态文案

当恢复模型被送入翻唱入口：

- 下拉框选中 `v_2c1603c7`。
- 显示“checkpoint 恢复模型，可用于试听验证”。
- 创建按钮必须仍要求用户选择歌曲，不能自动提交。

### 4. Studio 链路提示

对使用 checkpoint 恢复模型生成的 cover job，任务完成后：

- 显示“打开 Studio 试听”。
- Studio 顶部显示音色来源：checkpoint 恢复 / e90。
- 如果没有完成 cover job，则显示待验收提示，不要假装完成。

### 5. 浏览器 smoke

新增：

```text
frontend/playwright_stage41b_recovered_model_cover_product_acceptance_smoke.cjs
```

验证：

- 桌面端恢复模型验收入口存在。
- 移动端模型详情对焦正确。
- 送入翻唱入口只选模型，不自动创建 cover job。
- 未选择歌曲时创建按钮禁用或提示明确。

## 必测

```powershell
$tmp = Join-Path $env:TEMP 'feishark_jobs_check.mjs'; Copy-Item -LiteralPath 'frontend\js\jobs.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
$tmp = Join-Path $env:TEMP 'feishark_models_check.mjs'; Copy-Item -LiteralPath 'frontend\js\models.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
node --check frontend\playwright_stage41b_recovered_model_cover_product_acceptance_smoke.cjs
node frontend\playwright_stage41b_recovered_model_cover_product_acceptance_smoke.cjs
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-41b-recovered-model-cover-product-acceptance-report.md
```

## 本阶段好处

```text
让用户可以按页面指引完成第一次真实试听。
修掉移动端模型详情对焦问题。
把恢复模型从“技术上可用”变成“产品上可验收”。
```

