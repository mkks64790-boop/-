# Stage 35 交接：Studio 版本账本 + 版本管理 UI

## 给地基 Agent

发送这两个文件：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-35a-studio-version-master-contract-prompt.md
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-35a-studio-version-master-contract-report.md
```

## 给产品 Agent

产品 Agent 必须等地基 Agent 完成 Stage 35A 并写完报告后再开始。

发送这两个文件：

```text
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-35b-studio-version-ux-cleanup-prompt.md
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-35b-studio-version-ux-cleanup-report.md
```

## 本阶段边界

- Stage 35A：后端版本账本、主成品合同、测试。
- Stage 35B：Studio 版本 UI 收口、前端 smoke。
- 本阶段不接真实 DSP/VST。
- `copy_only_no_dsp` 继续表示“只登记草稿，不改变真实音频”。
