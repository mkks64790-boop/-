# Stage 39A：checkpoint 恢复登记能力（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本阶段只做后端、契约和测试。不要启动真实核心训练，不要调用 `train.py`，不要删除 RVC 日志和权重。目标是把 Stage 38 发现的 e90 checkpoint 恢复成模型库可用模型。

## 启动前必须阅读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-39-checkpoint-recovery-plan.md
D:\FeiSharkStudio-v2\backend\services\training_runtime_guard.py
D:\FeiSharkStudio-v2\backend\model_trainer.py
D:\FeiSharkStudio-v2\backend\main.py
D:\FeiSharkStudio-v2\backend\services\job_service.py
D:\FeiSharkStudio-v2\backend\services\asset_service.py
D:\FeiSharkStudio-v2\backend\services\model_service.py
D:\FeiSharkStudio-v2\backend\db.py
```

## 目标接口

### 1. 查询训练恢复候选

新增：

```text
GET /api/jobs/{job_id}/training-recovery
```

返回建议结构：

```json
{
  "job_id": "train_010253ec08f0",
  "can_recover": true,
  "recommended_exp_name": "feishark_v_62f76886",
  "reason": "检测到最高 e90 checkpoint，且特征目录可用于构建 index。",
  "candidates": [
    {
      "exp_name": "feishark_v_62f76886",
      "highest_epoch": 90,
      "highest_pth": "D:\\RVC\\RVCv2\\assets\\weights\\feishark_v_62f76886_e90_s6300.pth",
      "feature_count": 552,
      "index_feasible": true,
      "index_candidates": [],
      "is_recommended": true,
      "score": 90552
    }
  ],
  "warnings": []
}
```

要求：

- 从 job metadata、stage logs、error_log 中收集所有 `feishark_v_*`。
- 对每个 exp 调用 `inspect_training_checkpoint(exp_name)`。
- 推荐最高 `highest_epoch`，再按 `feature_count` 排序。
- 对 `train_010253ec08f0` 必须推荐 `feishark_v_62f76886`，不是 `feishark_v_2860bda4`。

### 2. 执行恢复登记

新增：

```text
POST /api/jobs/{job_id}/training-recovery/register
```

请求体建议：

```json
{
  "exp_name": "feishark_v_62f76886",
  "model_name": "朱朱_recovered_e90",
  "build_index_if_missing": true,
  "dry_run": false
}
```

行为要求：

- 不跑核心训练。
- 如果 index 不存在但 `index_feasible=true`，允许调用现有 `run_training_index(exp_name)` 构建 index。
- 使用恢复出的最高 epoch `.pth` 作为模型权重来源，不要误用 e10 或空壳文件。
- 将 `.pth/.index` 复制到 `shared_data/weights/{model_name}.pth` 和 `shared_data/weights/{model_name}.index`。
- 调用现有模型登记能力写入 `voice_models`。
- 写入 `job_artifacts`：`train_model_pth`、`train_model_index`，`is_final=1`。
- 写入 stage logs，例如：

```text
train_checkpoint_recover started/completed
train_index started/completed
train_register_model started/completed
```

- 恢复成功后，允许将原训练 job 标记为 `完成`，但 metadata 必须写明：

```json
{
  "recovered_from_checkpoint": true,
  "recovered_exp_name": "feishark_v_62f76886",
  "recovered_epoch": 90
}
```

### 3. dry_run

`dry_run=true` 时只能返回计划，不复制、不登记、不改 job 状态。

## 必测项

不启动真实训练。允许 mock `run_training_index`。

必须新增/补测试：

- recovery candidates 对 `train_010253ec08f0` 推荐 e90 的 `feishark_v_62f76886`。
- `dry_run=true` 不改 DB。
- index 缺失但 feature 存在时，会调用 index 构建函数。
- register 成功后 `voice_models` 有新模型。
- `job_artifacts` 有 `train_model_pth` 和 `train_model_index`。
- 原 job metadata 写入 recovery 信息。

验收命令：

```powershell
python -m pytest -q tests/unit/test_training_runtime_guard.py
python -m pytest -q
python -m backend.self_check
```

## 完成后写报告

使用：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-39a-checkpoint-recovery-contract-report-template.md
```

