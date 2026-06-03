# Stage58A Backend Noise Filter Report

## 发现的问题

- 现有 `smoke_filter.py` 只覆盖 `metadata.smoke/test_scope` 的少量值、`stageXX_single/multi_smoke|probe` 命名、以及旧 `suno_test.wav` fixture，不能稳定识别 `smoke_` 前缀、Playwright、自检、分离评估、通用 stage/test 生成记录。
- `/api/jobs`、`/api/jobs/summary`、`/api/models` 已有 `include_smoke`，但默认隐藏范围仍偏窄，且响应没有给前端解释隐藏数量或测试数据过滤原因。
- 需要避免把真实验收记录误判为测试噪声，尤其是 `stage47_real...`、`stage56_actual...` 这类真实工作流记录。

## 改动文件

- `backend/services/smoke_filter.py`
  - 扩展为通用 test data 识别：`smoke_` 前缀、stageXX + smoke/probe/test/playwright/self_check/separation_eval、metadata 中 `smoke/test_data/playwright/self_check/test_scope/source/generated_by/runner/suite/origin`。
  - 保留 `is_smoke_*` 旧入口作为兼容包装。
  - 新增 `explain_test_data_filter_reason()`，显式包含测试数据时可返回 `filter_reason`。
  - 对 `stageXX_real/actual/acceptance/closure/product` 做真实阶段保护，避免 Stage47/Stage56 真实记录被默认隐藏。
- `backend/services/job_service.py`
  - `list_jobs()` 支持 `include_test_data`，默认过滤测试噪声，显式包含时给测试记录附加 `filter_reason`。
  - 新增 `hidden_test_job_count()`。
  - `job_summary()` 默认排除测试噪声，并返回 `hidden_test_count`、`include_test_data`。
- `backend/services/model_service.py`
  - `list_models()` 支持 `include_test_data`，默认隐藏测试模型，显式包含时附加 `filter_reason`。
- `backend/main.py`
  - `/api/jobs` 增加 `include_test_data` 查询参数，保留 `include_smoke` 兼容，并返回 `hidden_test_count/include_test_data`。
  - `/api/jobs/summary` 增加 `include_test_data` 查询参数，保留 `include_smoke` 兼容。
  - `/api/models` 增加 `include_test_data` 查询参数，保留数组返回契约；由于 `response_model` 会过滤额外字段，补充 `VoiceAssetResponse.filter_reason`。
- `tests/api/test_stage58_user_noise_filter_api.py`
  - 覆盖默认隐藏、显式包含、`filter_reason`、Stage47/Stage56 真实记录保护、stale pending smoke 不污染默认列表、模型列表过滤。

## 验证命令与结果

- `python -m pytest tests\api\test_stage58_user_noise_filter_api.py -q`
  - 结果：`3 passed, 2 warnings`
- `python -m pytest tests\api\test_stage57_backend_contracts_api.py -q`
  - 结果：`3 passed, 2 warnings`
- `python -m pytest tests\api\test_model_registry_lineage_api.py -q`
  - 结果：`2 passed, 2 warnings`

## 未解决风险

- 本轮未改前端，因此前端是否展示 `hidden_test_count/include_test_data/filter_reason` 由其他 worker 接线。
- `/api/models` 为历史数组契约，无法在不破坏契约的情况下返回顶层 `hidden_test_count/include_test_data`；本轮只对显式包含的测试模型提供 item 级 `filter_reason`。
- 工作树已有大量非本轮 dirty/untracked 文件；本轮未回滚或整理其他 agent 改动。
