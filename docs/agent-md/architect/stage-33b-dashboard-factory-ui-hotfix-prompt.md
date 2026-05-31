# Stage 33B：Dashboard / Factory UI 定点回修

你现在是 FeiShark Studio 的产品体验 agent。

用户已经人工指出 4 个明确 UI 问题。本阶段不是泛泛美化，不新增功能，不做 Effect Rack 导出。只修下面 4 个产品问题，并保持现有业务绑定和 smoke selector 不破坏。

## 用户反馈问题

1. Dashboard 顶部 `查看用途` 展开后无法自然收起，导致上方黑色区域无法缩小。
2. Dashboard `任务详情` 长字符 / 长 ID / 长路径撑爆页面，没有局部滚动轴或受控换行。
3. Dashboard `产物` 列表没有收纳按钮，产物多时首屏被挤爆。
4. Factory `批次列表` 没有收纳/折叠，批次多时页面变成长列表。

## 阶段目标

- 把这 4 个问题逐条修掉。
- 修完后截图必须能看出页面更规整。
- 不改后端。
- 不改第29回归脚本。
- 不改 Stage 31 Effect Rack 导出合同。

## 必读文件

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32b-three-page-layout-normalization-report.md`
- `D:\FeiSharkStudio-v2\frontend\index.html`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\js\main.js`
- `D:\FeiSharkStudio-v2\frontend\js\jobs.js`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\playwright_stage32b_three_page_layout_smoke.cjs`

## 允许修改

- `frontend\index.html`
- `frontend\factory.html`
- `frontend\css\app.css`
- `frontend\js\main.js`
- `frontend\js\jobs.js`
- `frontend\js\factory\main.js`
- 新增：
  - `frontend\playwright_stage33b_ui_hotfix_smoke.cjs`
- 本阶段 report：
  - `docs\agent-md\worker\stage-33b-dashboard-factory-ui-hotfix-report.md`

## 禁止修改

- 后端任何文件
- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- `README.md`
- `frontend\studio.html`
- `frontend\js\studio.js`
- Stage 31 Effect Rack 导出合同相关文件

Studio 本轮不动。用户反馈集中在 Dashboard / Factory。

## 必须保留的 selector

### Dashboard

- `#engineUsageToggleBtn`
- `#engineUsagePanel`
- `#jobDetailPanel`
- `#jobDetailTitle`
- `#jobArtifactsList`
- `#jobSummaryCard`
- `#jobStageLogsBody`
- `#jobTechnicalBody`
- `#jobsTableBody`
- `.job-row[data-job-id]`
- `[data-open-studio="true"]`
- `button[data-artifact-download]`

### Factory

- `#factoryBatchesList`
- `#factoryBatchHint`
- `#factoryCreateBatchForm`
- `#factoryImportTracksForm`
- `#factoryTracksList`
- `#factoryTrackJobsList`
- `[data-batch-id]`
- `[data-track-id]`
- `[data-track-job-id]`
- `[data-studio-url]`
- `[data-download-url]`

## 具体任务

### 1. 修 `查看用途` 收纳

当前问题：`查看用途` 展开后占据顶部黑色区域，用户感觉无法收起或收起后高度不恢复。

要求：

- `#engineUsageToggleBtn` 必须稳定切换展开/收起。
- `#engineUsagePanel` 收起后必须 `hidden=true` 或视觉高度为 0。
- 顶部区域在收起后不能保留大块空白。
- 点击按钮文案正确：
  - 收起状态：`查看用途 ▾`
  - 展开状态：`收起用途 ▴`
- 如果当前动画 `slideToggle` 导致高度残留，可以改成更直接的 class/hidden 切换，但不要破坏其他抽屉。

### 2. 修任务详情长字符溢出

当前问题：任务详情标题、任务 ID、路径、摘要、技术字段等长字符会撑满页面或造成横向溢出。

要求：

- `#jobDetailPanel` 内部需要局部滚动策略。
- 长标题和长 ID 不能撑出右侧操作区。
- 任务详情内容区建议设置：
  - `max-height`
  - `overflow-y: auto`
  - `overflow-x: hidden`
