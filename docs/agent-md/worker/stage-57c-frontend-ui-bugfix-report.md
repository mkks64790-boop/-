# Stage57C Frontend UI Bugfix Report

日期：2026-06-03

范围：Dashboard / Factory / Studio 前端入口与 UI 状态审计。未运行训练，未运行 RVC/UVR，未修改 backend，未做大视觉重构。

## 发现的 bug

1. 训练观察器“用该模型翻唱”会向封面模型下拉框注入临时模型 option，但后续模型库刷新可能覆盖该临时 option，导致 UI 静默切换到其它可用模型，形成误导。
2. 临时注入的训练模型 id 可能被表现得像“模型库已确认可用”，用户可能直接创建翻唱任务，实际模型注册状态未确认。
3. Factory 批次列表抽屉会被刷新/载入动作强制改变展开状态，不能稳定保持用户收纳选择。
4. Studio 直链 `/studio?job_id=...&artifact_id=...` 在旧路由或契约 404 时，前端可能只显示失败/空状态，缺少“后端需重启或契约暂不可用”的明确提示。
5. 长任务 id、artifact id、路径、日志、阶段文案在部分列表/卡片内仍有撑爆布局风险。
6. QA 已确认当前 Stage47 Playwright smoke 的主要等待点是 Factory 模型资产不足，不应继续扩大为 UI 大重构问题。

## 已修复

1. `frontend/js/jobs.js`：训练观察器注入的封面模型 option 增加 pending registry 标记，并使用明确的 pending 文案。
2. `frontend/js/models.js`：模型库刷新时保留训练观察器注入的 pending option；当真实可用模型出现时真实 option 优先，否则继续选中 pending option，避免静默切换到其它模型。
3. `frontend/js/cover.js`：识别 pending registry 模型状态，并在模型库未确认前禁用创建翻唱；提示用户等待模型注册或刷新模型库。
4. `frontend/js/factory/main.js`：Factory 批次抽屉增加本地收纳状态持久化，刷新/载入批次时不再强制覆盖用户选择。
5. `frontend/js/studio.js`：Studio 直链在列表接口失败时优先尝试按 URL 中的 `job_id` 直接载入；任务载入失败时展示明确的 backend restart / contract unavailable 信息，并包含请求的 `job_id` / `artifact_id`。
6. `frontend/css/app.css`：对任务表、Studio 资源/历史/日志、Factory 项、抽屉摘要、路径和长文本补充 `min-width: 0` / `overflow-wrap` / ellipsis 防护。

## 未修复 / 待修

1. 未新增 `frontend/playwright_stage57_ui_contract_smoke.cjs`；本轮按用户中间收口要求停止扩展。
2. 未继续大范围 UI 翻新，未重构 Dashboard / Factory / Studio 布局。
3. 未修改 backend 契约；如果 live 8000 旧路由仍 404，需要后端重启或补齐契约，前端只负责清楚提示。
4. Stage47 Playwright smoke 若继续卡在 Factory 模型资产不足，需要补充可用测试模型资产或调整测试前置数据，不属于本次前端 UI 最小修复继续处理范围。

## 验证结果

已按前序执行过 touched JS files module syntax check，使用 PowerShell 兼容命令：

```powershell
cmd /c "node --input-type=module --check < frontend\js\jobs.js"
cmd /c "node --input-type=module --check < frontend\js\models.js"
cmd /c "node --input-type=module --check < frontend\js\cover.js"
cmd /c "node --input-type=module --check < frontend\js\studio.js"
cmd /c "node --input-type=module --check < frontend\js\factory\main.js"
```

结果：上述单文件 module syntax check 已通过。一次合并命令尝试因 PowerShell 5 不支持 `&&` 链接命令失败，非 JS 语法失败。

未运行：

```powershell
node frontend/playwright_stage47_e2e_acceptance_dashboard_smoke.cjs
```

原因：用户已要求立即收束，且 QA 已确认 Stage47 smoke 当前主要阻塞是 Factory 模型资产不足。

## 风险

1. 当前工作树存在大量既有改动，本报告只覆盖本次允许范围内的前端最小修复，不回滚其它改动。
2. pending 模型 option 现在会阻止直接创建翻唱，行为更保守；如果业务希望允许“未注册但已知路径”的模型直接使用，需要后续明确契约。
3. Studio 的 contract unavailable 是前端降级提示；真实 404/旧路由仍需要后端重启或契约更新。
4. 未做完整 live browser 回归，剩余风险集中在真实数据资产不足和旧服务未重启场景。
