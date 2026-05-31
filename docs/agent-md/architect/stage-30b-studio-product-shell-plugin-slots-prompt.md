# Stage 30B：Studio 修音室产品化 UI + 插件槽前端壳

你现在是 FeiShark Studio 的产品体验 agent。

注意：另一个工作 agent 正在执行第29阶段“回归脚本收口 + 产品验收口径固化”。你这条线是并行的产品体验线，不能和第29阶段抢同一批文件。

这轮目标不是继续修回归脚本，也不是接真实 VST。

这轮目标是把 `Studio` 从“工程验收页”改造成“用户愿意停留的修音室产品壳”：页面打开后应该是干净、清晰、有工作室感的成品处理空间，而不是一地测试痕迹。

## 背景

当前项目已经具备：

- 第26阶段：真实长干声训练链通过。
- 第27阶段：训练模型进入模型资产库，并能送入翻唱入口。
- 第28阶段：真实训练模型已经完成 `Train -> Model Registry -> Cover -> Factory -> Studio` 闭环。
- 第29阶段正在由稳定性 agent 修复旧 smoke / verify 脚本，不属于你这轮范围。

当前 Studio 的核心问题：

- 业务语义已经开始跑通，但页面仍像技术验收面板。
- 成品摘要、任务详情、音轨历史、模型来源、下载入口、试听入口的层级还不够产品化。
- 用户想看到的是“这首成品现在能怎么修、怎么听、怎么导出”，不是一堆裸露调试数据。
- 传统 Windows VST 不能被浏览器网页直接加载，所以这轮只能做“插件槽抽象和参数草稿”，不要伪装成真实 VST 已接入。

## 本阶段目标

1. 重构 `Studio` 页面信息架构，让它成为干净的修音室产品壳。
2. 保留第28阶段真实闭环需要的 DOM / 数据语义，不破坏已有 smoke。
3. 增加“后处理插件槽 / Effect Rack”前端抽象，为以后接 WebAudio / 后端 DSP / 原生 VST Host 留接口。
4. 把任务详情、阶段日志、技术字段收进抽屉或折叠区，默认不要铺满主页面。
5. 补一条轻量浏览器 smoke，确认 Studio 页面能打开、关键信息可见、抽屉可展开、插件槽状态可操作。

## 必读文件

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-28-trained-model-cover-studio-closure-report.md`
- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\js\api.js`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\playwright_trained_model_cover_studio_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-29-regression-closure-product-acceptance-report.md`

如果第29阶段 report 还没写完，不要等待它；只要不要修改第29阶段涉及的脚本即可。

## 并行协作边界

### 你允许修改

- `frontend\studio.html`
- `frontend\js\studio.js`
- `frontend\css\app.css`
- 新增一条 Stage 30B Studio 产品壳 smoke，例如：
  - `frontend\playwright_stage30b_studio_product_shell_smoke.cjs`
- 本阶段 worker report：
  - `docs\agent-md\worker\stage-30b-studio-product-shell-plugin-slots-report.md`

### 如非必要不要修改

- `frontend\factory.html`
- `frontend\js\factory\main.js`

只有 Studio 入口文案或跳转上下文确实需要轻量适配时才改，并必须在 report 里说明。

### 禁止修改

- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- `README.md`
- `backend\main.py`
- `backend\services\track_service.py`
- `backend\services\job_service.py`
- 任何 RVC / UVR / ffmpeg 执行层

这些属于第29阶段或后端主链路，不要碰。

## 兼容性硬约束

第28阶段真实闭环 smoke 依赖一些 Studio DOM 和语义。你可以美化和重排，但不要删掉或改坏这些关键锚点：

- `#studioSourceContextCard`
- `#studioSummaryDownloadBtn`
- `#studioTrackHistoryList`
- `[data-set-track-master-job-id]`
- Studio URL query 参数：
  - `batch_id`
  - `track_id`
  - `job_id`
  - `artifact_id`
- 页面中仍需默认可见或可被 smoke 找到：
  - `track_id`
  - 当前 job / artifact 上下文
  - `voice_model_id` 或模型名
  - `voice_model_source_summary` 或 `source_job_id`
  - 下载按钮可用状态

如果必须改 DOM 结构，请同步更新 Stage 30B 自己的 smoke；但不要破坏 `playwright_trained_model_cover_studio_smoke.cjs`。

## 产品设计方向

### 1. Studio 页面主结构

建议重构为四个清晰区域：

1. 顶部 Hero：
   - 当前成品名 / Track 标识
   - 当前音色 / 模型来源摘要
   - 下载 / 返回 Factory / 设为当前主成品的主操作
2. 主试听区：
   - 音频播放器
   - 成品状态
   - 当前 Master / 当前 Artifact
3. 右侧 Inspector：
   - 成品摘要
   - 模型来源
   - 任务上下文
   - 技术详情抽屉
4. 下方或侧边 Effect Rack：
   - 插件槽列表
   - 参数草稿
   - 暂不可用功能明确标注“下一阶段接入”，不要假装已经生效

### 2. 默认隐藏技术噪音

这些内容默认折叠：

- 任务详情 JSON / 原始字段
- 阶段日志
- Track History 长列表
- artifact 技术路径
- batch/job/track 的长 ID 列表

默认主屏只保留产品用户真正关心的：

- 成品能不能听
- 这次是谁的声音
- 这个声音来自哪次训练
- 能不能下载
- 能不能设为主成品
- 下一步能做什么后处理

