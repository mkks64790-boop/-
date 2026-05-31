# Agent MD 工作流

以后这个项目的阶段指令、执行汇报、转达说明统一落到这里，避免只停留在聊天记录里。

## 目录约定

- `architect/`
  - 架构师给工作 agent 的阶段提示词
  - 每一轮一个独立 `.md` 文件
- `worker/`
  - 工作 agent 完成后的阶段汇报
  - 每一轮一个独立 `.md` 文件
- `handoff/`
  - 给人转达时用的一页式说明
  - 作用是把“本轮该看哪个 prompt、该把结果写到哪个 report”说明白
  - 这个目录是辅助说明，不是必须再单独塞给工作 agent 的第三份任务书

## 文件命名建议

- 架构师提示词：`stage-XX-主题-prompt.md`
- 工作汇报：`stage-XX-主题-report.md`
- 转达说明：`stage-XX-主题-handoff.md`

## 使用规则

1. 架构师阶段指令先写入 `architect/`
2. 工作 agent 完成后，必须把结果按模板回填到 `worker/`
3. 后续验收、复盘、补修，统一拿 `architect/` 和 `worker/` 两份文件对照
4. `handoff/` 只负责把本轮要发给工作 agent 的路径说明清楚，减少传达混乱

## 默认转达方式

实际发给工作 agent 时，优先只给这两件事：

1. 让它严格执行对应的 `architect/stage-XX-...-prompt.md`
2. 让它把结果回填到对应的 `worker/stage-XX-...-report.md`

`handoff/` 文件你自己看就行，用来避免找错文件，不必每次也一起发过去。
