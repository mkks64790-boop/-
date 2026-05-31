# 第23阶段：Factory -> Studio 成品承接（来源上下文 + 返回链路 + 当前成品摘要）

你现在是 FeiShark Studio 的工作 agent。

第 22 阶段已经完成并通过独立验收：

- `Factory` 当前选中 `track` 可轻量自动刷新
- `Factory` 右侧详情区已收口为 `曲目资产 / 歌词资产 / 关联任务`
- 最新完成的 `cover job` 已可直接 `进入 Studio / 下载成品`
- 自动刷新不会叠加重复 timer，折叠态可保持
- `Dashboard / Studio / Factory / cover / train` 回归通过

这一轮不要再扩新页面，也不要重开任务系统。

本阶段只做一件事：

把 `Factory -> Studio` 的跳转承接做实，让用户进入 `Studio` 后，不再像落进一个与来源脱节的播放器页面，而是明确知道：

- 我是从哪个 `track` 进来的
- 这是谁的音色、哪一个任务、哪一个成品
- 我可以一键回到 `Factory` 的当前曲目位
- 我可以继续围绕这个成品工作

## 必读文件

- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\frontend\playwright_factory_job_bridge_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-22-factory-productization-report.md`

## 任务范围

### 允许修改

- `Studio` 页面的上下文承接 UI
- `Factory -> Studio` 跳转链路中必要的参数或最小后端补充
- `Job / Track` 详情接口的轻量补充字段
- 与本轮目标直接相关的 smoke / 回归测试
- 本轮提示词与汇报文件

### 禁止事项

- 不要推翻现有 `Studio` 播放器骨架
- 不要引入新的多页面路由体系
- 不要新建第二套产物系统
- 不要改动 `cover / train` 核心执行管线
- 不要上 WebSocket / Redis / Celery

## 具体任务

### 1. Studio 来源上下文卡

当用户从 `Factory` 的某个完成态 `cover job` 进入 `Studio` 时，`Studio` 顶部必须出现一个清晰的“来源上下文卡”。

至少展示：

- 来源 `track` 标题
- `track_id`
- 所属 `batch`
- 当前 `voice_name / voice_model_id`
- 当前 `job_id`
- 当前载入的成品文件名
- 当前成品状态

要求：

- 不能只显示 `job_id`
- 信息层级必须产品化，不要像调试面板
- 长 ID 和长路径做次级显示或省略显示

### 2. 返回链路做实

用户从 `Factory` 点进 `Studio` 后，必须能一键回到原来的曲目位，而不是只知道回 `/factory` 首页。

要求：

- 为 `Studio` 增加明确的返回动作，例如：
  - `返回 Factory 当前曲目`
  - `打开 Factory 曲目位`
- 返回时应尽量回到对应 `batch_id + track_id`
- 如果必要，可在 `studio_url` 中补充轻量参数，或者让 `Studio` 通过现有 `job_id` 反查 `track_id`
- 不要为了这个目标新造复杂路由

### 3. 当前成品摘要区强化

目前 `Studio` 能试听，但“当前成品是什么”还不够明确。

你要把当前成品摘要强化成可工作的状态，至少包含：

- 当前成品文件名
- 来源任务
- 当前阶段 / 状态
- 下载当前成品
- 打开当前产物路径或等价快捷动作（如果已有现成安全入口则复用；如果不适合直接打开本地路径，可保留为下载）

要求：

- 继续复用已有 `jobs + artifacts + download` 数据通路
- 不要新造重复下载接口
- 不要破坏现有 `试听品库`

### 4. Studio 对 Factory 来源的感知

当前 `Studio` 更像“全局已完成 cover 成品池”。本轮要让它在保留这个能力的同时，对来源 `Factory track` 有明确感知。

建议实现方向：

- 当 URL 带有 `job_id` 且该 job 关联 `track_id` 时：
  - 优先加载该 job
  - 显示来源 track 上下文
  - 将“回到 Factory”动作定位到这个 track
- 若不是从 `Factory` 进入，而是普通打开 `/studio`
  - 仍保持当前兼容行为

### 5. 测试补齐

至少完成以下验证：

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`
- `node frontend/playwright_stage17_smoke.cjs`
- `node frontend/playwright_stage18_smoke.cjs`
- `node frontend/playwright_stage19_smoke.cjs`
- `node frontend/playwright_factory_smoke.cjs`
- `node frontend/playwright_factory_job_bridge_smoke.cjs`
- `node frontend/playwright_factory_auto_refresh_smoke.cjs`

并新增一条本轮专用 smoke，建议命名：

- `frontend/playwright_factory_to_studio_context_smoke.cjs`

这条 smoke 至少验证：

1. 打开 `/factory`
2. 选中一个 track
3. 创建并等待一个可进入 `Studio` 的完成态 `cover job`
4. 点击 `进入 Studio`
5. 验证 `Studio` 顶部出现来源上下文卡
6. 验证存在 `返回 Factory 当前曲目`
7. 验证当前成品摘要区可见

## 交付要求

完成后必须输出：

1. 修改了哪些文件
2. `Studio` 是如何识别来源 `Factory track` 的
3. 返回链路是如何实现的
4. 当前成品摘要区补强了哪些信息
5. 跑了哪些测试，结果是什么
6. 还剩哪些已知限制
7. 将本轮汇报写入：
   - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-23-factory-studio-context-report.md`

## 完成标准

- 从 `Factory` 进入 `Studio` 后，用户能明确看到来源 `track` 上下文
- `Studio` 存在回到原 `Factory` 曲目位的明确动作
- 当前成品摘要比现在更完整，但不破坏播放器与试听品库
- 普通直接打开 `/studio` 的兼容行为不回退
- 新增 smoke 能证明 `Factory -> Studio` 承接链路成立
