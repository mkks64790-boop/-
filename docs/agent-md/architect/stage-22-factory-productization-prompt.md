# 第22阶段：Factory 产品化收口（自动刷新 + 资产摘要 + 完成态快捷入口）

你现在是 FeiShark Studio 的工作 agent。

第 21 阶段已经完成并通过独立验收：

- `Factory track -> cover job` 桥接已打通
- `GET /api/tracks/{track_id}/jobs` 已存在
- `POST /api/tracks/{track_id}/cover-jobs` 已存在
- `Factory` 可以直接从 `track` 创建翻唱任务，并看到关联任务
- `Dashboard / Studio / Factory / cover / train` 当前回归通过

这一轮不要重开新架构，不要引入分布式队列，不要碰大规模 UI 换皮。

本阶段只做一件事：

把 `Factory` 从“能跑通”的工作台，收口成“能连续工作”的产品面，让用户在不手动反复刷新页面的情况下，也能持续观察任务、看到成品、进入 `Studio`。

## 必读文件

- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\frontend\playwright_factory_job_bridge_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-21-factory-job-bridge-report.md`

## 任务范围

### 允许修改

- `Factory` 页面的前端交互与布局收口
- 为 `Factory` 详情区补充必要的轻量状态字段或辅助接口返回
- `Factory` 相关 smoke / 回归测试
- 本轮提示词与汇报文件

### 禁止事项

- 不要推翻现有 `Dashboard / Studio / Factory` 路由结构
- 不要改动 `cover / train` 核心执行管线
- 不要引入 `Redis / WebSocket / Celery / DAG`
- 不要把这一轮做成大范围视觉重设计
- 不要新增第二套任务系统

## 具体任务

### 1. 选中 Track 的轻量自动刷新

当前 `Factory` 的核心问题不是“不能建任务”，而是任务发出后，用户还要手动反复刷新才能知道状态是否变化。

你要做的是：

- 当用户选中了一个 `track`
- 且这个 `track` 最近关联任务存在 `pending / processing / 分离中 / 修音中 / 变声中 / 混音中 / 训练中` 这类非终态
- 前端应只对“当前选中的 track 详情 + 关联 jobs”做轻量轮询刷新

要求：

- 使用前端本地轮询即可，间隔控制在合理范围，例如 `3s ~ 5s`
- 只刷新当前选中的 `track` 和它的 `jobs`，不要每次全量刷新 `summary / batches / models`
- 当任务进入终态后自动停止轮询
- 切换 track、切换 batch、离开页面时，必须正确清理旧 timer
- 严禁出现重复 timer 叠加

### 2. Track 详情区产品化收口

把当前 `Factory` 里的单曲详情区，整理成更像工作台而不是调试台。

至少拆成以下三个信息块：

- `曲目资产`
- `歌词资产`
- `关联任务`

要求：

- 保留现有数据绑定，不得丢字段
- 信息层级更清楚，优先展示“我现在能干什么”
- 长路径、长 ID、技术字段要弱化，不要主导视觉
- 可加入轻量折叠/展开结构，但必须保证自动刷新时不会重置折叠状态

建议目标：

- `曲目资产`：标题、作者、来源音频、当前状态
- `歌词资产`：当前歌词文档 / 当前时间轴版本 / 相关版本
- `关联任务`：最新任务、阶段、状态、错误摘要、快捷动作

### 3. 完成态快捷入口收口

当某个 `track` 的最新 `cover job` 完成后，用户应该在 `Factory` 里一眼看到结果，而不是还要猜去哪里点。

要求：

- 在 `Factory` 当前 `track` 详情区明确展示“最新成品已就绪”
- 直接提供：
  - `进入 Studio`
  - `下载成品`
- 如果已有现成 `studio_url / final_artifact_download_url`，优先复用，不要新造重复路由
- 如果任务正在跑，优先展示当前阶段和进度感知文案

### 4. 保持状态折叠记忆

本轮涉及 `Factory` 详情区的结构整理后，必须注意一个产品问题：

- 自动刷新不能把用户刚刚折叠好的区域重新弹开
- 自动刷新也不能把用户刚刚展开看的区域重新收起

要求：

- 采用前端内存态或等价轻量方案
- 至少保证 `曲目资产 / 歌词资产 / 关联任务` 的折叠态在刷新后保持不变

### 5. 测试补齐

至少完成以下验证：

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`
- `node frontend/playwright_stage17_smoke.cjs`
- `node frontend/playwright_stage18_smoke.cjs`
- `node frontend/playwright_stage19_smoke.cjs`
- `node frontend/playwright_factory_smoke.cjs`
- `node frontend/playwright_factory_job_bridge_smoke.cjs`

并新增或升级一条与本轮目标强绑定的 smoke，建议命名：

- `frontend/playwright_factory_auto_refresh_smoke.cjs`

这条 smoke 至少验证：

1. 打开 `/factory`
2. 选中一个 `track`
3. 发起 `cover job`
4. 不手动点击“刷新当前曲目”
5. 等待前端自动刷新把任务状态更新出来
6. 若任务完成，则验证 `进入 Studio / 下载成品` 自动出现

## 交付要求

完成后必须输出：

1. 修改了哪些文件
2. `Factory` 自动刷新是如何实现的
3. 折叠状态是如何在刷新后保持不变的
4. 完成态快捷入口是如何落地的
5. 跑了哪些测试，结果是什么
6. 还剩哪些已知限制
7. 将本轮汇报写入：
   - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-22-factory-productization-report.md`

## 完成标准

- `Factory` 选中 track 后，活跃任务状态可自动刷新
- 自动刷新不会造成重复轮询、页面抖动或折叠态丢失
- 完成态成品可在 `Factory` 内直接进入 `Studio` 或下载
- `Dashboard / Studio / Factory / cover / train` 现有主链路不回退
- 新增 smoke 能证明“无需手动刷新当前曲目”也能看到任务状态推进
