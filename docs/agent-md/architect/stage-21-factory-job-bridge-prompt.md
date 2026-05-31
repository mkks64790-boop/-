# 第21阶段：Factory 与 Job 系统打通（Track -> Cover Job Bridge）

你现在是 FeiShark Studio 的实施 agent。

第 20 阶段已经完成：

- `Engine Center` 最小入口已经落地
- `Factory` 已具备 `batch / track / lyrics` 的最小闭环
- `Dashboard / Studio / cover / train` 主链路回归通过

这一轮不要重开新架构，不要引入分布式队列，不要做第二套真实引擎。

本阶段目标只有一个核心方向：

把 `Factory` 的 `track` 数据层与现有 `job` 系统打通，让导入进来的曲目不只是“静态记录”，而是真正能发起工作室生产任务。

## 必读文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\db.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\backend\services\batch_service.py`
- `D:\FeiSharkStudio-v2\backend\services\asset_service.py`
- `D:\FeiSharkStudio-v2\backend\services\model_service.py`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\js\jobs.js`
- `D:\FeiSharkStudio-v2\frontend\js\models.js`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-20-engine-center-factory-qa-report.md`

## 任务范围

### 允许修改

- `Factory` 的 track 详情区
- 与 `track` 关联的 job 查询与创建 API
- `jobs` 表的 `track_id / job_kind / resource_class / depends_on_json` 的实际使用
- 必要的轻量测试与 smoke

### 禁止事项

- 不要破坏现有 `Dashboard / Studio`
- 不要重写现有 cover 创建主流程
- 不要引入 Redis / Celery / WebSocket
- 不要上 DAG 全量编排
- 不要新增第二套前端框架

## 具体任务

### 1. Track 关联 Job 查询

新增或补齐后端能力，使单个 `track` 可以查询关联 `jobs`：

- 支持按 `track_id` 拉取关联 job 列表
- 返回至少包含：
  - `job_id`
  - `job_type`
  - `job_kind`
  - `status`
  - `current_stage`
  - `voice_model_id`
  - `voice_name`
  - `created_at`
  - 是否存在最终成品 / 可跳转 Studio

建议新增：

- `GET /api/tracks/{track_id}/jobs`

### 2. 从 Track 发起 Cover Job

让 `Factory` 里的单个曲目可以直接发起 cover job，而不是必须回到 Dashboard 重新上传。

要求：

- 新增 API：
  - `POST /api/tracks/{track_id}/cover-jobs`
- 前端在 `track` 详情区提供：
  - 可用模型下拉选择
  - `创建翻唱任务` 按钮
- 后端创建 cover job 时：
  - 使用该 `track` 的 `source_audio_path`
  - 正确写入 `jobs.track_id`
  - `job_kind='cover'`
  - `resource_class='gpu_heavy'`
  - 保持现有队列 / mutex / artifact 逻辑不变

不要走“重新上传一份同样的文件”的重复路径。

### 3. Factory 显示 Track 的 Job 状态

在 `Factory` 的单曲详情区新增一个 “关联任务” 区域，至少显示：

- 最近关联 job 列表
- 当前状态
- 当前阶段
- 已完成时的 `进入 Studio` / `下载成品`
- 失败时的错误摘要

要求：

- 信息层级沿用当前产品化风格，不要做成调试面板
- 技术字段折叠或弱化显示
- 不要把整套 Dashboard 明细原封不动复制进来

### 4. Track 状态与审计联动

当 `track` 发起或完成 job 后，补上最小状态联动：

- 发起 cover job 后，`track.status` 至少进入类似：
  - `cover_pending`
  - `cover_processing`
  - `cover_ready`
  - `cover_failed`
- 审计里记录：
  - `track_cover_job_create`
  - `track_cover_job_complete`
  - `track_cover_job_fail`

这轮不要求把所有历史 job 都回填，只要求新触发的流程是闭环的。

### 5. 测试补齐

至少补这些：

- `tests/api/test_track_jobs_api.py`
  - 查询 track 关联 jobs
  - 从 track 创建 cover job
- 如有需要补 unit test：
  - `tests/unit/test_track_job_bridge.py`
- 浏览器 smoke：
  - `frontend/playwright_factory_job_bridge_smoke.cjs`

这个 smoke 至少覆盖：

1. 打开 `/factory`
2. 选择 batch / track
3. 选择一个可用模型
4. 创建 cover job
5. 确认前端出现关联任务
6. 如任务完成，验证 `进入 Studio` 按钮或成品下载入口可见

## 交付要求

完成后必须输出：

1. 改了哪些文件
2. 新增了哪些 API
3. `track` 与 `job` 是如何关联的
4. 跑了哪些测试
5. 还有哪些已知限制
6. 将本轮汇报写入：
   - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-21-factory-job-bridge-report.md`

## 验证要求

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`
- `python -X utf8 backend/smoke_stage9.py`
- `node frontend/playwright_stage17_smoke.cjs`
- `node frontend/playwright_stage18_smoke.cjs`
- `node frontend/playwright_stage19_smoke.cjs`
- `node frontend/playwright_factory_smoke.cjs`
- `node frontend/playwright_factory_job_bridge_smoke.cjs`

## 完成标准

- `Factory` 中的 `track` 可以直接创建 cover job
- `track` 详情页能看到关联 job 列表
- 已完成 cover job 能从 `Factory` 直接进入 Studio 或下载成品
- `jobs.track_id` 在新链路里被真实使用
- `Dashboard / Studio / cover / train` 不回退

