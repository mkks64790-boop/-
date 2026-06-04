# ADR 0001: Stage60 Governance Sprint & Agent-Driven Development Process Upgrade

**状态**: Proposed / In Progress (Stage60)  
**日期**: 2026-06  
**决策者**: 项目负责人（人类）  
**相关**: release-factory-blueprint.md, docs/agent-md/README.md, docs/ARCHITECTURE_CONSTITUTION.md

## 背景

项目经过大量阶段性开发（尤其是 Stage59 系列），已经建立了真实可运行的 UVR/RVC 闭环、artifact 管理、job 流水线、Factory/Studio 产品形态。

然而，代码库呈现有机生长特征：
- 出现 10 个以 `stage59_` 命名的专项 service（backend/services/）。
- `backend/db.py` 承担了大量 legacy 兼容、backfill、migrate 逻辑。
- `main.py` 持续膨胀，包含路由、调度、shim、直接 DB 操作。
- legacy 表（tasks、voice_assets）与现代表（jobs、voice_models）长期双写。
- 架构决策和治理主要依赖 architect prompt 的“本阶段目标”，缺乏跨阶段强制收敛机制。

之前的 agent-md 流程（architect/ + worker/ + handoff/）在**交付能力**上非常有效，但**治理权重过低**。结果是每一步局部合理，整体复杂度持续上升。

## 决策

1. **立即启动 Stage60 Governance Sprint**（非功能 sprint）。
   - 本阶段**只做治理，不接新真实 UVR/RVC 功能**（暂停 C-4c 等真实执行）。
   - 目标：把“架构 + 治理”角色权重提升到 feature 之上，建立长期可维护骨架。

2. **建立硬性宪法与 ADR 制度**。
   - 创建 `docs/ARCHITECTURE_CONSTITUTION.md` 作为铁律。
   - 建立 `docs/adr/` 目录，跨 3 个以上核心文件的重大改动必须先有 ADR。
   - 所有后续 architect prompt / agent 工作必须以宪法为必读文件。

3. **升级 Agent MD 工作流**。
   - 强制 Governance Sprint 节奏：每 1-2 个 Feature Sprint 后必须有 1 个 Governance Sprint。
   - worker report 必须包含固定章节：Debt Delta、Invariant Violations、Simplification Opportunities。
   - architect prompt 模板升级，增加“治理优先”和“债务评估”要求。

4. **具体治理范围（Stage60 优先级）**：
   - Stage59 服务清点与合并计划（目标显著降低专项服务数量）。
   - DB 层治理（禁止继续向 db.py 塞 backfill，收敛直接 SQL，规划 Repository / migration 抽象）。
   - main.py 路由与职责拆分规划。
   - legacy 路径（tasks→jobs、voice_assets→voice_models 等）淘汰路线图。
   - 全局一致性审查（状态机、命名、抽象层）。
   - 更新 agent-md 流程文档，使治理成为制度而非建议。

## 后果与取舍

**积极后果**：
- 停止复杂度雪球继续滚大。
- 为未来大规模真实引擎集成和团队协作打下可维护基础。
- 让 13 亿 token 的投资从“堆功能”转向“可持续演进”。

**风险与代价**：
- 短期会“看起来没那么快出新功能”。
- 需要投入 token 和精力做清理（这是必要的投资，而不是浪费）。
- 现有 stage59 代码需要重读和设计合并方案，可能有短期不适。

**不这么做的后果**（已观察到）：
- 继续堆 stage60/61/xx 服务。
- db.py 继续变神。
- 未来想加功能或修 bug 的成本指数级上升。
- 团队（即使是 AI 团队） onboarding 和协作困难。

## 实施计划（概要）

1. 人类批准本 ADR。
2. 创建 Constitution + 本 ADR。
3. 执行 Stage60 具体任务（服务清点、DB 审计、路线图等）。
4. 产出合并计划 + 第一个 governance report。
5. 更新 agent-md/README.md 和 prompt-template.md。
6. 把 Stage60 作为新基准，后续所有工作必须遵守。

## 后续演进

- 每季度回顾宪法有效性。
- Governance Sprint 产出的计划将成为下一次 Feature Sprint 的硬约束。

**批准**：  
人类项目负责人 - 2026-06
