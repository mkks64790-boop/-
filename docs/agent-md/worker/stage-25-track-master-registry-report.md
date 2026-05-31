# 第25阶段执行汇报：Track 主成品注册（Current Master）Factory / Studio 双端联动

## 完成情况

- 已完成：
  - 为每个 `track` 建立可持久化的 `Current Master` 概念
  - 新增“设置当前主成品”API，并补齐校验与审计
  - Factory 显示“当前主成品”摘要，并与“最新完成版本”分离
  - Studio 历史区支持把旧版本设为“当前主成品”
  - 明确区分 `当前试听 / 最新版本 / 当前主成品`
  - 新增 Stage 25 浏览器 smoke，验证 `Studio -> Factory` 联动
- 未扩张：
  - 没有改 `cover / train` 主执行链
  - 没有引入 Redis / WebSocket / Celery
  - 没有新增独立后台页面

## 修改文件

- `D:\FeiSharkStudio-v2\backend\db.py`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\tests\api\test_track_jobs_api.py`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\playwright_track_master_registry_smoke.cjs`

## 功能结果

### Current Master 持久化

- 做了什么：
  - 在 `tracks` 表新增：
    - `current_master_job_id`
    - `current_master_artifact_id`
  - 保持默认空值，兼容“尚未指定主成品”的现状
- 使用了哪些字段：
  - `tracks.current_master_job_id`
  - `tracks.current_master_artifact_id`
- 空状态如何兼容：
  - 当前端发现 `Current Master` 为空时，仍然按“最新完成版本”作为默认工作流
  - 只有用户在 Studio 手动指定后，Factory / Studio 才会共同把该版本视为正式采用版本

### 设置主成品 API

- 新增接口：
  - `POST /api/tracks/{track_id}/master`
- 请求参数：
  - `job_id`
  - `artifact_id`（可选；如果传入则必须匹配该 job 的最终成品）
- 校验规则：
  - job 必须属于该 `track`
  - job 必须是 `cover` 任务
  - job 必须是已完成状态
  - job 必须存在最终可用成品
  - 如果传了 `artifact_id`，必须和最终成品一致
- 返回内容：
  - `ok`
  - `track_id`
  - `current_master_job_id`
  - `current_master_artifact_id`
  - `current_master`
- 审计记录：
  - 成功切换后写入 `track_master_set`

### Factory / Studio 联动

#### Factory

- 在曲目详情摘要区新增“当前主成品”卡片
- 当未指定主成品时：
  - 显示“当前尚未指定主成品”
  - 明确提示“默认仍按最新完成版本工作”
- 当已指定主成品时：
  - 显示音色 / job_id / 创建时间 / 最终成品
  - 提供 `进入 Studio`、`下载主成品`
  - 如果当前主成品不是最新完成版本，会明确显示“已手动固定”
- 在关联任务列表中，当前主成品版本会带 `当前主成品` tag

#### Studio

- 在“当前曲目成品历史”中，每个完成态版本增加：
  - `设为当前主成品`
- 当前已是主成品的版本：
  - 不再显示设置按钮
  - 直接显示 `当前主成品` tag
- 设置成功后：
  - 历史列表即时刷新
  - 摘要区即时刷新
  - 返回 Factory 后当前主成品卡片同步刷新

### 三种状态区分

- `当前试听`
  - 当前播放器正在试听的版本
- `最新版本`
  - 当前 Track 下最新完成的 cover 版本
- `当前主成品`
  - 当前正式采用的版本，可与“最新版本”不同

现在支持的组合示例：

- 同一个版本同时是：
  - `当前试听 + 最新版本 + 当前主成品`
- 旧版本被正式采用时：
  - 旧版本可显示 `当前试听 + 历史版本 + 当前主成品`
  - 最新版本仍只显示 `最新版本`

## 测试

### 新增或更新的测试

- API 测试：
  - `D:\FeiSharkStudio-v2\tests\api\test_track_jobs_api.py`
  - 新增 `test_track_master_endpoint_sets_current_master_and_marks_job`
- 浏览器 smoke：
  - `D:\FeiSharkStudio-v2\frontend\playwright_track_master_registry_smoke.cjs`

### 覆盖的回归点

- 同一 Track 创建两个完成态 cover 版本
- 在 Studio 把较旧版本设为当前主成品
- 旧版本显示 `当前主成品`
- 最新版本仍显示 `最新版本`
- 返回 Factory 后右侧“当前主成品”摘要正确切换

## 验证结果

```text
python -m pytest -q
结果：PASS（10 passed, 2 warnings）

python -X utf8 backend/self_check.py
结果：PASS（SELF_CHECK_SUMMARY PASS）

node frontend/playwright_factory_job_bridge_smoke.cjs
结果：PASS

node frontend/playwright_factory_to_studio_context_smoke.cjs
结果：PASS

node frontend/playwright_studio_track_history_smoke.cjs
结果：PASS

node frontend/playwright_track_master_registry_smoke.cjs
结果：PASS
```

相关截图：

- `D:\FeiSharkStudio-v2\stage21_factory_bridge.png`
- `D:\FeiSharkStudio-v2\stage23_factory_to_studio_context.png`
- `D:\FeiSharkStudio-v2\stage24b_studio_track_history.png`
- `D:\FeiSharkStudio-v2\stage25_track_master_registry.png`

## 风险与限制

- 当前没有“清空当前主成品”的独立接口；本阶段只支持“指定某个完成版本为当前主成品”
- 当前主成品仍限定为：
  - 属于该 Track
  - 已完成
  - 有最终成品的 `cover job`
- 这仍然是单机、本地流程：
  - 没有多用户抢占处理
  - 没有额外的资产审批流
- 多条真实 cover smoke 并行跑时会争用单机算力槽，因此最终验收以逐条独立通过为准

## 交接说明

- Stage 24B 的“版本历史 + 本机备注”已继续保留
- Stage 25 在此基础上补上“当前主成品”的正式采用语义
- 下一阶段如果继续深化，建议优先考虑：
  - 当前主成品清空 / 回退
  - Track 级导出版本说明
  - Factory 中更细的版本比较摘要
