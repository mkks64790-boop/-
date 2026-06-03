# Stage 39 checkpoint 恢复登记计划

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## Stage 38 验收结论

Stage 38A/38B 主体验收通过：

```text
python -m py_compile backend\services\training_runtime_guard.py backend\model_trainer.py backend\services\job_service.py backend\db.py backend\main.py backend\strategies\train_single_long_strategy.py backend\strategies\train_multi_clean_strategy.py
python -m pytest -q tests/unit/test_training_runtime_guard.py
python -m pytest -q
python -m backend.self_check
node --check frontend\playwright_stage38b_training_failure_ux_smoke.cjs
node frontend\playwright_stage38b_training_failure_ux_smoke.cjs
```

结果：

```text
Stage 38A unit: 6 passed
Full pytest: 45 passed
self_check: PASS
Stage 38B browser smoke: PASS
```

已重启后端，当前监听：

```text
8000 -> PID 29328
7866 -> PID 3292
```

实时 `/api/jobs/summary` 已修正：

```json
{
  "pending_count": 2,
  "processing_count": 0,
  "failed_count": 49,
  "completed_count": 25,
  "cancelled_count": 12,
  "cover_count": 56,
  "train_count": 36
}
```

## Stage 38 遗留问题

`GET /api/jobs/train_010253ec08f0` 现在能返回 `checkpoint_inspection`，但它选中了最新重复实验：

```text
feishark_v_2860bda4 -> e10
```

更有价值的可恢复实验其实是：

```text
feishark_v_62f76886 -> e90
```

确认存在：

```text
D:\RVC\RVCv2\assets\weights\feishark_v_62f76886_e90_s6300.pth
D:\RVC\RVCv2\logs\feishark_v_62f76886\G_2333333.pth
D:\RVC\RVCv2\logs\feishark_v_62f76886\D_2333333.pth
D:\RVC\RVCv2\logs\feishark_v_62f76886\3_feature768
feature_count = 552
index_feasible = true
```

## Stage 39 目标

不要重新训练。目标是把已有 e90 checkpoint 补齐 index/register，登记成可用于翻唱的模型。

执行顺序：

```text
1. 地基 Agent 先做 Stage 39A：checkpoint recovery API + 登记能力。
2. 产品 Agent 再做 Stage 39B：失败任务详情里的恢复入口和确认动作。
3. 两边都完成后，由架构师验收并决定是否执行一次真实 checkpoint recovery。
```

## 禁止事项

```text
禁止启动 train.py 核心训练。
禁止重新提交真实训练。
禁止删除 feishark_v_62f76886 日志目录。
禁止删除 feishark_v_62f76886_e90_s6300.pth。
禁止自动无确认登记模型。
```