### 3. 插件槽 / Effect Rack 抽象

这轮只做前端产品壳，不接真实 VST。

请实现一个轻量 `effectRackState`，建议包含：

```js
[
  {
    id: "eq",
    label: "EQ 均衡",
    enabled: false,
    status: "draft",
    params: { low: 0, mid: 0, high: 0 }
  },
  {
    id: "compressor",
    label: "Compressor 压缩",
    enabled: false,
    status: "draft",
    params: { threshold: -18, ratio: 3 }
  },
  {
    id: "reverb",
    label: "Reverb 空间",
    enabled: false,
    status: "draft",
    params: { mix: 10 }
  },
  {
    id: "limiter",
    label: "Limiter 限幅",
    enabled: true,
    status: "draft",
    params: { ceiling: -1 }
  }
]
```

要求：

- 可以在 UI 上开关插件槽。
- 可以调整少量参数。
- 状态暂存在前端内存或 `localStorage`。
- localStorage key 必须带上 `track_id / job_id / artifact_id`，避免不同成品互相污染。
- UI 必须明确提示：当前是“后处理参数草稿”，暂不改变已生成音频。
- 不要把按钮命名成“真实 VST 已启用”。
- 可以预留 `导出处理版` 按钮，但必须 disabled 或标注“下一阶段接入后端导出”。

### 4. 视觉方向

不要做普通后台管理页。

建议视觉关键词：

- 深色录音棚
- 暖橙高亮
- 大块留白
- 玻璃/金属质感可以少量使用
- 卡片不要密密麻麻贴边
- 技术 ID 和路径统一用小号、等宽、可复制或 tooltip

保留当前项目已有色彩体系即可，不要整套推翻。

### 5. 响应式

桌面端：

- 主试听区 + 右侧 Inspector + Effect Rack 可以并列或分区。

窄屏：

- 不要变成长蛇阵。
- 至少把 Inspector / Effect Rack 处理成折叠块或 tab。

## 具体任务

### 1. 先审计 Studio 当前信息架构

阅读 `studio.html` 和 `studio.js`，确认：

- 当前数据从哪些 API 来。
- 当前有哪些 DOM id 被 JS 绑定。
- 哪些 DOM id 被现有 smoke 依赖。
- 哪些区域是调试痕迹，应该折叠或降级。

不要一上来重写整页。先保留数据绑定，再改结构。

### 2. 重构 Studio 产品壳

请完成：

- 新 Studio 顶部 Hero。
- 更清晰的播放器 / 当前成品摘要。
- 模型来源摘要默认可见。
- 任务详情 / Track History / 阶段日志默认折叠。
- 下载和设主成品操作仍可用。
- 长路径、长 ID 继续截断，hover 或 title 可看完整内容。

### 3. 增加 Effect Rack 插件槽前端壳

请完成：

- 插件槽列表。
- 每个槽的启用开关。
- 基础参数控件。
- `localStorage` 草稿保存和恢复。
- 明确的“暂不改变音频”提示。
- 预留但禁用的“导出处理版”入口。

### 4. 增加 Stage 30B smoke

新增浏览器 smoke，建议：

- `frontend\playwright_stage30b_studio_product_shell_smoke.cjs`

它至少验证：

1. 能打开一个已有 Studio URL。
2. `#studioSourceContextCard` 存在。
3. 下载按钮存在。
4. 模型来源摘要可见。
5. Effect Rack 可见。
6. 能切换一个插件槽开关。
7. 刷新后插件槽草稿能恢复。
8. Track History 或技术详情抽屉能展开/收起。

如果本机缺少可用真实 Studio URL，请从 API 中寻找最近的可打开 Studio job；如果找不到，请让 smoke 给出清晰失败原因，不要静默通过。

### 5. 验证现有 Stage 28 smoke 没被破坏

本轮至少要做静态兼容检查：

- 确认 `playwright_trained_model_cover_studio_smoke.cjs` 依赖的关键 selector 仍存在。

如果时间和环境允许，执行：

```powershell
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

如果没有执行，必须在 report 里说明原因。

## 验证要求

必须执行：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
```

建议执行：

```powershell
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

不要执行或修改第29阶段的回归脚本：

```powershell
python -X utf8 backend\smoke_stage9.py
python -X utf8 backend\verify_stage11_train_flow.py
```

除非你只是确认它们属于另一个 agent 的范围，并在 report 里写“未执行，避免并行冲突”。

## 交付要求

完成后必须写入：

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-30b-studio-product-shell-plugin-slots-report.md`

report 必须包含：

1. 修改了哪些文件。
2. Studio 页面信息架构改成了什么。
3. 哪些技术噪音被收进抽屉。
4. Effect Rack 有哪些插件槽。
5. 插件槽状态如何保存。
6. 哪些按钮只是预留，尚未真实改变音频。
7. 是否保留第28阶段关键 DOM / selector。
8. 跑了哪些验证命令，结果是什么。
9. 哪些重型 smoke 没跑，原因是什么。
10. 是否和第29阶段文件产生冲突。

## 完成标准

- Studio 默认页面看起来像“修音室产品页”，不是工程调试页。
- 成品试听、下载、模型来源、当前主成品语义仍然可用。
- Effect Rack 插件槽能操作、能保存草稿，但不会谎称真实 VST 已生效。
- 技术详情默认折叠，用户主视线更干净。
- 新增 Stage 30B smoke 通过。
- 不破坏第28阶段真实闭环 selector。
- 不修改第29阶段负责的回归脚本和 README。
