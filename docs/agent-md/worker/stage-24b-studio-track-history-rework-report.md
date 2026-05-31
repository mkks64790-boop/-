# 第24B阶段执行汇报：Studio Track 历史返工（补做成品历史 + 版本备注 + 专用 smoke）

## 完成情况

- 已完成：
  - `Studio` 已新增“当前曲目成品历史”区域。
  - 从 `Factory` 带 `track_id` 进入 `Studio` 后，会优先读取并展示当前来源 `track` 的完成态 `cover` 历史。
  - 历史版本可点击切换试听，播放器、当前成品摘要、URL 查询参数同步更新。
  - 每个历史版本会明确标出 `当前试听 / 最新版本 / 历史版本`。
  - 当前试听不是最新版本时，摘要区会显示明确但不抢眼的提示。
  - 当前版本已支持本机轻量备注，备注按 `job_id` 存入 `localStorage`，刷新后可恢复。
  - 全局试听品库继续保留，但在有来源 `track` 时被降级为次级入口。
  - 已新增并通过 `frontend/playwright_studio_track_history_smoke.cjs`。
- 部分完成：
  - 备注是本机浏览器备注，不进入后端数据库，也不跨设备同步。
- 未完成：
  - 没有做真实多轨 DAW、版本导出、多人共享备注或正式资产层，这是本轮刻意不做的范围。

## 修改文件

- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\playwright_studio_track_history_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-24b-studio-track-history-rework-report.md`

## 功能结果

### 当前曲目成品历史

- 做了什么：
  - 在 `Studio` 右侧成品资源面板顶部新增 `当前曲目成品历史`。
  - 这个区域只在当前页面存在来源 `track_id` 时显示。
  - 若普通打开 `/studio` 或当前成品不关联 `track_id`，区域隐藏，页面保持 Stage 23 的兼容行为。
- 如何识别来源 `track`：
  - 优先从 `GET /api/jobs/{job_id}` 返回的 `track_id / batch_id / factory_url` 获取。
  - 也兼容从 URL 查询参数读取 `track_id / batch_id`。
  - 当切换到一个没有 `track_id` 的全局成品时，会清理旧的来源上下文，避免历史区残留上一个曲目。
- 成品历史如何获取：
  - 复用现有接口：
    - `GET /api/tracks/{track_id}/jobs?limit=50&offset=0`
  - 前端过滤规则：
    - `job_kind === "cover"` 或 `job_type === "cover"`
    - `status` 为完成态
    - `can_open_studio === true` 或存在 `final_artifact_download_url`
  - 不新增后端接口，不新造第二套产物系统。
- 历史版本如何切换：
  - 每条历史项是可点击按钮。
  - 点击后调用既有 `loadJob(job_id, { artifactId })`。
  - 切换后同步：
    - 播放器音频
    - 当前成品摘要
    - 版本标签
    - URL 中的 `job_id / artifact_id / track_id / batch_id`

### 当前试听 / 最新版本 / 历史版本

- 做了什么：
  - 历史列表项和当前成品摘要都增加版本身份标识。
  - 标识不是模糊文案，而是按固定规则计算。
- 如何判定“当前试听”：
  - `job_id === state.selectedJobId`
- 如何判定“最新版本”：
  - 当前来源 `track` 的完成态可试听 `cover` 历史按 `created_at` 倒序排序。
  - 排序后的第一条为 `最新版本`。
- 如何判定“历史版本”：
  - 当前来源 `track` 的历史中，非最新版本统一标为 `历史版本`。
  - 如果用户正在试听历史版本，它会同时显示 `当前试听` 与 `历史版本`，摘要区会提示“当前试听不是这个 Track 的最新版本”。
- UI 如何展示：
  - 历史列表每条展示：
    - `voice_name / voice_model_id`
    - `job_id`
    - 创建时间
    - 阶段
    - 状态 pill
    - `当前试听 / 最新版本 / 历史版本` 标签
  - 当前摘要区同步展示版本标签和非最新提示。

### 轻量版本备注

- 做了什么：
  - 当前成品摘要区新增 `本机版本备注` 编辑器。
  - 支持输入、自动保存和点击 `保存备注`。
  - 历史列表项会显示该版本已保存的备注摘要。
- 备注如何存储：
  - 使用 `localStorage`。
  - key 形式：
    - `feishark_studio_job_note_${jobId}`
  - 备注最大保留 240 字符，并在保存前做 trim。
- 刷新后如何恢复：
  - `Studio` 载入当前 `job_id` 时读取 `localStorage`。
  - 页面刷新、重新进入 `Studio` 或在历史版本间切换后，都会按 `job_id` 恢复对应备注。

### 全局试听品库降级

- 做了什么：
  - 有来源 `track` 时，右侧优先展示 `当前曲目成品历史`。
  - 全局试听品库、快速选择和完整卡片库仍保留。
  - 文案调整为“全局试听品库，作为次级入口保留”。
- 为什么这样做：
  - 不删除 Stage 17/18 已有全局试听品库能力。
  - 但用户从 `Factory` 某个曲目进入时，首要工作对象应该是当前 `track` 的版本历史，而不是全局成品池。

### 测试

- 新增或更新了哪些测试：
  - 新增：
    - `D:\FeiSharkStudio-v2\frontend\playwright_studio_track_history_smoke.cjs`
- 专用 smoke 覆盖点：
  - 创建 batch 并导入 track。
  - 为同一个 track 创建两个完成态 cover job。
  - 从 `/factory` 进入最新完成版本的 `Studio`。
  - 验证出现 `当前曲目成品历史`。
  - 验证列表中能看到 `当前试听 / 最新版本`。
  - 为当前版本写入备注并保存。
  - 刷新页面后验证备注恢复。
  - 切换到另一条历史版本后，播放器和摘要同步为旧版本。
  - 验证旧版本提示“不是这个 Track 的最新版本”。

## 验证结果

```text
python -m pytest -q
结果：
9 passed, 2 warnings in 2.03s

