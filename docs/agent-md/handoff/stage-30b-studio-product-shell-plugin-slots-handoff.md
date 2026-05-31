# Stage 30B Handoff

这是给产品体验 agent 的并行任务，不是给正在做第29阶段地基修复的 agent。

只发两份给产品 agent：

1. `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-30b-studio-product-shell-plugin-slots-prompt.md`
2. `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-30b-studio-product-shell-plugin-slots-report.md`

这轮主题：

- 把 `Studio` 从工程验收页改成修音室产品壳。
- 增加 Effect Rack / 插件槽前端抽象。
- 技术详情、阶段日志、Track History 默认折叠。
- 不接真实 VST，不伪装音频已被插件处理。

产品 agent 允许改：

- `frontend\studio.html`
- `frontend\js\studio.js`
- `frontend\css\app.css`
- 新增 `frontend\playwright_stage30b_studio_product_shell_smoke.cjs`
- 本阶段 report

产品 agent 禁止改：

- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- `README.md`
- 后端主链路
- RVC / UVR / ffmpeg 执行层

必须保留第28阶段关键 selector：

- `#studioSourceContextCard`
- `#studioSummaryDownloadBtn`
- `#studioTrackHistoryList`
- `[data-set-track-master-job-id]`

必须跑：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
```

建议跑：

```powershell
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

如果没跑建议项，必须在 report 里说明原因。

这份 handoff 仅供你自己对照，不必额外发给产品 agent。
