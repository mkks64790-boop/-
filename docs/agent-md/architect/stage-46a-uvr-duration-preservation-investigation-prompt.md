# Stage 46A：UVR 分离时长截断根因排查与保真策略

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本轮进入真正的分离质量根因排查。不要训练，不要 RVC 推理。

## 当前阻塞事实

最新真实 UVR 质检 run：

```text
stage45r_20260602_171704_201ec7ff
```

三组结果都存在同一个严重问题：

```text
original_excerpt.wav = 45.0s
vocal.wav            = 26.807s
instrumental.wav     = 26.807s
duration_ratio       = 0.5957
duration_mismatch    = true
duration_risk        = high
BLOCK_TRAINING       = true
```

这个问题没有解决前，禁止恢复训练和正式翻唱。

## 本轮目标

找出为什么 45 秒输入经过 UVR 后变成 26.807 秒，并给出可执行修复策略。优先定位：

```text
C:\Users\ASUS\AudioPipeline
D:\FeiSharkStudio-v2\backend\vocal_separator.py
D:\FeiSharkStudio-v2\backend\services\separation_eval_service.py
```

## 必须排查

### 1. 检查 FeiShark 调用 UVR 的参数

确认：

- 传给 AudioPipeline 的输入文件是不是完整 45 秒。
- UVR 输出前后是否有重命名、搬运、覆盖、截断。
- 是否只取了某个 chunk、segment、buffer 的前半段。
- 是否存在 sample rate、mono/stereo、ffmpeg trim 参数错误。

### 2. 检查 AudioPipeline / UVR runner

只读优先检查，不要破坏外部引擎目录。

确认：

- `run_uvr5_split.py` 或等价脚本是否存在固定 chunk 长度。
- 是否有 STFT/ISTFT overlap、padding、hop size、batch chunk 截断问题。
- 是否使用了临时输出但 FeiShark 取错文件。
- 是否模型只输出了一段，后续段没有拼回。

### 3. 做最小对照实验

允许执行短片段 UVR 质检，但必须严格限额：

```text
limit <= 1
clip_seconds <= 45
```

要求至少比较：

- 15 秒 excerpt -> vocal/instrumental 时长
- 30 秒 excerpt -> vocal/instrumental 时长
- 45 秒 excerpt -> vocal/instrumental 时长

如果 15/30/45 都按比例缩短，说明 runner 有系统性输出比例问题。
如果只有 45 秒被截断，说明 chunk/padding 边界有问题。

### 4. 不要急着“补静音糊住”

禁止只用 ffmpeg padding 把 26.807s 补成 45s 就宣布修复。

可以提出临时降级方案，但必须区分：

```text
真实修复：UVR 输出完整 stem。
临时兜底：检测 mismatch 后禁止训练，只允许试听。
不可接受：静音补齐后放开训练。
```

### 5. 输出工程判断

最终必须给出：

- 根因候选排序。
- 证据路径。
- 哪个脚本/参数最可能导致截断。
- 推荐修复方案。
- 是否需要换 UVR 模型或换 MDX23C/UVR 引擎。
- 是否可以恢复训练：默认必须为否，除非时长 mismatch 真正消失。

## 禁止事项

```text
禁止启动 train.py。
禁止 RVC 推理。
禁止删除/移动 D:\测试音乐。
禁止递归全盘扫描 D:。
禁止修改 C:\Users\ASUS\AudioPipeline，除非先复制到 FeiShark 可控目录并说明。
禁止用 padding 静音补齐冒充修复。
```

## 必测

```powershell
python -m pytest -q
python -m backend.self_check
python backend\verify_stage45r_separation_quality_audit.py
```

如执行对照实验，必须把 run_id、输入时长、输出时长、duration_ratio 写清楚。

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-46a-uvr-duration-preservation-investigation-report.md
```

报告必须包含：

```text
是否完成
是否启动 train.py：必须为否
是否 RVC 推理：必须为否
对照实验 run_id
15/30/45 秒输入输出时长表
根因候选排序
推荐修复方案
BLOCK_TRAINING 是否仍为 true
测试结果
```
