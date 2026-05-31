# Stage 33A 执行汇报：UI 定点回修回归守门

## 阶段标题

Stage 33A：UI 定点回修回归守门

## 执行顺序

```text
是否等到 Stage 33B 完成后执行 = 是
读取的 Stage 33B report = D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-33b-dashboard-factory-ui-hotfix-report.md
读取的 Stage 32B report = D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32b-three-page-layout-normalization-report.md
读取的 Stage 29 report = D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-29-regression-closure-product-acceptance-report.md
```

## 完成情况

- 已完成：新增只读 Stage 33A UI hotfix guard smoke。
- 已完成：逐项验收 Stage 33B 针对 4 个用户 UI 问题的修复结果。
- 已完成：复跑必跑后端/前端回归。
- 已完成：复跑建议 smoke，包括真实 Stage 28 trained model cover closure。

## 修改文件

- `D:\FeiSharkStudio-v2\frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-33a-ui-hotfix-regression-guard-report.md`

## 禁止修改检查

本阶段未主动修改禁止范围内文件。

```text
是否修改 frontend 页面实现 = 否
是否修改 frontend CSS = 否
是否修改 frontend JS 业务实现 = 否
是否修改后端 = 否
是否修改 README = 否
```

说明：当前工作区存在大量前序阶段 dirty 文件；Stage 33A 本轮只新增只读守门脚本并回填 report，没有回滚或改写产品线/后端实现。

## 4 个用户问题验收

```text
1. 查看用途可收起 = PASS
   验证点：#engineUsageToggleBtn 和 #engineUsagePanel 存在；默认 hidden；展开后高度 > 0；再次点击后 hidden=true，display=none 或高度=0，aria-expanded=false。

2. 任务详情长字符串受控 = PASS
   验证点：选中 job 后 #jobDetailPanel 不产生横向撑爆；panel.scrollWidth <= panel 宽度；overflow-x=hidden；Dashboard 页面无横向滚动。

3. 产物可收纳 = PASS
   验证点：#jobArtifactsToggleBtn、#jobArtifactsBody、#jobArtifactsList 存在；产物区可展开/收起并恢复状态；若存在 button[data-artifact-download]，至少有可用下载按钮。

4. 批次列表可收纳 = PASS
   验证点：#factoryBatchesToggleBtn、#factoryBatchesBody、#factoryBatchesList 存在；批次列表可展开/收起并恢复状态；[data-batch-id] 点击选择逻辑可用；Factory 页面无横向滚动。
```

## 新增守门脚本

```text
路径 = D:\FeiSharkStudio-v2\frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs
性质 = 只读浏览器验收脚本
覆盖 = 4 个用户 hotfix 问题、Dashboard 横向滚动、Factory 横向滚动、关键 selector 存在、截图输出
截图 = D:\FeiSharkStudio-v2\stage33a_dashboard_guard.png
截图 = D:\FeiSharkStudio-v2\stage33a_factory_guard.png
```

## 验证结果

```text
python -m pytest -q
结果：PASS，19 passed, 2 warnings in 3.40s

python -X utf8 backend\self_check.py
结果：PASS，SELF_CHECK_SUMMARY PASS

python -X utf8 backend\smoke_stage9.py
结果：PASS，cover pass；single short train rejection pass；multi train pass；all smoke checks pass
补充：cover_job=task_997a87c7f28e；multi_train_job=train_6ef29c05d40b；multi_final_stage=train_register_model

python -X utf8 backend\verify_stage11_train_flow.py
结果：PASS，short single rejected -> train_material_not_eligible / single_short_out_of_window；multi ok -> train_178af4015c90；stage11 verification PASS

node frontend\playwright_stage33b_ui_hotfix_smoke.cjs
结果：PASS，STAGE33B_UI_HOTFIX_SMOKE PASS
截图：D:\FeiSharkStudio-v2\stage33b_dashboard_hotfix.png；D:\FeiSharkStudio-v2\stage33b_factory_hotfix.png

node frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs
结果：PASS，STAGE33A_UI_HOTFIX_GUARD_SMOKE PASS
截图：D:\FeiSharkStudio-v2\stage33a_dashboard_guard.png；D:\FeiSharkStudio-v2\stage33a_factory_guard.png

node frontend\playwright_stage32b_three_page_layout_smoke.cjs
结果：PASS，STAGE32B_THREE_PAGE_LAYOUT_SMOKE PASS
截图：D:\FeiSharkStudio-v2\stage32b_dashboard_layout.png；D:\FeiSharkStudio-v2\stage32b_factory_layout.png；D:\FeiSharkStudio-v2\stage32b_studio_layout.png

node frontend\playwright_stage17_smoke.cjs
结果：PASS，STAGE17_PLAYWRIGHT_SMOKE PASS
截图：D:\FeiSharkStudio-v2\stage17_dashboard.png；D:\FeiSharkStudio-v2\stage17_studio.png

node frontend\playwright_factory_smoke.cjs
结果：PASS，FACTORY_PLAYWRIGHT_SMOKE PASS
截图：D:\FeiSharkStudio-v2\stage20_factory.png

node frontend\playwright_model_registry_linkage_smoke.cjs
结果：PASS，STAGE27_MODEL_REGISTRY_SMOKE PASS model=v_b5c8427a source_job=train_d8cd4ed377ca
是否执行：是

node frontend\playwright_factory_to_studio_context_smoke.cjs
结果：PASS，FACTORY_TO_STUDIO_CONTEXT_PLAYWRIGHT_SMOKE PASS
Batch=batch_e90ffd85c5；Track=trk_c6420eb801；Job=task_5ec72638fc2d
是否执行：是

node frontend\playwright_trained_model_cover_studio_smoke.cjs
结果：PASS，STAGE28_TRAINED_MODEL_COVER_SMOKE PASS
model_id=v_b5c8427a；source_job_id=train_d8cd4ed377ca；track_id=trk_0562c7ad49；cover_job_id=task_0057f33d34b1；final_stage=cover_mix
studio_url=/studio?batch_id=batch_1955ab0fba&track_id=trk_0562c7ad49&job_id=task_0057f33d34b1&artifact_id=art_d611b362e783
是否执行：是
```

## 产品线回修项

- 未发现必须回修的问题。
- 4 个用户指出的 UI hotfix 点均通过自动验收。
- Dashboard / Factory / Stage 9 / Stage 11 / Stage 28 真实闭环未发现回退。

## 风险与限制

- Stage 33A 脚本是守门脚本，不替代人工视觉验收；它验证的是明确的 4 个问题和基础布局安全，不评价整体审美。
- 产物下载按钮检查依赖当前所选 job 是否有 artifacts；脚本逻辑为：如果存在 `button[data-artifact-download]`，则必须至少有一个可用下载按钮。
- 当前工作区 dirty 面较大，后续提交时建议按阶段拆分，避免将 Stage 33A 的只读守门脚本与 Stage 33B 产品线实现混在同一个提交里。

## 交接说明

- 后续如果再次调整 Dashboard 顶部用途面板、任务详情、产物区或 Factory 批次列表，必须继续跑 `frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs`。
- `#jobArtifactsToggleBtn` / `#jobArtifactsBody` / `#factoryBatchesToggleBtn` / `#factoryBatchesBody` 已成为 Stage 33 后的稳定 UI contract。
- 地基回归建议保留本轮命令集：pytest、self_check、Stage 9、Stage 11、Stage 33B、Stage 33A、Stage 32B、Stage 17、Factory；真实环境可用时继续补跑 model registry、Factory->Studio、Stage 28 closure。
