# Stage 45RB：分离质量实验室 UI（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本阶段目标是在 Factory 或 Studio 增加“分离质量实验室”，让用户能用 D 盘测试音乐 A/B 试听原曲、人声、伴奏，并看到电流音排查指标。禁止自动训练，禁止自动 RVC 推理。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-45r-separation-quality-audit-plan.md
D:\FeiSharkStudio-v2\frontend\factory.html
D:\FeiSharkStudio-v2\frontend\studio.html
D:\FeiSharkStudio-v2\frontend\js\factory\main.js
D:\FeiSharkStudio-v2\frontend\js\studio.js
D:\FeiSharkStudio-v2\frontend\css\app.css
```

## 必做任务

### 1. 新增分离质量实验室

建议放在 Factory：

```text
Factory -> Local AI Engine 下方 -> 分离质量实验室
```

功能：

- 显示候选测试音乐。
- 显示最近 eval runs。
- 支持选择一个 run。
- 展示原曲 / 人声 / 伴奏 三个播放器。
- 展示质量指标和电流音风险。

### 2. A/B 试听布局

每个 run 至少展示：

```text
原曲 excerpt
分离人声 vocal
分离伴奏 instrumental
```

要求：

- 不自动播放。
- 三个播放器清楚标注。
- 下载按钮只下载分离产物，不触发训练。
- 如果产物不存在，显示“等待分离产物”。

### 3. 电流音排查面板

展示指标：

```text
peak_db
rms_db
clipping_risk
high_freq_energy_ratio
zero_crossing_rate
noise_risk
suspected_causes
next_step
```

文案要直白：

```text
高频噪声偏高：可能是 UVR 模型/采样率/输入压缩导致。
削波风险：可能原曲或分离输出电平过高。
采样率异常：建议统一转 44.1k/48k 后再分离。
```

### 4. 运行按钮安全限制

如果接入 `POST /api/separation/eval/run`：

- 默认 limit=1。
- 默认 clip_seconds=45。
- 按钮文案必须说明“只裁剪短片段，不跑整首歌”。
- 不允许一键扫完整 D 盘。

如果接口不存在，按钮置灰并显示“等待地基接口”。

### 5. 新增 smoke

新增：

```text
frontend/playwright_stage45rb_separation_quality_lab_smoke.cjs
```

验证：

```text
分离质量实验室存在。
候选测试音乐区域存在。
run 列表区域存在。
三轨播放器区域存在或空态明确。
电流音指标面板存在。
运行按钮不会触发训练或 RVC。
无 pageerror。
移动端无横向溢出。
```

## 禁止事项

```text
禁止自动训练。
禁止自动 RVC 推理。
禁止自动跑完整歌曲。
禁止一键扫完整 D 盘。
禁止把指标写死成 PASS。
```

## 必测

```powershell
$checks = @('frontend\js\jobs.js','frontend\js\models.js','frontend\js\cover.js','frontend\js\factory\main.js','frontend\js\studio.js','frontend\js\train.js'); foreach ($file in $checks) { $tmp = Join-Path $env:TEMP ((Split-Path $file -Leaf) + '.mjs'); Copy-Item -LiteralPath $file -Destination $tmp -Force; node --check $tmp; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Remove-Item -LiteralPath $tmp -Force }
node --check frontend\playwright_stage45rb_separation_quality_lab_smoke.cjs
node frontend\playwright_stage45rb_separation_quality_lab_smoke.cjs
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-45rb-separation-quality-product-report.md
```

报告必须包含：

```text
是否完成
修改文件清单
分离质量实验室 UI 结果
A/B 播放器结果
电流音指标展示结果
运行按钮安全限制
移动端结果
浏览器 smoke 结果
遗留问题
```
