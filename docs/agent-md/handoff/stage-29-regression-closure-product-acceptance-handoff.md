# Stage 29 Handoff

这轮继续固定转达方式，只发两份给工作 agent：

1. `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-29-regression-closure-product-acceptance-prompt.md`
2. `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-29-regression-closure-product-acceptance-report.md`

这轮主题不是新增功能，而是验收体系收口：

- 修复 `backend\smoke_stage9.py`
- 修复 `backend\verify_stage11_train_flow.py`
- 更新 `README.md` 常用验证说明
- 保持第28阶段真实闭环不回退

关键判断：

- 3 秒单文件训练样本现在被 `422 train_material_not_eligible` 拒绝是正确行为。
- 工作 agent 不许为了旧脚本通过而放宽后端训练规则。
- 多文件短干声训练仍然应该作为正向路径通过。

必须跑：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
python -X utf8 backend\smoke_stage9.py
python -X utf8 backend\verify_stage11_train_flow.py
```

可选重型验收：

```powershell
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

如果没跑重型验收，必须在 report 里写原因。

这份 handoff 仅供你自己对照，不必额外发给工作 agent。
