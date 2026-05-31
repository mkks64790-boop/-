# Stage 36 交接：Studio ffmpeg DSP v0 渲染

## 给地基 Agent

发送这两个文件：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-36a-studio-ffmpeg-dsp-v0-prompt.md
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-36a-studio-ffmpeg-dsp-v0-report.md
```

## 给产品 Agent

产品 Agent 必须等地基 Agent 完成 Stage 36A 并写完报告后再开始。

发送这两个文件：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-36b-studio-render-mode-ux-prompt.md
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-36b-studio-render-mode-ux-report.md
```

## 本阶段边界

- Stage 36A：后端 ffmpeg DSP v0、capabilities、artifact/versions/master 合同。
- Stage 36B：Studio 输出模式 UI、版本抽屉展示、前端 smoke。
- 本阶段不接 VST。
- `copy_only_no_dsp` 继续表示“只登记草稿，不改变真实音频”。
- `ffmpeg_dsp_v0` 才表示“后端已生成真实处理版音频”。
