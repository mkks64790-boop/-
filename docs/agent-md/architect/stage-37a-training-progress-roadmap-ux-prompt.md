# Stage 37A：训练进度路线图 + 防误关提醒（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”agent。本阶段只做前端 UI/UX 修补和前端 smoke，原则上不改后端训练主链。目标是解决用户在训练模型时看不懂当前进度、误以为卡住并关闭训练的问题。

## 背景

当前真实训练任务示例：

```text
job_id = train_010253ec08f0
strategy_key = single_long_preprocess
current_stage = train_core
status = 训练中
voice_name = 朱朱
```

这个任务已经完成：

```text
train_dataset_prepare
train_preprocess
train_pitch_extract
train_feature_extract
```

现在正在：

```text
train_core
```

后面还会继续：

```text
train_index
train_register_model
```

问题不是训练没跑，而是 Dashboard 任务详情里的“下一步”现在只显示通用兜底：

```text
下一步：等待当前阶段完成。
```

这会让用户以为训练卡住。必须修。

## 启动前必须读取

```text
D:\FeiSharkStudio-v2\frontend\js\jobs.js
D:\FeiSharkStudio-v2\frontend\js\ui.js
D:\FeiSharkStudio-v2\frontend\index.html
D:\FeiSharkStudio-v2\frontend\css\app.css
D:\FeiSharkStudio-v2\backend\strategies\train_single_long_strategy.py
D:\FeiSharkStudio-v2\backend\strategies\train_multi_clean_strategy.py
D:\FeiSharkStudio-v2\backend\services\stage_log_service.py
```

## 目标

在 Dashboard 任务详情中，为训练任务增加清晰的“训练路线图 / 当前阶段 / 下一阶段 / 卡住判断提醒”。

用户看到训练中任务时，必须能一眼知道：

- 现在在哪一步。
- 前面哪些步骤已经完成。
- 后面还剩哪些步骤。
- 当前阶段是否本来就很久。
- 什么时候应该等，什么时候才该怀疑卡住。
- 训练结束后去哪里找模型。

## 必做任务

### 1. 增加训练阶段路线图

在 `frontend/js/jobs.js` 中新增训练阶段配置。

建议：

```js
const TRAIN_STAGE_FLOW = {
  single_long_preprocess: [
    "train_upload",
    "train_preflight",
    "train_dataset_prepare",
    "train_preprocess",
    "train_pitch_extract",
    "train_feature_extract",
    "train_core",
    "train_index",
    "train_register_model",
  ],
  multi_clean_direct: [
    "train_upload",
    "train_preflight",
    "train_dataset_prepare",
    "train_direct_prepare",
    "train_pitch_extract",
    "train_feature_extract",
    "train_core",
    "train_index",
    "train_register_model",
  ],
};
```

如果遇到未知 `strategy_key`，使用通用训练流程兜底。

### 2. 训练任务详情增加“路线图进度条”

在任务详情中，针对 `job.job_type === "train"` 渲染一个新的模块，例如：

```text
训练路线图
[✓ 上传] [✓ 预检] [✓ 预处理] [✓ Pitch] [✓ 特征] [● 核心训练] [○ 索引] [○ 模型登记]
```

要求：

- 已完成阶段显示完成态。
- 当前阶段显示高亮进行中。
- 未开始阶段显示等待态。
- 失败阶段显示失败态。
- 不要用“精确百分比”冒充真实 epoch 进度。
- 可以显示“阶段进度 6 / 8”，但要标注“阶段进度，不等于训练 epoch 百分比”。

### 3. 下一步文案按训练阶段精确化

替换当前 `getJobNextStepText(job)` 对训练进行中任务的粗糙兜底。

建议文案：

