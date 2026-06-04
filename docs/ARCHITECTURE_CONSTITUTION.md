# FeiShark Studio 架构宪法 (Architecture Constitution)

**版本**: v1.0  
**生效日期**: 2026-06 (Stage60 Governance Sprint 开始)  
**拥有者**: 项目负责人（人类）  
**强制性**: 所有 AI agent、人类开发者、未来团队成员必须严格遵守。违反即为阻断事项。

## 核心原则

1. **治理优先于功能 (Governance Over Features)**
   - 长期可维护性 > 短期功能交付。
   - 每 1-2 个 Feature Sprint 之后，必须执行一次 Governance Sprint。
   - 禁止在没有偿还部分历史债务的情况下进入下一个重大功能阶段。

2. **人类是最终治理负责人 (Human is the Chief Governance Owner)**
   - AI（无论 GPT、Grok、Claude 或未来模型）是执行者、提议者、严格审查者。
   - 架构宪法、重大重构决策、ADR 批准权永远在人类手中。
   - AI 不得单方面决定改变核心抽象、数据模型或兼容策略。

3. **复杂度必须被主动压缩 (Complexity Must Be Actively Compressed)**
   - 禁止通过“再加一层”来解决问题。
   - 每次实现新功能时，必须同时寻找并执行至少一项简化（删除代码、合并服务、抽象收敛）。

4. **向后兼容是成本，不是美德 (Backward Compatibility is a Cost)**
   - legacy 路径（tasks ↔ jobs、voice_assets ↔ voice_models 等）必须有明确的淘汰时间表。
   - 长期背负双写、backfill 是技术债，不是“务实”。

## 硬性不变式 (Hard Invariants)

这些规则是铁律，任何改动都必须先修改本宪法并获得批准。

### DB 层
- **禁止**继续在 `backend/db.py` 中添加新的 `_migrate_*`、`backfill_*` 或大段 `executescript` 逻辑。
- 新数据库变更必须走独立的 migration 机制或 Repository 层（当前没有时，先建立最小抽象）。
- 所有直接裸 `get_connection()` + `execute` 的地方，必须逐步收敛到集中的数据访问层。
- 启动时重度 backfill 逻辑必须有上限（单次启动不得超过 N 秒，当前需测量并设定）。

### 服务层
- **禁止**再创建以 `stage59_`、`stage60_` 等里程碑命名的专项 service 文件。
- 现有 10 个 stage59_*_service.py 必须在 Stage60 期间进行清点与合并计划。目标是将专项服务数量显著降低，通过通用抽象实现。
- 新功能必须优先复用/扩展现有 service，而不是新建。

### 执行与状态
- Job 执行核心（job_service + pipelines + strategies）是圣域。任何改动必须先写 ADR 并通过严格 review。
- 状态机（status / current_stage / lifecycle_state）必须保持单一事实来源，避免多处推导 + 回填。
- compute_mutex、队列派发逻辑的改动必须经过人工批准。

### 路由与入口
- `backend/main.py` 不得继续膨胀为路由 + 业务逻辑 + 兼容 shim 的巨石。
- 计划进行 router 分层拆分（APIRouter），main.py 只保留启动、静态、调度、薄桥接。

### 文档与流程
- 跨 3 个以上核心文件的重大改动，必须先在 `docs/adr/` 写入 ADR。
- 所有 worker/agent 报告必须包含固定章节：
  - Debt Delta（本次新增/减少的技术债）
  - Invariant Violations（违反了本宪法哪些条款）
  - Simplification Opportunities（本次有机会但未执行的简化）
- 禁止“先实现功能，治理以后再说”。

## 里程碑与债务

- **Stage59 及之前**：能力建设期（已完成大量真实闭环，值得肯定）。
- **Stage60**：治理刹车期。重点是收敛复杂度、建立宪法、清理 Stage59 服务、DB 层治理、legacy 路线图。
- **未来**：只有在 Governance Sprint 确认骨架健康后，才允许大规模接真实 UVR / RVC 危险入口或新产品功能。

## 违反处理

- AI agent 必须在报告中主动申报违反。
- 人类 review 时发现违反，阻断合并/部署。
- 严重或反复违反的 agent prompt 必须被修订或禁用相关模式。

## 演进

本宪法由人类维护。任何修改必须：
1. 写 ADR 说明理由和影响。
2. 更新本文件。
3. 在下一次 Governance Sprint 中作为强制阅读材料。

**签名**：  
项目负责人（人类） - 2026-06

---

*本宪法是项目长期生存的护城河。功能可以迭代，宪法必须守护。*
