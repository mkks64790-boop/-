# 第24阶段：Studio 按来源 Track 聚焦的成品历史（轻量版本备注 + 当前版本切换）

你现在是 FeiShark Studio 的工作 agent。

第 23 阶段已经完成并通过独立验收：

- `Factory -> Studio` 已能带入 `batch_id + track_id + job_id + artifact_id`
- `Studio` 已有来源上下文卡
- `Studio` 已有回到 `Factory` 当前曲目位的返回链路
- `Studio` 已有更清晰的当前成品摘要
- `Dashboard / Factory / Studio / cover / train` 回归通过

这一轮不要扩新页面，不要上 DAW，不要改执行引擎。

本阶段只做一件事：

把 `Studio` 从“知道自己从哪个 track 来”再推进一步，变成“围绕这个 track 的成品历史工作”的页面。

也就是说，用户进入 `Studio` 后，不只是看到当前一个成品，而是能围绕当前来源 `track`：

- 看见这个 track 的已完成 cover 历史
- 在这些历史版本之间切换试听
- 给每个版本写轻量备注
- 明确知道当前听的是最新版本还是历史版本

## 必读文件

- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\frontend\playwright_factory_to_studio_context_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-23-factory-studio-context-report.md`

## 任务范围

### 允许修改

- `Studio` 页面的信息结构和交互
- 为 `Studio` 读取当前来源 `track` 的成品历史补充必要的轻量接口消费
- 轻量版本备注能力
- 与本轮目标直接相关的 smoke / 回归测试
- 本轮提示词与汇报文件

### 禁止事项

- 不要新增独立页面
- 不要推翻现有播放器与试听品库
- 不要改 `cover / train` 执行管线
- 不要引入 WebSocket / Redis / Celery
- 不要上重型后处理系统或真实多轨 DAW

## 具体任务

### 1. 当前来源 Track 的成品历史区

当 `Studio` 是从某个 `Factory track` 进入时，在页面中新增一个明确的“当前曲目成品历史”区域。

要求：

- 只展示当前来源 `track` 关联的、已完成的 `cover job`
- 每条至少展示：
  - `voice_name / voice_model_id`
  - `job_id`
  - 创建时间
  - 当前是否为最新版本
  - 当前是否就是正在试听的版本
- 必须能一键切换到该版本试听
- 如果当前不是从 `Factory track` 进入，则优雅降级，不报错

建议实现：

- 直接复用 `GET /api/tracks/{track_id}/jobs`
- 在前端过滤出可试听的完成态 `cover` 项
- 不要新造第二套历史接口，除非确有必要且代价很小

### 2. 最新版本 / 当前版本标识

当前 `Studio` 还缺少一个很重要的产品信号：用户不知道自己听的是不是这个 track 的最新成品。

要求：

- 在当前成品摘要区或历史列表中明确标注：
  - `当前试听`
  - `最新版本`
  - `历史版本`
- 如果当前正在试听的版本不是最新版本，要给出明显但不刺眼的提示

### 3. 轻量版本备注

为每个已完成成品增加一个非常轻的备注能力。

要求：

- 每个版本至少可保存一段短备注，例如：
  - “这个版本齿音更顺”
  - “这个版本适合发 B 站”
- 备注必须在刷新后仍能保留
- 这一轮优先采用低风险方案

建议约束：

- 可以使用 `localStorage`
- key 建议与 `job_id` 或 `artifact_id` 绑定
- 明确这是“本机工作备注”，不是多人共享元数据

### 4. 全局试听品库降级为次要入口

当前 `Studio` 右侧的全局试听品库还保留，但本轮需要把它降为次要入口。

要求：

- 如果存在来源 `track`，优先显示“当前曲目成品历史”
- 全局试听品库保留，但不应压过当前 `track` 的版本工作区
- 不要删掉全局试听品库

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
- `node frontend/playwright_factory_to_studio_context_smoke.cjs`

并新增一条本轮专用 smoke，建议命名：

- `frontend/playwright_studio_track_history_smoke.cjs`

这条 smoke 至少验证：

1. 从 `/factory` 进入一个可回到 `Studio` 的完成态成品
2. `Studio` 中出现“当前曲目成品历史”
3. 历史列表中能识别 `当前试听 / 最新版本`
4. 给当前版本写一条备注
5. 刷新或重新载入后备注仍在
6. 切换到另一条历史版本时，播放器和摘要同步更新

## 交付要求

完成后必须输出：

1. 修改了哪些文件
2. 当前来源 `track` 的成品历史是如何组织的
3. 最新版本 / 当前版本是如何判定的
4. 版本备注如何存储与恢复
5. 跑了哪些测试，结果是什么
6. 还剩哪些已知限制
7. 将本轮汇报写入：
   - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-24-studio-track-history-report.md`

## 完成标准

- 从 `Factory` 进入 `Studio` 后，能看到当前来源 `track` 的完成态成品历史
- 可在历史版本之间切换试听
- 当前版本与最新版本状态明确
- 轻量备注在刷新后仍保留
- 全局试听品库保留，但不再压过当前 `track` 的工作区
