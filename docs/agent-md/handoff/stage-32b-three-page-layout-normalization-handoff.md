# Stage 32B Handoff

这是给产品体验 agent 的任务。

只发两份给产品 agent：

1. `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-32b-three-page-layout-normalization-prompt.md`
2. `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32b-three-page-layout-normalization-report.md`

这轮主题：

- 规整 `Dashboard / Factory / Studio` 三个页面。
- 统一布局、卡片、抽屉、主操作和默认折叠规则。
- 不新增后端功能。
- 不做 Effect Rack 导出。
- 不动第29阶段回归脚本。

产品 agent 允许改：

- 三个前端页面
- 前端 UI / 布局 JS
- `frontend\css\app.css`
- 新增 `frontend\playwright_stage32b_three_page_layout_smoke.cjs`
- 本阶段 report

产品 agent 禁止改：

- 后端
- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- README
- Stage 31 Effect Rack 导出合同

必须跑：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
node frontend\playwright_stage32b_three_page_layout_smoke.cjs
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

这份 handoff 仅供你自己对照，不必额外发给产品 agent。
