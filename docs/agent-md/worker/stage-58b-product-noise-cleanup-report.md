# Stage58B Product Noise Cleanup Report

## 发现的问题

- Dashboard / Factory / Studio 会在用户默认视角暴露 smoke、stage、test、self_check、playwright 记录，容易把用户产品面板变成验收/测试垃圾堆。
- 后端接口是否已支持 `include_test_data` / `include_smoke` 不能完全依赖，前端需要在列表渲染前做防御性过滤。
- Dashboard 的 Stage 验收类面板、任务详情产物和阶段日志容易占据主区；Factory 批次/模型列表、Studio 试听品库需要继续默认收起并限制展开高度。
- 入口按钮仍有 `cover job` 等工程口吻，用户入口需要明确回到 “AI 一键翻唱 / 单文件快速训练 / 多文件批量精训”。

## 改动文件

- `frontend/js/jobs.js`
- `frontend/js/models.js`
- `frontend/js/factory/main.js`
- `frontend/js/studio.js`
- `frontend/js/cover.js`
- `frontend/js/train.js`
- `frontend/css/app.css`
- `frontend/playwright_stage58_user_noise_ui_smoke.cjs`
- `docs/agent-md/worker/stage-58b-product-noise-cleanup-report.md`

## 验证命令与结果

- `node --check frontend\playwright_stage58_user_noise_ui_smoke.cjs`
  - 结果：通过。
- ESM 前端语法检查：
  - 命令：复制 `frontend/js/jobs.js`、`models.js`、`factory/main.js`、`studio.js`、`cover.js`、`train.js` 到 `%TEMP%/*.mjs` 后执行 `node --check`。
  - 结果：全部通过。
  - 说明：直接 `node --check frontend/js/*.js` 会被根 `package.json` 的 CommonJS 设置误判为非 ESM；PowerShell stdin 管道会破坏中文编码，因此改用临时 `.mjs` 检查。
- `node frontend\playwright_stage58_user_noise_ui_smoke.cjs`
  - 结果：通过。
  - 覆盖：默认不显示测试噪声；打开“显示测试记录”后可显示；Dashboard / Factory / Studio 无横向溢出；核心入口仍可见；请求中观察到 `include_test_data/include_smoke` 的 false/true 两种状态。

## 主控补充项确认

- Factory summary 已改为请求 `/api/factory/summary?include_test_data=...&include_smoke=...`。
- Factory batch list 已改为请求 `/api/batches?...include_test_data/include_smoke...`，并保留本地防御过滤。
- Factory track list 已改为 batch detail 带参数，并优先读取 `/api/batches/{id}/tracks?...include_test_data/include_smoke...`；旧后端不可用时回退 embedded tracks，再本地过滤。
- Studio 默认资源库已对 `/api/jobs?job_type=cover...` 本地过滤 smoke/test/stage 成品；默认 off 时不会展示 Stage47/stageXX smoke 成品。
- Studio URL 直达 smoke/test/stage job 时，默认 off 不自动载入，改为提示“测试成品已隐藏，打开显示测试记录后可查看”。
- `frontend/playwright_stage58_user_noise_ui_smoke.cjs` 覆盖 Dashboard / Factory / Studio 默认隐藏、打开开关后可见、无横向溢出、核心入口仍可见。

## 未解决风险

- 前端已携带 `include_test_data` / `include_smoke` 并做本地过滤；如果后端尚未补齐这两个参数，前端仍能防御显示，但分页 total / summary 等服务端聚合仍可能包含测试数据，需要后端补齐。
- 测试记录识别采用前端启发式：`smoke`、`self_check`、`playwright`、`test`、`stage数字`。若真实用户命名也包含这些模式，默认会被隐藏，用户可用开关找回。
- 本次不改后端、不删除数据、不启动训练/RVC/UVR/GPU 长任务；Playwright smoke 使用拦截 API 数据验证 UI 行为。
