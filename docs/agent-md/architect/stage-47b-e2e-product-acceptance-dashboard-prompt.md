# Stage 47B：端到端训练/翻唱/Studio 验收看板

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本轮配合地基 Stage47A，把真实业务闭环变成用户看得懂、测得动的验收界面。不要大改皮肤，不要新开无关页面。

## 目标

在现有 Dashboard / Factory / Studio 中补齐“端到端验收看板”：

```text
训练输入 -> 训练 job -> 新模型 -> cover job -> 最终音频 -> Studio 试听
```

## 必须实现

### 1. Dashboard 增加 Stage47 验收卡

显示：

- 当前真实训练 job。
- 当前新模型。
- 当前 cover job。
- 每个阶段状态：pending/running/success/failed/blocked。
- 可点击跳转到 Factory 模型或 Studio 试听。

要求：

- 不要写死成功。
- 没有 Stage47 job 时显示“等待地基生成真实闭环”。
- job 失败时显示失败原因和日志入口。

### 2. Factory 模型区标注 Stage47 新模型

如果出现新模型：

```text
朱朱_stage47_single_long
```

或报告里给出的 model_id，必须能在模型资产库里识别为“Stage47 实训模型”。

显示：

- pth 是否存在。
- index 是否存在。
- source training job。
- 是否可用于 cover。

### 3. Studio 入口补齐

如果 Stage47 cover job 有最终 artifact：

- Studio 页面必须能显示它。
- 播放器可播放。
- 下载按钮可用。
- 明确标注“Stage47 短 smoke / 完整 cover”，不要误导为正式成品。

### 4. 真实浏览器 smoke

新增或扩展 Playwright：

```text
frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
```

要求：

- 使用真实 `127.0.0.1:8000` API。
- 禁止 mock 最终通过。
- 如果地基还没生成 Stage47 model/cover，smoke 可以通过“等待真实闭环”的空态，但必须不报假成功。
- 如果地基已生成，必须验证 model、cover artifact、Studio 播放器。

### 5. 不触发后端重任务

产品侧只读真实状态，不要从 UI 自动触发训练/RVC/cover。

## 必测

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
node frontend\playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
```

## 禁止事项

```text
禁止 mock Stage47 成功。
禁止触发训练/RVC/cover。
禁止把历史 recovered model 冒充 Stage47 新模型。
禁止把没有 artifact 的 job 显示成可试听。
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-47b-e2e-product-acceptance-dashboard-report.md
```

报告必须包含：

```text
是否完成
是否发现 Stage47 training job
是否发现 Stage47 model
是否发现 Stage47 cover job
Studio 是否可播放
真实 API smoke 结果
是否触发训练/RVC：必须为否
测试结果
```
