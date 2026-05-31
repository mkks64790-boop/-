# Stage 32A：三页 UI 合同与回归守门

你现在是 FeiShark Studio 的地基 agent。

注意：产品 agent 会先执行 Stage 32B，负责规整 `Dashboard / Factory / Studio` 三页。  
你这轮不要抢 UI 文件，不要自己去“顺手美化”。你的任务是做验收守门：确认产品 agent 的三页规整没有破坏业务 selector、默认折叠、页面可用性和主链路。

## 执行顺序

请在产品 agent 完成 Stage 32B 并写好 report 后再执行。

必读：

- `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-32b-three-page-layout-normalization-prompt.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32b-three-page-layout-normalization-report.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-29-regression-closure-product-acceptance-report.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-30b-studio-product-shell-plugin-slots-report.md`

如果 Stage 32B report 还没完成，请不要改代码，只在你的 report 写明“等待产品线完成”。

## 允许修改

- 新增或调整只读验收脚本：
  - `frontend\playwright_stage32a_ui_contract_guard_smoke.cjs`
- 新增 UI selector 合同文档：
  - `docs\ui-contract\stage32-three-page-selector-contract.md`
- 本阶段 report：
  - `docs\agent-md\worker\stage-32a-ui-contract-regression-guard-report.md`

## 禁止修改

- `frontend\index.html`
- `frontend\factory.html`
- `frontend\studio.html`
- `frontend\css\app.css`
- `frontend\js\*.js`
- `frontend\js\factory\*.js`
- 后端任何文件
- README

地基 agent 只验收，不修 UI。发现问题要写清楚，交回产品 agent 修。

## 验收重点

### 1. Selector 合同

请把三页关键 selector 固化到文档：

- Dashboard selectors
- Factory selectors
- Studio selectors

文档要说明：

- selector 名称
- 属于哪个页面
- 被哪个 smoke 或业务交互依赖
- 是否允许未来重命名

### 2. 三页默认折叠合同

验证默认状态：

- Dashboard：
  - 模型库存 / 技术详情 / 阶段日志等噪音默认折叠
- Factory：
  - 历史 / 歌词 / 关联任务等长内容默认紧凑或折叠
- Studio：
  - 技术详情 / Track History / 试听品库默认折叠

### 3. 三页布局合同

新增 smoke 至少检查：

- Dashboard / Factory / Studio 都能打开
- 顶部导航存在且链接可见
- 页面没有横向滚动
- 桌面宽度下关键 panel 没有明显 DOM 缺失
- 移动宽度下页面不出现横向滚动
- 关键 CTA 存在：
  - Dashboard 创建入口
  - Factory 创建 cover / 进入 Studio
  - Studio 下载 / Effect Rack

### 4. 回归守门

必须复跑核心回归，确认产品线没有破坏地基：

- pytest
- self_check
- 第29两条脚本
- Stage 32B 三页布局 smoke
- Dashboard / Factory / Studio 相关 smoke

## 必须执行

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

建议执行：

```powershell
node frontend\playwright_model_registry_linkage_smoke.cjs
node frontend\playwright_factory_to_studio_context_smoke.cjs
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

如果建议项没跑，必须写明原因。

## 交付要求

必须写入：

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-32a-ui-contract-regression-guard-report.md`

report 必须包含：

1. 是否等到 Stage 32B 完成后再执行。
2. 是否修改了禁止修改的 UI / 后端文件。
3. 新增 selector 合同文档路径。
4. 新增 UI contract smoke 路径。
5. 三页关键 selector 是否完整。
6. 三页默认折叠是否符合要求。
7. 桌面和移动宽度是否无横向滚动。
8. 执行过哪些命令，结果是什么。
9. 产品线还有哪些必须回修的问题。

## 完成标准

- 地基 agent 不改 UI 实现文件。
- selector 合同文档落地。
- UI contract smoke 通过。
- 第29地基回归继续通过。
- Stage 32B 的三页布局 smoke 通过。
- 如果发现 UI 问题，明确列为产品 agent 回修项，而不是自己偷偷改。
