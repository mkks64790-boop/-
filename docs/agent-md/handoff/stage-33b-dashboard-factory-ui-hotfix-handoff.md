# Stage 33B Handoff

这是给产品 agent 的任务。只发两份：

1. `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-33b-dashboard-factory-ui-hotfix-prompt.md`
2. `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-33b-dashboard-factory-ui-hotfix-report.md`

这轮只修用户明确指出的 4 个 UI 问题：

- Dashboard 顶部 `查看用途` 展开后收不干净。
- Dashboard `任务详情` 长字符 / 长路径没有局部滚动和截断。
- Dashboard `产物` 没有收纳按钮。
- Factory `批次列表` 没有收纳按钮。

产品 agent 禁止改：

- 后端
- README
- 第29回归脚本
- Studio 页面
- Stage 31 Effect Rack 导出合同

必须新增并跑：

```powershell
node frontend\playwright_stage33b_ui_hotfix_smoke.cjs
```

必须同时跑：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
node frontend\playwright_stage32b_three_page_layout_smoke.cjs
node frontend\playwright_stage17_smoke.cjs
node frontend\playwright_factory_smoke.cjs
```

这份 handoff 仅供你自己对照，不必额外发给产品 agent。
