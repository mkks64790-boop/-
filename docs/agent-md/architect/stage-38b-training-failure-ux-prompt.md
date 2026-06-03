# Stage 38B：训练失败态与日志降噪 UX 修复（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”Agent。本阶段只做前端 UI/UX、轻量浏览器验收和文案修复。不要修改训练主链，不要启动真实训练，不要占用 GPU。

## 启动前必须阅读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-38-training-failure-web-audit.md
D:\FeiSharkStudio-v2\frontend\js\jobs.js
D:\FeiSharkStudio-v2\frontend\js\ui.js
D:\FeiSharkStudio-v2\frontend\js\train.js
D:\FeiSharkStudio-v2\frontend\css\app.css
D:\FeiSharkStudio-v2\frontend\index.html
```

## 当前 Web 问题

真实失败任务：

```text
job_id = train_010253ec08f0
status = 失败
current_stage = train_core
```

页面现在的问题：

1. “最近阶段日志”把完整 command 和 torch warning 直接展示出来，用户看不到重点。
2. 同一 job 的两个 exp_name 混在一起，用户不知道这是重复派发/恢复冲突。
3. 失败摘要只说“最后失败在核心训练”，没有说明是“3600 秒超时”。
4. 失败任务仍给普通“重试”按钮，没有高风险提示。
5. 训练路线图显示 7/9，但不能告诉用户“已有 checkpoint，尚未 index/register”。
6. 顶部统计的完成数异常由地基修，但产品层不要用本地硬编码绕过。

## 禁止事项

- 禁止启动真实训练。
- 禁止调用 `/api/train` 提交真实音频。
- 禁止改后端训练策略。
- 禁止删除历史 job、模型、RVC 日志或权重。

## 必做任务

### 1. 增加训练失败诊断卡

在 Dashboard 任务详情中，对 `job.job_type === "train"` 且失败时展示一个清晰卡片。

卡片必须区分：

```text
训练超时
人工停止/进程中断
RVC 脚本异常
重复派发/多 exp_name 风险
未知失败
```

当 message 中包含：

```text
timed out after 3600 seconds
```

显示：

```text
核心训练超过后端保护时限，不是显存爆炸。当前模型尚未完成索引和登记。
```

当同一 job 的 stage logs 中出现多个 exp_name，例如：

```text
feishark_v_62f76886
feishark_v_2860bda4
```

显示：

```text
检测到同一任务生成了多个 RVC 实验名，疑似重复派发/恢复冲突。修复前不要直接重试。
```

### 2. 最近阶段日志降噪

改造 `renderRecentStageLogDigest`：

- 只显示最近 5 条仍可保留，但每条 message 只展示最多 120-180 字。
- 超长内容要单行/两行截断，不允许撑爆卡片。
- 对 command、traceback、warning 类内容显示“查看完整日志”提示，不直接铺满页面。
- `FutureWarning` 不应作为失败摘要主文案。
- 保留完整阶段日志抽屉，用于技术排查。

### 3. 阶段日志抽屉增加分类与滚动

改造 `renderJobStageLogs`：

- 每条日志显示 stage、status、time、短摘要。
- 原始 message 放到可展开 `<details>` 或“查看原文”区域。
- 原文区域必须有 `max-height` 和滚动条。
- path / command 使用 monospace，必须 `overflow-wrap:anywhere`。

### 4. 失败任务重试按钮防误触

对训练失败任务，如果失败原因为 timeout、duplicate exp、manual stop、unknown long-running error：

- 不要直接显示裸“重试”。
- 显示“修复后重试”或禁用按钮。
- 给用户提示：先修地基，不要再次启动同一训练，避免重复派发。

如果后端仍未提供结构化字段，就先通过 stage logs message 做兼容判断；等 Stage 38A 完成后再优先读取后端结构化字段。

### 5. 训练路线图补充“恢复建议”

对失败在 `train_core` 的训练任务，路线图下方显示：

```text
核心训练失败后不会自动生成可用模型。必须完成 index 和 model register 后，模型才会进入模型库。
```

如果日志中能识别到 checkpoint/exp_name，可显示：

```text
检测到实验名：feishark_v_xxx。若地基支持 checkpoint 恢复，可从已有权重继续索引/登记。
```

### 6. 完成/失败提醒预埋

保留现有轮询机制，增加前端 transition 提醒：

- 当 train job 从 active 变为 completed：toast 提醒“训练完成，模型已登记”。
- 当 train job 从 active 变为 failed：toast 提醒“训练失败，已停止，请查看失败诊断”。
- 防止 15 秒轮询重复弹同一个 job。

## 必测项

不跑真实训练，只跑前端轻量验证：

```powershell
node --check frontend\js\jobs.js
node --check frontend\js\train.js
```

如果本机浏览器可用，增加一个 Playwright smoke：

```text
打开 http://127.0.0.1:8000/
确认 train_010253ec08f0 详情中出现训练失败诊断卡。
确认最近阶段日志不会被超长 warning 撑爆。
确认阶段日志抽屉可展开且原文有滚动。
确认高风险训练失败任务不会给裸重试误导。
```

截图输出建议：

```text
D:\FeiSharkStudio-v2\output\playwright\stage38b_training_failure_ux.png
```

## 完成后写报告

使用：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-38b-training-failure-ux-report-template.md
```

