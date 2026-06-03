# Stage 46B：UVR Runner 时长保真修复

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本轮是核心修复，不是继续分析。目标是让 UVR 分离输出时长不再从 `45s` 缩成 `26.807s`。

## 已确认根因

Stage46A 已经确认当前 runner 存在系统性时长缩短：

```text
15s -> 8.928s   ratio=0.5952
30s -> 17.868s  ratio=0.5956
45s -> 26.807s  ratio=0.5957
```

根因高度匹配：

```text
chunk_seconds=5
frames_per_chunk=int(5*44100/512)=430
model_frames=256
256/430=0.5953
```

当前模板在 `backend\vocal_separator.py` 的 `_RUNNER_SCRIPT` 里把每个 5 秒 STFT chunk 裁成 256 帧，直接丢掉约 40% 时间帧。

## 必须修改

### 1. 修复 FeiShark 控制的 runner 模板

修改：

```text
backend\vocal_separator.py
```

重点修 `_RUNNER_SCRIPT`。

要求：

- 不再使用 `chunk_seconds=5` 推出 430 帧再裁成 256。
- 直接以 `model_frames=256` 作为时间窗口步长。
- 每个 chunk 的 `actual_frames = end_f - start_f` 必须在 padding 前记录。
- 如果最后一个 chunk 不足 256 帧，只 pad 到模型输入，推理后只取回 `actual_frames`。
- 频率维度裁剪/补齐可以保留，时间维度禁止丢真实帧。

推荐结构：

```python
frames_per_chunk = model_frames
n_chunks = max(1, (n_total_frames + frames_per_chunk - 1) // frames_per_chunk)

for i in range(n_chunks):
    start_f = i * frames_per_chunk
    end_f = min((i + 1) * frames_per_chunk, n_total_frames)
    actual_frames = end_f - start_f
    chunk_stft = stft[:, start_f:end_f]
    ...
    if real.shape[1] < model_frames:
        pad_t = model_frames - real.shape[1]
        real = np.pad(real, ((0, 0), (0, pad_t)))
        imag = np.pad(imag, ((0, 0), (0, pad_t)))
    elif real.shape[1] > model_frames:
        raise RuntimeError("time chunk exceeds model_frames; chunking contract broken")
    ...
    v_spec = (out[0] + 1j * out[1])[:, :actual_frames]
```

### 2. ISTFT 必须强制原始采样长度

修改 runner：

```python
vocal_audio = librosa.istft(..., length=len(audio))
instr_audio = librosa.istft(..., length=len(audio))
```

注意：这不是用静音 padding 假修复，而是让 ISTFT 按原始 waveform 长度重建。真实 STFT 帧必须已经完整保留。

### 3. 增加 split_audio 后置时长检查

在 `split_audio()` 完成后，比较输入、vocal、instrumental 时长。

要求：

- 如果 vocal/instrumental 与输入时长差异超过 5%，返回失败或明确标记失败。
- 不允许在正式 cover/train 流程中把 mismatch stem 当成功。
- 错误信息必须包含：

```text
duration mismatch
input=...
vocal=...
instrumental=...
```

### 4. 保持外部 AudioPipeline 修改边界安全

不要手工硬改：

```text
C:\Users\ASUS\AudioPipeline\run_uvr5_split.py
```

允许通过 FeiShark 的 `_ensure_runner_script()` 由模板重新生成 runner。报告里说明这是 FeiShark 控制的自动生成脚本。

### 5. 更新验证脚本和测试

更新或新增测试，至少覆盖：

- `_RUNNER_SCRIPT` 不再包含时间维度裁掉真实帧的逻辑。
- `split_audio()` 有 duration mismatch 后置保护。
- `verify_stage45r_separation_quality_audit.py` 能输出修复后 ratio。

## 必须执行的真实验证

在修复后执行：

```powershell
python backend\verify_stage45r_separation_quality_audit.py --execute --limit 1 --clip-seconds 15
python backend\verify_stage45r_separation_quality_audit.py --execute --limit 1 --clip-seconds 30
python backend\verify_stage45r_separation_quality_audit.py --execute --limit 1 --clip-seconds 45
python -m pytest -q
python -m backend.self_check
python backend\verify_stage45r_separation_quality_audit.py
```

验收标准：

```text
15s ratio >= 0.95
30s ratio >= 0.95
45s ratio >= 0.95
duration_mismatch=false 或 risk!=high
BLOCK_TRAINING=false 仅在所有真实时长比通过后允许
```

如果修复后音质变差，也必须如实报告，不允许只看时长。

## 禁止事项

```text
禁止启动 train.py。
禁止 RVC 推理。
禁止删除/移动 D:\测试音乐。
禁止递归扫描 D:。
禁止用静音补齐 26.807s 到 45s 冒充修复。
禁止跳过 15/30/45 真实对照实验。
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-46b-uvr-runner-duration-preservation-patch-report.md
```

报告必须包含：

```text
是否完成
修改文件清单
是否启动 train.py：必须为否
是否 RVC 推理：必须为否
15/30/45 秒修复后 run_id
15/30/45 秒输入/输出时长表
duration_ratio 是否 >=0.95
BLOCK_TRAINING 最终状态
是否改动外部 AudioPipeline：只能由模板自动生成
音质主观风险说明
测试结果
```
