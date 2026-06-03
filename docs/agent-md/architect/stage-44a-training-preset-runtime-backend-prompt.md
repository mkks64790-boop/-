# Stage 44A：训练调参台接管真实训练契约（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本阶段目标是让训练调参台的 preset/config 真正进入训练任务契约，并被训练策略读取。默认禁止启动 `train.py`，禁止长训练，禁止改动 `D:\RVC\RVCv2` 文件。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-44-training-preset-runtime-takeover-plan.md
D:\FeiSharkStudio-v2\backend\main.py
D:\FeiSharkStudio-v2\backend\services\training_tuning_service.py
D:\FeiSharkStudio-v2\backend\strategies\train_single_long_strategy.py
D:\FeiSharkStudio-v2\backend\strategies\train_multi_clean_strategy.py
D:\FeiSharkStudio-v2\backend\model_trainer.py
D:\FeiSharkStudio-v2\backend\services\job_service.py
```

## 必做任务

### 1. 训练配置标准化

定义统一 training config，建议字段：

```json
{
  "preset_key": "balanced",
  "epochs": 90,
  "batch_size": 8,
  "sample_rate": "40k",
  "f0_enabled": true,
  "index_enabled": true,
  "pitch_guidance": "default",
  "created_by": "training_tuning_v0"
}
```

要求：

- 配置来源可以是 preset，也可以是前端传入的覆盖值。
- 必须做边界校验和安全钳制。
- 不允许 epochs/batch 为空或乱传字符串。
- 不允许 sample_rate 传入 RVC 不支持的值。
- 默认值必须保持现有训练行为尽量不变。

### 2. 训练创建接口接收 training_config

对现有训练创建入口进行兼容增强：

- 单文件训练可以接收 `training_config`。
- 多文件训练可以接收 `training_config`。
- 若前端不传，自动使用 `balanced`。
- 写入 job `metadata_json`。
- `GET /api/jobs/{job_id}` 返回训练配置摘要。

不要破坏旧请求。

### 3. 训练策略读取 training_config

更新：

```text
train_single_long_strategy.py
train_multi_clean_strategy.py
model_trainer.py
```

要求：

- RVC train command 的 epochs / batch_size / sample_rate / f0 / index 开关来自 training_config。
- 如果 config 不合法，回退到安全默认，并在 job metadata / stage log 中写明。
- `index_enabled=false` 时不得强行生成 index；但默认仍为 true。
- 不要改变 checkpoint recovery 逻辑。

### 4. 新增 dry-run 训练契约脚本

新增：

```text
backend/verify_stage44_training_preset_runtime_contract.py
```

默认不启动训练：

```powershell
python backend\verify_stage44_training_preset_runtime_contract.py
```

验收项：

- `GET /api/training/presets` 可用。
- 创建一个 smoke/dry-run 训练配置，不启动 `train.py`。
- 训练 job metadata 能看到 preset/config。
- 训练命令构建函数能返回预期 epochs/batch/sample_rate/f0/index 参数。
- 若有 `--execute-smoke`，必须只允许短样本，并在报告中明确是否启动 train.py。

### 5. 测试

新增或扩展测试：

```text
tests/api/test_stage44_training_preset_runtime_api.py
```

覆盖：

- 不传 config 使用 balanced。
- fast_preview / quality 可被保存。
- 非法 epochs/batch 被拒绝或钳制。
- sample_rate 非法被拒绝。
- 训练命令参数映射正确。
- 默认 dry-run 不启动 train.py。

## 禁止事项

```text
禁止默认启动 train.py。
禁止跑长训练。
禁止改动 D:\RVC\RVCv2 文件。
禁止破坏 Stage43 Studio 入口契约。
禁止让前端旧请求失效。
```

## 必测

```powershell
python -m pytest -q
python -m backend.self_check
python backend\verify_stage43_studio_entry_contract.py
python backend\verify_stage44_training_preset_runtime_contract.py
python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/training/presets').json())"
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-44a-training-preset-runtime-backend-report.md
```

报告必须包含：

```text
是否完成
修改文件清单
training_config 契约
训练创建接口兼容结果
训练命令参数映射结果
是否启动 train.py：默认必须为否
测试结果
遗留风险
```
