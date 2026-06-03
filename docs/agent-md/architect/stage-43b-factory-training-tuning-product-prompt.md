# Stage 43B：Factory 训练调教台 v0 + Engine Manager 操作化 + Studio 入口修复（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本阶段目标是让 Factory 不再只是展示状态，而是开始变成真正的模型工厂：能看引擎、搜外部 RVC 模型、登记模型、理解训练参数，并能从已完成 cover 打开 Studio。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-43-studio-entry-engine-cache-training-tuning-plan.md
D:\FeiSharkStudio-v2\frontend\factory.html
D:\FeiSharkStudio-v2\frontend\index.html
D:\FeiSharkStudio-v2\frontend\studio.html
D:\FeiSharkStudio-v2\frontend\js\factory\main.js
D:\FeiSharkStudio-v2\frontend\js\jobs.js
D:\FeiSharkStudio-v2\frontend\js\models.js
D:\FeiSharkStudio-v2\frontend\js\cover.js
D:\FeiSharkStudio-v2\frontend\js\studio.js
D:\FeiSharkStudio-v2\frontend\css\app.css
```

## 必做任务

### 1. Dashboard / 任务中心补 Studio 入口

当 completed cover job 返回：

```text
can_open_studio = true
studio_url
final_artifact_download_url
```

要求：

- 任务详情显示“打开 Studio 试听”。
- 同时显示“下载最终成品”。
- 如果 `can_open_studio` 不为 true，不要伪造按钮，显示“等待产物登记”。
- `task_stage41_ce1b32f2` 必须能被 smoke 强验。

### 2. Factory Engine Manager 操作化

基于：

```text
GET /api/engines
GET /api/engines/rvc/models?limit=&offset=&q=&registered=&has_index=
POST /api/engines/scan?force=true
POST /api/models/import-rvc
```

要求：

- Engine Manager 卡片保留 RVC / UVR / SVC 三状态。
- RVC 模型列表不要一次铺 400 条，做分页或“加载更多”。
- 增加搜索框。
- 增加过滤：全部 / 已登记 / 未登记 / 有 index。
- 未登记模型显示“登记到肥鲨”按钮。
- 登记成功后刷新模型库摘要。
- 如果后端登记 API 不存在，按钮置灰并提示“等待地基接口”，不能 JS 报错。

### 3. 训练调教台 v0

新增 Factory 区域：

```text
训练调教台
```

功能：

- 读取 `GET /api/training/presets`。
- 展示 `fast_preview / balanced / quality` 三个预设。
- 用户选择预设后显示 epochs、batch_size、sample_rate、f0、index、GPU 风险、预计耗时。
- 提供素材信息输入/选择后，调用 `POST /api/training/estimate`。
- 只做估算和解释，不自动创建训练 job。

文案必须清楚：

```text
快速预览：先听方向，不追求极致质量。
均衡推荐：默认建议，适合普通单文件训练。
高质量慢速：更耗时，显存/时间风险更高。
```

### 4. Studio 入口体验

要求：

- 从 Dashboard 点击 Stage41 completed cover 能进入 Studio 并载入对应成品。
- Studio 顶部显示来源任务、来源音色、checkpoint 恢复标签。
- 如果 URL 指定的 track/job 无法打开，显示明确空态，不要自动跳到旧成品误导用户。

### 5. UI 继续收纳

要求：

- Factory 的 RVC 模型列表默认收起或分页，不允许 400 条铺满。
- 技术详情、路径、诊断继续收纳。
- 长路径单行截断 + title。
- 移动端保持底部 Tab，不横向溢出。

## 新增 smoke

新增：

```text
frontend/playwright_stage43b_factory_training_tuning_smoke.cjs
```

必须验证：

```text
Dashboard completed cover 显示 Studio 入口或明确等待产物登记。
如果 can_open_studio=true，点击后 Studio 载入对应 job/track，不跳旧成品。
Factory Engine Manager RVC 模型列表分页/搜索存在。
未登记模型登记按钮不会自动触发训练或 cover。
训练调教台能显示三个 preset。
训练 estimate 只返回风险和耗时，不创建任务。
移动端无横向溢出。
无 pageerror。
无 /api/process/* 或 POST /api/train 非预期调用。
```

## 必测

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage43b_factory_training_tuning_smoke.cjs
node frontend\playwright_stage43b_factory_training_tuning_smoke.cjs
```

## 禁止事项

```text
禁止自动提交训练。
禁止自动提交 cover。
禁止把 400 条模型一次铺满首屏。
禁止硬编码 task_stage41_ce1b32f2 成唯一逻辑。
禁止接 VST。
禁止把 SVC/SVT 显示成已可用。
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-43b-factory-training-tuning-product-report.md
```

报告必须包含：

```text
是否完成
修改文件清单
Dashboard Studio 入口结果
Factory Engine Manager 分页/搜索/登记 UI 结果
训练调教台 v0 结果
Studio 指定 job/track 打开结果
移动端结果
浏览器 smoke 结果
遗留问题
```
