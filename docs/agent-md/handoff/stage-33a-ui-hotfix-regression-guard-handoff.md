# Stage 33A Handoff

这是给地基 agent 的任务。必须等产品 agent 完成 Stage 33B 后执行。

只发两份给地基 agent：

1. `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-33a-ui-hotfix-regression-guard-prompt.md`
2. `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-33a-ui-hotfix-regression-guard-report.md`

这轮地基 agent 不修 UI，只验收：

- 查看用途可收起
- 任务详情长字符受控
- 产物可收纳
- 批次列表可收纳

地基 agent 允许改：

- `frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs`
- 本阶段 report

地基 agent 禁止改：

- 页面
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
node frontend\playwright_stage33b_ui_hotfix_smoke.cjs
node frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs
node frontend\playwright_stage32b_three_page_layout_smoke.cjs
node frontend\playwright_stage17_smoke.cjs
node frontend\playwright_factory_smoke.cjs
```

这份 handoff 仅供你自己对照，不必额外发给地基 agent。
