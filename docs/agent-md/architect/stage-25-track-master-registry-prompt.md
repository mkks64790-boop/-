# 第25阶段：Track 主成品注册（Current Master）+ Factory / Studio 双端联动

你现在是 FeiShark Studio 的工作 agent。

第 24B 阶段已经通过独立验收：

- `Studio` 已能围绕来源 `track` 展示完成态 cover 历史
- 用户可在历史版本间切换试听
- `当前试听 / 最新版本 / 历史版本` 已能明确区分
- 本机轻量版本备注已可保存并恢复
- `Factory -> Studio` 主链路回归通过

这一轮不要扩新页面，不要上 DAW，不要改执行引擎。

本阶段只做一件事：

把“最新版本”与“真正采用的版本”正式分开，建立每个 `track` 的 `当前主成品（Current Master）` 概念。

也就是说：

- 最新跑完的版本不一定就是最终要用的版本
- 用户可以在 `Studio` 历史版本里，指定某一个版本为当前主成品
- `Factory` 和 `Studio` 都要能清楚显示哪个版本才是当前主成品

## 必读文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\db.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\playwright_studio_track_history_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-24b-studio-track-history-rework-report.md`

## 任务范围

### 允许修改

- `track` 数据模型的轻量扩展
- `Factory` 和 `Studio` 的成品状态展示
- 必要的 API
- 与本轮目标直接相关的 smoke / 回归测试
- 本轮提示词与汇报文件

### 禁止事项

- 不要改 `cover / train` 执行管线
- 不要引入 Redis / WebSocket / Celery
- 不要新建独立页面
- 不要做多人协作权限系统
- 不要把本轮做成重型资产管理后台

## 具体任务

### 1. 为 Track 建立 Current Master 概念

为每个 `track` 正式建立“当前主成品”标识。

建议最小实现：

- 在 `tracks` 表或等价持久层中增加：
  - `current_master_job_id`
- 必要时可同时补：
  - `current_master_artifact_id`

要求：

- 当用户未手动指定时，可以为空
- 空时前端仍能继续用“最新版本”作为默认工作流
- 一旦手动指定，`Factory / Studio` 都必须识别为“当前主成品”

### 2. 新增设置当前主成品 API

新增一个轻量动作接口，建议类似：

- `POST /api/tracks/{track_id}/master`

请求体至少包含：

- `job_id`
- 如有必要可带 `artifact_id`

要求：

- 只能将属于该 `track`、且已完成、且有最终成品的 `cover job` 设为当前主成品
- 成功后记录审计事件，例如：
  - `track_master_set`
- 不要影响原有 job 执行状态

### 3. Factory 显示当前主成品

当前 `Factory` 只知道最近任务和完成态入口。本轮要让它知道“当前主成品是谁”。

要求：

- 在当前 `track` 详情区新增“当前主成品”摘要
- 至少展示：
  - 主成品对应 `voice_name`
  - `job_id`
  - 创建时间
  - `进入 Studio`
  - `下载成品`
- 如果当前主成品为空，则优雅回退：
  - 显示“当前尚未指定主成品”
  - 同时可提示“默认仍按最新完成版本工作”

### 4. Studio 历史中支持“设为当前主成品”

在 `Studio` 的 `当前曲目成品历史` 中，为每个可用版本增加动作：

- `设为当前主成品`

要求：

- 当前已经是主成品的版本，要明确标注：
  - `当前主成品`
- 最新版本与当前主成品可能不是同一个，必须能区分
- 切换主成品后：
  - 历史列表即时更新
  - 摘要区即时更新
  - 返回 `Factory` 后也能看到新主成品

### 5. 明确 3 个不同概念

本轮要把下面三个概念彻底区分清楚：

- `当前试听`
- `最新版本`
- `当前主成品`

要求：

- 这三个标签可以同时出现在同一版本上，也可以分离
- UI 文案必须让用户一眼懂
- 不要再用“最新”去偷换“最终采用”

### 6. 测试补齐

至少完成以下验证：

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`
- `node frontend/playwright_factory_job_bridge_smoke.cjs`
- `node frontend/playwright_factory_to_studio_context_smoke.cjs`
- `node frontend/playwright_studio_track_history_smoke.cjs`

并新增本轮专用 smoke，建议命名：

- `frontend/playwright_track_master_registry_smoke.cjs`

这条 smoke 至少验证：

1. 创建同一 `track` 的两个完成态 cover 版本
2. 进入 `Studio`
3. 将较旧版本设为 `当前主成品`
4. 验证该版本显示 `当前主成品`
5. 验证最新版本仍显示 `最新版本`
6. 回到 `Factory` 后，验证右侧当前主成品摘要已切换到这个较旧版本

## 交付要求

完成后必须输出：

1. 修改了哪些文件
2. `Current Master` 如何持久化
3. 设置主成品的 API 如何工作
4. `当前试听 / 最新版本 / 当前主成品` 如何区分
5. 跑了哪些测试，结果是什么
6. 还剩哪些已知限制
7. 将本轮汇报写入：
   - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-25-track-master-registry-report.md`

## 完成标准

- 每个 `track` 可以手动指定 `当前主成品`
- `Studio` 历史区能设置并展示当前主成品
- `Factory` 能看到当前主成品摘要
- `最新版本` 与 `当前主成品` 清晰分离
- 新增 smoke 能证明跨 `Studio -> Factory` 的主成品联动成立
