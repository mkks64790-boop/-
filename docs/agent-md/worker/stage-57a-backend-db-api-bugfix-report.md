# Stage57A 后端接口/数据库 Bugfix 报告

## 结论

已在允许范围内完成一组最小修复，覆盖后端运行时漂移提示、jobs/tasks 状态规范化同步、job_artifacts 重复登记契约、final artifact Studio/download URL 稳定性。未改前端，未触碰 `D:\RVC\RVCv2` 或 `D:\AudioPipeline`，未运行训练、RVC、UVR 长任务，未下载素材。

当前状态：代码与新增 API 回归测试已落盘，验证命令尚未完成执行。

## 发现的 Bug

1. `/api/health` 和 `/api/diagnostics/summary` 只返回普通健康信息，缺少当前进程加载的 `backend/main.py` 源码签名、路由签名和重启提示；live 8000 如果加载旧代码，前端/主控不容易判断是否需要重启。

2. jobs/tasks 状态契约不一致：`list_jobs(status=...)` 使用原始字符串精确过滤，`retry/requeue/cancel` 也只认部分中文状态，导致 `failed/completed/cancelled/queued` 等英文或历史状态漏查、不可控或 current_stage 残留。

3. `update_task_status()` 对终态同步不够稳定：`failed/cancelled/completed` 的 `current_stage` 可能保留 `pending` 或无明确终态，影响 `/api/jobs/{job_id}`、observer、summary 这类读接口判断。

4. `register_job_artifact()` 命中同一 `job_id/stage_name/artifact_type/file_path` 时直接返回旧 `artifact_id`，不会更新 `file_size/is_final/metadata_json`；如果首次非 final、后续 final，会导致 final artifact 缺失或下载/Studio 契约不稳定。

5. Studio/review URL 参数手写拼接，遇到空格、`+` 等特殊字符时不稳定。

6. 工作区存在 `backend/feishark.db-shm` 和 `backend/feishark.db-wal` 未跟踪文件。它们属于 SQLite WAL 临时文件，应进入 `.gitignore`；但 `.gitignore` 不在本 agent 允许写入范围内，因此未直接修改，需报告主控处理。

## 已修内容

1. `backend/main.py`

增加运行时源码契约：`loaded_source/current_source/route_signature/needs_restart/restart_hint`，并挂到 `/api/health` 与 `/api/diagnostics/summary`。`_build_studio_entry_contract()` 改用 `normalize_job_status()` 判断 completed，并使用 `urlencode()` 构造 `studio_url`。

2. `backend/services/job_service.py`

新增/复用状态规范化：`pending/completed/failed/cancelled/processing`。`canonical_current_stage()`、`list_jobs(status=...)`、`job_summary()`、`retry_job()`、`requeue_job()`、`cancel_job()` 改为按规范化状态判断，避免中文/英文状态漂移。`current_stage='pending'` 不再覆盖终态显示。

3. `backend/db.py`

新增本地 `_normalize_status()`，避免从 service 反向导入。`update_task_status()` 现在对 `cancelled/failed/completed` 明确同步 `current_stage` 与 `error_log`，并按规范化终态触发生命周期清理调度。

4. `backend/services/asset_service.py`

`register_job_artifact()` 命中已有 artifact 时会更新 `file_size`、提升 `is_final`、合并 metadata，并保留已有 `listening_review` 等 metadata 字段。review artifact 的 `studio_url` 改为 `urlencode()`。

5. `tests/api/test_stage57_backend_contracts_api.py`

新增 API 回归测试，覆盖 health/diagnostics 运行时签名、状态过滤与控制规范化、重复 artifact final 更新与 review 保留、Studio/download URL 契约。

## 未修/待主控处理

1. 未修改 `.gitignore`。建议主控加入：

```gitignore
backend/feishark.db-shm
backend/feishark.db-wal
```

2. 未改前端、未改音频管线、未改 RVC/UVR 外部目录。

3. `retry/requeue` 的产品语义仍是“置回 pending 后请求队列调度”；这不是训练误启动修复点。已通过状态规范化降低错误对象被 retry/requeue 的风险。是否需要“retry/requeue 只入队不自动尝试调度”属于产品契约变更，未做。

## 验证结果

截至本报告首次落盘，验证尚未完成执行。

计划执行但尚未完成：

```powershell
python -m py_compile backend/main.py backend/db.py backend/services/job_service.py backend/services/asset_service.py
python -m pytest tests/api/test_stage55_training_observer_api.py tests/api/test_stage54_training_gpu_api.py -q
python -m pytest tests/api/test_stage57_backend_contracts_api.py -q
```

## 风险

1. 当前工作区已有大量未提交改动，本 agent 只在允许范围内编辑；`backend/main.py`、`backend/db.py` 等文件本身已有其他阶段改动，最终集成仍需主控确认。

2. `update_task_status(completed)` 现在在缺省阶段下写入 `cover_mix/train_register_model`，这对读接口更稳定，但如果未来有新的 job_type，需要扩展默认阶段映射。

3. 新增测试尚未执行，可能暴露现有 fixture 或编码历史状态兼容问题；如验证失败，应仅在本报告和允许文件内做最小修正。
