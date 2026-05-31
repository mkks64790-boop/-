# Stage 26 Handoff

这次发给工作 agent，继续保持固定两份文件即可：

1. `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-26-real-audio-training-acceptance-prompt.md`
2. `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-26-real-audio-training-acceptance-report.md`

这轮的关键不是泛维护，而是围绕两份真实桌面样本做训练验收与分流收口：

- 长样本：
  - `C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3`
  - 约 `45分10秒`
  - 应视为单文件快速训练候选
- 短样本：
  - `C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3`
  - 约 `15分33秒`
  - 不应被误视为合规单文件长干声

这轮要点：

- 后端不能再只按 `file_count` 判定训练策略
- 前端要能把素材判定和下一步建议说清楚
- 长样本要真实进入训练链
- 短样本要么被拒绝，要么被明确分流
- 必须新增可重复执行的 Stage 26 真实验收脚本

这份 handoff 只是给你自己对照用，不必额外再发给工作 agent。
