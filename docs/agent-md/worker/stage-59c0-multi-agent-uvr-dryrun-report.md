# Stage59C-0 多子 Agent UVR A/B Dry-run 集成报告

Date: 2026-06-03  
Workspace: `D:\FeiSharkStudio-v2`  
角色: 主控集成（Sub-agents A/B/C/D + 主 Agent API 接线）  
状态: **59C-0 dry-run 验收 PASS**（不等于完整 59C `--execute` UVR）

---

## 1. 极致诚实：技术限制、假设、不可能路径

### 技术限制

| 限制 | 说明 |
| --- | --- |
| 无 UVR 子进程 | `short_chain_uvr_service` 与 `verify_stage59_uvr_ab.py` 不调用 `subprocess`、不加载 `vocal_separator` / `separation_eval_service` 执行路径 |
| 无 RVC 7866 | API `/api/stage59/short-chain/uvr-ab/execute` 固定 **403**；CLI `--execute` → `execute_blocked_by_stage59c0` |
| 无 GPU 长任务 | `safety.gpu_required` 恒为 `false`；本阶段 pytest 不触发 CUDA |
| 无新音频产物 | `planned_actions` 仅 JSON 元数据；不写 `job_artifacts` / `shared_data/separation_eval/` |
| Manifest 磁盘依赖 | 生产 manifest 默认 `shared_data/materials/stage59/short_chain_manifest.json`（gitignore）；仓库仅脱敏 `docs/agent-md/evidence/stage59-short-chain-manifest.redacted.json` |
| `check_file_exists=True` | 无本地 wav 时 gate 会 honest blocked（exit 3 / HTTP 422） |

### 假设

- Stage59B `evaluate_short_chain_gate` / `build_short_chain_whitelist` 为 59C/59D 唯一 runner 入口权威。
- `entry_id` 为 manifest 主键；**禁止**客户端传入任意 `source_path` 绕过白名单。
- 59C-0 通过后，主控另开 PR 才允许 `--execute` 与真实分离（59C-1+）。

### 本阶段不可能路径（故意未实现）

- 启动 UVR / RVC WebUI / 训练管线。
- 将 `shared_data` 原始 wav 提交 Git。
- 59D fresh cover / `stage59_fresh_*` job。
- Studio 完整 A/B 试听 UI（仅 contract + plan API + CLI）。

---

## 2. 子 Agent 分工与写入边界

| Agent | 职责 | 写入范围 | 越界检查 |
| --- | --- | --- | --- |
| **A** | Manifest 白名单与 gate 审计 | `tests/unit/test_stage59c0_manifest_whitelist.py`；`build_short_chain_whitelist()`（59B 服务增量） | 未读/提交 raw audio |
| **B** | UVR dry-run 计划器 | `backend/services/short_chain_uvr_service.py` | 无 `voice_changer`/`model_trainer` import |
| **C** | CLI 验证器 | `backend/verify_stage59_uvr_ab.py`、`tests/unit/test_stage59c0_verify_uvr_ab_cli.py` | 默认 dry-run；`--execute` 阻断 |
| **D** | 只读 QA | `docs/agent-md/worker/stage-59c0-qa-audit-report.md` | 未改业务代码 |
| **主控** | API 合同 + 集成报告 | `backend/main.py`（3 路由）、`tests/api/test_stage59_uvr_ab_api.py`、本文件 | 不重叠 A/B/C 核心逻辑 |

---

## 3. 交付物

| 路径 | 作用 |
| --- | --- |
| `backend/services/short_chain_manifest_service.py` | `build_short_chain_whitelist()` |
| `backend/services/short_chain_uvr_service.py` | `plan_short_chain_uvr` / `plan_dry_run` |
| `backend/verify_stage59_uvr_ab.py` | CLI dry-run + JSON |
| `backend/main.py` | `GET/POST /api/stage59/short-chain/uvr-ab/*` |
| `tests/unit/test_stage59c0_*.py` | A/B/C 单元门禁 |
| `tests/api/test_stage59_uvr_ab_api.py` | API 合同 |
| `docs/agent-md/evidence/stage59-short-chain-manifest.redacted.json` | 脱敏证据 |
| `docs/agent-md/worker/stage-59c0-qa-audit-report.md` | D 审计 |
| `docs/agent-md/worker/stage-59c0-multi-agent-uvr-dryrun-report.md` | 本报告 |

