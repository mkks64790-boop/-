# Stage 41 恢复模型真实翻唱验收计划

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## 当前状态

Stage 40 已把失败训练任务恢复成可用模型：

```text
job_id = train_010253ec08f0
model_id = v_2c1603c7
model_name = 朱朱_recovered_e90
source exp = feishark_v_62f76886
recovered epoch = 90
pth = shared_data/weights/朱朱_recovered_e90.pth
index = shared_data/weights/朱朱_recovered_e90.index
usable = true
cover preflight = PASS
```

已验证：

```text
python -m pytest -q = 48 passed
python -m backend.self_check = PASS
frontend stage40b smoke = PASS
```

## 当前遗留

1. `GET /api/jobs/train_010253ec08f0` 可能返回 `current_stage=train_checkpoint_recover`，而 DB 主状态为 `train_register_model`。需要统一恢复完成态的 canonical stage。
2. 产品移动端 smoke 中，模型库详情文本没有完全对焦到恢复模型，但选中模型和按钮行为是正确的。需要补移动端模型详情对焦验收。
3. 目前只验证了模型可入库、可 preflight，还没有跑“恢复模型 -> 一键翻唱 -> Studio 可试听”的真实短链路。

## Stage 41 总目标

用恢复模型跑一个小规模真实翻唱验收，不跑长任务、不重新训练，确认：

```text
恢复模型可用于 cover job
cover job 能产出 final artifact
Studio 能打开产物
产品上能清楚展示来源：checkpoint 恢复模型
```

