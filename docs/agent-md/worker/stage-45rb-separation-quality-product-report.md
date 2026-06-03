# Stage 45RB：分离质量实验室 UI 产品报告

> 返工说明：本报告中上一轮 smoke 属于 mock 数据结构验收，不能作为真实后端验收结论。真实 API 验收已由 `docs/agent-md/worker/stage-45r-hotfix-product-real-api-smoke-report.md` 覆盖；最终以 hotfix 报告为准。

## 是否完成

已完成产品侧 Stage 45RB。

已在 Factory 的 Local AI Engine 下方新增“分离质量实验室”，用于展示 D 盘测试音乐候选、最近 eval runs、三轨 A/B 试听和电流音排查指标。前端不会自动训练、不会自动 RVC 推理、不会触发整首歌扫描。

## 修改文件清单

- `frontend/factory.html`
- `frontend/js/factory/main.js`
- `frontend/css/app.css`
- `frontend/playwright_stage45rb_separation_quality_lab_smoke.cjs`
- `docs/agent-md/worker/stage-45rb-separation-quality-product-report.md`

## 分离质量实验室 UI 结果

- 新增 `#factorySeparationLabPanel`。
- 候选测试音乐区域：`#factorySeparationCandidatesList`。
- 最近 eval runs 区域：`#factorySeparationRunsList`。
- 支持选择 run，并自动读取 `GET /api/separation/eval/runs/{run_id}`。
- 如果地基接口未就绪，显示“等待地基接口”，按钮保持灰态。

接入接口：

- `GET /api/separation/eval/sources`
- `GET /api/separation/eval/runs`
- `GET /api/separation/eval/runs/{run_id}`
- `POST /api/separation/eval/run`

## A/B 播放器结果

已提供三轨区：

- 原曲 excerpt
- 分离人声 vocal
- 分离伴奏 instrumental

播放器不自动播放。分离产物不存在时显示“等待分离产物”。下载按钮只出现在 vocal / instrumental 分离产物上，不给原曲下载按钮，也不绑定训练或 RVC 行为。

## 电流音指标展示结果

指标面板按 run 的 `quality_report` / `metrics` 原样展示，不写死 PASS。

覆盖字段：

- `peak_db`
- `rms_db`
- `clipping_risk`
- `high_freq_energy_ratio`
- `zero_crossing_rate`
- `noise_risk`
- `suspected_causes`
- `next_step`

已加入直白排查提示：

- 高频噪声偏高：可能是 UVR 模型、采样率或输入压缩导致。
- 削波风险：可能是原曲或分离输出电平过高。
- 采样率异常：建议统一转 44.1k/48k 后再分离。

## 运行按钮安全限制

按钮文案为：

```text
只裁剪 45 秒短片段，不跑整首歌
```

点击后只会调用：

```json
{
  "limit": 1,
  "clip_seconds": 45
}
```

如果 `/api/separation/eval/*` 接口缺失，按钮禁用并显示“等待地基接口”。本阶段没有新增任何训练、RVC 推理、全盘扫描入口。

## 移动端结果

分离实验室布局在 1080px 以下压成单列。Stage45RB smoke 已验证 900px 视口无横向溢出。

## 浏览器 smoke 结果

已通过：

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage45rb_separation_quality_lab_smoke.cjs
node frontend\playwright_stage45rb_separation_quality_lab_smoke.cjs
```

Smoke 关键结果：

- `playerAudioCount = 3`
- POST `/api/separation/eval/run` payload 为 `{"limit":1,"clip_seconds":45}`
- `pageErrors = []`
- `unsafeCalls = []`
- desktop/mobile 均无横向溢出
- 截图：`output/playwright/stage45rb_separation_quality_lab.png`

## 遗留问题

- 当前产品侧已准备好接口接入；如果 Stage45RA 后端尚未提供真实 `/api/separation/eval/*`，页面会停留在“等待地基接口”灰态。
- 真实 UVR 分离质量、D 盘候选发现和 `quality_report.json` 指标准确性需要由地基 Agent 的 Stage45RA 实现与验收确认。
