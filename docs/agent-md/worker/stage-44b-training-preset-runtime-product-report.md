# Stage 44B Training Preset Runtime Product Report

## 结论

已完成。产品侧已把训练调参台 preset 接入训练创建流：Factory 选择 preset 后写入共享状态，Dashboard 训练入口显示紧凑摘要，训练创建请求携带 `training_config_json` / `training_config` / `preset_key`。任务详情新增“训练配置”抽屉，旧任务显示“旧任务 / 默认配置”。

## 修改文件

- `frontend/factory.html`
  - 沿用 Stage43B 训练调参台，并作为 preset 选择源。
- `frontend/js/factory/main.js`
  - Factory preset 选择写入 `feishark.training-preset-key`。
  - 训练调参台展示最终 training_config JSON。
  - estimate 请求改用后端契约字段 `duration_seconds` / `gpu_label`。
- `frontend/index.html`
  - Dashboard 训练入口新增紧凑 preset 摘要与“去 Factory 调参”入口。
  - 任务详情新增“训练配置”默认收起抽屉。
- `frontend/js/train.js`
  - 读取 `/api/training/presets`，默认 balanced，兼容接口不可用时本地 fallback。
  - 训练提交前展示最终参数确认。
  - `/api/train` FormData 携带 `training_config_json`、`training_config`、`preset_key`。
- `frontend/js/jobs.js`
  - 训练 job 详情渲染训练配置抽屉。
  - 旧任务无 config 时显示“旧任务 / 默认配置”。
- `frontend/css/app.css`
  - 新增 Dashboard preset 摘要、training_config JSON、hash scroll-margin 样式。
- `frontend/playwright_stage44b_training_preset_runtime_smoke.cjs`
  - 新增 Stage44B smoke。

## Factory training_config 提交结果

Smoke 在 Factory 选择 `quality` 后，Dashboard 创建单文件训练时拦截 `/api/train`，payload 包含：

```json
{
  "preset_key": "quality",
  "epochs": 150,
  "batch_size": 6,
  "sample_rate": "40k",
  "f0_enabled": true,
  "index_enabled": true,
  "gpu_risk_label": "高",
  "estimated_runtime_label": "较长，请确认 GPU 空闲和散热稳定",
  "source": "product_ui",
  "entry_kind": "single"
}
```

Smoke 使用 route 拦截 `/api/train`，没有让真实训练进入后端。

## Dashboard 训练摘要结果

Dashboard 训练入口显示紧凑摘要：

```text
quality
150 epochs · batch 6 · 40k · GPU 高
去 Factory 调参
```

没有把完整调参台塞进 Dashboard。

## 任务详情训练配置结果

- 新增“训练配置”抽屉，默认收起。
- 旧任务显示“旧任务 / 默认配置”。
- 若后端后续返回 `training_config` 或 `metadata.training_config`，会展示：
  - 训练预设
  - epochs
  - batch_size
  - sample_rate
  - f0_enabled
  - index_enabled

## Sticky 导航修复结果

- Factory 关键区块增加 `scroll-margin-top`，从 Dashboard “去 Factory 调参”跳转到 `#factoryTrainingTuningPanel` 时不会被顶部 sticky 导航压住。
- Smoke 中 `factoryTrainingTuningPanel` 的 top 为正值，移动端无横向溢出。

## 浏览器 Smoke 结果

- `node frontend/playwright_stage44b_training_preset_runtime_smoke.cjs`：通过。
- 无 pageerror。
- 无 `/api/process/*`。
- `/api/train` 被 smoke 拦截，仅用于校验 payload，不真实提交训练。
- 截图：`output/playwright/stage44b_training_preset_runtime.png`

## 必测结果

- temp `.mjs` `node --check`：
  - `frontend/js/jobs.js`
  - `frontend/js/models.js`
  - `frontend/js/cover.js`
  - `frontend/js/factory/main.js`
  - `frontend/js/studio.js`
  - `frontend/js/train.js`
  - 结果：通过。
- `node --check frontend/playwright_stage44b_training_preset_runtime_smoke.cjs`：通过。
- `node frontend/playwright_stage44b_training_preset_runtime_smoke.cjs`：通过。

## 遗留问题

- 当前后端 `/api/train` 函数签名未在可见代码片段中显式声明 `training_config_json`，产品侧已随请求提交；是否真正保存并被 RVC runtime 使用，以 Stage44A 后端验收为准。
- 真实训练执行仍不在本阶段默认 smoke 范围内，Stage45 再做短样本真实训练验收。
