# Stage 34B Handoff

这是给产品 agent 的任务。必须等 Stage 34A 地基完成后执行。

只发两份：

1. `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-34b-effect-rack-export-ui-hookup-prompt.md`
2. `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-34b-effect-rack-export-ui-hookup-report.md`

核心目标：

- 把 Studio `导出处理版` 按钮接入 `/api/studio/effect-rack/export`
- 成功后跳转到新 artifact 的 Studio URL
- 明确提示 copy-only / no DSP / no VST
- 不改后端
- 不改 Dashboard / Factory

必须跑：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

这份 handoff 仅供你自己对照，不必额外发给产品 agent。
