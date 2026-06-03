# Stage 41A：恢复模型真实翻唱后端验收（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本阶段只做后端契约修补和真实短链路验收。禁止重新训练，禁止启动 `train.py`，禁止跑长音频压力测试。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-41-recovered-model-cover-acceptance-plan.md
D:\FeiSharkStudio-v2\backend\services\job_service.py
D:\FeiSharkStudio-v2\backend\services\track_service.py
D:\FeiSharkStudio-v2\backend\strategies\cover_strategy.py
D:\FeiSharkStudio-v2\backend\main.py
```

## 必做任务

### 1. 修复恢复完成态 canonical stage

当前恢复 job 已完成，但 API 可能返回：

```text
current_stage = train_checkpoint_recover
```

要求：

- 对训练 job，若 status 是完成态且已存在 generated/recovered model，则 `GET /api/jobs/{job_id}` 应返回 `current_stage=train_register_model`。
- `train_checkpoint_recover` 可以保留在 stage logs，但不能覆盖主业务阶段。
- 补单元测试覆盖该场景。

### 2. 新增恢复模型真实 cover 验收脚本

新增：

```text
backend/verify_stage41_recovered_model_cover_smoke.py
```

要求默认安全：

```text
默认只做 preflight + 参数检查。
只有 --execute 才创建真实 cover job。
```

执行对象：

```text
model_id = v_2c1603c7
model_name = 朱朱_recovered_e90
```

音频策略：

- 优先使用项目内已有短 smoke 音频或自动生成 5-10 秒 wav。
- 不要使用 45 分钟训练素材。
- 不跑长音频。

验收项：

- cover preflight 通过。
- 创建 cover job 时 metadata 写入 voice_model_source：checkpoint recovery。
- job 完成后有 final artifact。
- artifacts 可下载且非空。
- track/factory/studio 相关字段能读到恢复模型来源。
- 如果外部 RVC 接口失败，报告必须区分“模型不可用”还是“RVC 服务调用失败”。

### 3. 不破坏既有测试

必须跑：

```powershell
python -m pytest -q
python -m backend.self_check
python backend\verify_stage41_recovered_model_cover_smoke.py
```

如果机器状态允许，再跑：

```powershell
python backend\verify_stage41_recovered_model_cover_smoke.py --execute
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-41a-recovered-model-cover-backend-acceptance-report.md
```

## 本阶段好处

```text
把“模型可用”推进到“模型真的能跑一键翻唱”。
提前暴露 RVC 推理接口、模型路径、产物登记、Studio 打开链路的真实问题。
避免用户下一次手动测试时踩长任务坑。
```

