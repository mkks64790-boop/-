# Stage 44A 训练调参台接管真实训练契约报告

## 是否完成

已完成。

本轮将 Stage 43 的训练调教 preset/config 接入训练任务契约、job metadata、训练策略和 RVC train.py 命令参数预览。默认没有启动 `train.py`，没有跑长训练，没有跑长 cover，没有删除、移动或覆盖 `D:\RVC\RVCv2` 内任何文件。

## 修改文件清单

- `backend/services/training_tuning_service.py`
  - 新增 `normalize_training_config`。
  - 新增训练配置边界校验与安全钳制。
  - 新增 `training_config_summary`。
  - 新增 `build_rvc_train_runtime_options`。

- `backend/main.py`
  - `/api/train` 兼容接收 training config：
    - `training_config` JSON
    - `preset_key`
    - `epochs`
    - `batch_size`
    - `sample_rate`
    - `f0_enabled`
    - `index_enabled`
  - 不传 config 时自动使用 `balanced`。
  - 将标准化后的 `training_config` 写入 job `metadata_json`。
  - `TrainResponse` 返回 `training_config` 和 `training_config_summary`。
  - `GET /api/jobs/{job_id}` 返回训练配置摘要。
  - 非法 `sample_rate` 返回 `422 invalid_training_config`。

- `backend/model_trainer.py`
  - 训练 runtime options 从 `training_config` 映射到 RVC 参数。
  - `prepare_single_long_preprocess_dataset` / `prepare_multi_clean_direct_dataset` 支持 `training_config`。
  - `run_training_pitch_extract` / `run_training_core` / `run_training_index` 支持 `training_config`。
  - RVC train.py 命令使用配置中的：
    - `epochs`
    - `batch_size`
    - `sample_rate`
    - `f0_enabled`
  - `index_enabled=false` 时跳过 index 构建，不生成假 index。
  - 新增 `build_training_command_preview`，用于 dry-run 验证命令映射，不启动 train.py。

- `backend/strategies/train_single_long_strategy.py`
  - 从 `job.metadata.training_config` 读取训练配置。
  - 将配置传给 preprocess / pitch / feature / core / index / register。
  - stage log 写入 `training_config`。
  - `index_enabled=false` 时不执行 index stage。

- `backend/strategies/train_multi_clean_strategy.py`
  - 与单文件策略保持一致，读取并传递 `training_config`。
  - `index_enabled=false` 时不执行 index stage。

- `backend/verify_stage44_training_preset_runtime_contract.py`
  - 新增 Stage44 dry-run 验收脚本。
  - 默认不启动训练。
  - 验证 presets、job metadata、命令预览映射。
  - 显式拒绝 `--execute-smoke`，避免本阶段误启动 train.py。

- `tests/api/test_stage44_training_preset_runtime_api.py`
  - 新增 Stage44 API 测试。
  - 覆盖默认 balanced、fast_preview、quality、非法 sample_rate、epochs/batch 钳制、命令映射。

## training_config 契约

标准结构：

```json
{
  "preset_key": "balanced",
  "epochs": 90,
  "batch_size": 8,
  "sample_rate": "40k",
  "f0_enabled": true,
  "index_enabled": true,
  "pitch_guidance": "default",
  "created_by": "training_tuning_v0",
  "warnings": []
}
```

支持 preset：

- `fast_preview`
- `balanced`
- `quality`

边界策略：

- `epochs` 钳制范围：`1..300`
- `batch_size` 钳制范围：`1..32`
- `sample_rate` 允许：`32k / 40k / 48k`
- 非法 `sample_rate` 在 `/api/train` 创建阶段拒绝，返回 `422`
- runtime 读取到历史非法配置时回退到 `balanced` 并加入 warning

## 训练创建接口兼容结果

已兼容旧请求。

- 旧请求不传 config：自动使用 `balanced`
- 新请求可传 `training_config` JSON
- 新请求也可传单独表单字段覆盖：
  - `preset_key`
  - `epochs`
  - `batch_size`
  - `sample_rate`
  - `f0_enabled`
  - `index_enabled`

写入位置：

```text
jobs.metadata_json.training_config
```

任务详情返回：

```text
training_config
training_config_summary
```

## 训练命令参数映射结果

`build_training_command_preview("stage44_preview", config)` 已验证：

输入：

```json
{
  "preset_key": "quality",
  "epochs": 999,
  "batch_size": 0,
  "sample_rate": "48k",
  "f0_enabled": false,
  "index_enabled": false
}
```

输出映射：

```text
epochs -> 300
batch_size -> 1
sample_rate -> 48k
f0_enabled -> false
index_enabled -> false
```

RVC train.py 参数：

```text
-te 300
-bs 1
-sr 48k
-f0 0
```

说明：

- `starts_train_py=false`
- 该函数只构造命令预览，不执行 subprocess。
- 默认 `index_enabled=true` 保持 Stage 11 真实 index 主链。
- 当 `index_enabled=false` 时，不强行构建 index，也不生成空 index 兜底。

## 是否启动 train.py

否。

## 是否修改 D:\RVC\RVCv2

否。

本轮没有执行训练命令，没有写入 RVC 目录。

## 测试结果

- `python -m py_compile backend\services\training_tuning_service.py backend\model_trainer.py backend\strategies\train_single_long_strategy.py backend\strategies\train_multi_clean_strategy.py backend\main.py backend\verify_stage44_training_preset_runtime_contract.py`
  - PASS

- `python -m pytest -q tests\api\test_stage44_training_preset_runtime_api.py`
  - PASS，`4 passed`

- `python -m pytest -q`
  - PASS，`59 passed`

- `python -m backend.self_check`
  - PASS
  - `CODE_STRUCTURE_SUMMARY PASS`
  - `RUNTIME_ENVIRONMENT_SUMMARY PASS`
  - `SELF_CHECK_SUMMARY PASS`

- `python backend\verify_stage43_studio_entry_contract.py`
  - PASS

- `python backend\verify_stage44_training_preset_runtime_contract.py`
  - PASS
  - `starts_train_py=False`

- `python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/training/presets').json())"`
  - PASS

## 遗留风险

- 本阶段只做 dry-run / contract 接管，没有执行真实短训练；真实执行应放到 Stage 45，并且只用短样本 smoke。
- `index_enabled=false` 支持 pth-only 登记，但产品层需要明确提示“无 index 可能影响推理质量”；默认仍为 true。
- 当前 sample_rate 允许 `32k / 40k / 48k`，但真实 RVC 安装的 configs/pretrained 是否完整，需要 Stage 45 执行前预检确认。
- `/api/train` 当前仍是表单上传入口，前端 Stage 44B 需要保证配置字段稳定提交并做最终参数确认。
