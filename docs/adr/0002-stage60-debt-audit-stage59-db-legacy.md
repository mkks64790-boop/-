# ADR 0002 (Draft): Stage60 Debt Audit - Stage59 Services, DB Layer, Legacy Paths

**状态**: Draft - For Review in Stage60  
**日期**: 2026-06  
**基于**: 实时代码检查 + Constitution v1.0

## 当前债务快照（Stage60 开始时）

### 1. Stage59 服务膨胀
- 存在 10 个独立 `stage59_*_service.py` 文件：
  - stage59_approval_audit_service.py
  - stage59_artifact_persistence_service.py
  - stage59_execution_guard_service.py
  - stage59_execution_policy_service.py
  - stage59_job_artifact_promotion_service.py
  - stage59_listening_bridge_service.py
  - stage59_real_smoke_plan_service.py
  - stage59_transient_artifact_service.py
  - stage59_uvr_mock_execute_service.py
  - stage59_uvr_runner_contract.py
- 此外还有 short_chain_manifest_service.py、short_chain_uvr_service.py 与 Stage59 强相关。
- main.py 中有大量 Stage59 专属 Pydantic model（Stage59UvrAb*Request）和 /api/stage59/short-chain/uvr-ab/* 路由块（plan, readiness, mock-execute, approval-preflight, real-smoke-plan, execute-blocked 等）。
- **问题**：里程碑命名导致服务碎片化。每个新阶段都倾向于新建专项服务，而不是扩展/抽象现有能力。

**治理目标**：产出合并/抽象计划，将专项服务数量降低，职责收敛到通用 short_chain / artifact / approval 抽象。

### 2. DB 层债务（backend/db.py + 散落访问）
- db.py 包含：
  - 大量 legacy 表 + 现代表（tasks + jobs, voice_assets + voice_models）。
  - 启动时执行多轮 _migrate_add_column + _backfill_legacy_* + _dedupe + index 创建。
  - 直接裸 SQL CRUD 函数 + 复杂 status normalize 逻辑。
- 散落直接 DB 访问：
  - main.py 有直接 conn = get_connection()。
  - lifecycle_service.py 有大量 backfill_lifecycle_states 逻辑。
  - model_service.py、其他 services 均有 from ..db import get_connection + execute。
- **问题**：单文件承担过多（模型定义、迁移、CRUD、兼容 shim）。无集中数据访问层。启动 side-effect 重。

**治理目标**：
- 禁止继续向 db.py 添加 backfill/migrate。
- 规划轻量 Repository 抽象或分层。
- 收敛直接 get_connection 调用。
- 制定 legacy 表逐步淘汰路线（带时间表和迁移脚本）。

### 3. main.py 膨胀
- 同时承担：启动、CORS、静态服务、队列调度、大量 Pydantic model、路由（包括厚厚的 Stage59 路由块）、直接 DB 操作、兼容 shim。
- **问题**：违反单一职责，难以测试和演进。

**治理目标**：规划 APIRouter 拆分 + 职责下沉到 services/routers。

### 4. Legacy 双写路径
- 代码中持续维护 tasks ↔ jobs、voice_assets ↔ voice_models 的镜像写入 + backfill。
- 很多地方用 legacy_task_id、legacy_model_id 做桥接。
- **问题**：增加状态不一致风险、理解成本、测试负担。

**治理目标**：产出清晰的淘汰路线图（先只读兼容 → 迁移工具 → 最终移除）。

**Phase 4 更新 (Stage60D)**: Backfill retirement from startup completed (verifiers + init_db cleanup + docs). Dual-writes still active for compat (gradual retirement per legacy map).

## 建议的 Stage60 产出

1. Stage59 服务合并设计文档（哪些可以并入 short_chain_manifest / artifact / job 核心）。
2. DB 治理计划 + 最小 Repository 接口草案。
3. main.py 路由拆分提案。
4. Legacy 淘汰 ADR + 时间表。
5. 更新 Constitution（如果需要）和 agent-md 模板（已部分完成）。
6. 一个可执行的 “Governance Report” 放在 worker/ 或 handoff/。

## 下一步行动

人类 + AI（当前会话）协作完成以上审计细化和计划制定。
优先使用 Constitution 和本 ADR 作为约束。

**下一步**：由人类批准后，AI 开始具体服务清点 + 合并提案起草。
