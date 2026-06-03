# Stage 38 训练失败事故记录与修复分工

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## 当前结论

这次真实训练不是 CUDA OOM，而是后端核心训练超时。

失败任务：

```text
job_id = train_010253ec08f0
voice_name = 朱朱
strategy_key = single_long_preprocess
material = 单文件 45分10秒 / mp3 / 103.4 MB
```

第一条 RVC 实验：

```text
exp_name = feishark_v_62f76886
error = train.py timed out after 3600 seconds
```

第二条重复/恢复实验：

```text
exp_name = feishark_v_2860bda4
pid = 30884
status = 已由架构师手动停止
```

手动停止范围：

```text
只停止 train.py 训练进程 PID 30884。
没有停止 RVC WebUI：PID 3292 / http://127.0.0.1:7866。
没有停止后端监听进程：PID 34084 / http://127.0.0.1:8000。
```

当前 GPU 已回落：

```text
GPU-Util = 0%
Memory = 1533MiB / 8151MiB
```

旧实验已产生中间权重，但没有进入 index / register：

```text
D:\RVC\RVCv2\assets\weights\feishark_v_62f76886_e90_s6300.pth
D:\RVC\RVCv2\logs\feishark_v_62f76886\G_2333333.pth
D:\RVC\RVCv2\logs\feishark_v_62f76886\D_2333333.pth
```

## Web 真机检查结果

截图：

```text
D:\FeiSharkStudio-v2\output\playwright\stage38_dashboard_failed_train.png
```

浏览器页面：

```text
http://127.0.0.1:8000/
title = FeiShark Studio 工作台
```

页面实际问题：

1. Dashboard 顶部统计显示 `完成 0`，但任务列表里有大量完成任务，说明 `/api/jobs/summary` 状态归一化不完整。
2. 任务详情的“最近阶段日志”直接展示超长 `Command ... timed out after 3600 seconds` 和整段 torch warning，用户无法快速看懂真实失败原因。
3. 同一个 job 出现两个 exp_name：`feishark_v_62f76886` 和 `feishark_v_2860bda4`，产品层没有提示“疑似重复派发/恢复冲突”。
4. 失败任务仍显示普通“重试”按钮，但没有提示该任务当前属于“训练超时 + 重复实验残留”的高风险状态。
5. 训练路线图只显示阶段 7/9，不能说明“核心训练超时 3600 秒”和“已有 e90 checkpoint 但尚未登记模型”。

## 地基 Agent 修复方向

交给：

```text
docs\agent-md\architect\stage-38a-training-runtime-guard-prompt.md
docs\agent-md\worker\stage-38a-training-runtime-guard-report-template.md
```

核心目标：

```text
修训练超时、重复派发、状态统计、错误摘要、checkpoint 恢复入口。
```

## 产品 Agent 修复方向

交给：

```text
docs\agent-md\architect\stage-38b-training-failure-ux-prompt.md
docs\agent-md\worker\stage-38b-training-failure-ux-report-template.md
```

核心目标：

```text
修失败详情展示、阶段日志噪音、重复实验风险提示、重试防误触、训练完成/失败提醒。
```

## 禁止事项

在 Stage 38 修复完成前：

```text
不要再提交真实训练。
不要点击失败任务的“重试”。
不要启动第二个后端。
不要删除 D:\RVC\RVCv2\logs\feishark_v_62f76886。
不要删除 D:\RVC\RVCv2\assets\weights\feishark_v_62f76886_e90_s6300.pth。
```

