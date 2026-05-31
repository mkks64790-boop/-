# Stage 32A 执行汇报：三页 UI 合同与回归守门

## 阶段标题

Stage 32A：三页 UI 合同与回归守门

## 执行顺序

```text
是否等到 Stage 32B 完成后执行 = 是
读取的 Stage 32B report = D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32b-three-page-layout-normalization-report.md
读取的 Stage 29 report = D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-29-regression-closure-product-acceptance-report.md
读取的 Stage 30B report = D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-30b-studio-product-shell-plugin-slots-report.md
```

## 完成情况

- 已完成：新增三页 selector 合同文档。
- 已完成：新增只读 UI contract smoke。
- 已完成：验证 Dashboard / Factory / Studio 关键 selector、默认折叠、桌面/移动无横向滚动、核心 CTA 存在。
- 已完成：复跑必跑后端/前端回归。
- 已完成：复跑建议 smoke，包括真实 Stage 28 trained model cover closure。

## 修改文件

- `D:\FeiSharkStudio-v2\frontend\playwright_stage32a_ui_contract_guard_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\ui-contract\stage32-three-page-selector-contract.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32a-ui-contract-regression-guard-report.md`

## 禁止修改检查

本阶段未主动修改禁止范围内文件。

```text
是否修改 frontend 页面实现 = 否
是否修改 frontend CSS = 否
是否修改 frontend JS 业务实现 = 否
是否修改后端 = 否
是否修改 README = 否
```

说明：当前工作区存在大量前序阶段已留下的 dirty 文件；Stage 32A 本轮只新增/回填上述允许范围内的守门文件和 report，没有回滚或改写前序改动。

## Selector 合同结果

```text
Dashboard selectors = 完整固化；覆盖任务中心、创建入口、模型面板、诊断面板、任务详情、操作区、模型库存、移动 tab、动态 job/model anchor
Factory selectors = 完整固化；覆盖 batch/track 导入、cover job 创建、歌词抽屉、关联任务、当前主成品、Studio/download 动作 anchor
Studio selectors = 完整固化；覆盖来源上下文、下载、Track History、主成品设置、Effect Rack、技术详情、试听品库
合同文档路径 = D:\FeiSharkStudio-v2\docs\ui-contract\stage32-three-page-selector-contract.md
UI contract smoke 路径 = D:\FeiSharkStudio-v2\frontend\playwright_stage32a_ui_contract_guard_smoke.cjs
```

## 默认折叠与布局结果

```text
Dashboard default collapsed = PASS；job technical、stage logs、models inventory、diagnostics detail 默认折叠
Factory default collapsed = PASS；lyrics body、related jobs body 默认折叠
Studio default collapsed = PASS；technical body、track history body、studio library body 默认折叠
Desktop horizontal overflow = PASS；1500x1060 无页面级横向滚动
Mobile horizontal overflow = PASS；390x920 无页面级横向滚动
```

## 验证结果

```text
python -m pytest -q
结果：PASS，19 passed, 2 warnings in 3.27s

python -X utf8 backend\self_check.py
结果：PASS，SELF_CHECK_SUMMARY PASS

python -X utf8 backend\smoke_stage9.py
结果：PASS，cover pass；single short train rejection pass；multi train pass；all smoke checks pass
补充：cover_job=task_13c834e3119b，multi_train_job=train_c110b3af101e，multi_final_stage=train_register_model

python -X utf8 backend\verify_stage11_train_flow.py
结果：PASS，short single rejected -> train_material_not_eligible / single_short_out_of_window；multi ok -> train_f1a0b9f3f512；stage11 verification PASS

node frontend\playwright_stage32b_three_page_layout_smoke.cjs
结果：PASS，STAGE32B_THREE_PAGE_LAYOUT_SMOKE PASS
截图：D:\FeiSharkStudio-v2\stage32b_dashboard_layout.png；D:\FeiSharkStudio-v2\stage32b_factory_layout.png；D:\FeiSharkStudio-v2\stage32b_studio_layout.png

node frontend\playwright_stage32a_ui_contract_guard_smoke.cjs
结果：PASS，STAGE32A_UI_CONTRACT_GUARD_SMOKE PASS
覆盖：selector contract、default collapsed、desktop/mobile horizontal overflow、core CTA

node frontend\playwright_stage17_smoke.cjs
结果：PASS，STAGE17_PLAYWRIGHT_SMOKE PASS
截图：D:\FeiSharkStudio-v2\stage17_dashboard.png；D:\FeiSharkStudio-v2\stage17_studio.png

node frontend\playwright_factory_smoke.cjs
结果：PASS，FACTORY_PLAYWRIGHT_SMOKE PASS
截图：D:\FeiSharkStudio-v2\stage20_factory.png

node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
结果：PASS，STAGE30B_STUDIO_PRODUCT_SHELL_SMOKE PASS
studio_url=http://127.0.0.1:8000/studio?track_id=trk_5a8466de9f&job_id=task_fe97656d0589

node frontend\playwright_model_registry_linkage_smoke.cjs
结果：PASS，STAGE27_MODEL_REGISTRY_SMOKE PASS model=v_b5c8427a source_job=train_d8cd4ed377ca
是否执行：是

node frontend\playwright_factory_to_studio_context_smoke.cjs
结果：PASS，FACTORY_TO_STUDIO_CONTEXT_PLAYWRIGHT_SMOKE PASS
Batch=batch_98c96df2ad；Track=trk_7fa5f463c4；Job=task_4c122c3ef0ce
是否执行：是

node frontend\playwright_trained_model_cover_studio_smoke.cjs
结果：PASS，STAGE28_TRAINED_MODEL_COVER_SMOKE PASS
model_id=v_b5c8427a；source_job_id=train_d8cd4ed377ca；track_id=trk_6225dc8673；cover_job_id=task_838d14312200；final_stage=cover_mix
studio_url=/studio?batch_id=batch_15e7d44ca4&track_id=trk_6225dc8673&job_id=task_838d14312200&artifact_id=art_d6cd377bbb8d
是否执行：是
```

## 产品线回修项

- 未发现必须回修的 UI selector 缺失。
- 未发现默认折叠状态回退。
- 未发现桌面或移动页面级横向滚动。
- 未发现 Dashboard / Factory / Studio 主链 smoke 回退。

## 风险与限制

- `playwright_stage32a_ui_contract_guard_smoke.cjs` 是守门脚本，不替代完整业务 smoke；它只验证 selector、折叠、CTA 和布局基础契约。
- 动态 selector 例如 `.job-row[data-job-id]`、`#modelsList [data-model-id]`、`[data-batch-id]`、`[data-track-id]`、`[data-studio-url]` 依赖运行时数据；本脚本同时做源码合同检查和页面静态锚点检查，业务动态链路由 Stage 17 / Factory / Stage 23 / Stage 28 smoke 覆盖。
- 当前工作区 dirty 面较大，后续提交时需要按阶段拆分，避免把 Stage 32A 守门文件和其他阶段实现改动混在一起。

## 交接说明

- 后续产品线可以继续调整三页视觉，但不能删除或重命名合同文档中的 selector，除非同步更新依赖 smoke 和合同文档。
- 如果三页默认信息密度再次升高，优先检查合同中的默认折叠项。
- 地基回归建议保留本轮命令集：`pytest`、`self_check`、Stage 9、Stage 11、Stage 32B、Stage 32A、Stage 17、Factory、Stage 30B；真实闭环有环境时继续补跑 Stage 28 smoke。
