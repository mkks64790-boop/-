# Stage60 Bugfix: Small Debt-Repaying Bug Fixes (Governance Only - No New Features or Services)

**Project root**: `D:\FeiSharkStudio-v2`

**重要**：本阶段严格属于 Stage60 Governance 延伸的“小额债务偿还 bugfix”。**不是 Feature Sprint**。必须遵守 Architecture Constitution 和 Stage60 治理计划。

## Stage Boundary (Hard)

- **只做小的、孤立的 bug 修复和 hardening**（每个 fix 理想情况下影响 1-3 个文件）。
- **禁止**新增任何以 `stage59_`、`stage60_` 等里程碑命名的 service。
- **禁止**向 `backend/db.py` 添加任何新的 `_migrate_*`、`_backfill_*` 或大段 executescript 逻辑（small bug fixes in existing functions 允许，但必须极度克制）。
- **禁止**真实 UVR / RVC / GPU / ffmpeg 执行或任何会写入 raw audio/model 的操作。
- **禁止**扩大 main.py 职责（除非是极小的、配套的 bugfix，且有测试）。
- **禁止**任何 UI 改动或新产品功能。
- 当前工作树包含未提交的 Stage59C-4b 代码 + Stage60 治理文档，**本轮只允许小修复，不得大动这些未提交变更的结构**。
- 所有工作必须先阅读必读文件，并在思考中声明已遵守 Constitution。

## Required Reading (强制，先读完再思考)

**第一优先**（本 memory snapshot 是当前 Grok/其他 agent 的标准 handoff，必须最先阅读）：
- `docs/agent-md/handoff/stage-60-governance-memory-snapshot.md`

然后按顺序阅读：
1. `docs/ARCHITECTURE_CONSTITUTION.md`（铁律）
2. `docs/adr/0001-stage60-governance-sprint-and-process-upgrade.md`
3. `docs/adr/0002-stage60-debt-audit-stage59-db-legacy.md`
4. `docs/adr/0003-stage59-consolidation-proposal.md`
5. `docs/governance/stage60-db-governance-plan.md`（重点看 Current Hotspots）
6. `docs/governance/stage60-stage59-service-consolidation-plan.md`
7. `docs/governance/stage60-main-router-split-plan.md`
8. `docs/governance/stage60-legacy-retirement-map.md`
9. `docs/agent-md/worker/stage-60-governance-sprint-report.md`
10. `docs/agent-md/worker/stage-60-governance-review.md`（Grok 的审查报告，Verdict: Pass）
11. `docs/agent-md/worker/stage-59c4b-real-smoke-plan-report.md`（了解当前未提交的 c4b 变更）
12. `docs/agent-md/architect/prompt-template.md`（本 prompt 就是按它写的）
13. `docs/agent-md/worker/worker-report-template.md`（你的最终报告必须严格按此模板，包含 Debt Delta、Invariant Violations、Simplification Opportunities）

**必须在报告开头声明**：“已完整阅读 stage-60-governance-memory-snapshot.md + 以上所有必读文件，并严格遵守 Constitution 和治理模式。”

## Goal

利用 Stage60 刚建立的治理框架，进行**小额、快速、可验证的 bug 修复**，优先针对 governance plans 中列出的 “Current Hotspots” 和历史已知债务，**减少立即的风险和不一致性**，而不触及大重构（大重构留给 Stage60A+）。

优先级（从高到低）：
1. 可能导致状态不一致、清理遗漏、或双写不同步的 legacy `tasks` / `voice_assets` 访问路径的小修复。
2. 直接 `get_connection()` 调用点的明显 bug / 缺少错误处理 / 日志不足（但不做大 Repository 抽象）。
3. 近期 Stage59C-4b 相关的小集成/边界问题（如果有证据）。
4. 其他低风险、孤立的 runtime bug（需有重现证据或测试证明）。

**量化目标**：本次最多处理 3-5 个独立的小 bug/fix。每个必须有：
- 问题描述 + 根因
- 最小改动
- 新/更新的测试
- 验证命令

## Allowed Changes

- 后端 services / 工具类中的小修复（1-3 文件）。
- 增加/改进测试（unit / api / 验证脚本）。
- 改进日志、错误消息、边界检查。
- 小的兼容性/防御性代码（例如双表查询时增加一致性检查并记录 mismatch）。
- 更新相关文档或报告（如果必要）。

## Forbidden (再次强调)

