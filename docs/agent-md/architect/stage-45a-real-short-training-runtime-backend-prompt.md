# Stage 45A：真实短样本训练 runtime smoke（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本阶段目标是验证训练调参契约真的能驱动 RVC 训练 runtime。默认禁止启动 `train.py`；只有显式 `--execute-smoke` 才允许跑真实短训练 smoke。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-45-real-short-training-smoke-plan.md
D:\FeiSharkStudio-v2\backend\verify_stage44_training_preset_runtime_contract.py
D:\FeiSharkStudio-v2\backend\services\training_tuning_service.py
D:\FeiSharkStudio-v2\backend\model_trainer.py
D:\FeiSharkStudio-v2\backend\strategies\train_single_long_strategy.py
D:\FeiSharkStudio-v2\backend\services\training_runtime_guard.py
D:\FeiSharkStudio-v2\backend\main.py
```

## 必做任务

### 1. 新增 Stage45 验证脚本

新增：

```text
backend/verify_stage45_real_short_training_smoke.py
```

默认执行：

```powershell
python backend\verify_stage45_real_short_training_smoke.py
```

默认只做 dry-run：

- 检查 RVC root。
- 检查 train.py。
- 检查 RVC WebUI / local script 环境。
- 检查 GPU/训练互斥锁是否空闲。
- 构造短训练 job 的 training_config。
- 构造命令预览。
- 不启动 train.py。

### 2. 可选真实短训练执行

只有显式运行：

```powershell
python backend\verify_stage45_real_short_training_smoke.py --execute-smoke
```

才允许真实训练。

执行约束：

- 禁止使用 45 分钟训练素材。
- 优先寻找用户桌面 `干声文件` 中的短唱歌干声；若无法定位，使用项目内已有短干声或自动从可用干声裁剪 45-90 秒。
- 如果只能找到长素材，必须裁剪成短样本副本，不能直接使用原长文件。
- 训练配置必须使用 fast_preview 派生 smoke 配置：

```json
{
  "preset_key": "fast_preview",
  "epochs": 1,
  "batch_size": 2,
  "sample_rate": "40k",
  "f0_enabled": true,
  "index_enabled": true,
  "created_by": "stage45_execute_smoke"
}
```

- 超时建议 10-15 分钟。
- 如果 RVC 对超短数据集不支持，必须归类为 `dataset_too_small` 或 `rvc_training_rejected`，不要糊成普通失败。

### 3. 失败分类

新增或复用失败分类：

```text
environment_not_ready
gpu_busy
dataset_not_found
dataset_too_small
rvc_preprocess_failed
rvc_feature_failed
rvc_train_failed
rvc_index_failed
timeout
unknown
```

返回报告必须包含：

```text
job_id
preset_key
epochs
batch_size
sample_rate
f0_enabled
index_enabled
started_train_py
terminal_status
failure_category
next_step
```

### 4. 训练配置传递验收

无论 dry-run 还是 execute，都必须验证：

- job metadata 有 `training_config`。
- stage logs 有 `training_config`。
- RVC train.py 命令包含：

```text
-te
-bs
-sr
-f0
```

- `index_enabled` 能控制 index stage 是否执行。

### 5. 不破坏现有契约

必须继续通过：

```powershell
python backend\verify_stage44_training_preset_runtime_contract.py
python backend\verify_stage43_studio_entry_contract.py
```

## 禁止事项

```text
禁止默认启动 train.py。
禁止直接用 45 分钟长素材。
禁止修改 D:\RVC\RVCv2 文件。
禁止删除训练日志或 checkpoint。
禁止为了通过 smoke 硬编码固定 job_id。
```

## 必测

```powershell
python -m pytest -q
python -m backend.self_check
python backend\verify_stage43_studio_entry_contract.py
python backend\verify_stage44_training_preset_runtime_contract.py
python backend\verify_stage45_real_short_training_smoke.py
```

只有环境空闲并确认安全时才补跑：

```powershell
python backend\verify_stage45_real_short_training_smoke.py --execute-smoke
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-45a-real-short-training-runtime-backend-report.md
```

报告必须包含：

```text
是否完成
修改文件清单
dry-run 结果
是否执行 --execute-smoke
是否启动 train.py
训练配置映射结果
真实短训练结果或阻塞原因
失败分类
测试结果
遗留风险
```