python -X utf8 backend/self_check.py
结果：
SELF_CHECK_SUMMARY PASS

node frontend/playwright_stage17_smoke.cjs
结果：
PASS
截图：
D:\FeiSharkStudio-v2\stage17_dashboard.png
D:\FeiSharkStudio-v2\stage17_studio.png

node frontend/playwright_stage18_smoke.cjs
结果：
PASS
截图：
D:\FeiSharkStudio-v2\stage18_dashboard.png
D:\FeiSharkStudio-v2\stage18_studio.png

node frontend/playwright_stage19_smoke.cjs
结果：
PASS
截图：
D:\FeiSharkStudio-v2\stage19_dashboard.png
D:\FeiSharkStudio-v2\stage19_model_detail.png

node frontend/playwright_factory_smoke.cjs
结果：
PASS
备注：
第一次执行时 8000 本地服务已掉线，脚本卡在 Factory 页入口；重启本地 uvicorn 后重跑通过。
截图：
D:\FeiSharkStudio-v2\stage20_factory.png

node frontend/playwright_factory_job_bridge_smoke.cjs
结果：
PASS
截图：
D:\FeiSharkStudio-v2\stage21_factory_bridge.png

node frontend/playwright_factory_auto_refresh_smoke.cjs
结果：
PASS
截图：
D:\FeiSharkStudio-v2\stage22_factory_auto_refresh.png

node frontend/playwright_factory_to_studio_context_smoke.cjs
结果：
PASS
截图：
D:\FeiSharkStudio-v2\stage23_factory_to_studio_context.png

node frontend/playwright_studio_track_history_smoke.cjs
结果：
PASS
截图：
D:\FeiSharkStudio-v2\stage24b_studio_track_history.png
```

## 风险与限制

- 还没做完的点：
  - 当前版本备注只存本机浏览器，不做后端同步，不适合作为多人协作元数据。
  - 历史版本只展示完成态且可试听的 `cover` job，不展示失败、排队、训练任务。
- 暂时保留的技术债：
  - 当前历史列表仍通过前端拉取 `GET /api/tracks/{track_id}/jobs` 后过滤，没有新增专门的 Studio history API。
  - 最新版本按 `created_at` 倒序判定；如果未来需要更严格的版本号，应补正式版本字段。
  - `Studio` 仍是试听与轻量工作备注，不是完整 DAW 或后处理版本管理系统。
- 需要架构师复查的点：
  - 是否在后续阶段把本机备注升级成可选的后端持久化版本备注。
  - 是否为 `track` 引入正式 `current_master_job_id / latest_master_job_id` 字段，减少前端排序判定。

## 交接说明

- 后续若继续做 `Studio`，优先考虑“Track 版本历史的正式资产层”，不要直接跳到 VST / DAW。
- 如果要让备注跨设备可见，应新增后端字段或版本表，不要继续扩大 `localStorage` 语义。
- 当前阶段仍严格沿用：
  - 现有 `Factory -> Studio` 跳转
  - 现有 `jobs + artifacts + download` 数据通路
  - 现有本地轮询 / 静态加载方式
