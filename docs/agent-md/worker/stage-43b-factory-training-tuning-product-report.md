# Stage 43B Factory Training Tuning Product Report

## 结论

已完成产品侧 Stage 43B。Factory 增加第三方 RVC 模型操作区与训练调参台 v0；Dashboard completed cover 的 Studio 入口改为只信后端真实契约；新增并通过 Stage43B 浏览器 smoke。没有自动提交训练或 cover。

## 修改文件

- `frontend/factory.html`
  - 新增第三方 RVC 模型区：搜索、登记状态过滤、index 过滤、分页。
  - 新增训练调参台 v0：三预设、素材信息输入、估算按钮。
- `frontend/js/factory/main.js`
  - 接入 `/api/engines/rvc/models?limit=&offset=&q=&registered=&has_index=`，后端未分页时前端兜底分页，每页 8 条。
  - 接入 `/api/models/import-rvc`，接口不存在时只提示“等待地基接口”，不报 JS 错。
  - 接入 `/api/training/presets` 与 `/api/training/estimate`，接口缺失时显示产品侧默认预设和粗估，不创建训练 job。
  - `/api/engines/scan?force=true` 后刷新 Engine 与 RVC 模型列表。
- `frontend/js/jobs.js`
  - completed cover 只有 `can_open_studio` 或 `studio_url` 为真时显示 Studio 按钮。
  - 没有 Studio 契约时显示“等待产物登记，Studio 入口暂不可用”。
  - `final_artifact_download_url` 或真实 artifact 仍可显示下载入口。
- `frontend/css/app.css`
  - 新增 RVC 模型操作区、分页、训练 preset、估算结果与移动端单列样式。
- `frontend/playwright_stage43b_factory_training_tuning_smoke.cjs`
  - 新增 Stage43B smoke。

## Dashboard Studio 入口结果

- `task_stage41_ce1b32f2` 当前接口可读，状态为“完成”。
- 当前接口仍未返回 `can_open_studio`、`studio_url`、`final_artifact_download_url`。
- 产品侧没有伪造 Studio 按钮，Dashboard 显示“等待产物登记，Studio 入口暂不可用”。
- 如果后端返回 `can_open_studio=true` 或 `studio_url`，Dashboard 会显示 Studio 入口并优先使用 `studio_url`。

## Factory Engine Manager / RVC 结果

- Engine Manager 保留 RVC / UVR / SVC 三状态卡。
- RVC 模型区具备搜索、全部/已登记/未登记、有 index/无 index 过滤。
- 当前 `/api/engines/rvc/models` 仍是旧全量返回：`model_count=400`，没有真实分页字段。
- 产品侧兜底后首屏只渲染 8 条，避免 400 条铺满页面。
- 未登记模型显示“登记到肥鲨”按钮；当前 `/api/models/import-rvc` 未就绪时安全提示，不触发训练或 cover。

## 训练调参台 v0 结果

- 显示三预设：
  - 快速预览：先听方向，不追求极致质量。
  - 均衡推荐：默认建议，适合普通单文件训练。
  - 高质量慢速：更耗时，显存和时间风险更高。
- 当前 `/api/training/presets` 返回 404，因此使用产品侧默认预设。
- 当前 `/api/training/estimate` 不可用时使用产品侧粗估，展示 epochs、batch、sample rate、f0、index、GPU 风险、预计耗时。
- 调参台只做估算和解释，不创建训练 job。

## Studio 指定 job/track 打开结果

- Dashboard 现在不会在缺少 Studio 契约时把 completed cover 伪装成可打开。
- Studio 既有逻辑在 URL 指定 job 时会加载该 job；失败时不会自动替换为其他旧成品。
- 更明确的失败空态文案仍可在后续继续整理。

## 移动端结果

- 900px Factory smoke 无横向溢出。
- RVC 模型列表仍只渲染 8 条。
- 训练 preset 在移动端单列展示。

## 浏览器 Smoke 结果

- `node frontend/playwright_stage43b_factory_training_tuning_smoke.cjs`：通过。
- 无 `pageerror`。
- 无 `/api/process/*`。
- 无 `POST /api/train`。
- 截图：`output/playwright/stage43b_factory_training_tuning.png`

## 必测结果

- temp `.mjs` `node --check`：
  - `frontend/js/jobs.js`
  - `frontend/js/models.js`
  - `frontend/js/cover.js`
  - `frontend/js/factory/main.js`
  - `frontend/js/studio.js`
  - `frontend/js/train.js`
  - 结果：通过。
- `node --check frontend/playwright_stage43b_factory_training_tuning_smoke.cjs`：通过。
- `node frontend/playwright_stage43b_factory_training_tuning_smoke.cjs`：通过。

## 遗留问题

- 地基接口仍需补：
  - `can_open_studio` / `studio_url` / `final_artifact_download_url`
  - `/api/engines/rvc/models` 后端真分页、搜索、过滤
  - `/api/models/import-rvc`
  - `/api/training/presets`
  - `/api/training/estimate`
- 产品侧当前均有降级，不阻塞页面验收。
