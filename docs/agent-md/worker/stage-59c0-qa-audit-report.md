# Stage59C-0 QA 审计报告

审计时间：2026-06-03  
审计角色：Sub-agent D（只读 QA，本报告为唯一写入物）  
工作区：`D:\FeiSharkStudio-v2`  
边界：未改业务代码；未启动 UVR/RVC/GPU；未向 `shared_data` 写入 wav；未执行 59D fresh cover。

---

## 总结结论

**59C-0 干跑（dry-run）功能验收：PASS**  
**合并/发布就绪：BLOCKED（交付物未入库）**

Stage59C-0 目标是在不调用 UVR/RVC/subprocess 的前提下，为 short-chain manifest 提供 **gate 白名单 + UVR A/B 计划 JSON**。当前实现满足该范围：40 条定向单测全绿，全量 `pytest -q` 为 **166 passed**；`verify_stage59_uvr_ab.py` 与 `verify_stage59_short_chain_manifest.py` 对脱敏模板均可 **PASS**。  
Agents A/B/C 在 Stage59 短链相关路径上 **未发现** 启动 UVR/RVC、导入 `voice_changer`/`model_trainer`、向 Git 跟踪的 `shared_data` 提交 raw wav、或混入 59D fresh cover 的违规。

**诚实限制**：59C-0 **不是** PR 计划中的完整 `59C-uvr-ab`（无 `--execute` 真实分离、无 `job_artifacts` 写入、无 API 层）。主控若将本阶段标为「59C 完成」，属于范围夸大，应仅标 **59C-0 dry-run planner DONE**。

---

## 审计范围与依据

| 项 | 内容 |
| --- | --- |
| 必读服务 | `backend/services/short_chain_manifest_service.py`、`short_chain_uvr_service.py` |
| 必读 CLI | `backend/verify_stage59_uvr_ab.py`（另参考已合并的 `verify_stage59_short_chain_manifest.py`） |
| 必读测试 | `test_stage59_short_chain_manifest.py`、`test_stage59c0_manifest_whitelist.py`、`test_stage59c0_short_chain_uvr_service.py`、`test_stage59c0_verify_uvr_ab_cli.py` |
| 违规扫描 | 短链/UVR/59C 路径是否启动 UVR/RVC、是否 import 推理/训练模块、是否 commit wav 到 `shared_data`、是否做 59D mix |

---

## 交付物清单

| 文件 | 状态 | 说明 |
| --- | --- | --- |
| `backend/services/short_chain_manifest_service.py` | 已存在，**工作区已修改未提交** | 新增 `build_short_chain_whitelist()`（+13 行） |
| `backend/services/short_chain_uvr_service.py` | 存在，**git untracked `??`** | dry-run planner；`execute=True` 硬阻断 |
| `backend/verify_stage59_uvr_ab.py` | 存在，**`??`** | 默认 dry-run；`--execute` → `execute_blocked_by_stage59c0` |
| `tests/unit/test_stage59c0_manifest_whitelist.py` | 存在，**`??`** | 白名单与 gate 对齐 |
| `tests/unit/test_stage59c0_short_chain_uvr_service.py` | 存在，**`??`** | planner + 禁止模块 import 断言 |
| `tests/unit/test_stage59c0_verify_uvr_ab_cli.py` | 存在，**`??`** | CLI 退出码与 JSON 契约 |
| `tests/unit/test_stage59_short_chain_manifest.py` | 已跟踪（59B） | 回归 9 条，与 59C-0 叠加 |

**说明**：审计开始时部分路径曾报 `File not found`（索引/缓存时序）；复扫工作树后上述文件均存在。阻塞合并的主因是 **未 `git add` / 未 commit**，而非源码缺失。

---

## 测试结果

### 定向验收（Stage59C-0 命令）

```text
python -m pytest tests/unit/test_stage59_short_chain_manifest.py \
  tests/unit/test_stage59c0_manifest_whitelist.py \
  tests/unit/test_stage59c0_short_chain_uvr_service.py \
  tests/unit/test_stage59c0_verify_uvr_ab_cli.py -q

40 passed, 2 warnings in 0.33s
```

### 全量回归

```text
python -m pytest -q --tb=no

166 passed, 2 warnings in 49.91s
```

警告来源：`backend/main.py` 的 `@app.on_event("startup")` DeprecationWarning（Stage59F 范畴，非 59C-0 回归失败）。

### CLI 冒烟（脱敏 manifest）

| 命令 | 结果 |
| --- | --- |
| `python backend\verify_stage59_uvr_ab.py --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --skip-file-exists` | **STAGE59_UVR_AB PASS**（`uvr_ab_entries=["stage59_redacted_cover_source"]`，`planned_count=1`） |
| `python backend\verify_stage59_short_chain_manifest.py`（同上 manifest） | **STAGE59_SHORT_CHAIN PASS**（`approved=1 blocked=1`） |

---

## Agents A/B/C 合规扫描（Stage59 短链相关）

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 启动 UVR/RVC 推理 | **未发现违规** | `short_chain_uvr_service`：`execute=True` → `EXECUTE_BLOCKED_REASON`；无 `subprocess` import |
| 导入 `voice_changer` / `model_trainer` | **未发现违规** | 源码 grep + 单测 `test_service_does_not_import_forbidden_modules` / `test_verifier_does_not_import_separation_or_subprocess` |
| 向 Git 跟踪的 `shared_data` 提交 `.wav` | **未发现违规** | `glob **/shared_data/**/*.wav` → 0；测试仅在 `tmp_path` 生成 wav |
| 59D fresh cover / mix | **未发现违规** | 无 `verify_stage59_rvc_fresh_cover.py`、`stage59_fresh_*` job 前缀实现；`backend/*stage59*` 无 `audio_mixer`/`cover_pipeline` 引用 |

