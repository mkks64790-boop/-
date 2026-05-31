# Stage 32B：三页产品布局规整化

你现在是 FeiShark Studio 的产品体验 agent。

用户已经明确反馈：`Dashboard / Factory / Studio` 三个页面看起来仍然乱糟糟、不规整。  
这轮不要继续加新功能，不要继续做 Effect Rack 导出，不要再堆更多模块。

这轮只做一件事：把三个页面收束成一套统一、干净、可理解的产品工作台。

## 阶段定位

第29阶段已经完成地基回归收口。  
第30B阶段已经完成 Studio 产品壳和 Effect Rack 草稿。  
现在的问题不是链路不通，而是页面视觉和信息架构仍然像“多个阶段堆出来的测试现场”。

所以本阶段优先级是：

1. 规整布局
2. 统一视觉语法
3. 降低默认信息噪音
4. 保留已有业务绑定和 smoke selector

不要为了“好看”破坏功能。

## 必读文件

- `D:\FeiSharkStudio-v2\frontend\index.html`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\js\main.js`
- `D:\FeiSharkStudio-v2\frontend\js\ui.js`
- `D:\FeiSharkStudio-v2\frontend\js\jobs.js`
- `D:\FeiSharkStudio-v2\frontend\js\models.js`
- `D:\FeiSharkStudio-v2\frontend\js\train.js`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-29-regression-closure-product-acceptance-report.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-30b-studio-product-shell-plugin-slots-report.md`

## 允许修改

- `frontend\index.html`
- `frontend\factory.html`
- `frontend\studio.html`
- `frontend\css\app.css`
- 前端 JS 中只和布局、折叠、默认选区、文案、轻量 UI 状态有关的部分：
  - `frontend\js\ui.js`
  - `frontend\js\main.js`
  - `frontend\js\jobs.js`
  - `frontend\js\models.js`
  - `frontend\js\train.js`
  - `frontend\js\factory\main.js`
  - `frontend\js\studio.js`
- 新增浏览器验收脚本：
  - `frontend\playwright_stage32b_three_page_layout_smoke.cjs`
- 本阶段 report：
  - `docs\agent-md\worker\stage-32b-three-page-layout-normalization-report.md`

## 禁止修改

- 后端任何文件
- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- RVC / UVR / ffmpeg 执行层
- README
- 第31阶段 Effect Rack 导出合同相关文件

如果你发现必须改后端，停下来写到 report，不要自己动。

## 三页统一目标

### 全局布局规则

三页必须统一成同一种产品语言：

- 顶部：统一品牌区 + 主导航 + 当前状态 / 主操作
- 主体：统一最大宽度、统一左右边距、统一卡片圆角、统一 section 间距
- 默认主屏：只展示用户当前最需要做的 3-5 件事
- 技术字段：默认折叠，不要铺满首屏
- 长 ID / 路径：单行截断，hover/title 可看完整
- CTA：每页最多 1 个主按钮，其余降级为次级按钮
- 空状态：用产品语言解释下一步，不要只显示“暂无数据”

### Dashboard 工作台

目标：用户一进来就知道三件事：

1. 我要创建翻唱还是训练
2. 当前任务跑到哪了
3. 当前可用模型 / 系统状态是否正常

请规整为：

- 左或上方：创建入口
  - AI 一键翻唱
  - 单文件快速训练
  - 多文件批量精训
- 中心：任务中心
  - 默认显示关键任务摘要
  - 任务详情、阶段日志、技术详情默认折叠
- 右侧或下方：模型资产 + 诊断摘要
  - 模型清单默认收起，只显示可用数量和最近选中
  - 诊断长列表默认收起

不要让首页一打开像“所有功能全摊开”。

### Factory 工厂页

目标：Factory 是“批次 / 曲目 / 成品流转”的生产页面，不是第二个 Dashboard。

请规整为：

- 顶部：当前批次和当前曲目状态
- 左侧：批次 / 曲目选择，默认紧凑
- 中心：当前曲目的生产面板
  - 导入音轨
  - 选择模型
  - 创建 cover job
  - 最新成品 / 当前主成品
- 右侧或下方：歌词 / 历史 / 关联任务抽屉

当前主成品、最新成品、进入 Studio 的路径要清晰，但不要把所有历史版本默认铺开。

### Studio 修音室

目标：Studio 是“围绕一个成品继续试听、确认、后处理草稿”的空间。

请规整为：

- 左侧或中心：播放器和当前成品
- 右侧：Inspector
  - 成品摘要
  - 模型来源
  - 下载
- Effect Rack 保留，但视觉上要像工具区，不要压过播放器
- 技术详情、阶段日志、Track History、全局试听库默认折叠

Studio 默认首屏应该更像修音台，不像资源管理器。

## 必须保留的关键 selector

### Dashboard

- `#taskCenter`
- `#entryCenter`
- `#modelPanel`
- `#diagnosticsPanel`
- `#coverModelSelect`
- `#jobsTableBody`
- `.job-row[data-job-id]`
- `#jobSummaryCard`
- `#jobActionBar`
- `[data-open-studio="true"]`
- `#jobStageLogsBody`
- `#jobTechnicalBody`
- `#modelsInventoryBody`
- `#modelsInventoryToggleBtn`
- `#modelsList [data-model-id]`
- `#modelDetailCard`
- `#modelUseForCoverBtn`
- `#modelSourceJobBtn`
- `#modelTechnicalBody`
- `[data-mobile-tab-target]`

