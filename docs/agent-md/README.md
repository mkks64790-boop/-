# Agent MD 工作流

以后这个项目的阶段指令、执行汇报、转达说明统一落到这里，避免只停留在聊天记录里。

**重要更新（Stage60 Governance 后）**：本流程已升级为“功能交付 + 强制治理”双轨制。治理不再是可选，而是制度。

## 核心原则（宪法级）

- **治理优先于功能**：每 1-2 个 Feature Sprint 后，必须执行一次 Governance Sprint。
- 所有工作必须遵守 `docs/ARCHITECTURE_CONSTITUTION.md`。
- 跨 3 个以上核心文件的重大改动，必须先在 `docs/adr/` 写入 ADR 并获得批准。

## 目录约定

- `architect/`
  - 架构师给工作 agent 的阶段提示词
  - 每一轮一个独立 `.md` 文件
- `worker/`
  - 工作 agent 完成后的阶段汇报（**必须包含 Debt Delta、Invariant Violations、Simplification Opportunities**）
  - 每一轮一个独立 `.md` 文件
- `handoff/`
  - 给人转达时用的一页式说明
- `docs/adr/`（仓库级目录）
  - Architecture Decision Records
  - 重大设计决策必须有记录

## 文件命名建议

- 架构师提示词：`stage-XX-主题-prompt.md`
- 工作汇报：`stage-XX-主题-report.md`
- 转达说明：`stage-XX-主题-handoff.md`
- ADR：`docs/adr/NNNN-主题.md`（从 0001 开始）

## 使用规则（强制）

1. 架构师阶段指令先写入 `architect/`
2. **工作 agent 必须先阅读**：
   - `docs/ARCHITECTURE_CONSTITUTION.md`
   - 最近的相关 ADR
   - 当前阶段的 architect prompt
3. 工作 agent 完成后，必须把结果按模板回填到 `worker/`，**报告必须包含以下固定章节**：
   - 改了哪些文件
   - Debt Delta（本次新增/减少了多少技术债，具体量化）
   - Invariant Violations（违反了宪法哪些条款）
   - Simplification Opportunities（本次有机会简化但未做的地方及理由）
   - 还有哪些已知限制
4. 后续验收、复盘、补修，统一拿 `architect/` 和 `worker/` 两份文件对照
5. `handoff/` 只负责把本轮要发给工作 agent 的路径说明清楚

## 节奏要求（双轨制）

- **Feature Sprint**：交付用户可见能力。architect prompt 必须包含“债务评估”和“最小化新增复杂度”要求。
- **Governance Sprint**（每 1-2 个 Feature Sprint 必须有 1 个）：**只做治理，不准加新功能**（除非是支撑重构的最小必要）。
  - 典型任务：服务收敛、DB 层治理、legacy 淘汰规划、一致性审查、宪法演进。
  - 必须产出可执行的偿还计划。

## 默认转达方式

实际发给工作 agent 时，优先只给这两件事：

1. 让它严格执行对应的 `architect/stage-XX-...-prompt.md`
2. 让它把结果回填到对应的 `worker/stage-XX-...-report.md`（并强制包含治理章节）

`handoff/` 文件你自己看就行，用来避免找错文件，不必每次也一起发过去。

**违背本规则的 agent 工作将被视为无效，需要重做或阻断。**