---

## 4. API / CLI 合同摘要

### API（59C-0）

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| GET | `/api/stage59/short-chain/uvr-ab/contract` | 返回 `stage59c0`、`execute_allowed=false`、safety 标志 |
| POST | `/api/stage59/short-chain/uvr-ab/plan` | Body: `entry_id?`, `manifest_path?`, `skip_file_exists`, `clip_seconds`, `limit` → dry-run plan；blocked → **422** |
| POST | `/api/stage59/short-chain/uvr-ab/execute` | 恒 **403** `execute_blocked_by_stage59c0` |

### CLI `verify_stage59_uvr_ab.py`

| 场景 | exit code | reason |
| --- | --- | --- |
| dry-run PASS | 0 | — |
| manifest 读失败 / schema / rights | 1 | `schema`, `rights_or_gate`, `entry_id_not_in_whitelist`, … |
| manifest 缺失 | 2 | `manifest_missing` |
| 无 approved / 无可规划 UVR | 3 | `no_approved_entries` / `no_uvr_ab_eligible_approved_entries` |
| `--execute` | 1 | `execute_blocked_by_stage59c0` |

---

## 5. 验收命令与结果（2026-06-03 主控复跑）

```powershell
Set-Location D:\FeiSharkStudio-v2

python -m pytest tests/unit/test_stage59_short_chain_manifest.py -q
# 9 passed

python -m pytest tests/api/test_stage59_uvr_ab_api.py -q
# 6 passed

python -m pytest tests/unit/test_stage59c0_manifest_whitelist.py `
  tests/unit/test_stage59c0_short_chain_uvr_service.py `
  tests/unit/test_stage59c0_verify_uvr_ab_cli.py -q
# 31 passed

python -m pytest -q
# 193 passed, 2 warnings (FastAPI on_event deprecation)

python backend\verify_stage59_short_chain_manifest.py `
  --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json `
  --skip-file-exists
# STAGE59_SHORT_CHAIN PASS (approved=1 blocked=1)

python backend\verify_stage59_uvr_ab.py --dry-run `
  --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json `
  --skip-file-exists
# STAGE59_UVR_AB PASS (uvr_ab_entries=["stage59_redacted_cover_source"], planned_count=1)
```

**定向 59C-0 合计**: 9 + 6 + 31 = **46 passed**（含 59B 回归 9 条）。

---

## 6. 验收标准对照

| 标准 | 结果 |
| --- | --- |
| 不启动 UVR/RVC/GPU | **PASS**（grep + 单测 + API execute 403） |
| 不产生新音频 | **PASS** |
| 不提交 shared_data 原始文件 | **PASS**（测试 wav 仅在 `tmp_path`） |
| 无合法素材时 honest blocked | **PASS**（exit 3 / 422 / `entry_id_not_whitelisted`） |
| 仅 approved_entry_ids 可规划 | **PASS**（Agent A 测试 + planner 阻断） |
| `--execute` 本阶段拒绝 | **PASS** `execute_blocked_by_stage59c0` |
| 未混入 59D fresh cover | **PASS** |

---

## 7. 裁决与下一步

| 维度 | 裁决 |
| --- | --- |
| **59C-0 dry-run 架构 / manifest 白名单 / API+CLI 合同** | **PASS** |
| **Stage59C 完整 execute（真实 UVR + artifacts）** | **未开始** — 需主控显式批准 59C-1+ PR |
| **合并 main** | 建议单独 commit：`59C-0-short-chain-uvr-dry-run` |

**允许进入**: Stage59C **execute 设计**文档与 mock runner PR 排队。  
**禁止进入**: 在未批准前跑 `--execute`、开 59D、或向 Git 提交 raw 音频。

---

*报告路径: `docs/agent-md/worker/stage-59c0-multi-agent-uvr-dryrun-report.md`*