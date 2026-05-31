# Stage 33B 执行汇报：Dashboard / Factory UI 定点回修

## 阶段标题

Stage 33B：Dashboard / Factory UI 定点回修

## 完成情况

- 已完成：4 个用户反馈 UI 问题全部修复；新增 Stage 33B 定点 smoke；必选验证与建议验证均通过。
- 部分完成：无。
- 未完成：无。

## 用户反馈问题修复结果

### 1. 查看用途无法自然收起

- 原问题：`#engineUsageToggleBtn` 展开后，`#engineUsagePanel` 即使设置 hidden，仍可能被 `.engine-usage-panel { display: grid; }` 覆盖，视觉上保留顶部黑色区域。
- 修复方式：`frontend/js/main.js` 改为直接同步 `hidden` 状态并清理动画残留样式；`frontend/css/app.css` 增加 `[hidden] { display: none !important; }`，确保 hidden 在视觉上确实为 0 高度。
- selector / 状态：保留 `#engineUsageToggleBtn`、`#engineUsagePanel`；按钮文案为收起态 `查看用途 ▾`，展开态 `收起用途 ▴`。
- 验证结果：Stage 33B smoke 校验默认 hidden、展开、再次收起、computed display 为 none、实际高度为 0，结果 PASS。

### 2. 任务详情长字符串没有受控滚动

- 原问题：`#jobDetailPanel` 中长 job id、路径、标题、错误文本可能横向撑开详情区。
- 修复方式：在 `#jobDetailPanel` 上强化 `max-height`、`overflow-y: auto`、`overflow-x: hidden`、`overscroll-behavior: contain`；对详情区内元素统一 `min-width: 0`。
- 长字符串处理策略：标题/摘要类文本使用 `overflow-wrap: anywhere`；`.mono`、`.path-line`、`.path-text`、`.artifact-path` 使用 `white-space: nowrap`、`overflow: hidden`、`text-overflow: ellipsis`，完整值通过既有 `title` 保留。
- 验证结果：Stage 33B smoke 校验 `#jobDetailPanel.scrollWidth` 不超过面板宽度，Dashboard 无横向滚动，结果 PASS。

### 3. 产物没有收纳按钮

- 原问题：`#jobArtifactsList` 直接铺开，多产物任务会挤占首屏详情区域。
- 修复方式：在 Dashboard 产物区接入抽屉结构，列表移入 `#jobArtifactsBody`，按钮通过 `setJobArtifactsCollapsed()` 控制。
- 新增 selector：
  - `#jobArtifactsToggleBtn`
  - `#jobArtifactsBody`
  - `#jobArtifactsSummary`
  - `#jobArtifactsDrawer`
- 默认折叠规则：未选任务或无产物默认折叠；产物数 <= 1 默认展开紧凑显示；产物数 > 1 默认折叠，只显示数量摘要。
- 下载逻辑：保留 `#jobArtifactsList` 与 `button[data-artifact-download]` 事件绑定，下载入口未改。
- 验证结果：Stage 33B smoke 校验按钮和 body 存在、可展开/收起，结果 PASS。

### 4. Factory 批次列表没有收纳

- 原问题：`#factoryBatchesList` 默认直接铺开，批次多时左侧区域变成长列表。
- 修复方式：在 Factory 批次列表外增加 `#factoryBatchesDrawer` 和 `#factoryBatchesBody`，通过 `#factoryBatchesToggleBtn` 控制折叠；保留原 `#factoryBatchesList` 内部点击委托。
- 新增 selector：
  - `#factoryBatchesToggleBtn`
  - `#factoryBatchesBody`
  - `#factoryBatchesDrawer`
- 默认折叠规则：无选中批次时展开，方便首次选择；选中批次后默认折叠，顶部保留当前批次摘要。
- 点击逻辑：保留 `#factoryBatchesList [data-batch-id]` 选择批次逻辑。
- 验证结果：Stage 33B smoke 校验按钮和 body 存在、可展开/收起，Factory 无横向滚动，结果 PASS。

## 修改文件

- `D:\FeiSharkStudio-v2\frontend\index.html`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\js\main.js`
- `D:\FeiSharkStudio-v2\frontend\js\jobs.js`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\playwright_stage33b_ui_hotfix_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-33b-dashboard-factory-ui-hotfix-report.md`

## 默认折叠内容

```text
engine usage = 默认收起；点击后展开，再次点击后 hidden=true 且视觉高度为 0
job artifacts = 未选任务/无产物默认折叠；产物数 <= 1 默认展开；产物数 > 1 默认折叠
factory batches = 无选中批次默认展开；选中批次后默认折叠
```

## 截图

```text
Dashboard screenshot = D:\FeiSharkStudio-v2\stage33b_dashboard_hotfix.png
Factory screenshot = D:\FeiSharkStudio-v2\stage33b_factory_hotfix.png
```

## 验证结果

```text
python -m pytest -q
结果：PASS，19 passed, 2 warnings in 3.39s

python -X utf8 backend\self_check.py
结果：PASS，SELF_CHECK_SUMMARY PASS

node frontend\playwright_stage33b_ui_hotfix_smoke.cjs
结果：PASS，STAGE33B_UI_HOTFIX_SMOKE PASS；输出 stage33b_dashboard_hotfix.png / stage33b_factory_hotfix.png

node frontend\playwright_stage32b_three_page_layout_smoke.cjs
结果：PASS，STAGE32B_THREE_PAGE_LAYOUT_SMOKE PASS

node frontend\playwright_stage17_smoke.cjs
结果：PASS，STAGE17_PLAYWRIGHT_SMOKE PASS

node frontend\playwright_factory_smoke.cjs
结果：PASS，FACTORY_PLAYWRIGHT_SMOKE PASS

node frontend\playwright_model_registry_linkage_smoke.cjs
结果：PASS，STAGE27_MODEL_REGISTRY_SMOKE PASS
是否执行：是

node frontend\playwright_factory_to_studio_context_smoke.cjs
结果：PASS，FACTORY_TO_STUDIO_CONTEXT_PLAYWRIGHT_SMOKE PASS
是否执行：是
```

补充：浏览器 ES module 文件使用 `Get-Content -Raw ... | node --input-type=module --check` 做语法检查，`frontend/js/main.js`、`frontend/js/jobs.js`、`frontend/js/factory/main.js` 均 PASS。直接 `node --check frontend/js/*.js` 会按 CommonJS 解析并误报 import 语法错误，不作为本阶段验证结论。

## 并行边界

```text
是否修改后端 = 否
是否修改第 9 回归脚本 = 否
是否修改 README = 否
是否修改 Studio = 否
是否修改 Stage 31 Effect Rack 导出合同 = 否
是否破坏现有 smoke selector = 否
```

## 风险与限制

- 风险 1：本轮只做 Dashboard / Factory UI 热修，不改变后端数据契约和任务流程。
- 风险 2：批次列表选中后默认收起，人工切换批次需要先点击 `展开批次 ▾`。

## 交接说明

- 事项 1：Dashboard 顶部用途面板已能稳定展开/收起，收起后不再保留黑色区域。
- 事项 2：Dashboard 任务详情和产物列表已建立局部滚动与长字符串约束。
- 事项 3：Factory 批次列表已建立默认折叠策略，并保留原 `[data-batch-id]` 行为。
