# Stage 32B 执行汇报：三页产品布局规整化

## 阶段标题

Stage 32B：三页产品布局规整化

## 完成情况

- 已完成：Dashboard / Factory / Studio 三页布局规整、关键抽屉默认折叠、三页布局 smoke、新旧核心 smoke 与建议 smoke。
- 部分完成：无。
- 未完成：无。

## 三页混乱点审计

### Dashboard

- 创建入口被任务中心压在下方，用户首屏先看到任务表而不是“我要做什么”。
- 侧栏模型 / 诊断区域信息密度偏高，容易像系统调试面板。
- 顶栏状态、导航和摘要在中等桌面宽度下容易拥挤。

### Factory

- 歌词资产和关联任务默认展开，当前曲目生产动作被长历史内容稀释。
- 页面顶栏与右侧工位在 1500px 宽度下存在横向溢出风险。
- 批次 / 曲目 / 当前主成品层级可用，但视觉间距和默认展开状态不够克制。

### Studio

- Studio 已有产品壳，但仍需要和 Dashboard / Factory 保持统一导航顺序、shell 宽度和侧栏约束。
- Effect Rack 保留为工具区，不能压过播放器。
- 技术详情、历史、试听库需要继续默认折叠。

## 规整后的信息架构

### Dashboard

- 默认首屏：创建入口、任务中心、模型/诊断摘要。
- 默认折叠：任务技术详情、阶段日志、模型库存、诊断长列表。
- 主操作：创建 cover / train job，任务中心继续作为状态查看与后续动作入口。

### Factory

- 默认首屏：批次入口、曲目导入、当前曲目工位、最新成品 / 当前主成品。
- 默认折叠：歌词资产、关联任务 / 审计记录。
- 主操作：创建 batch、导入 tracks、从当前 track 创建 cover job、进入 Studio / 下载成品。

### Studio

- 默认首屏：来源上下文、播放器、当前成品、Inspector 摘要、Effect Rack 工具区。
- 默认折叠：技术详情、阶段日志、Track History、全局试听库。
- 主操作：播放 / 下载 / 返回 Factory / 设置主成品。

## 修改文件

- `D:\FeiSharkStudio-v2\frontend\index.html`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\playwright_stage32b_three_page_layout_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32b-three-page-layout-normalization-report.md`

## 保留的关键 selector

```text
Dashboard core selectors = 已保留：#taskCenter, #entryCenter, #modelPanel, #diagnosticsPanel, #coverModelSelect, #jobsTableBody, .job-row[data-job-id], #jobSummaryCard, #jobActionBar, [data-open-studio="true"], #jobStageLogsBody, #jobTechnicalBody, #modelsInventoryBody, #modelsInventoryToggleBtn, #modelsList [data-model-id], #modelDetailCard, #modelUseForCoverBtn, #modelSourceJobBtn, #modelTechnicalBody, [data-mobile-tab-target]

Factory core selectors = 已保留：#factoryCreateBatchForm, #factoryImportTracksForm, #factoryRefreshBtn, #factoryBatchesList, #factoryTracksList, #factoryCoverModelSelect, #factoryCreateCoverJobBtn, #factoryTrackJobsList, #factoryTrackOutcomeCard, #factoryCurrentMasterCard, #factoryTrackTitle, #factoryTrackSubtitle, #factoryLyricText, #factoryLyricsToggleBtn, #factoryLyricsBody, [data-batch-id], [data-track-id], [data-track-job-id], [data-studio-url], [data-download-url]

Studio core selectors = 已保留：#studioSourceContextCard, #studioSourceMetaGrid, #studioFactoryBackBtn, #studioArtifactSummaryCard, #studioSummaryDownloadBtn, #studioTrackHistoryPanel, #studioTrackHistoryList, [data-track-history-job-id], [data-set-track-master-job-id], #studioEffectRackList, [data-effect-slot-toggle], #studioTechnicalToggleBtn, #studioTechnicalBody
```

## 默认折叠内容

```text
Dashboard = 任务技术详情、阶段日志、模型库存、模型技术详情、诊断长列表
Factory = 歌词资产、关联任务 / 审计记录
Studio = 技术详情、阶段日志、Track History、全局试听库
```

## 截图

```text
Dashboard screenshot = D:\FeiSharkStudio-v2\stage32b_dashboard_layout.png
Factory screenshot = D:\FeiSharkStudio-v2\stage32b_factory_layout.png
Studio screenshot = D:\FeiSharkStudio-v2\stage32b_studio_layout.png
```

## 验证结果

```text
python -m pytest -q
结果：PASS，19 passed, 2 warnings in 3.31s

python -X utf8 backend\self_check.py
结果：PASS，SELF_CHECK_SUMMARY PASS

node frontend\playwright_stage32b_three_page_layout_smoke.cjs
结果：PASS，三页打开、统一导航、关键 selector、默认折叠、无横向滚动、三张截图均通过

node frontend\playwright_stage17_smoke.cjs
结果：PASS，STAGE17_PLAYWRIGHT_SMOKE PASS

node frontend\playwright_factory_smoke.cjs
结果：PASS，FACTORY_PLAYWRIGHT_SMOKE PASS

node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
结果：PASS，STAGE30B_STUDIO_PRODUCT_SHELL_SMOKE PASS

node frontend\playwright_model_registry_linkage_smoke.cjs
结果：PASS，STAGE27_MODEL_REGISTRY_SMOKE PASS
是否执行：是

node frontend\playwright_factory_to_studio_context_smoke.cjs
结果：PASS，FACTORY_TO_STUDIO_CONTEXT_PLAYWRIGHT_SMOKE PASS
是否执行：是

node frontend\playwright_trained_model_cover_studio_smoke.cjs
结果：PASS，STAGE28_TRAINED_MODEL_COVER_SMOKE PASS
是否执行：是
```

说明：建议 smoke 首次并发运行时 API 服务一度不可连接，已重启本地 FastAPI 服务后按顺序重跑，最终全部通过。

## 并行边界

```text
是否修改后端 = 否
是否修改第29回归脚本 = 否
是否修改 README = 否
是否修改 Stage 31 Effect Rack 导出合同 = 否
```

## 风险与限制

- 风险 1：本轮只做布局规整，不新增后端能力，也不改变 Effect Rack 导出真实性。
- 风险 2：Factory 歌词 / 关联任务默认折叠后，旧 smoke 仍可通过 DOM 操作访问隐藏控件；人工操作时需要先展开抽屉。
- 需要地基 agent 复核的点：无后端改动；后续若改变 track / artifact / Studio URL 语义，再补地基验收即可。

## 交接说明

- 事项 1：三页导航顺序统一为 Dashboard / Factory / Studio。
- 事项 2：三页 shell 使用统一宽度、间距和侧栏约束，避免 1500px 桌面宽度横向滚动。
- 事项 3：后续继续加功能前，优先复用现有抽屉和 compact list 语法，避免重新把技术细节铺满首屏。
