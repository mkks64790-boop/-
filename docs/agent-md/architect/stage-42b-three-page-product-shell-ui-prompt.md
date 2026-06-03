# Stage 42B：三页面正式产品骨架 + Engine Manager UI（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本阶段目标是把当前测试痕迹很重的页面，重排成正式工作站的三页面骨架：Dashboard / Factory / Studio。不要破坏任何已有业务数据绑定，不要自动提交训练或 cover job。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-42-engine-manager-and-product-shell-plan.md
D:\FeiSharkStudio-v2\frontend\index.html
D:\FeiSharkStudio-v2\frontend\studio.html
D:\FeiSharkStudio-v2\frontend\js\jobs.js
D:\FeiSharkStudio-v2\frontend\js\models.js
D:\FeiSharkStudio-v2\frontend\js\cover.js
D:\FeiSharkStudio-v2\frontend\js\factory\main.js
D:\FeiSharkStudio-v2\frontend\js\studio.js
D:\FeiSharkStudio-v2\frontend\css\app.css
```

## 产品分区原则

### Dashboard

只保留：

```text
AI 翻唱创建入口
训练创建入口
任务中心
当前进度/完成提醒
必要的恢复模型验收提示
```

要求：

- 不要把模型库详情、长诊断、批次列表长期铺在首屏。
- 任务详情必须有滚动容器，长日志不能撑爆页面。
- 阶段日志、产物、任务详情默认可折叠。

### Factory

负责：

```text
模型资产库
训练调教入口
Local AI Engine Manager
第三方 RVC 读取结果
模型导入/重新扫描
```

要求：

- 新增“引擎管理”区，读取地基 Agent 的 `/api/engines`。
- RVC、UVR、SVC/SVT 各做一张状态卡。
- RVC 卡片要显示 WebUI 在线、根目录、模型数量、外部未登记模型数量。
- UVR 卡片要显示分离器是否配置。
- SVC/SVT 卡片未配置时显示“备用引擎未配置”，不要假装完成。
- 模型库列表默认收起为“模型资产抽屉”，点击再展开。

### Studio

负责：

```text
成品试听
版本列表
音轨来源
后续修音入口
导出入口
```

要求：

- 对 `task_stage41_ce1b32f2` 这类已完成 cover，明确展示“可打开 Studio 试听”。
- Studio 顶部保留音色来源：checkpoint 恢复 / e90 / 来源任务。
- 如果没有可试听产物，不要伪造成完成态。
- 先做清爽骨架，不接 VST。

## 必做任务

### 1. 整体视觉整理

要求：

- 保持当前黑橙方向，但减少“测试台”观感。
- 首屏更干净：把诊断、批次、产物、日志、技术详情全部收纳。
- 所有长路径使用单行截断 + hover/title 显示完整路径。
- 右侧面板不要默认堆满所有模型详情，默认只显示“当前选中摘要 + 展开详情”。

### 2. Dashboard 收纳修复

必须修：

- 任务详情长字符无滚动轴。
- 阶段日志默认收起。
- 产物列表默认收起。
- 批次列表默认收起。
- “查看用途/查看说明”类面板可收起，不能撑高顶部黑布。

### 3. Factory 引擎管理 UI

新增 UI 区域：

```text
Local AI Engine
RVC WebUI
UVR 分离器
SVC/SVT 备用引擎
第三方 RVC 模型读取
```

要求：

- 优先调用 `/api/engines`。
- 如果地基接口尚未完成，必须 graceful fallback，不允许 JS 报错。
- 展示状态必须来自 API，不允许写死“可用”。
- 增加“重新扫描引擎”按钮，调用 `POST /api/engines/scan`；接口不存在时显示“等待地基接口”，不要崩。

### 4. Stage 41 成品入口

对已完成短 cover：

```text
task_stage41_ce1b32f2
```

要求：

- 任务中心显示“已完成试听品”收纳按钮。
- 展开后能看到打开 Studio 的入口。
- Studio 中能看到 checkpoint 恢复来源。
- 不自动播放，不自动提交新任务。

### 5. 移动端

要求：

- 小于 1024px 保持底部 Tab。
- Dashboard / Factory / Studio 三个视窗单屏显示，不要无限长蛇阵。
- 抽屉和折叠状态在自动刷新后不能被冲开。

## 必测命令

```powershell
$tmp = Join-Path $env:TEMP 'feishark_jobs_check.mjs'; Copy-Item -LiteralPath 'frontend\js\jobs.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
$tmp = Join-Path $env:TEMP 'feishark_models_check.mjs'; Copy-Item -LiteralPath 'frontend\js\models.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
$tmp = Join-Path $env:TEMP 'feishark_cover_check.mjs'; Copy-Item -LiteralPath 'frontend\js\cover.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
$tmp = Join-Path $env:TEMP 'feishark_factory_check.mjs'; Copy-Item -LiteralPath 'frontend\js\factory\main.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
$tmp = Join-Path $env:TEMP 'feishark_studio_check.mjs'; Copy-Item -LiteralPath 'frontend\js\studio.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
```

新增浏览器 smoke：

```text
frontend/playwright_stage42b_three_page_product_shell_smoke.cjs
```

Smoke 必须验证：

```text
Dashboard 首屏没有大面积诊断/批次/日志展开。
任务详情、阶段日志、产物、批次列表可收起/展开。
Factory 存在 Engine Manager，并能优雅处理 /api/engines 不可用。
如果 /api/engines 可用，能展示 RVC/UVR/SVC 状态。
Studio 能打开 Stage41 成品或至少显示明确的待选择状态。
移动端底部 Tab 可切换，抽屉不会被自动刷新冲开。
无 pageerror。
无自动 /api/process 调用。
```

运行：

```powershell
node --check frontend\playwright_stage42b_three_page_product_shell_smoke.cjs
node frontend\playwright_stage42b_three_page_product_shell_smoke.cjs
```

## 禁止事项

```text
禁止重写业务流程。
禁止删除现有按钮绑定。
禁止自动提交训练或 cover。
禁止把测试数据硬编码成唯一真实数据。
禁止接 VST。
禁止把 RVC/UVR/SVC 状态写死为可用。
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-42b-three-page-product-shell-ui-report.md
```

报告必须包含：

```text
是否完成
修改文件清单
Dashboard 收纳结果
Factory Engine Manager 展示结果
Studio 成品入口结果
移动端结果
浏览器 smoke 结果
遗留问题
```

## 本阶段好处

```text
让三个页面职责清楚，项目从调试台向正式工作站过渡。
给 RVC/UVR/SVC 整合提供清晰入口。
把用户最烦的臃肿、不能收起、长字符撑爆、测试痕迹铺满首屏集中处理。
```
