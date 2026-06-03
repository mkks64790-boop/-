# Stage 37A 执行汇报：训练进度路线图 + 防误关提醒

## 启动检查

- 已读取 `frontend\js\jobs.js`。
- 已读取 `frontend\js\ui.js`。
- 已读取 `frontend\index.html`。
- 已读取 `frontend\css\app.css`。
- 已读取 `backend\strategies\train_single_long_strategy.py`。
- 已读取 `backend\strategies\train_multi_clean_strategy.py`。
- 已读取 `backend\services\stage_log_service.py`。
- 本阶段未修改后端训练执行主链。

## 完成情况

- 已完成：新增训练路线图配置 `TRAIN_STAGE_FLOW`。
- 已完成：Dashboard 任务详情为训练任务新增“训练阶段路线图”。
- 已完成：路线图支持完成、当前、等待、失败状态。
- 已完成：显示阶段进度，例如 `阶段进度 6 / 9`，并明确标注“阶段进度不等于训练 epoch 百分比”。
- 已完成：训练任务下一步文案按 `current_stage` 精确化，不再只显示通用兜底。
- 已完成：`train_core + 训练中` 时显示核心训练防误关提醒。
- 已完成：训练创建成功 toast 增加“不要关闭 RVC / 后端 / 当前训练进程，可到任务详情看路线图”的提示。
- 已完成：任务摘要区显示最近 5 条阶段日志摘要，不展开技术 JSON。
- 已完成：新增前端 smoke `frontend\playwright_stage37a_training_progress_roadmap_smoke.cjs`。

## 修改文件

- `D:\FeiSharkStudio-v2\frontend\js\jobs.js`
- `D:\FeiSharkStudio-v2\frontend\js\train.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\playwright_stage37a_training_progress_roadmap_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-37a-training-progress-roadmap-ux-report.md`

## 训练路线图配置

```text
single_long_preprocess:
train_upload -> train_preflight -> train_dataset_prepare -> train_preprocess -> train_pitch_extract -> train_feature_extract -> train_core -> train_index -> train_register_model

multi_clean_direct:
train_upload -> train_preflight -> train_dataset_prepare -> train_direct_prepare -> train_pitch_extract -> train_feature_extract -> train_core -> train_index -> train_register_model
```

未知 `strategy_key` 时：
- 如果 stage logs 中出现 `train_direct_prepare`，按 `multi_clean_direct` 渲染。
- 否则按 `single_long_preprocess` 兜底。

## UI 行为

- 进行中训练任务：摘要卡片显示路线类型、当前阶段、阶段进度、阶段卡片状态和最近阶段日志。
- 核心训练阶段：显示“核心训练是最长阶段，可能长时间停在这里”的防误关提醒。
- 完成训练任务：路线图全链路标为完成态，下一步提示去模型库查看生成模型或送入 AI 翻唱。
- 失败训练任务：失败阶段标红，下一步提示查看技术详情错误原文，并确认 RVC 训练窗口是否报错后再重试。
- 训练创建成功：toast 提醒核心训练阶段可能较久，不要关闭 RVC / 后端 / 当前训练进程。

## 卡住判断提醒文案

```text
核心训练是最长阶段，可能长时间停在这里。
只要 RVC 训练窗口、CPU/GPU 或 RVC logs 仍在更新，就不是卡死。不要关闭训练进程。

卡住判断：
1. 短时间不跳阶段是正常的。
2. 如果 20-30 分钟没有任何 RVC 日志更新、CPU/GPU 也几乎不动，再怀疑卡住。
3. 如果失败，任务会进入失败态并显示错误摘要。
```

## 验证结果

```text
cmd /c "node -e ""process.stdout.write(require('fs').readFileSync('frontend/js/jobs.js'))"" | node --input-type=module --check"
结果：PASS

cmd /c "node -e ""process.stdout.write(require('fs').readFileSync('frontend/js/train.js'))"" | node --input-type=module --check"
结果：PASS

node --check frontend\playwright_stage37a_training_progress_roadmap_smoke.cjs
结果：PASS

node frontend\playwright_stage37a_training_progress_roadmap_smoke.cjs
结果：PASS
job_id=train_010253ec08f0
current_stage=train_core
status=训练中
route=single_long_preprocess
step_count=9

node frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs
结果：PASS
dashboard_screenshot=D:\FeiSharkStudio-v2\stage33a_dashboard_guard.png
factory_screenshot=D:\FeiSharkStudio-v2\stage33a_factory_guard.png

node frontend\playwright_stage32b_three_page_layout_smoke.cjs
结果：PASS
dashboard_screenshot=D:\FeiSharkStudio-v2\stage32b_dashboard_layout.png
factory_screenshot=D:\FeiSharkStudio-v2\stage32b_factory_layout.png
studio_screenshot=D:\FeiSharkStudio-v2\stage32b_studio_layout.png

python -m pytest -q
结果：PASS，39 passed, 2 warnings in 7.07s

python -X utf8 backend\self_check.py
结果：PASS
CODE_STRUCTURE_SUMMARY PASS
RUNTIME_ENVIRONMENT_SUMMARY PASS
SELF_CHECK_SUMMARY PASS
```

补充：`stage33a_ui_hotfix_guard_smoke` 首次运行时本地 8000 服务不可连接，重启 uvicorn 后复跑通过；最终结果以复跑 PASS 为准。

## 风险与限制

- UI 只展示阶段级路线图，不伪造 epoch 百分比。
- 前端不读取本机 RVC log 文件更新时间，只给用户“如何判断是否卡住”的提醒。
- 核心训练仍可能长时间停留在 `train_core`，这是正常训练阶段，不应被 UI 误导成卡死。
- 完整阶段日志仍保留在原阶段日志抽屉中，摘要区只展示最近 5 条。

## 交接说明

- Stage 37A 可以进入验收。
- 后续阶段如果要做更细粒度训练进度，必须接入真实训练后端指标或日志合同后再展示，不能用前端假百分比。
