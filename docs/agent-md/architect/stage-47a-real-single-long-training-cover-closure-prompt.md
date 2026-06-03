# Stage 47A：真实单文件长干声训练 + 翻唱闭环验收

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本轮是超大任务，但必须有熔断，不允许无人值守乱跑。目标是跑通真实业务闭环：

```text
朱朱长干声 -> 单文件训练 -> 新模型登记 -> 固定 UVR 翻唱 -> 混音产物 -> Studio 可试听
```

## 已确认前置条件

UVR 时长保真已修复：

```text
latest fixed run: stage45r_20260602_193728_d0f83e7c
duration_ratio=1.0
BLOCK_TRAINING=false
```

可用干声：

```text
C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3
duration=2709.995s
size=108400926
```

辅助干声：

```text
C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3
duration=932.702s
size=37309203
```

测试音乐优先选择低削波风险文件：

```text
D:\测试音乐\如愿-孔老师.wav
D:\测试音乐\画心-孔老师.wav
```

## 总体策略

优先用 FeiShark 已有 job/service/API 路径跑，不要绕过工程体系直接野跑。

任务分三层：

```text
Layer 1: 环境/资源/数据预检
Layer 2: 真实训练闭环
Layer 3: 新模型真实 cover smoke
```

任何一层失败，立即停止后续层，写清楚原因。

## Layer 1：预检

必须检查并报告：

- FastAPI 是否运行在 `127.0.0.1:8000`。
- 当前 GPU 是否已有训练/推理进程占用。
- 可用磁盘空间。
- RVC/训练依赖是否通过既有 preflight。
- 最新 UVR fixed run 是否仍为 `BLOCK_TRAINING=false`。
- 两个桌面干声是否存在、时长是否与上方一致。
- 训练 job 队列/资源锁是否空闲。

如果 GPU 已满或训练进程仍在跑，不要强行抢占，直接报告 blocked。

## Layer 2：真实单文件长干声训练

使用：

```text
C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3
```

要求：

- 按“单文件快速训练”路线进入：上传/接收文件 -> 秋叶/RVC 原生预处理切片 -> 特征提取 -> 训练 -> index -> 模型登记。
- 不允许走多文件批量路线。
- 不允许覆盖旧的 `朱朱_recovered_e90` 模型。
- 新模型名建议：

```text
朱朱_stage47_single_long
```

- 新 job/model 必须有唯一 id。
- 训练必须有日志、进度、阶段状态。
- 如果训练参数可控，使用 smoke/fast preset，不要直接开生产级长训。
- 如果系统只能按固定训练流程跑，也必须记录实际命令、epoch、batch、GPU、耗时。

墙钟熔断：

```text
如果 30 分钟内没有进入训练/特征提取的明确阶段，停止并报告。
如果训练超过 2 小时仍无 checkpoint/index 产出，停止或标记 blocked，不要无限等待。
```

## Layer 3：新模型真实 cover smoke

训练成功并模型登记后，选择一个测试音乐跑短 cover smoke：

优先：

```text
D:\测试音乐\如愿-孔老师.wav
```

要求：

- 使用修复后的 UVR runner。
- 分离输出时长必须与输入片段接近，ratio >= 0.95。
- 使用新训练模型进行 RVC 推理。
- ffmpeg 混音产出最终 wav。
- 产物必须登记到 job artifacts，并可通过 API 下载。
- Studio 页面必须能拿到这个 cover 产物。

如果完整歌曲过长，允许先做 45-90 秒受控 smoke，但必须写清楚不是正式完整翻唱。

## 必须跑的验证

```powershell
python -m pytest -q
python -m backend.self_check
python backend\verify_stage45r_separation_quality_audit.py
```

训练/cover 完成后追加验证：

- 查询新 training job detail。
- 查询新 model detail。
- 查询新 cover job detail。
- 下载最终 artifact，确认 `content-type=audio/wav` 或合理音频类型。
- 确认没有重复 final artifact。

## 禁止事项

```text
禁止删除、移动、重命名 C:\Users\ASUS\Desktop\干声文件 内文件。
禁止覆盖历史模型。
禁止绕过 job/service 体系直接把结果塞数据库。
禁止同时跑多个训练。
禁止训练时并发 cover 抢 GPU。
禁止无限等待。
禁止把失败报告写成成功。
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-47a-real-single-long-training-cover-closure-report.md
```

报告必须包含：

```text
是否完成
预检结果
是否启动 train.py / 训练命令
训练 job_id
模型 model_id / pth / index
训练耗时
cover job_id
cover 输入音乐
UVR 输入/输出时长 ratio
最终 artifact 路径与下载 API
Studio 是否可读取
失败/阻塞原因
测试结果
```
