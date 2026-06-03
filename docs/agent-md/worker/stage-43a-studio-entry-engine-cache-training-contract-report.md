# Stage 43A Studio 入口契约 + Engine Manager 收口 + 训练调教契约报告

## 是否完成

已完成。

本轮只做后端契约、轻量验收和安全登记能力；没有启动 `train.py`，没有跑长训练，没有跑长 cover，没有删除、移动或覆盖 `D:\RVC\RVCv2` 内任何文件。

## 修改文件清单

- `backend/main.py`
  - 为 `GET /api/jobs/{job_id}` 增加 Studio 入口字段：
    - `can_open_studio`
    - `final_artifact_id`
    - `final_artifact_download_url`
    - `studio_url`
    - `studio_track_id`
    - `studio_artifact_id`
  - 为 `GET /api/task_status/{job_id}` 增加轻量 Studio 字段：
    - `can_open_studio`
    - `final_artifact_download_url`
    - `studio_url`
  - 新增 `POST /api/models/import-rvc`，只登记外部 RVC 模型到 FeiShark DB，不修改 RVC 文件。
  - 增强 `GET /api/engines/rvc/models` query 参数：
    - `limit`
    - `offset`
    - `q`
    - `registered=true|false|all`
    - `has_index=true|false|all`
    - `force`
  - 增强 `POST /api/engines/scan?force=true` 强制刷新能力。
  - 新增训练调教契约：
    - `GET /api/training/presets`
    - `POST /api/training/estimate`
  - 修复 Windows 测试隔离场景下跨盘 `relpath` 报错问题。

- `backend/services/engine_manager_service.py`
  - 为 RVC 模型扫描增加 TTL 缓存，默认 20 秒。
  - 缓存按 RVC root / weights / indices / logs 路径区分，避免测试或配置切换时串缓存。
  - 支持 RVC 模型分页、搜索、registered 过滤、has_index 过滤。
  - `/api/engines` 保持轻量摘要，完整列表仍由 `/api/engines/rvc/models` 提供。

- `backend/services/training_tuning_service.py`
  - 新增训练调教 v0 只读契约。
  - 提供 `fast_preview`、`balanced`、`quality` 三档预设。
  - 根据素材时长、文件数量和 preset 返回风险/耗时提示，不创建 job。

- `backend/verify_stage43_studio_entry_contract.py`
  - 新增 Stage 43 Studio 入口验收脚本。
  - 默认验证 `task_stage41_ce1b32f2`，不创建新任务。

- `tests/api/test_stage43_contracts_api.py`
  - 新增 API 测试：
    - completed cover job 暴露 Studio 入口字段。
    - RVC models 分页、搜索、过滤。
    - `POST /api/models/import-rvc` 成功、重复、缺文件场景。
    - 训练预设和估算只读契约。

## Studio 入口契约修复结果

已修复。

对已完成 cover job，只有满足以下条件才返回 `can_open_studio=true`：

- `job_type == cover`
- `status` 为完成态
- 存在 final artifact
- artifact 类型为 `cover_master`
- artifact 文件存在且非空

真实验收：

```text
python backend\verify_stage43_studio_entry_contract.py
```

结果：

```text
[STAGE43A][PASS] studio entry contract ok job_id=task_stage41_ce1b32f2 artifact_id=art_718543e5f783 studio_url=/studio?track_id=trk_stage41_cfc34dfd&job_id=task_stage41_ce1b32f2&artifact_id=art_718543e5f783
```

## RVC models 分页/搜索/缓存结果

已完成。

示例命令：

```text
python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/engines/rvc/models?limit=5&offset=0').json())"
```

结果摘要：

```text
engine_key = rvc_webui
status = online
total = 400
limit = 5
offset = 0
items = 5
read_only = true
```

兼容字段：

```text
models = items
model_count = 400
```

缓存说明：

- 默认 TTL：20 秒。
- `POST /api/engines/scan?force=true` 可强制刷新。
- 缓存只影响扫描性能，不修改文件，不改变安全边界。

## 外部 RVC 模型登记 API 结果

已完成。

新增：

```text
POST /api/models/import-rvc
```

安全策略：

- `.pth` 必须存在。
- `.index` 可选；传入时必须存在。
- 同名模型拒绝登记。
- 同路径模型拒绝登记。
- 只写 FeiShark 数据库。
- 不复制、不删除、不移动、不覆盖 `D:\RVC\RVCv2` 文件。

测试覆盖：

- 成功登记临时 RVC 模型。
- 重复模型名返回 `409`。
- 缺失 `.pth` 返回 `422`。

## 训练调教契约结果

已完成。

新增：

```text
GET /api/training/presets
POST /api/training/estimate
```

预设：

- `fast_preview`：快速预览，30 epochs。
- `balanced`：均衡推荐，90 epochs。
- `quality`：高质量慢速，150 epochs。

示例命令：

```text
python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/training/presets').json())"
```

结果：

```text
PASS，返回 fast_preview / balanced / quality 三档预设，read_only=true。
```

`POST /api/training/estimate` 只返回风险提示与参数估算：

```text
submission_creates_job = false
```

## 是否启动 train.py

否。

## 是否修改 D:\RVC\RVCv2

否。

本轮只读扫描 RVC 模型文件；登记 API 只登记数据库，不触碰 RVC 文件。

## 测试结果

- `python -m py_compile backend\services\engine_manager_service.py backend\services\training_tuning_service.py backend\main.py backend\verify_stage43_studio_entry_contract.py`
  - PASS

- `python -m pytest -q tests\api\test_engines_api.py tests\api\test_stage43_contracts_api.py`
  - PASS，`6 passed`

- `python -m pytest -q`
  - PASS，`55 passed`

- `python -m backend.self_check`
  - PASS
  - `CODE_STRUCTURE_SUMMARY PASS`
  - `RUNTIME_ENVIRONMENT_SUMMARY PASS`
  - `SELF_CHECK_SUMMARY PASS`

- `python backend\verify_stage41_recovered_model_cover_smoke.py`
  - PASS
  - `stage41 recovered model cover dry-run PASS`

- `python backend\verify_stage43_studio_entry_contract.py`
  - PASS

- `python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/engines/rvc/models?limit=5&offset=0').json())"`
  - PASS

- `python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/training/presets').json())"`
  - PASS

## 遗留风险

- `/api/engines/rvc/models` 当前仍最多扫描 400 条，虽然已分页返回，但真实全量模型资产治理还需要后续 Stage 做搜索索引/分页扫描增强。
- `POST /api/models/import-rvc` 当前采用“重名拒绝”策略；如果产品层希望自动安全后缀，需要 Stage 43B/44 再确认 UX 语义。
- 训练调教 v0 只是参数预设/风险估算契约，尚未把参数真正接入 RVC 训练命令；真实接管应放到 Stage 44。
- SVC/SVT 仍保持 not_configured 占位，未做真实 runner 适配。
