# Stage54 GPU 训练加速契约与验收报告

## 范围

- 项目根目录：`D:\FeiSharkStudio-v2`
- 目标：不要把未完整质检的朱朱训练结果当作最终模型；先补齐 RVC 训练 GPU 加速可用性探针、训练预检阻断、前端可见提示。
- 边界：本轮不运行朱朱长训练，不运行 UVR/RVC 真实训练，不改第三方 `D:\RVC\RVCv2`，只做探针、契约和验证。

## 子 agent 审计结论

- Kepler 后端审计确认：当前 RVC 训练链已经会在 pitch/feature/train core 阶段传 GPU 参数，但旧 `_has_cuda()` 只看 `nvidia-smi`，不能证明 RVC Python 的 `torch.cuda` 真可用。
- Turing 产品审计确认：数据库里 Stage47 朱朱训练闭环已有可用记录，但用户容易误判，因为训练完成、index 完成、模型登记完成、模型可用于翻唱这四个状态在 UI 里不够集中。

## 已完成修改

- `backend/services/training_gpu_service.py`
  - 新增 GPU 探针服务。
  - 检查 `nvidia-smi`、RVC Python `torch.cuda.is_available()`、`FEISHARK_RVC_GPUS` 选择是否越界。
  - 返回 `starts_train_py=false`，明确不会启动训练脚本。
- `backend/services/preflight_service.py`
  - `/api/preflight/train` 返回 `gpu_status`、`gpu_acceleration_available`、`device_mode`。
  - GPU 不可用会进入 `errors`，从而让 `preflight.ok=false`，阻止长训练入队。
- `backend/main.py`
  - 新增 `GET /api/training/gpu-status`。
  - 扩展 `PreflightResponse`，避免 FastAPI 过滤 GPU 字段。
- `backend/model_trainer.py`
  - `_has_cuda()` 改为优先使用 RVC Python 的 `torch.cuda` 探针，不再只看宿主机 `nvidia-smi`。
- `frontend/js/train.js`
  - 训练预检通过/失败文案显示真实 GPU 加速状态。
  - 提交训练确认弹窗显示 `GPU 加速: 可用/未就绪`。
- `tests/unit/test_training_gpu_service.py`
  - 覆盖 GPU id 解析、CUDA 可用、GPU 编号越界。
- `tests/api/test_stage54_training_gpu_api.py`
  - 覆盖新接口与训练预检 GPU 字段。

## 真实本机探针结果

```json
{
  "ok": true,
  "gpu_acceleration_available": true,
  "device_mode": "cuda",
  "selected_gpus": [0],
  "torch": "2.11.0+cu128",
  "cuda_version": "12.8",
  "devices": ["NVIDIA GeForce RTX 5060"],
  "starts_train_py": false,
  "error_count": 0
}
```

## 临时 HTTP 验证

- 为避免打断当前 `127.0.0.1:8000` 旧后端进程，本轮临时在 `127.0.0.1:8024` 启动新版后端。
- 验证完立刻停止临时进程。

```json
{
  "GpuStatus": true,
  "DeviceMode": "cuda",
  "StartsTrainPy": false,
  "PreflightGpu": true,
  "PreflightOk": true
}
```

## 验收命令

- `python -m py_compile backend/services/training_gpu_service.py backend/services/preflight_service.py backend/model_trainer.py backend/main.py`：通过。
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\train.js','rb').read())"" | node --input-type=module --check"`：通过。
- `python -m pytest -q tests/unit/test_training_gpu_service.py tests/api/test_stage54_training_gpu_api.py tests/unit/test_training_runtime_guard.py tests/api/test_stage44_training_preset_runtime_api.py`：`15 passed`。
- `python -m pytest -q`：`97 passed`。
- `python -m backend.self_check`：`SELF_CHECK_SUMMARY PASS`。

## 当前判断

- 朱朱模型不能直接当最终商业级结果，应继续作为训练链闭环参考和质量基准。
- 当前机器的 RVC Python CUDA 环境可用，后续可以在明确授权时跑短 GPU 训练 smoke，不建议立刻重跑 30-50 分钟朱朱长训练。
- `127.0.0.1:8000` 当前仍是旧进程，浏览器要看到新 GPU 状态接口，需要重启 FeiShark 后端。

## 下一步子 agent 拆分建议

- 后端子 agent：做训练观察合同，补 `current_stage_started_at`、`last_stage_log_at`、`model_registration_status`、`generated_model_usable`、可选 `current_epoch/total_epochs/eta_seconds`。
- 产品子 agent：做 Dashboard 训练观察卡，把“训练中/核心训练/索引/模型登记/可翻唱”集中显示，提交训练后自动聚焦到观察卡。
- QA 子 agent：只在用户明确允许时，跑 1-3 分钟短素材 GPU 训练 smoke，验证 `train_core` 是否真的调用 CUDA；不跑朱朱长训练。
