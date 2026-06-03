# Stage 40A：真实 checkpoint 恢复登记 + 模型可用契约（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本阶段是一个大任务：把 `train_010253ec08f0` 的 e90 checkpoint 真正恢复登记为模型库可用模型，并补齐可重复验收脚本。禁止启动核心训练 `train.py`，禁止删除 RVC 日志和权重。

## 启动前必须阅读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-40-real-recovery-product-closure-plan.md
D:\FeiSharkStudio-v2\backend\services\training_recovery_service.py
D:\FeiSharkStudio-v2\backend\services\training_runtime_guard.py
D:\FeiSharkStudio-v2\backend\model_trainer.py
D:\FeiSharkStudio-v2\backend\main.py
D:\FeiSharkStudio-v2\backend\services\model_service.py
D:\FeiSharkStudio-v2\backend\services\asset_service.py
```

## 必做任务

### 1. 真实恢复前安全闸

执行真实恢复前必须检查：

```text
GET /api/jobs/train_010253ec08f0/training-recovery
recommended_exp_name 必须是 feishark_v_62f76886
highest_epoch 必须是 90
dry_run=true 必须成功
当前不能存在 infer\modules\train\train.py 进程
```

如果任一条件不满足，停止并在报告中写明，不要继续。

### 2. 执行一次真实 checkpoint recovery

允许执行：

```text
POST /api/jobs/train_010253ec08f0/training-recovery/register
```

建议请求：

```json
{
  "exp_name": "feishark_v_62f76886",
  "model_name": "朱朱_recovered_e90",
  "build_index_if_missing": true,
  "dry_run": false
}
```

要求：

- 不启动核心训练。
- 如 index 缺失，允许构建 index。
- 生成并登记 `.pth/.index`。
- job_artifacts 写入 `train_model_pth` 和 `train_model_index`。
- voice_models 写入恢复模型。
- 原 job metadata 写入 recovery 信息。

### 3. 修正/增强恢复登记的健壮性

检查并修复以下风险：

- 如果目标 `model_name` 已存在，必须避免覆盖，自动追加安全后缀或返回明确错误。
- 如果 index 构建失败，不得登记半成品模型。
- 如果 `.index` 是空壳或过小，必须拒绝登记。
- 恢复成功后 `GET /api/models` 必须显示模型 `usable=true`。
- `GET /api/jobs/{job_id}` 应该能显示 `generated_model_id` 或 recovery 相关模型信息。

### 4. 增加可重复验收脚本

新增建议脚本：

```text
backend/verify_stage40_recovered_model_closure.py
```

脚本必须默认安全：

```text
默认只做 dry-run 和读检查。
只有传入 --execute 才执行真实恢复。
```

脚本验收内容：

- recovery candidate 推荐 e90。
- dry_run 成功。
- execute 后模型入库。
- pth/index 文件存在且非空。
- job_artifacts 有最终产物。
- `/api/models` 里恢复模型 usable。
- cover preflight 对恢复模型通过。

### 5. 测试

必须跑：

```powershell
python -m pytest -q tests/unit/test_training_runtime_guard.py tests/unit/test_training_recovery_service.py
python -m pytest -q
python -m backend.self_check
```

如果执行了真实恢复，再额外跑：

```powershell
python backend\verify_stage40_recovered_model_closure.py
python backend\verify_stage40_recovered_model_closure.py --execute
```

## 完成后写报告

使用：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-40a-real-checkpoint-recovery-and-model-contract-report-template.md
```

## 本大任务对当前阶段的好处

```text
把“训练失败”转化成“模型可用”，避免重新烧 1 小时 GPU。
验证训练主链的最后两步：index 和 model register。
为后续一键翻唱提供真实用户音色，而不是只停留在测试模型。
给项目建立可重复的 checkpoint 灾难恢复能力。
```

