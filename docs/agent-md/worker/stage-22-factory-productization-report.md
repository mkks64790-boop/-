# 第22阶段执行汇报：Factory 产品化收口（自动刷新 + 资产摘要 + 完成态快捷入口）

## 完成情况

- 已完成：
  - `Factory` 选中单曲后，当前 `track` 的详情与关联任务支持轻量自动刷新。
  - `Factory` 右侧单曲工位收口为 `曲目资产 / 歌词资产 / 关联任务` 三个可折叠信息块。
  - 最新 `cover job` 完成后，可在 `Factory` 内直接看到 `进入 Studio / 下载成品` 快捷入口。
  - 三个信息块的折叠态在自动刷新后保持不变。
  - Stage 22 专用浏览器 smoke 已新增并通过。
- 部分完成：
  - 自动刷新只覆盖当前选中的 `track`，不做全局 `summary / batches / models` 轮询，这是刻意保留的轻量设计。
- 未完成：
  - 暂无阻塞项。

## 修改文件

- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\playwright_factory_auto_refresh_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-22-factory-productization-report.md`

## 功能结果

### 自动刷新

- 做了什么：
  - 为当前选中的 `track` 增加了本地轻量轮询。
  - 轮询只请求：
    - `GET /api/tracks/{track_id}`
    - `GET /api/tracks/{track_id}/jobs`
  - 不再反复全量刷新 `summary / batches / models`。
- 当前如何触发：
  - 当用户选中某个 `track`，且最近关联任务存在非终态（如 `pending / 分离中 / 修音中 / 变声中 / 混音中 / 训练中`）时自动启动。
  - 轮询间隔为 `4s`。
- 如何避免重复 timer：
  - 前端只维护一个 `trackPollTimer`。
  - 每次重新调度前都会先 `clearTimeout`。
  - 轮询中用 `trackPollInFlight` 防止并发请求叠加。
  - 切换 `track`、切换 `batch`、页面隐藏或离开页面时，旧 timer 会被清理。
- 如何在终态停止：
  - 当当前 `track` 的关联任务全部进入 `完成 / 失败 / 已取消` 等终态后，自动停止轮询。
  - 当前状态 chip 会回到 `当前曲目已同步`。

### 详情区收口

- 做了什么：
  - 把右侧单曲工位从“散块堆叠”收口为：
    - `曲目资产`
    - `歌词资产`
    - `关联任务`
  - 在摘要卡下方新增一个独立的结果提示区，用于显示：
    - 最近任务正在推进
    - 最近任务失败
    - 最新成品已就绪
- `曲目资产 / 歌词资产 / 关联任务` 现在分别展示什么：
  - `曲目资产`
    - 标题
    - 作者
    - Track ID
    - 当前状态
    - 来源音频
    - 所属批次
    - 可用模型选择
    - `创建翻唱任务`
  - `歌词资产`
    - 当前歌词文档
    - 当前时间轴版本
    - 歌词文档数
    - 时间轴版本数
    - 歌词草稿编辑区
    - 歌词文档 / 时间轴版本列表
  - `关联任务`
    - 最近任务摘要
    - 状态 pill
    - 阶段 pill
    - 错误摘要
    - `进入 Studio / 下载成品`
    - 审计记录
- 哪些技术字段被弱化或折叠：
  - 长路径继续走单行省略。
  - 长 `job_id / track_id / lyric_document_id / timeline_id` 只做次级展示。
  - 审计记录从主信息降级为 `关联任务` 下方的次级信息。

### 折叠状态保持

- 使用了什么状态保存方式：
  - 使用 `localStorage` 保存三个区块的折叠态。
  - 新增 key：
    - `feishark_ui_factory_asset_collapsed`
    - `feishark_ui_factory_lyrics_collapsed`
    - `feishark_ui_factory_jobs_collapsed`
- 页面自动刷新后哪些区域能保持原状态：
  - `曲目资产`
  - `歌词资产`
  - `关联任务`
  - 上述三块在自动刷新、手动刷新当前曲目、重新载入当前 `track` 后都保持原折叠态，不会被强行弹开或收起。

### 完成态快捷入口

- `进入 Studio` 如何出现：
  - 当最近完成的 `cover job` 带有 `can_open_studio=true` 时，`Factory` 顶部结果提示区和关联任务列表都会出现 `进入 Studio`。
- `下载成品` 如何出现：
  - 当最近完成的 `cover job` 带有 `final_artifact_download_url` 时，同样会在结果提示区和关联任务列表出现 `下载成品`。
- 使用了哪些现有字段或接口：
  - 直接复用 `GET /api/tracks/{track_id}/jobs` 返回的：
    - `can_open_studio`
    - `studio_url`
    - `final_artifact_download_url`
    - `current_stage`
    - `latest_stage_message`
  - 本阶段没有新造重复路由。

### 测试

- 新增或更新了哪些测试：
  - 新增：
    - `D:\FeiSharkStudio-v2\frontend\playwright_factory_auto_refresh_smoke.cjs`
  - 复用了既有回归：
    - `playwright_stage17_smoke.cjs`
    - `playwright_stage18_smoke.cjs`
    - `playwright_stage19_smoke.cjs`
    - `playwright_factory_smoke.cjs`
    - `playwright_factory_job_bridge_smoke.cjs`
- 哪些回归点被覆盖：
  - `Factory` 打开与基础流程
  - `Factory track -> cover job` 桥接
  - 不手动点“刷新当前曲目”也能看到任务推进
  - 完成态下 `进入 Studio / 下载成品` 自动出现
  - 折叠态在自动刷新期间保持不变
  - `Dashboard / Studio / Factory` 既有页面回归

## 验证结果

逐条列出实际执行过的命令和结果：

```text
python -m pytest -q
结果：
9 passed, 2 warnings

python -X utf8 backend/self_check.py
结果：
SELF_CHECK_SUMMARY PASS

node frontend/playwright_stage17_smoke.cjs
结果：
PASS

node frontend/playwright_stage18_smoke.cjs
结果：
PASS

node frontend/playwright_stage19_smoke.cjs
结果：
PASS
备注：
首次执行出现一次瞬时 selector timeout，重跑通过。

node frontend/playwright_factory_smoke.cjs
结果：
PASS

node frontend/playwright_factory_job_bridge_smoke.cjs
结果：
PASS

node frontend/playwright_factory_auto_refresh_smoke.cjs
结果：
PASS
截图：
D:\FeiSharkStudio-v2\stage22_factory_auto_refresh.png
```

## 风险与限制

- 还没做完的点：
  - 当前自动刷新只照顾“当前选中的单曲工位”，不做跨批次或整页全局任务墙同步。
- 暂时保留的技术债：
  - 仍然使用本地轮询，不做 WebSocket / SSE。
  - 因此任务状态展示存在最多约 `4s` 的自然延迟。
  - 审计记录仍以轻量列表为主，暂未进一步翻译更多底层 action。
- 需要架构师复查的点：
  - 若后续 `Factory` 继续扩成更完整的生产工位，可能需要决定：
    - 是否给 `track` 引入更明确的“当前主任务”字段
    - 是否把歌词草稿本地编辑态再做更强的未保存保护

## 交接说明

下一轮继续前，优先关注：

- 若继续做 `Factory`，优先补“当前成品资产摘要”与“更多关联任务历史视图”，而不是扩新页面。
- 若继续做实时体验，优先先判断本地轮询是否够用，再决定是否需要更重的推送方案。
- 继续保持 Stage 21 的桥接方式：
  - 通过 `jobs.track_id` 关联
  - 复用现有 `studio_url / final_artifact_download_url`
  - 不新造第二套任务系统
