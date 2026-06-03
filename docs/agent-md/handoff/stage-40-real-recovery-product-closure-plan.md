# Stage 40 真实 checkpoint 恢复与产品闭环计划

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## Stage 39 验收结论

Stage 39A/39B 主体通过。

已验证：

```text
GET /api/jobs/train_010253ec08f0/training-recovery
推荐 feishark_v_62f76886 / e90 / feature_count 552 / index_feasible true
```

dry_run 已验证：

```text
POST /api/jobs/train_010253ec08f0/training-recovery/register
dry_run = true
exp_name = feishark_v_62f76886
model_name = 朱朱_recovered_e90
would_build_index = true
```

真实页面已验证：

```text
Dashboard 任务详情出现 checkpoint 恢复卡
推荐实验 = feishark_v_62f76886
最高 epoch = e90
特征数 = 552
状态 = 可构建 index / 可登记模型
```

验证命令：

```text
tests/unit/test_training_runtime_guard.py + tests/unit/test_training_recovery_service.py: 9 passed
python -m pytest -q: 48 passed
python -m backend.self_check: PASS
frontend stage39b smoke: PASS
```

真实后端状态：

```text
8000 -> backend online
7866 -> RVC WebUI online
GPU -> idle / no core training
```

## 仍未完成的闭环

尚未执行真实 checkpoint recovery：

```text
voice_models 中还没有 source_job_id=train_010253ec08f0 的恢复模型
job_artifacts 中还没有 train_010253ec08f0 的 train_model_pth / train_model_index
```

因此当前阶段还只是“可恢复”，不是“已恢复并能用于翻唱”。

## Stage 40 总目标

用已有 e90 checkpoint 把失败训练任务救成可用模型，并把这个模型送入产品主路径：

```text
失败训练 -> checkpoint recovery -> 模型库可用 -> 一键送入翻唱 -> Factory/Studio 可识别来源
```

## 执行顺序

```text
1. 地基 Agent 先跑 Stage 40A：真实恢复登记 + 后端验收脚本 + 可用模型契约。
2. 产品 Agent 再跑 Stage 40B：恢复后模型的产品路径、按钮、状态、页面闭环。
3. 架构师最后做一次真实网页 + API + 文件系统验收。
```

## 禁止事项

```text
禁止重新训练 train.py。
禁止删除 feishark_v_62f76886 日志和权重。
禁止自动跑长音频翻唱压力测试。
真实恢复允许构建 index，但必须先确认 dry_run 通过、无 train.py 进程。
```