- 长 path / id / mono 字段使用：
  - `white-space: nowrap`
  - `overflow: hidden`
  - `text-overflow: ellipsis`
  - `title` 保留完整值
- 对需要多行阅读的摘要，使用 `overflow-wrap: anywhere`，不要横向撑爆。

### 3. 给 Dashboard 产物列表加收纳

当前问题：`#jobArtifactsList` 直接铺开，产物多时挤爆任务详情。

要求：

- 在产物标题旁增加收纳按钮，例如：
  - `展开产物 ▾`
  - `收起产物 ▴`
- 增加稳定 selector：
  - `#jobArtifactsToggleBtn`
  - `#jobArtifactsBody`
- 默认折叠规则：
  - 没选任务：折叠
  - 已选任务且产物数量 <= 1：可以保持紧凑显示
  - 产物数量 > 1：默认折叠，只显示数量摘要
- 展开后列表内部最大高度受控，有滚动条。
- 不要破坏 `button[data-artifact-download]` 下载逻辑。

### 4. 给 Factory 批次列表加收纳

当前问题：`#factoryBatchesList` 默认铺开，批次多时变成长列表。

要求：

- 在“批次列表”标题旁增加收纳按钮，例如：
  - `展开批次 ▾`
  - `收起批次 ▴`
- 增加稳定 selector：
  - `#factoryBatchesToggleBtn`
  - `#factoryBatchesBody`
- 默认折叠或紧凑：
  - 有选中批次时默认折叠，显示当前批次摘要
  - 无选中批次时可展开，方便首次选择
- 展开后列表内部最大高度受控，有滚动条。
- 不要破坏 `#factoryBatchesList [data-batch-id]` 点击加载逻辑。

### 5. 新增定点 smoke

新增：

- `frontend\playwright_stage33b_ui_hotfix_smoke.cjs`

至少验证：

1. Dashboard 打开后 `#engineUsagePanel` 默认收起。
2. 点击 `#engineUsageToggleBtn` 后展开，再点击能收起，收起后 panel hidden。
3. 选中一个任务后，`#jobDetailPanel` 不造成横向滚动。
4. `#jobArtifactsToggleBtn` 与 `#jobArtifactsBody` 存在；产物区可展开/收起。
5. Factory 打开后 `#factoryBatchesToggleBtn` 与 `#factoryBatchesBody` 存在；批次列表可展开/收起。
6. Dashboard / Factory 都没有横向滚动：
   - `document.documentElement.scrollWidth <= window.innerWidth + 8`
7. 输出截图：
   - `stage33b_dashboard_hotfix.png`
   - `stage33b_factory_hotfix.png`

## 验证要求

必须执行：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
node frontend\playwright_stage33b_ui_hotfix_smoke.cjs
node frontend\playwright_stage32b_three_page_layout_smoke.cjs
node frontend\playwright_stage17_smoke.cjs
node frontend\playwright_factory_smoke.cjs
```

建议执行：

```powershell
node frontend\playwright_model_registry_linkage_smoke.cjs
node frontend\playwright_factory_to_studio_context_smoke.cjs
```

如果建议项没跑，必须写明原因。

## 交付要求

必须写入：

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-33b-dashboard-factory-ui-hotfix-report.md`

report 必须包含：

1. 4 个用户反馈问题分别如何修。
2. 修改了哪些文件。
3. 新增了哪些 selector。
4. 哪些内容默认折叠。
5. 截图路径。
6. 验证命令和结果。
7. 是否修改后端：必须为否。
8. 是否破坏现有 smoke selector：必须为否。

## 完成标准

- `查看用途` 可稳定展开/收起，收起后顶部不留大黑布。
- `任务详情` 长字符不再撑爆页面。
- `产物` 有收纳按钮和局部滚动。
- `批次列表` 有收纳按钮和局部滚动。
- Dashboard / Factory 无横向滚动。
- 核心 smoke 通过。
