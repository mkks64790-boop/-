# Stage 45B：训练 runtime 可观察 UI（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本阶段目标是让真实训练 smoke 或后续训练任务在 UI 上可观察、可理解、可判断，不再让用户误以为“卡住了”。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-45-real-short-training-smoke-plan.md
D:\FeiSharkStudio-v2\frontend\index.html
D:\FeiSharkStudio-v2\frontend\factory.html
D:\FeiSharkStudio-v2\frontend\js\jobs.js
D:\FeiSharkStudio-v2\frontend\js\train.js
D:\FeiSharkStudio-v2\frontend\js\factory\main.js
D:\FeiSharkStudio-v2\frontend\css\app.css
```

## 必做任务

### 1. 训练中状态卡

对 train job 显示：

```text
当前阶段
preset
epochs
batch
sample_rate
f0
index
已运行时间
最后一条 stage log
```

如果 job 处于 `train_core`：

```text
核心训练通常最长，请不要关闭后端/RVC。
如果超过预期时间，可查看诊断和阶段日志。
```

### 2. 训练进度路线图

把训练阶段显示为路线：

```text
素材准备 -> 预处理 -> 音高/特征 -> 核心训练 -> index -> 模型登记
```

要求：

- 当前阶段高亮。
- 完成阶段打勾。
- 跳过 index 时显示“按配置跳过”。
- 失败时显示失败分类和下一步建议。

### 3. 训练配置抽屉增强

继续保持默认收起，但展开后显示：

```text
preset_key
epochs
batch_size
sample_rate
f0_enabled
index_enabled
created_by
warnings
```

### 4. 失败/阻塞提示

如果后端返回失败分类：

```text
environment_not_ready
gpu_busy
dataset_too_small
rvc_train_failed
timeout
```

前端展示对应建议：

```text
环境未就绪：先看诊断。
GPU 忙：等待或取消其他任务。
数据太短：换更长干声或增加短片段。
RVC 训练失败：展开阶段日志。
超时：检查 epoch / batch / 散热。
```

### 5. 新增 Stage45B smoke

新增：

```text
frontend/playwright_stage45b_training_runtime_observability_smoke.cjs
```

验证：

```text
训练任务详情能看到训练状态卡。
训练路线图存在。
训练配置抽屉默认收起，展开后可读。
旧任务无配置时显示默认配置。
模拟 train_core 时显示“不要关闭后端/RVC”提示。
模拟失败分类时显示下一步建议。
无 pageerror。
无自动 /api/train 真实提交。
移动端无横向溢出。
```

## 禁止事项

```text
禁止自动提交训练。
禁止自动提交 cover。
禁止把训练进度伪造成百分比精确值。
禁止接 VST。
禁止把失败统一写成“失败了”。
```

## 必测

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage45b_training_runtime_observability_smoke.cjs
node frontend\playwright_stage45b_training_runtime_observability_smoke.cjs
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-45b-training-runtime-observability-product-report.md
```

报告必须包含：

```text
是否完成
修改文件清单
训练状态卡结果
训练路线图结果
失败分类 UI 结果
移动端结果
浏览器 smoke 结果
遗留问题
```
