# Stage 45RA：UVR 分离质量审计与电流音排查（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本阶段暂停真实训练，目标是用用户 D 盘测试音乐验证当前 UVR 分离链路质量，并定位“电流音/滋滋声/高频噪声”的来源。禁止启动 `train.py`，禁止 RVC 推理，禁止删除或移动用户音乐文件。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-45r-separation-quality-audit-plan.md
D:\FeiSharkStudio-v2\backend\vocal_separator.py
D:\FeiSharkStudio-v2\backend\audio_mixer.py
D:\FeiSharkStudio-v2\backend\services\engine_manager_service.py
D:\FeiSharkStudio-v2\backend\main.py
```

## 必做任务

### 1. 安全发现 D 盘测试音乐

不要递归扫完整 D 盘。

只允许有限候选路径：

```text
D:\测试音乐
D:\测试音频
D:\音乐测试
D:\MusicTest
D:\TestMusic
D:\FeiSharkStudio-v2\shared_data\separation_eval\input
```

如果都不存在，可以浅层扫描 `D:\` 的一级目录名，只挑包含以下关键词的目录：

```text
测试
音乐
音频
music
audio
test
```

音频格式：

```text
.wav .mp3 .flac .m4a .aac
```

最多选 5 首，优先选 30 秒以上、20 分钟以内的文件。不要移动、删除、重命名原文件。

### 2. 新增分离质量审计脚本

新增：

```text
backend/verify_stage45r_separation_quality_audit.py
```

默认 dry-run：

```powershell
python backend\verify_stage45r_separation_quality_audit.py
```

默认只做：

- 找测试音乐。
- 检查 ffmpeg。
- 检查 UVR / AudioPipeline。
- 输出候选文件列表。
- 不执行分离。

真实执行必须显式：

```powershell
python backend\verify_stage45r_separation_quality_audit.py --execute --limit 3 --clip-seconds 45
```

### 3. 执行分离时的产物规则

输出目录：

```text
shared_data/separation_eval/runs/{run_id}
```

每首测试音乐输出：

```text
original_excerpt.wav
vocal.wav
instrumental.wav
quality_report.json
```

要求：

- 先用 ffmpeg 裁剪短片段，不要直接跑整首长歌。
- 保持采样率、声道、时长信息可追踪。
- 调用现有 UVR 分离链路，不要绕开项目主流程。
- 失败也要留下 report，不要静默跳过。

### 4. 电流音基础指标

每个产物至少检测：

```text
duration_seconds
sample_rate
channels
peak_db
rms_db
clipping_risk
silence_ratio
high_freq_energy_ratio
zero_crossing_rate
dc_offset_estimate
```

不用追求专业音频算法完美，但要能粗略判断：

```text
是否爆音/削波
是否采样率异常
是否高频噪声偏高
是否有明显静音或异常电平
```

如果高频噪声/削波风险明显，`quality_report.json` 里给出：

```text
noise_risk = low | medium | high
suspected_causes
next_step
```

### 5. 新增轻量 API

建议新增：

```text
GET /api/separation/eval/sources
GET /api/separation/eval/runs
GET /api/separation/eval/runs/{run_id}
```

可选新增：

```text
POST /api/separation/eval/run
```

如果新增执行接口，必须默认限制：

```text
limit <= 3
clip_seconds <= 60
```

不要让前端一键跑完整 D 盘。

### 6. 测试与验证

新增或补充测试：

```text
tests/api/test_stage45r_separation_eval_api.py
```

覆盖：

- 无候选音乐时不报 500。
- sources 接口结构稳定。
- quality_report 结构稳定。
- execute 默认不会跑长音频。
- 不触发训练/RVC。

## 禁止事项

```text
禁止启动 train.py。
禁止调用 RVC 推理。
禁止跑整首长音频。
禁止递归扫完整 D 盘。
禁止删除、移动、覆盖用户测试音乐。
禁止把“电流音”简单归因给用户素材，必须提供指标和排查建议。
```

## 必测

```powershell
python -m pytest -q
python -m backend.self_check
python backend\verify_stage45r_separation_quality_audit.py
```

只有确认候选文件合理时，才执行：

```powershell
python backend\verify_stage45r_separation_quality_audit.py --execute --limit 3 --clip-seconds 45
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-45ra-separation-quality-backend-report.md
```

报告必须包含：

```text
是否完成
修改文件清单
候选测试音乐列表
是否执行分离
分离产物路径
质量指标摘要
电流音风险判断
疑似原因
下一步建议
是否启动 train.py：必须为否
是否调用 RVC 推理：必须为否
测试结果
```
