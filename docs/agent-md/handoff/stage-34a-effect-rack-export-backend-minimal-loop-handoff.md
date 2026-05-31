# Stage 34A Handoff

这是给地基 agent 的任务。先执行它，再让产品 agent 执行 Stage 34B。

只发两份：

1. `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-34a-effect-rack-export-backend-minimal-loop-prompt.md`
2. `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-34a-effect-rack-export-backend-minimal-loop-report.md`

核心目标：

- 新增 `POST /api/studio/effect-rack/export`
- 校验 track/job/artifact/effect_rack
- 复制源音频生成新的 `studio_effect_draft_master` artifact
- 明确 `processing_mode = copy_only_no_dsp`
- 不做真实 DSP / VST
- 不改前端

必须跑：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
```

这份 handoff 仅供你自己对照，不必额外发给地基 agent。
