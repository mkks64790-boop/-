# Stage 42B Three Page Product Shell UI Report

## 结论

已完成产品侧三页壳验收修补：Dashboard 保持任务中心 + 创建入口并默认收纳长详情；Factory 新增 Local AI Engine Manager 和模型资产抽屉；Studio 保持试听、版本、后处理导出入口的产品壳。未触发 cover/train 自动提交。

## 改动文件

- `frontend/factory.html`
  - 在 Factory 首屏主区新增 Local AI Engine Manager。
  - 新增“模型资产抽屉”，默认收起，避免模型库挤占 Factory 首屏。
- `frontend/js/factory/main.js`
  - 接入 `GET /api/engines` 渲染 RVC / UVR / SVC 状态。
  - 接入 `POST /api/engines/scan` 扫描按钮，接口不可用时降级提示，不阻断 Factory 主流程。
  - 模型资产抽屉读取 `/api/models`，只展示模型资产摘要和列表，不硬编码可用状态。
  - 移动端/刷新后保持模型资产抽屉收起。
- `frontend/css/app.css`
  - 补充 Engine Manager 卡片、模型资产抽屉、移动端单列样式。
- `frontend/playwright_stage42b_three_page_product_shell_smoke.cjs`
  - 新增 Stage 42B 三页产品壳 smoke。

## 验收覆盖

- Dashboard
  - 任务中心存在。
  - cover / 单文件训练 / 多文件训练创建入口存在。
  - 未选择音频时 cover 创建按钮保持 disabled。
  - artifacts / technical / stage logs 默认收起。
  - 模型库存默认收起。
- Factory
  - Engine Manager 渲染 3 个 API 返回引擎：RVC WebUI、UVR、SVC/SVT。
  - `/api/engines/scan` 按钮可触发并恢复 enabled。
  - 模型资产抽屉默认收起。
  - 移动端无横向溢出。
- Studio
  - 播放器、资源选择、Effect Rack、导出按钮存在。
  - Studio 资源库和技术抽屉默认收起。
- Mobile
  - 900px 下移动 tabs 存在。
  - `feishark.mobile-tab` 能保存 `models` tab。
  - Dashboard 长抽屉和 Factory 模型资产抽屉保持收起。
- 安全护栏
  - smoke 未捕获 `/api/process/*` 或 `POST /api/train` 调用。

## 命令结果

- `node --check` temp `.mjs`:
  - `frontend/js/jobs.js`
  - `frontend/js/models.js`
  - `frontend/js/cover.js`
  - `frontend/js/factory/main.js`
  - `frontend/js/studio.js`
  - 结果：通过。
- `node --check frontend/playwright_stage42b_three_page_product_shell_smoke.cjs`
  - 结果：通过。
- `node frontend/playwright_stage42b_three_page_product_shell_smoke.cjs`
  - 结果：通过。
  - 截图：`output/playwright/stage42b_three_page_product_shell.png`

## 现场观察

- 本地 FastAPI 已启动在 `http://127.0.0.1:8000`。
- `/api/engines` 当前返回 3 个引擎：
  - RVC WebUI：offline，模型 400，root `D:\RVC\RVCv2`
  - UVR 分离器：online，模型 1，root `C:\Users\ASUS\AudioPipeline`
  - SVC/SVT 备用引擎：not_configured，模型 0
- `task_stage41_ce1b32f2` 当前可读且状态为“完成”，但接口未返回 `can_open_studio` 或 `final_artifact_download_url`，因此本次 smoke 按“Studio entry if available”跳过强断言。

## 遗留

- Dashboard 侧 Stage41 完成 cover 是否应该补 `can_open_studio/final_artifact_download_url` 仍取决于地基接口/产物登记状态；产品侧没有伪造 Studio 入口。
- 本阶段没有新增自动任务创建或训练触发。
