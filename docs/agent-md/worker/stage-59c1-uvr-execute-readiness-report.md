# Stage59C-1 UVR Execute Readiness 集成报告

Date: 2026-06-03  
Workspace: `D:\FeiSharkStudio-v2`  
状态: **PASS**（readiness harness；真实 UVR 仍禁用）

---

## 1. 评分：4 / 5

| 维度 | 分 | 说明 |
| --- | --- | --- |
| 安全边界 | 5 | 无 UVR/RVC/subprocess/GPU；无音频写入 |
| 合同完整度 | 4 | CLI `--readiness` + API `/readiness` + mock/real runner 合同 |
| 可执行就绪 | 3 | `RealUvrAbRunnerAdapter` 故意 `requires_manual_approval` |
| 合并卫生 | 4 | 仅 Stage59 路径；manifest 路径沙箱 |

扣 1 分：真实 UVR execute 与 `job_artifacts` 写入仍属 **59C-2+**，本阶段仅 harness。

---

## 2. 技术限制、假设、不可能路径

### 限制

- **不跑真实 UVR**：`MockUvrAbRunner` 仅返回 `uvr_vocal` / `uvr_instrumental` 元数据合同。
- **`RealUvrAbRunnerAdapter`**：恒 `real_uvr_runner_requires_manual_approval`。
- **Manifest 路径**：仅 default、`docs/agent-md/evidence/**`、`shared_data/materials/stage59/**`。
- **API 测试**：使用 `isolated_backend` 内相对路径；禁止绝对路径指向仓库外隔离根。

### 假设

- 59B gate + 59C-0 dry-run 行为保持不变。
- 未来真实 execute 需新增显式批准闸门（非本 PR）。

### 不可能路径（本阶段）

- 调用 `vocal_separator` / `separation_eval_service` 执行分离。
- RVC 7866、`ffmpeg` 混音、CUDA 长任务。
- 向 Git 跟踪目录写入 raw 音频。

---

## 3. 变更摘要

| 组件 | 变更 |
| --- | --- |
| `short_chain_manifest_service.py` | `resolve_safe_manifest_path()`、`ManifestPathSafetyError` |
| `stage59_uvr_runner_contract.py` | **新建** `UvrAbRunnerRequest/Plan`、`MockUvrAbRunner`、`RealUvrAbRunnerAdapter` |
| `short_chain_uvr_service.py` | 计划器走安全路径；`evaluate_uvr_ab_readiness()` |
| `verify_stage59_uvr_ab.py` | `--readiness`、`--runner real` 阻断；路径校验前置 |
| `main.py` | `POST /readiness`；plan/readiness 经 `_resolve_stage59_manifest_or_400` |
| 测试 | `test_stage59c1_*` + 59C-0 测试适配安全 manifest 目录 |

---

## 4. 故意保持阻断

- `POST /api/stage59/short-chain/uvr-ab/execute` → **403** `execute_blocked_by_stage59c0`
- CLI `--execute` → FAIL
- CLI/API `--runner real` / `runner_mode=real` → FAIL / 403
- 无 `job_artifacts` 写入、无 separation 子进程

---

## 5. 验收命令与输出

```text
pytest test_stage59_short_chain_manifest.py -q          → 9 passed
pytest test_stage59_uvr_ab_api.py -q                    → 6 passed
pytest test_stage59c0_* -q                              → 31 passed
pytest test_stage59c1_* (unit) -q                       → 24 passed
pytest test_stage59c1_uvr_readiness_api.py -q           → 7 passed
verify_stage59_short_chain_manifest.py ...              → STAGE59_SHORT_CHAIN PASS
verify_stage59_uvr_ab.py --dry-run ...                  → STAGE59_UVR_AB PASS
verify_stage59_uvr_ab.py --readiness --entry-id ...   → STAGE59_UVR_AB PASS (artifact_contracts=2)
pytest -q                                               → 224 passed, 2 warnings
```

---

## 6. 问题清单

| 级别 | 项 |
| --- | --- |
| — | 无 P0 安全违规 |
| P2 | 全仓 `pytest` 基数 224（含其它 Stage 未提交测试） |
| P2 | `on_event` DeprecationWarning（59F） |
| 预期 | 真实 UVR 需 **59C-2 execute** + 主控批准 |

---

## 7. Git add / commit 列表

见 commit `Stage59C-1: add UVR execute readiness harness`（仅 Stage59C-1 相关路径 + 59C-0 测试路径适配）。

---

## 8. 推荐下一阶段

**59C-2-uvr-execute-mock**：在 `requires_manual_approval` 闸门后，mock `separation_eval_service` 写 transient `job_artifacts`（仍禁止 GPU 长任务），再接 Stage49 试听 A/B。

---

*报告: `docs/agent-md/worker/stage-59c1-uvr-execute-readiness-report.md`*