# Stage 44B：训练调参台接入训练创建流程（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本阶段目标是让用户在创建训练任务前能选择 preset、看到最终训练参数，并把 training_config 随训练请求提交给后端。禁止自动启动训练，禁止自动提交 cover。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-44-training-preset-runtime-takeover-plan.md
D:\FeiSharkStudio-v2\frontend\factory.html
D:\FeiSharkStudio-v2\frontend\index.html
D:\FeiSharkStudio-v2\frontend\js\factory\main.js
D:\FeiSharkStudio-v2\frontend\js\train.js
D:\FeiSharkStudio-v2\frontend\js\jobs.js
D:\FeiSharkStudio-v2\frontend\css\app.css
```

## 必做任务

### 1. Factory 训练调参台绑定真实提交配置

要求：

- 用户选择 `fast_preview / balanced / quality` 后，生成 `training_config`。
- 单文件训练和多文件训练创建时都带上 `training_config`。
- 创建前展示确认摘要：

```text
Preset
Epochs
Batch
Sample Rate
F0
Index
GPU 风险
预计耗时
```

- 用户没有选择时默认 `balanced`。
- 后端不支持时降级提示，不报 JS 错。

### 2. Dashboard 训练入口同步调参摘要

Dashboard 创建训练区域也要能看到当前训练 preset 摘要。

要求：

- 不要把完整调参台塞满 Dashboard。
- 只显示紧凑摘要和“去 Factory 调参”按钮。
- Dashboard 创建训练请求也必须带 `training_config`。

### 3. 任务详情展示训练配置

训练 job 详情中展示：

```text
训练预设
epochs
batch_size
sample_rate
f0_enabled
index_enabled
```

要求：

- 如果是旧 job 没有 config，显示“旧任务 / 默认配置”。
- 不要撑爆任务详情，默认收纳在“训练配置”抽屉。

### 4. 修复 Factory sticky 导航遮挡

当前截图里 Factory 中部 sticky 导航会压住内容。要求：

- 导航不遮挡卡片内容。
- 滚动到中段时布局仍规整。
- 移动端不横向溢出。

### 5. 新增 Stage44B smoke

新增：

```text
frontend/playwright_stage44b_training_preset_runtime_smoke.cjs
```

必须验证：

```text
Factory 能读取三个 preset。
选择 quality 后，训练配置摘要更新为 quality 参数。
创建训练请求 payload 包含 training_config，但 smoke 不真正提交训练，或使用拦截确认 payload。
Dashboard 训练入口能显示 preset 摘要。
训练 job 详情能展示旧任务默认配置或新任务配置。
Factory sticky 导航不遮挡关键内容。
移动端无横向溢出。
无 pageerror。
无非预期 /api/process/* 或 POST /api/train。
```

## 禁止事项

```text
禁止自动提交训练。
禁止自动提交 cover。
禁止把 training_config 写死在前端不随选择变化。
禁止破坏 Stage43 Studio 入口。
禁止接 VST。
```

## 必测

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage44b_training_preset_runtime_smoke.cjs
node frontend\playwright_stage44b_training_preset_runtime_smoke.cjs
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-44b-training-preset-runtime-product-report.md
```

报告必须包含：

```text
是否完成
修改文件清单
Factory training_config 提交结果
Dashboard 训练摘要结果
任务详情训练配置结果
sticky 导航修复结果
浏览器 smoke 结果
遗留问题
```
