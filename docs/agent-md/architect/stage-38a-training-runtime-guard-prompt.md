# Stage 38A：训练运行时护栏修复（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本阶段只做后端、契约、测试和轻量自检，不做 UI 美化。目标是修掉真实训练暴露出来的运行时地基问题：1 小时超时误杀、同一 job 重复派发、任务汇总统计错误、错误信息不可读、checkpoint 无法恢复登记。

## 启动前必须阅读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-38-training-failure-web-audit.md
D:\FeiSharkStudio-v2\backend\model_trainer.py
D:\FeiSharkStudio-v2\backend\services\job_service.py
D:\FeiSharkStudio-v2\backend\services\stage_log_service.py
D:\FeiSharkStudio-v2\backend\strategies\train_single_long_strategy.py
D:\FeiSharkStudio-v2\backend\strategies\train_multi_clean_strategy.py
D:\FeiSharkStudio-v2\backend\main.py
D:\FeiSharkStudio-v2\backend\db.py
```

## 当前事故事实

真实任务：

```text
job_id = train_010253ec08f0
strategy_key = single_long_preprocess
exp_name_1 = feishark_v_62f76886
exp_name_2 = feishark_v_2860bda4
```

失败根因：

```text
backend/model_trainer.py 默认 FEISHARK_RVC_TRAIN_TIMEOUT = 3600。
150 epoch / batch 8 / 45 分钟素材在 1 小时内没有完成，被 subprocess timeout 判失败。
```

连带问题：

```text
同一 job 又启动了第二个 exp_name，说明恢复/重复派发护栏不足。
/api/jobs/summary 显示 completed_count = 0，但任务列表里有完成任务，说明状态归一化不完整。
失败日志把完整 command / warning 塞进 status message，前端无法可靠展示。
```

## 禁止事项

- 禁止启动真实 RVC 训练。
- 禁止删除 `D:\RVC\RVCv2\logs\feishark_v_62f76886`。
- 禁止删除 `D:\RVC\RVCv2\assets\weights\feishark_v_62f76886_e90_s6300.pth`。
- 禁止杀 RVC WebUI：`http://127.0.0.1:7866`。
- 禁止为了测试长训练而占用 GPU。

## 必做任务

### 1. 修正训练核心超时策略

在 `backend/model_trainer.py` 中重构训练超时配置：

```text
默认 FEISHARK_RVC_TRAIN_TIMEOUT 不得再是 3600。
建议默认改为 21600 秒（6 小时），并允许环境变量覆盖。
```

要求：

- timeout 文案必须明确是“训练超过后端保护时限”，不要伪装成 RVC 崩溃。
- TimeoutExpired 要返回结构化错误码，例如 `train_core_timeout`。
- 错误 detail 中保留 `exp_name`、`timeout_seconds`、`command_preview`、`checkpoint_hint`。
- 不要把整段 stdout/stderr 全塞进 `jobs.error_log` 和 `job_stage_logs.message`。

### 2. 修同一 job 重复派发护栏

查清 `_run_job`、`reserve_job`、`release_job`、启动恢复逻辑之间为什么同一个 `train_010253ec08f0` 会生成两个 exp：

```text
feishark_v_62f76886
feishark_v_2860bda4
```

必须补护栏：

- 同一个 `job_id` 在 `train_core` 未终态时，不允许再次进入策略执行。
- `retry/requeue` 只能对终态任务生效。
- 如果任务已有 `train_core started` 且没有 terminal log，不允许自动恢复重复派发，除非先确认没有对应 RVC 训练进程。
- 将当前 run 的 `exp_name` 写入 job metadata 或 stage detail，后续阶段必须复用，不要每次策略执行重新生成新 exp。

### 3. 修 `/api/jobs/summary` 状态归一化

当前 `/api/jobs/summary` 返回：

```json
{
  "pending_count": 2,
  "processing_count": 0,
  "failed_count": 49,
  "completed_count": 0
}
```

但任务列表里存在大量完成任务。必须修：

- 统一识别 `完成`、`已完成`、`completed`。
- 统一识别 `失败`、`failed`。
- 统一识别 `已取消`、`cancelled`。
- 统一识别 `训练中`、`处理中`、`running`、`processing`。
- smoke 过滤逻辑不能误伤真实任务。

### 4. 增加训练错误摘要器

新增或改造一个后端函数，将底层异常压缩为产品可读字段：

```json
{
  "error_code": "train_core_timeout",
  "error_title": "核心训练超过后端保护时限",
  "error_summary": "RVC 核心训练运行超过 21600 秒，任务已停止等待人工处理。",
  "raw_error_preview": "...最多 500 字...",
  "exp_name": "feishark_v_62f76886",
  "checkpoint_hint": "检测到 e90 checkpoint，可在修复后继续索引/登记。"
}
```

要求：

- API 不破坏旧字段。
- `GET /api/jobs/{job_id}` 可以返回新增摘要字段。
- `GET /api/jobs/{job_id}/stage-logs` 可以保留原文，但 message 不应再用超长 warning 当摘要。

### 5. 增加 checkpoint 恢复/登记预备能力

不要本阶段直接自动登记旧模型，但要为下一步留接口或服务函数：

```text
扫描指定 exp_name 是否存在可用 checkpoint。
返回最高 epoch 的 .pth、G/D 权重、特征目录、是否可构建 index。
```

建议服务函数：

```text
inspect_training_checkpoint(exp_name) -> dict
```

后续阶段会用它做“从 e90 checkpoint 继续 index/register”。

### 6. 增加后端单实例/启动器护栏检查

本次事故中曾看到两组后端启动命令痕迹：

```text
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

虽然最终只有一个 PID 监听 8000，但多次启动会让恢复逻辑、后台任务和用户判断变乱。请检查启动器或后端启动流程：

- 如果 8000 已被当前项目后端占用，不要再启动第二个后端。
- 如果 8000 被无关进程占用，给出清晰错误，不要静默继续。
- 启动恢复逻辑只应由实际监听中的后端实例执行。
- 报告中写明是否发现启动器层面需要后续继续修。

## 必测项

优先跑轻量测试，不要占 GPU：

```powershell
python -m pytest -q
python -m backend.self_check
```

如果 `self_check` 因外部 RVC 或历史脏任务失败，要在报告中明确区分“外部环境失败”和“本阶段回归失败”。

新增/补充测试建议：

- `job_summary` 对 `完成/已完成/completed` 计数正确。
- `job_summary` 对 `失败/failed` 计数正确。
- `train_core_timeout` 被压缩成结构化错误摘要。
- 同一 active job 不能重复 dispatch。
- `inspect_training_checkpoint("feishark_v_62f76886")` 能识别已有 checkpoint，但不自动登记。

## 完成后写报告

使用：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-38a-training-runtime-guard-report-template.md
```