**范围外说明（诚实）**：工作区存在大量其它 **untracked** 模块（如 `separation_eval_service.py`、`engine_manager_service.py`），且 `preflight_service.py` 等 **已修改** 文件仍含 `voice_changer`/`model_trainer` import——属历史/其它 Stage，**不记入 59C-0 短链交付违规**，但会增加并行 agent 合并冲突风险。

---

## 功能与设计核对

### 已实现（符合 59C-0）

1. **Manifest gate 白名单**：`build_short_chain_whitelist()` 与 `evaluate_short_chain_gate().approved_entry_ids` 一致；pending/restricted/unknown/quarantine/archived/rights_blocked 均不可入白名单。  
2. **UVR 计划器**：`plan_short_chain_uvr()` / `plan_dry_run()` 仅输出 JSON plan（`dry_run: true`，`stages: ["uvr_ab"]`）；拒绝 path 型伪 `entry_id`。  
3. **执行硬闸**：CLI `--execute` 与 `plan_short_chain_uvr(execute=True)` 均失败，reason=`execute_blocked_by_stage59c0`。  
4. **安全声明**：`plan_dry_run` 返回 `safety.uvr_subprocess/rvc_inference/gpu_required = false`。

### 未实现（59C-0 故意不包含，非本次 FAIL 项）

- 真实 UVR 分离与 `job_artifacts`（`uvr_vocal` / `uvr_instrumental`）写入。  
- `tests/api/test_stage59_uvr_ab_api.py` 与 Studio/Stage49 联动。  
- 默认磁盘 manifest：`shared_data/materials/stage59/short_chain_manifest.json`（需本地填充；仓库仅脱敏 JSON 证据）。

---

## 局限性与风险

1. **Git 卫生**：59C-0 核心文件均为 `??` 或 `M`，未进入 `01b19be` 之后的提交链；CI/他机克隆将 **缺测或缺模块**。  
2. **范围命名**：目录/常量使用 `stage59c0`，PR 计划写的是 `59C-uvr-ab`；主控需避免将 dry-run 误报为「UVR A/B 已跑通」。  
3. **`--no-dry-run`**：`verify_stage59_uvr_ab` 在 `not args.dry_run` 时同样走 execute 阻断（设计一致，但易与 59C 全量 CLI 混淆）。  
4. **全量 pytest 基数**：166 passed 含大量其它 Stage 的 untracked 测试；59C-0 定向 40 条才是本阶段权威门禁。  
5. **并行脏工作区**：`git status` 显示数十个无关 `??`/`M` 文件；合并前需 rebase/拆分 PR，避免 59C-0 被连带 revert。

---

## 违规项汇总

| 级别 | 项 | 判定 |
| --- | --- | --- |
| — | UVR/RVC 未授权启动 | **无** |
| — | 短链路径 import 推理/训练 | **无** |
| — | `shared_data` raw wav 入库 | **无** |
| — | 59D fresh cover | **无** |
| P1 | 59C-0 交付未 commit | **有**（合并 BLOCKED） |
| P2 | 与完整 59C PR 计划差距 | **有**（预期内，需后续 PR） |

---

## 修复建议（主控 / Agent A–C）

1. **立即**：`git add` 并单独 commit：`short_chain_uvr_service.py`、`verify_stage59_uvr_ab.py`、`test_stage59c0_*.py`、`short_chain_manifest_service.py` 白名单增量。  
2. **PR 标题**：使用 `59C-0-short-chain-uvr-dry-run`，勿标 `59C-uvr-ab execute`。  
3. **下一 PR（59C-1+）**：在保持 whitelist 前提下接入 `separation_eval_service` mock/execute 路径与 artifact 契约；须主控显式 `--execute` 批准。  
4. **59D**：保持独立 PR，依赖 59C 试听/分离验收后再做 `stage59_fresh_*` job。

---

## 验收命令存档

```powershell
Set-Location D:\FeiSharkStudio-v2

python -m pytest tests/unit/test_stage59_short_chain_manifest.py `
  tests/unit/test_stage59c0_manifest_whitelist.py `
  tests/unit/test_stage59c0_short_chain_uvr_service.py `
  tests/unit/test_stage59c0_verify_uvr_ab_cli.py -q

python -m pytest -q --tb=no

python backend\verify_stage59_uvr_ab.py `
  --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json `
  --skip-file-exists

python backend\verify_stage59_short_chain_manifest.py `
  --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json `
  --skip-file-exists
```

---

## 最终裁决

| 维度 | 裁决 |
| --- | --- |
| **59C-0 功能 / 测试 / 合规** | **PASS** |
| **合并到 main / 标 Stage59C 完成** | **BLOCKED**（未提交；且不等于完整 59C UVR execute） |

**推荐主控动作**：接受 59C-0 dry-run 验收 → 督促 commit → 排队下一 PR 做真实 UVR A/B（带 mock + 显式 execute 闸门）。

---

*报告路径：`docs/agent-md/worker/stage-59c0-qa-audit-report.md`*