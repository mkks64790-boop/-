# 第21阶段执行汇报：Factory 与 Job 系统打通（Track -> Cover Job Bridge）

## 完成情况

- 已完成：
  - `Factory` 的单曲 `track` 现在可以直接创建真实 `cover job`。
  - 新增 `track -> jobs` 查询接口，前端可在曲目详情区看到关联任务状态、阶段、失败摘要、下载入口、Studio 入口。
  - `jobs.track_id / job_kind / resource_class / depends_on_json` 在新链路里被真实写入和使用。
  - `track.status` 已与 cover job 生命周期联动，并补齐最小审计事件。
  - Stage 21 专用 API 测试与浏览器 smoke 已落地并通过。
- 部分完成：
  - 当前 `Factory` 仍采用“刷新当前曲目”同步完成态，不做 WebSocket / 实时推送。
- 未完成：
  - 暂无阻塞项。

## 修改文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\playwright_factory_job_bridge_smoke.cjs`
- `D:\FeiSharkStudio-v2\tests\api\test_track_jobs_api.py`

## 功能结果

### Track 关联 Job 查询

- 新增接口：
  - `GET /api/tracks/{track_id}/jobs`
- 返回的关联任务项包含：
  - `job_id`
  - `job_type`
  - `job_kind`
  - `status`
  - `current_stage`
  - `voice_model_id`
  - `voice_name`
  - `created_at`
  - `updated_at`
  - `error_log`
  - `error_summary`
  - `latest_stage_message`
  - `depends_on`
  - `has_final_artifact`
  - `final_artifact_id`
  - `final_artifact_type`
  - `final_artifact_download_url`
  - `can_open_studio`
  - `studio_url`
- `current_stage` 不是生硬回显数据库字段，而是优先用 stage logs 推导出更接近业务阶段的结果。
- 对已完成 cover job，会根据真实 `cover_master` 产物生成 `下载成品` 与 `进入 Studio` 的可用入口。

### Track -> Cover Job 创建

- 新增接口：
  - `POST /api/tracks/{track_id}/cover-jobs`
- 前端 `Factory` 单曲详情区新增：
  - 可用模型下拉框
  - `创建翻唱任务` 按钮
  - 创建提示文案，明确“直接复用当前 track 的源音频，不重复上传”
- 后端创建时会：
  - 读取 `track.source_audio_path`
  - 先执行 `run_cover_preflight(model_id)`
  - 调用现有 `create_cover_job(...)`
  - 写入 `jobs.track_id`
  - 写入 `job_type='cover'`
  - 写入 `job_kind='cover'`
  - 写入 `resource_class='gpu_heavy'`
  - 把 `current_timeline_version_id / current_lyric_document_id` 收进 `depends_on_json`
  - 复用现有 queue / mutex / dispatcher，不新造第二套调度

### Factory 关联任务区

- `Factory` 单曲详情区新增“关联任务”展示：
  - 最近关联任务列表
  - 当前状态 pill
  - 当前阶段 pill
  - 简短任务摘要
  - 已完成时显示 `进入 Studio / 下载成品`
  - 失败时显示失败摘要
- 信息层级保持产品化：
  - 优先展示可执行动作和状态
  - 技术字段弱化
  - 不把 Dashboard 的调试详情原封不动搬过来

### Track 状态与审计联动

- 新链路下，`track.status` 会最小联动为：
  - `cover_pending`
  - `cover_processing`
  - `cover_ready`
  - `cover_failed`
- 审计事件已补齐：
  - `track_cover_job_create`
  - `track_cover_job_complete`
  - `track_cover_job_fail`
- `retry / requeue / cancel` 相关 job 控制也会把已关联 `track` 同步回对应状态或重置为空闲态。

## `track` 与 `job` 如何关联

- 关联主键是 `jobs.track_id`。
- `Factory` 从 `track` 发起 cover job 时，后端会把当前 `track_id` 写进 `jobs`。
- `depends_on_json` 记录了当前曲目的歌词时间轴与歌词文档来源，当前最小实现写入：
  - `current_timeline_version_id`
  - `current_lyric_document_id`
- `track_service.list_track_jobs(track_id)` 通过 `jobs.track_id` 反查任务，并结合：
  - stage logs
  - 最终产物
  - 模型信息
  组装成 `Factory` 可直接消费的任务摘要。

## 验证结果

```text
python -m pytest -q
结果：
9 passed, 2 warnings

python -X utf8 backend/self_check.py
结果：
SELF_CHECK_SUMMARY PASS

python -X utf8 backend/smoke_stage9.py
结果：
PASS

node frontend/playwright_stage17_smoke.cjs
结果：
PASS

node frontend/playwright_stage18_smoke.cjs
结果：
PASS

node frontend/playwright_stage19_smoke.cjs
结果：
PASS

node frontend/playwright_factory_smoke.cjs
结果：
PASS

node frontend/playwright_factory_job_bridge_smoke.cjs
结果：
PASS

附加回归：
python -X utf8 backend/verify_stage11_train_flow.py
结果：
PASS
```

## 浏览器验收结论

- `/factory` 可正常打开。
- 可以创建 batch、导入曲目、选中 track。
- 可以从 track 直接选择一个可用模型并创建 cover job。
- 关联任务区会出现真实 job。
- 已完成的 cover job 可从 `Factory` 直接看到：
  - `进入 Studio`
  - `下载成品`
- Stage 21 截图已生成：
  - `D:\FeiSharkStudio-v2\stage21_factory_bridge.png`

## 已知限制

- 当前桥接只覆盖 `Factory track -> cover job`，没有扩展到训练 job。
- 当前不做 Redis / Celery / WebSocket / DAG；仍完全复用本地单机队列与 dispatcher。
- `Factory` 关联任务完成后的动作区，目前通过“刷新当前曲目”同步到最新状态，不做实时推送。
- 本阶段只打通最小生产链路，不新增 Project Layer，也不改 Dashboard / Studio 既有主流程。

## 交接说明

- 下一阶段如果继续做 `Factory`，建议优先补“任务完成态的轻量自动刷新”或“更完整的 track 资产视图”。
- 当前基础桥已经可用，后续扩展应继续沿用：
  - `jobs.track_id`
  - `depends_on_json`
  - `track.status` 联动
  - 现有 queue / mutex / dispatcher
