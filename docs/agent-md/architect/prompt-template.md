# Stage XX Prompt Template

## 阶段标题

一句话写清楚这轮要解决的核心问题。**如果是 Governance Sprint，必须在标题中明确标注“Governance Only - No New Features”**。

## 背景

- 当前项目已经具备什么
- 这轮为什么要做
- 哪些前置阶段已经完成
- **当前技术债状况摘要**（必须引用 Constitution 和最近 ADR）

## 本阶段目标

- 目标 1
- 目标 2
- 目标 3
- **治理目标**（必须有）：本次必须减少/控制哪些复杂度？偿还哪些具体债务？

## 必读文件（强制）

- `docs/ARCHITECTURE_CONSTITUTION.md`（铁律，必读）
- 最近 2-3 个相关 ADR
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\frontend\index.html`
- 按实际阶段补充

**所有 agent 工作前必须先阅读 Constitution 并在思考中声明已遵守。**

## 实施范围

明确这轮允许改什么，不允许改什么。

### 允许修改

- 后端
- 前端
- 测试
- 文档

### 禁止事项

- 不要推倒重来
- 不要破坏现有 `cover/train` 核心闭环
- **禁止**继续创建 stage59_/stage60_ 等里程碑专项 service（除非本阶段就是为了合并它们）
- **禁止**向 `backend/db.py` 添加新的大段 backfill/migrate 逻辑
- 不要引入额外复杂中间件

## 具体任务

### 1. 任务一

写清楚要改到什么程度。

### 2. 任务二

写清楚需要交付什么。

### 3. 任务三

写清楚如何验证。

**对于 Feature Sprint**：必须在任务中包含“债务评估”和“寻找至少一项可执行的简化”要求。

**对于 Governance Sprint**：任务必须聚焦收敛、清理、抽象、路线图制定。**严禁添加新用户功能**。

## 交付要求（强制升级）

执行 agent 完成后，必须输出：

1. 改了哪些文件
2. 实现了哪些功能 / 完成了哪些治理
3. **Debt Delta**：本次新增了多少债？减少了多少债？具体量化（文件数、行数、抽象数等）
4. **Invariant Violations**：违反了 ARCHITECTURE_CONSTITUTION.md 哪些条款？为什么？
5. **Simplification Opportunities**：本次有机会但未执行的简化点及理由
6. 跑了哪些测试 / smoke
7. 还有哪些已知限制
8. 将汇报写入 `docs/agent-md/worker/stage-XX-简短主题-report.md`

## 验证要求

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`

按实际阶段补充 smoke / playwright / verify。

**Governance Sprint 额外验证**：必须运行 Constitution 合规自检（如有脚本）或人工对照检查。

## 完成标准

- 标准 1
- 标准 2
- 标准 3
- **治理完成标准**（必须）：本阶段 Debt Delta 为负或为 0，且无未解释的 Invariant Violations。

