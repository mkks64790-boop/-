# Stage 38B 产品 Agent 汇报

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## 任务结论

```text
是否完成：是
是否启动真实训练：否
是否修改后端主链：否
```

## 修改文件清单

```text
frontend\js\jobs.js
frontend\css\app.css
frontend\playwright_stage38b_training_failure_ux_smoke.cjs
docs\agent-md\worker\stage-38b-training-failure-ux-report.md
```

## 修复点对照

### 1. 训练失败诊断卡

```text
是否完成：是
识别 timeout：是，timed out after 3600 seconds 显示为“训练超时”
识别 duplicate exp_name：是，同一 job 多个 feishark_v_* 会提示重复派发/恢复冲突
识别 manual stop / unknown：是，兼容人工停止/进程中断、RVC 脚本异常、未知失败
```

### 2. 最近阶段日志降噪

```text
截断长度：摘要按 160 字以内生成，CSS 限制为最多 2 行
是否保留完整原文入口：是，完整内容进入阶段日志抽屉里的“查看原文”
是否避免 warning 撑爆页面：是，FutureWarning 显示摘要，不再直接铺满卡片
```

### 3. 阶段日志抽屉

```text
是否支持滚动：是，原文区域 max-height 220px
是否支持查看原文：是，每条日志有 details / summary
是否保护 command/path 换行：是，原文使用 monospace、pre-wrap、overflow-wrap:anywhere
```

### 4. 重试防误触

```text
高风险失败任务按钮状态：禁用“修复后重试”
提示文案：先修地基，不要再次启动同一训练，避免重复派发。
```

### 5. 训练路线图恢复建议

```text
失败在 train_core 时显示内容：核心训练失败后不会自动生成可用模型，必须完成 index 和 model register 后才会进入模型库。
exp_name 显示方式：检测到实验名：feishark_v_62f76886、feishark_v_2860bda4。
```

### 6. 完成/失败提醒

```text
完成提醒：训练完成，模型已登记。
失败提醒：训练失败，已停止，请查看失败诊断。
防重复提醒机制：按 job_id + 目标状态做 15 秒节流。
```

## 验证记录

```powershell
$tmp = Join-Path $env:TEMP 'feishark_jobs_check.mjs'; Copy-Item -LiteralPath 'frontend\js\jobs.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
$tmp = Join-Path $env:TEMP 'feishark_train_check.mjs'; Copy-Item -LiteralPath 'frontend\js\train.js' -Destination $tmp -Force; node --check $tmp; Remove-Item -LiteralPath $tmp -Force
node --check frontend\playwright_stage38b_training_failure_ux_smoke.cjs
node frontend\playwright_stage38b_training_failure_ux_smoke.cjs
```

说明：

```text
仓库 package.json 当前为 "type": "commonjs"，直接运行 node --check frontend\js\jobs.js / frontend\js\train.js 会把浏览器 ES module 的 import 当作 CommonJS 语法错误。
因此使用临时 .mjs 副本做等价语法检查，两个前端模块均通过。
```

浏览器 smoke：

```text
截图路径：D:\FeiSharkStudio-v2\output\playwright\stage38b_training_failure_ux.png
验证页面：http://127.0.0.1:8000/
验证任务：train_010253ec08f0
验证结论：失败诊断卡出现；最近阶段日志已降噪；阶段日志原文可展开且可滚动；高风险训练失败任务不再给裸重试误导。
```

## 风险与遗留

```text
等待 Stage 38A 后端结构化字段：失败原因、duplicate exp_name、checkpoint 恢复入口、可安全重试状态。
当前仍是兼容旧日志的前端启发式判断：timeout/manual stop/script exception/duplicate exp_name/checkpoint 线索均来自 job error_log 与 stage logs message/detail_json。
```
