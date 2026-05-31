# Stage 33A：UI 定点回修回归守门

你现在是 FeiShark Studio 的地基 agent。

必须在产品 agent 完成 Stage 33B 后再执行。  
你不修 UI，只验收产品 agent 是否真正修掉用户指出的 4 个问题，并确认没有破坏地基回归。

## 必读文件

- `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-33b-dashboard-factory-ui-hotfix-prompt.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-33b-dashboard-factory-ui-hotfix-report.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32b-three-page-layout-normalization-report.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-29-regression-closure-product-acceptance-report.md`

如果 Stage 33B report 还没完成，请不要改代码，只在你的 report 写明等待产品线。

## 允许修改

- 新增只读验收脚本：
  - `frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs`
- 本阶段 report：
  - `docs\agent-md\worker\stage-33a-ui-hotfix-regression-guard-report.md`

## 禁止修改

- `frontend\index.html`
- `frontend\factory.html`
- `frontend\studio.html`
- `frontend\css\app.css`
- `frontend\js\*.js`
- `frontend\js\factory\*.js`
- 后端任何文件
- README

发现问题写回修项，不要自己修。

## 必须验收的 4 个点

1. `#engineUsageToggleBtn` 能展开/收起 `#engineUsagePanel`，收起后 `hidden=true` 或高度归零。
2. `#jobDetailPanel` 不因长标题 / 长 ID / 长路径造成横向滚动，任务详情内部有受控滚动。
3. `#jobArtifactsToggleBtn` 与 `#jobArtifactsBody` 存在，产物区可展开/收起，下载按钮仍可见可用。
4. `#factoryBatchesToggleBtn` 与 `#factoryBatchesBody` 存在，批次列表可展开/收起，`[data-batch-id]` 点击逻辑仍可用。

## 必须执行

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

建议执行：

```powershell
node frontend\playwright_model_registry_linkage_smoke.cjs
node frontend\playwright_factory_to_studio_context_smoke.cjs
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

如果建议项没跑，必须写明原因。

## 交付要求

必须写入：

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-33a-ui-hotfix-regression-guard-report.md`

report 必须包含：

1. 是否等到 Stage 33B 完成后执行。
2. 是否修改了禁止修改的 UI / 后端文件。
3. 4 个用户问题逐项验收结果。
4. 执行过哪些命令，结果是什么。
5. 是否还有产品线必须回修的问题。

## 完成标准

- 地基 agent 不改 UI 实现文件。
- 4 个用户问题均通过自动或人工可验证检查。
- 第29回归继续通过。
- Dashboard / Factory smoke 继续通过。
