# 第23阶段执行汇报：Factory -> Studio 成品承接（来源上下文 + 返回链路 + 当前成品摘要）

## 完成情况

- 已完成：
  - `Factory -> Studio` 跳转现在会把 `batch_id + track_id + job_id + artifact_id` 一起带入 `Studio`。
  - `Studio` 顶部新增了产品化的“来源上下文卡”，能明确告诉用户自己是从哪个 `track`、哪个 `batch`、哪个 `job` 进来的。
  - `Studio` 顶栏和上下文卡都补上了“返回 Factory 当前曲目 / 打开 Factory 曲目位”动作。
  - `Studio` 的“当前成品摘要”补强为可工作状态，能看到当前文件、任务、状态、阶段、来源音色，并可直接下载当前成品。
  - 新增了 Stage 23 专用浏览器 smoke，并已通过。
  - `python -m pytest -q` 与 `python -X utf8 backend/self_check.py` 继续通过。
- 部分完成：
  - `Studio` 右侧试听品库仍然是“全局已完成 cover 池”，本轮只是让从 `Factory` 进入时优先围绕来源 job 工作，没有把整套资源库改造成按 `track` 隔离的资产系统。
- 未完成：
  - 暂无阻塞项。

## 修改文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\playwright_factory_to_studio_context_smoke.cjs`
- `D:\FeiSharkStudio-v2\tests\api\test_track_jobs_api.py`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-23-factory-studio-context-report.md`

## 功能结果

### 来源上下文卡

- 做了什么：
  - `Studio` 主区顶部新增了 `来源上下文` 卡片。
  - 顶栏新增 `返回 Factory 当前曲目`，卡片内新增 `打开 Factory 曲目位`。
- 现在会显示哪些来源信息：
  - 来源 `track` 标题
  - `track_id`
  - 所属 `batch`
  - 当前 `voice_name / voice_model_id`
  - 当前 `job_id`
  - 当前成品状态
  - 当前载入文件名
- `Studio` 如何识别来源 `Factory track`：
  - `Factory` 侧通过 `studio_url` 直接带入：
    - `batch_id`
    - `track_id`
    - `job_id`
    - `artifact_id`
  - `Studio` 侧优先读取 URL 参数。
  - 若普通打开 `/studio` 只有 `job_id`，则通过 `GET /api/jobs/{job_id}` 返回的新字段补全：
    - `track_id`
    - `track_title`
    - `track_artist`
    - `batch_id`
    - `batch_name`
    - `factory_url`
- 从普通 `/studio` 进入时如何兼容：
  - 如果没有 `track_id` 来源，`Studio` 仍按原有“全局已完成 cover 成品池”兼容工作。
  - 上下文卡会显示“当前不是从 Factory 曲目位进入”，不会让页面报错或空白。

### 返回链路

- `返回 Factory 当前曲目` 如何实现：
  - `backend/main.py` 的 `GET /api/jobs/{job_id}` 补充 `factory_url`。
  - `frontend/js/studio.js` 里的 `resolveFactoryContext()` 会优先从 job detail 或 URL 中解析 `batch_id + track_id`，统一生成 `/factory?batch_id=...&track_id=...`。
  - `studioFactoryBackBtn` 和 `studioFactoryOpenBtn` 共用这条链接。
- 使用了哪些 URL 参数或接口字段：
  - URL 参数：
    - `batch_id`
    - `track_id`
    - `job_id`
    - `artifact_id`
  - 新增 / 补充的接口字段：
    - `JobResponse.track_id`
    - `JobResponse.track_title`
    - `JobResponse.track_artist`
    - `JobResponse.batch_id`
    - `JobResponse.batch_name`
    - `JobResponse.factory_url`
    - `track_service` 侧 `studio_url`
- 是否能回到对应 `batch_id + track_id`：
  - 能。
  - 本轮专用 smoke 已校验 `Studio` 内返回链接实际包含原始 `batch_id` 和 `track_id`。

### 当前成品摘要区

- 补强了哪些信息：
  - 当前成品文件名
  - 当前任务状态 pill
  - 当前阶段 pill
  - 一句产品化摘要，明确说明“当前正围绕哪一个任务的最终成品继续工作”
  - 来源任务
  - 来源音色
- 复用了哪些已有接口或字段：
  - `GET /api/jobs/{job_id}`
  - `GET /api/jobs/{job_id}/artifacts`
  - 既有 artifact `download_url`
- 哪些动作可直接执行：
  - `下载当前成品`
  - `返回 Factory 当前曲目`
  - `打开 Factory 曲目位`
- 额外修正：
  - `Studio` 资源刷新逻辑改为优先保住 URL 中传入的 `job_id`。
  - 即使该来源 job 没有出现在当前全局试听品池里，也会继续加载它，并把它临时注入当前页的快速选择列表，避免刚从 `Factory` 跳进来就被别的成品抢走焦点。

### 测试

- 新增或更新了哪些测试：
  - 新增：
    - `D:\FeiSharkStudio-v2\frontend\playwright_factory_to_studio_context_smoke.cjs`
  - 更新：
    - `D:\FeiSharkStudio-v2\tests\api\test_track_jobs_api.py`
- 哪些回归点被覆盖：
  - `Factory` 打开与基础流程
  - `Factory track -> cover job -> Studio` 跳转链
  - `Studio` 顶部来源上下文卡是否出现
  - `Studio` 返回 `Factory` 当前曲目位链接是否精确
  - `Studio` 当前成品摘要区是否围绕正确 job 渲染
  - `Dashboard / Studio / Factory` 既有页面回归

## 验证结果

逐条列出实际执行过的命令和结果：

```text
python -m pytest -q
结果：
9 passed, 2 warnings in 2.00s

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
```

## 风险与限制

- 还没做完的点：
  - `Studio` 右侧“试听品库”仍然是全局已完成 `cover` 资源池，不是按 `Factory batch / track` 做的独立资产库。
- 暂时保留的技术债：
  - 当前只补了“来源上下文 + 返回链路 + 当前成品摘要”，没有继续扩展真实后处理版本管理。
  - `Studio` 仍以轮询 / 静态加载为主，不引入 WebSocket / SSE。
  - 当前成品摘要区保留“下载当前成品”，没有新增直接打开本地目录动作，避免引入新的桌面安全面。
- 需要架构师复查的点：
  - 后续如果要把 `Studio` 继续做成更强的单曲工作位，可能需要明确：
    - 是否引入“按 track 聚焦的成品历史”
    - 是否为 `Factory / Studio` 共用一个更正式的成品资产层

## 交接说明

下一轮继续前，优先关注：

- 如果继续增强 `Studio`，优先补“当前来源 track 的成品历史”和“轻量版本备注”，不要急着上完整 DAW。
- 如果继续增强 `Factory`，优先让 `track` 与成品之间的关系在右侧详情里更稳定、更可追踪。
- 保持本轮确定下来的承接方式：
  - `Factory` 通过 `studio_url` 带入 `batch_id + track_id + job_id + artifact_id`
  - `Studio` 通过 URL 与 `GET /api/jobs/{job_id}` 双通路恢复来源上下文
  - 不新造第二套路由体系，不改 `cover / train` 主链