- 任何新 service 文件（stage* 或其他）。
- 对 `backend/db.py` 的结构性改动或新增 backfill。
- 改动 job 执行核心（pipelines, strategies）除非极小且有 ADR 理由（本阶段没有）。
- 任何会使 real_execute_allowed 变 true 或运行真实引擎的操作。
- 大范围重构、router 拆分、facade 引入（这些是 Stage60A 的工作）。
- 跟踪任何 raw assets 到 git。

## Required Deliverables

1. **最多 3-5 个小修复**，每个有清晰的 commit 风格描述（即使不提交）。
2. **完整的 worker report**：严格按 `docs/agent-md/worker/worker-report-template.md` 写，文件名为 `docs/agent-md/worker/stage-60-bugfix-small-debt-fixes-report.md`
   - 必须包含：
     - Scope（明确只做小 bugfix）
     - Files Changed（列出所有，包括测试）
     - What Was Done（每个 bug 的描述 + 改动 + 理由）
     - **Debt Delta**（量化：修复了多少潜在不一致风险、减少了多少 direct access、是否引入新债等）
     - **Invariant Violations**（必须主动申报；理想为 None，并解释为什么没有违反）
     - **Simplification Opportunities**（本次有机会但因为治理边界没做的简化）
     - Validation（完整命令 + 输出）
     - Known Limits + Next Recommended Step（建议如何并入 Stage60A）
3. 所有测试必须通过（包括你新增的）。
4. 运行 `python -X utf8 backend\self_check.py` 并记录结果。
5. 资产扫描干净（无新 tracked audio/model/db）。

## Validation Commands (必须全部运行并记录输出)

```powershell
cd D:\FeiSharkStudio-v2

# 1. 针对性回归（至少包含受影响模块的测试）
python -m pytest tests/unit/test_lifecycle*.py tests/api/test_*.py -q --tb=short

# 2. 全量回归
python -m pytest -q

# 3. Self check
python -X utf8 backend\self_check.py

# 4. 资产扫描（必须无输出）
git ls-files | Select-String -Pattern '(\.wav|\.mp3|\.flac|\.m4a|\.aac|\.ogg|\.pth|\.index|\.sqlite|\.db)$'

# 5. Git 状态检查
git status --porcelain
git diff --stat
```

**额外**：如果修复涉及 c4b 未提交代码，额外运行：
```powershell
python backend\verify_stage59_uvr_ab.py --real-smoke-plan --confirm-execute --approval-token stage59-local-approval --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --entry-id stage59_redacted_cover_source --skip-file-exists
```

## How to Work (Extreme Honesty Mode)

1. 先完整阅读所有 Required Reading。
2. 基于 governance plans 的 Hotspots，**主动列出你发现的潜在 bug**（即使只修复其中一部分）。
3. 对每个计划修复的 bug：
   - 写清楚 “问题现象 / 根因 / 为什么是 bug / 影响范围”
   - 只做最小必要改动。
   - 增加针对性测试（最好能证明修复前会 fail，修复后 pass）。
4. 如果发现某个 “bug” 其实需要大改动 → **记录在 Known Limits 里，推荐给 Stage60A**，不要强行小改。
5. 最终报告必须诚实：如果本次只做了 2 个小 fix，也要写清楚为什么只做了这些（符合治理边界）。
6. 不要 `git add .` 或 commit。除非用户明确要求，否则只改工作区 + 写 report。

## Report Location

`docs/agent-md/worker/stage-60-bugfix-small-debt-fixes-report.md`

报告写完后，**必须**同时更新本 prompt 所在目录下的对应 handoff 或直接让用户把 report 发给 reviewer（Grok）进行跟进审查。

## Success Criteria (本阶段完成标准)

- 所有验证命令通过。
- Worker report 完整、诚实、包含所有强制章节。
- Debt Delta 为负或中性（减少了已知债务风险，没有新增大债）。
- 无 Invariant Violations（或有但已最小化并解释）。
- 没有违反本 prompt 的任何 Hard Boundary。
- 为 Stage60A 提供了可直接使用的 “已修复小问题列表”。

**违背本规则的任何输出将被视为无效，需要重做。**

---

**准备好后，严格执行以上所有要求。**
**开始前请在你的思考中明确写出：“我已阅读 Constitution + 所有列出的 ADR 和 governance plans，并将严格遵守。”**

Good luck. 记住：这次是**治理框架下的小额偿债**，不是堆功能。质量和纪律 > 数量。