```text
train_preprocess -> 下一步：切片/重采样完成后进入 Pitch 提取。
train_pitch_extract -> 下一步：Pitch 提取完成后进入特征提取。
train_feature_extract -> 下一步：特征提取完成后进入核心训练。
train_core -> 下一步：核心训练完成后会自动进入索引训练，请不要关闭训练进程。
train_index -> 下一步：索引训练完成后会登记模型到模型库。
train_register_model -> 下一步：模型登记完成后，可在模型库查看并送入翻唱。
```

完成态：

```text
下一步：去模型库查看生成模型，或直接送入 AI 翻唱。
```

失败态：

```text
下一步：查看技术详情错误原文，确认 RVC 训练窗口是否报错，再决定重试。
```

### 4. 增加“核心训练防误关提醒”

当训练任务处于：

```text
current_stage = train_core
status = 训练中 / 进行中 / running / processing
```

必须显示醒目但不吓人的提醒：

```text
核心训练是最长阶段，可能长时间停在这里。只要 RVC 训练窗口、CPU/GPU 或 RVC logs 仍在更新，就不是卡死。不要关闭训练进程。
```

同时显示：

```text
卡住判断：
1. 短时间不跳阶段是正常的。
2. 如果 20-30 分钟没有任何 RVC 日志更新、CPU/GPU 也几乎不动，再怀疑卡住。
3. 如果失败，任务会进入失败态并显示错误摘要。
```

注意：前端不能直接读取本机 RVC 文件更新时间，所以不要在 UI 中假装自己知道 RVC logs 是否更新。只能用“如何判断”的提醒。

### 5. 训练创建后增加提示

在用户点击创建训练任务成功后，toast 或任务详情顶部必须显示：

```text
训练已启动。核心训练阶段可能较久，请不要关闭 RVC / 后端 / 当前训练进程；可在任务详情查看阶段路线图。
```

单文件快速训练和多文件精训都要覆盖。

### 6. 技术详情里显示最近阶段日志摘要

任务详情已有 stage logs 拉取能力时，增加一个简短“最近阶段日志”区域：

```text
最近阶段日志：
12:06 数据集准备完成
12:07 Pitch 提取完成
12:08 特征提取完成
12:08 核心训练开始
```

要求：

- 默认展示最近 5 条。
- 不要把超长 JSON 展开到主视图。
- 完整技术 JSON 仍保持折叠或放到技术详情里。

### 7. 新增前端 smoke

新增：

```text
frontend\playwright_stage37a_training_progress_roadmap_smoke.cjs
```

至少验证：

- Dashboard 能打开一个训练任务详情。
- 训练任务显示“训练路线图”。
- `train_core` 时显示“核心训练是最长阶段”或等价提醒。
- 下一步文案不再只是“等待当前阶段完成”。
- 能看到后续阶段“索引训练 / 模型登记”。
- 旧的任务详情基础结构仍存在。

如果本机没有正在训练的任务，smoke 可以用现有 API/数据库中最近的 train job；如果没有 active train，可以用已完成 train job 验证完成态路线图。

## 禁止事项

- 禁止修改训练后端执行流程。
- 禁止杀掉或重启正在训练的 RVC 进程。
- 禁止伪造真实 epoch 百分比。
- 禁止把“核心训练长时间不更新”判断成失败。
- 禁止把全部技术 JSON 默认展开。
- 禁止破坏 Dashboard / Factory / Studio 现有入口。

## 验证命令

必须运行：

```powershell
node frontend\playwright_stage37a_training_progress_roadmap_smoke.cjs
node frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs
node frontend\playwright_stage32b_three_page_layout_smoke.cjs
python -m pytest -q
```

如果 `python -X utf8 backend\self_check.py` 因 RVC Gradio 服务离线失败，不要归因到本阶段；但仍建议运行并在报告中说明。

## 输出报告

完成后填写：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-37a-training-progress-roadmap-ux-report.md
```

报告必须包含：

- 修改文件清单。
- 新增 UI 区域说明。
- 训练路线图阶段配置。
- 卡住判断提醒文案。
- 创建训练后的提示行为。
- smoke / pytest / self_check 结果。
- 未完成项和风险。
