# Stage 41A 地基 Agent 汇报

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## 任务结论

```text
是否完成：是
是否重新训练：否
是否启动核心训练 train.py：否
是否执行真实短 cover：是
恢复模型 ID：v_2c1603c7
恢复模型名：朱朱_recovered_e90
真实 cover job：task_stage41_ce1b32f2
```

本阶段完成了恢复模型的后端短链路验收：`朱朱_recovered_e90` 通过 cover preflight，并用 6 秒短 wav 跑通分离、修音、RVC 推理、混音和最终 artifact 登记。没有重新训练，没有调用 `train.py`。

## 修改文件清单

```text
backend/services/job_service.py
backend/services/track_service.py
backend/main.py
backend/verify_stage41_recovered_model_cover_smoke.py
tests/unit/test_training_recovery_service.py
docs/agent-md/worker/stage-41a-recovered-model-cover-backend-acceptance-report.md
```

## 修复点

### canonical stage

恢复训练 job 的主业务阶段已统一：

```text
job_id：train_010253ec08f0
status：完成
db current_stage：train_register_model
canonical current_stage：train_register_model
```

修复方式：

```text
对训练 job，如果 status 是完成态，且 metadata 或 voice_models 能证明已有 generated/recovered model，则 canonical_current_stage() 优先返回 train_register_model。
train_checkpoint_recover 仍保留在 stage logs，不再覆盖主业务阶段。
track job 序列化也同步做了恢复模型完成态归一。
```

新增单测：

```text
test_completed_recovered_train_job_canonical_stage_prefers_register
```

### task status 来源字段

`GET /api/task_status/{job_id}` 兼容新增恢复模型来源字段：

```text
voice_model_origin_kind
voice_model_source_job_id
voice_model_source_summary
voice_model_source_strategy_key
voice_model_source_material_profile
```

旧字段不删除、不改名。

## 真实短链路结果

```text
cover job：task_stage41_ce1b32f2
status：完成
current_stage：cover_mix
voice_model_id：v_2c1603c7
voice_name：朱朱_recovered_e90
```

输入音频：

```text
D:\FeiSharkStudio-v2\shared_data\jobs\stage41_recovered_model_cover_smoke\input\short_smoke.wav
约 6 秒，脚本自动生成
```

最终产物：

```text
artifact_type：cover_master
is_final：1
size：350,252 bytes
path：D:\FeiSharkStudio-v2\shared_data\jobs\task_stage41_ce1b32f2\artifacts\cover_mix\final_master.wav
```

验收项：

```text
cover preflight：PASS
UVR 分离：PASS
修音：PASS
RVC 推理：PASS
混音：PASS
final artifact：PASS
artifact download：PASS
track job entry can_open_studio：PASS
Studio versions：PASS
恢复模型来源字段：PASS
```

RVC 推理日志摘要：

```text
RVC 返回 Success
使用 index：D:\RVC\RVCv2\assets\indices\朱朱_recovered_e90.index
```

## 验证记录

```powershell
python -m py_compile backend\services\job_service.py backend\services\track_service.py backend\main.py backend\verify_stage41_recovered_model_cover_smoke.py
```

结果：

```text
PASS（无输出，退出码 0）
```

```powershell
python -m pytest -q tests/unit/test_training_recovery_service.py
```

结果：

```text
4 passed, 2 warnings
```

```powershell
python -m pytest -q
```

结果：

```text
49 passed, 2 warnings
```

```powershell
python -m backend.self_check
```

结果：

```text
CODE_STRUCTURE_SUMMARY PASS
RUNTIME_ENVIRONMENT_SUMMARY PASS
SELF_CHECK_SUMMARY PASS
```

```powershell
python backend\verify_stage41_recovered_model_cover_smoke.py
```

结果：

```text
stage41 recovered model cover dry-run PASS
```

```powershell
python backend\verify_stage41_recovered_model_cover_smoke.py --execute
```

结果：

```text
stage41 recovered model cover execute PASS: task_stage41_ce1b32f2
```

## 风险与遗留

```text
1. 本阶段只跑了 6 秒短音频真实 cover，未跑长音频压力测试，符合 Stage 41A 禁止事项。
2. 真实 cover 依赖本机 AudioPipeline、RVC WebUI 和模型文件；本次都通过，但其他机器仍需环境预检。
3. 控制台中文在当前 PowerShell 编码下仍显示乱码；数据库、文件名和 API 字段通过 python -X utf8 核对为正确中文。
4. Stage 41B 可继续补产品侧按钮、模型来源展示和 Studio 打开体验验收。
```