### Factory

- `#factoryCreateBatchForm`
- `#factoryImportTracksForm`
- `#factoryRefreshBtn`
- `#factoryBatchesList`
- `#factoryTracksList`
- `#factoryCoverModelSelect`
- `#factoryCreateCoverJobBtn`
- `#factoryTrackJobsList`
- `#factoryTrackOutcomeCard`
- `#factoryCurrentMasterCard`
- `#factoryTrackTitle`
- `#factoryTrackSubtitle`
- `#factoryLyricText`
- `#factoryLyricsToggleBtn`
- `#factoryLyricsBody`
- `[data-batch-id]`
- `[data-track-id]`
- `[data-track-job-id]`
- `[data-studio-url]`
- `[data-download-url]`

### Studio

- `#studioSourceContextCard`
- `#studioSourceMetaGrid`
- `#studioFactoryBackBtn`
- `#studioArtifactSummaryCard`
- `#studioSummaryDownloadBtn`
- `#studioTrackHistoryPanel`
- `#studioTrackHistoryList`
- `[data-track-history-job-id]`
- `[data-set-track-master-job-id]`
- `#studioEffectRackList`
- `[data-effect-slot-toggle]`
- `#studioTechnicalToggleBtn`
- `#studioTechnicalBody`

可以重排 DOM，但不能删掉这些语义锚点。

## 具体任务

### 1. 做三页视觉审计

先不要改代码，先在 report 里记录当前三页混乱点：

- 哪些模块默认太重
- 哪些区域重复
- 哪些 CTA 互相抢
- 哪些技术字段应该折叠
- 哪些页面不像同一个产品

### 2. 统一 CSS 设计语法

在 `app.css` 中整理或补齐一套共享布局语法：

- page shell
- section header
- card / panel
- drawer
- compact list
- primary / secondary / ghost action
- meta grid
- status pill
- responsive grid

不要重复复制三套相似 CSS。能抽共享类就抽共享类。

### 3. Dashboard 规整

- 把创建入口、任务中心、模型资产、诊断摘要摆成清晰主次。
- 模型清单 / 诊断长列表默认折叠。
- 任务详情、阶段日志、技术详情默认折叠。
- 保留现有任务过滤、任务详情、模型选择、训练/翻唱表单。

### 4. Factory 规整

- 强化“当前批次 / 当前曲目 / 当前主成品”的层级。
- 批次列表、曲目列表、关联任务、歌词历史默认紧凑或折叠。
- 创建 cover 的入口要明确，但不要压过当前曲目摘要。
- `进入 Studio` 和 `下载` 操作必须清晰。

### 5. Studio 规整

- 播放器和当前成品摘要要成为视觉中心。
- Effect Rack 变成工具区，不要占据过多首屏权重。
- 技术详情、历史、资源库继续默认折叠。
- 修正已加载状态下仍显示“选择一个已完成 cover job”这类不合时宜文案。

### 6. 新增三页布局 smoke

新增：

- `frontend\playwright_stage32b_three_page_layout_smoke.cjs`

至少验证：

1. Dashboard / Factory / Studio 三页都能打开。
2. 三页都有统一导航。
3. 三页关键 selector 存在。
4. 默认没有横向滚动：
   - `document.documentElement.scrollWidth <= window.innerWidth + 8`
5. 关键抽屉默认折叠：
   - Dashboard 技术详情 / 模型库存
   - Factory 歌词或历史抽屉
   - Studio 技术详情 / 历史 / 试听库
6. 截图输出：
   - `stage32b_dashboard_layout.png`
   - `stage32b_factory_layout.png`
   - `stage32b_studio_layout.png`

## 验证要求

必须执行：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
node frontend\playwright_stage32b_three_page_layout_smoke.cjs
node frontend\playwright_stage17_smoke.cjs
node frontend\playwright_factory_smoke.cjs
node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
```

建议执行：

```powershell
node frontend\playwright_model_registry_linkage_smoke.cjs
node frontend\playwright_factory_to_studio_context_smoke.cjs
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

如果建议项没跑，必须写明原因。

## 交付要求

必须写入：

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32b-three-page-layout-normalization-report.md`

report 必须包含：

1. 三页当前混乱点审计。
2. 三页规整后的信息架构。
3. 修改了哪些文件。
4. 保留了哪些关键 selector。
5. 哪些技术信息被默认折叠。
6. 三页截图路径。
7. 执行过哪些验证命令，结果是什么。
8. 哪些建议 smoke 没跑，原因是什么。
9. 是否修改后端：必须为否。
10. 是否发现后续需要地基 agent 验收的风险。

## 完成标准

- 三页视觉语言明显统一。
- 三页默认首屏不再像测试痕迹堆叠。
- 关键 selector 未破坏。
- 三页布局 smoke 通过。
- Dashboard / Factory / Studio 各自核心 smoke 通过。
- 没有改后端。
