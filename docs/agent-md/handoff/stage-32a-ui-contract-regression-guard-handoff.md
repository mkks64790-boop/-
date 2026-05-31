# Stage 32A Handoff

这是给地基 agent 的任务。必须在产品 agent 完成 Stage 32B 后执行。

只发两份给地基 agent：

1. `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-32a-ui-contract-regression-guard-prompt.md`
2. `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32a-ui-contract-regression-guard-report.md`

这轮主题：

- 不修 UI。
- 不改后端。
- 给三页建立 selector 合同。
- 写只读 UI contract smoke。
- 复跑回归，判断产品 agent 是否把页面规整且没破坏业务。

地基 agent 允许改：

- `frontend\playwright_stage32a_ui_contract_guard_smoke.cjs`
- `docs\ui-contract\stage32-three-page-selector-contract.md`
- 本阶段 report

地基 agent 禁止改：

- 三个页面
- CSS
- 前端业务 JS
- 后端
- README

必须跑：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
python -X utf8 backend\smoke_stage9.py
python -X utf8 backend\verify_stage11_train_flow.py
node frontend\playwright_stage32b_three_page_layout_smoke.cjs
node frontend\playwright_stage32a_ui_contract_guard_smoke.cjs
node frontend\playwright_stage17_smoke.cjs
node frontend\playwright_factory_smoke.cjs
node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
```

建议跑：

```powershell
node frontend\playwright_model_registry_linkage_smoke.cjs
node frontend\playwright_factory_to_studio_context_smoke.cjs
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

这份 handoff 仅供你自己对照，不必额外发给地基 agent。
