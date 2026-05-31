# 第24B阶段：Studio Track 历史返工（补做成品历史 + 版本备注 + 专用 smoke）

你现在是 FeiShark Studio 的工作 agent。

本轮不是进入新阶段，而是对第 24 阶段进行返工。

## 返工原因

上一轮第 24 阶段未通过架构验收，原因不是“小瑕疵”，而是核心交付缺失：

1. `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-24-studio-track-history-report.md` 仍是模板空壳，未填写实际结果
2. 要求新增的 `frontend/playwright_studio_track_history_smoke.cjs` 文件不存在
3. `Studio` 当前代码仍停留在第 23 阶段的“来源上下文 + 返回链路 + 当前成品摘要”
4. 没有看到“当前来源 track 的成品历史”区域
5. 没有看到“当前试听 / 最新版本 / 历史版本”标识体系
6. 没有看到“轻量版本备注”能力

所以这一轮不要声称完成，必须把第 24 阶段真正做完。

## 本轮目标

把第 24 阶段的三个核心交付真正落地：

- `Studio` 中出现“当前来源 Track 的成品历史”
- 用户可在这些历史版本间切换试听
- 每个版本具备本机轻量备注能力，并在刷新后恢复

## 必读文件

- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\frontend\playwright_factory_to_studio_context_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-24-studio-track-history-prompt.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-23-factory-studio-context-report.md`

## 任务范围

### 允许修改

- `Studio` 页面结构与样式
- `Studio` 前端数据组织
- 必要时复用 `GET /api/tracks/{track_id}/jobs`
- 本机 `localStorage` 备注能力
- 与本轮直接相关的 smoke / 回归测试
- 本轮汇报文件

### 禁止事项

- 不要新增页面
- 不要改 `cover / train` 执行管线
- 不要上 WebSocket / Redis / Celery
- 不要做真实多轨 DAW
- 不要把全局试听品库删掉

## 必做任务

### 1. 当前来源 Track 的成品历史区

在 `Studio` 中新增一个明确区域，建议标题直接使用：

- `当前曲目成品历史`

要求：

- 仅在存在来源 `track_id` 时显示
- 数据优先复用 `GET /api/tracks/{track_id}/jobs`
- 前端过滤出：
  - `job_kind === "cover"` 或 `job_type === "cover"`
  - 已完成
  - 有可试听成品
- 每条至少展示：
  - `voice_name / voice_model_id`
  - `job_id`
  - 创建时间
  - 当前状态标签
  - `当前试听 / 最新版本 / 历史版本`
- 每条必须可点击切换试听

### 2. 当前试听 / 最新版本 / 历史版本判定

必须实现明确规则，不要写模糊文案：

- `当前试听`
  - `job_id === state.selectedJobId`
- `最新版本`
  - 当前来源 `track` 的已完成 cover 历史中，按 `created_at` 倒序第一条
- `历史版本`
  - 非最新，且不是当前试听的其他完成版本

要求：

- 这三个状态要在 UI 中清晰可见
- 如果当前试听不是最新版本，要在摘要区给出提示

### 3. 轻量版本备注

为当前来源 `track` 的每个版本加入本机备注能力。

要求：

- 备注与 `job_id` 绑定
- 使用 `localStorage`
- 刷新或重新进入 `Studio` 后备注仍在
- 备注区域可以放在：
  - 历史列表项内
  - 或当前成品摘要区内
- 但至少要能编辑并保存当前选中的版本备注

建议 key 形式：

- `feishark_studio_job_note_${jobId}`

### 4. 全局试听品库降级

要求：

- 若存在来源 `track`，优先展示“当前曲目成品历史”
- 全局试听品库继续保留，但放在次级位置
- 不要让全局试听品库压过当前来源 `track` 的工作区

### 5. 专用 smoke 必须补齐

必须新增：

- `D:\FeiSharkStudio-v2\frontend\playwright_studio_track_history_smoke.cjs`

至少验证：

1. 从 `/factory` 进入某个完成态成品的 `Studio`
2. 出现 `当前曲目成品历史`
3. 历史列表可识别 `当前试听 / 最新版本`
4. 给当前版本写一条备注
5. 重新载入后备注仍在
6. 切换到另一条历史版本时，播放器和摘要同步更新

## 验证要求

必须实际执行并写入报告：

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`
- `node frontend/playwright_stage17_smoke.cjs`
- `node frontend/playwright_stage18_smoke.cjs`
- `node frontend/playwright_stage19_smoke.cjs`
- `node frontend/playwright_factory_smoke.cjs`
- `node frontend/playwright_factory_job_bridge_smoke.cjs`
- `node frontend/playwright_factory_auto_refresh_smoke.cjs`
- `node frontend/playwright_factory_to_studio_context_smoke.cjs`
- `node frontend/playwright_studio_track_history_smoke.cjs`

## 交付要求

完成后必须：

1. 把真实结果回填到：
   - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-24b-studio-track-history-rework-report.md`
2. 不要留模板空壳
3. 写清楚：
   - 改了哪些文件
   - 成品历史如何获取
   - 当前试听 / 最新版本如何判定
   - 备注如何存储与恢复
   - 跑了哪些测试
   - 还有哪些限制

## 完成标准

- `Studio` 中确实出现当前来源 `track` 的成品历史
- 可在历史版本之间切换试听
- 当前试听 / 最新版本标识清楚
- 备注刷新后保留
- `playwright_studio_track_history_smoke.cjs` 存在且通过
- 报告不是模板空壳
