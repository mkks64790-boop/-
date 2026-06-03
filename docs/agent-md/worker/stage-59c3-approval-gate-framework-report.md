# Stage59C-3 Real UVR Approval Gate Framework 集成报告

Date: 2026-06-04  
Workspace: `D:\FeiSharkStudio-v2`  
状态: **PASS**（approval gate + execution policy 框架；**非**真实 UVR）

---

## 1. 评分：4 / 5

| 维度 | 分 | 说明 |
| --- | --- | --- |
| 安全 | 5 | 默认阻断 real execute；即使 token 齐全仍 `real_uvr_runner_not_enabled_stage59c3` |
| 合同 | 5 | 五模式区分、CLI/API approval-preflight、caps/sandbox/disk 元数据预检 |
| 审计 | 4 | 内存 audit 记录，`requires_later_db_integration=true` |
| 可进 59C-4 | 4 | 框架就绪；真实 smoke 需下一 stage 显式启用 runner |

---

## 2. 技术限制与诚实声明

- **未运行**真实 UVR、RVC WebUI、`127.0.0.1:7866`、GPU、ffmpeg 或长音频处理。
- **未写入**任何 `.wav` / `.mp3` / `.flac` 等原始音频到 `shared_data`。
- Stage59C-3 新服务路径 **未** import `vocal_separator`、`voice_changer`、`subprocess`、`requests` 等。
- 即使 `confirm_execute=true` 且 `approval_token=stage59-local-approval`，`real_execute_allowed` **恒为 false**。
- `requested_mode=real_execute` → CLI exit 1 / API **403**，原因：`real_uvr_runner_not_enabled_stage59c3`。
- 本阶段为 **未来 tiny real smoke（59C-4）** 做准备，**不执行**真实分离。

---

## 3. 架构与服务层

| 文件 | 职责 |
| --- | --- |
| `stage59_execution_policy_service.py` | 模式路由、批准条件、blocked_reasons、`next_allowed_stage=stage59c4_tiny_real_uvr_smoke` |
| `stage59_execution_guard_service.py` | caps（max_items=1, clip 20–60s）、sandbox 规划、`disk_check_mode=metadata_only` |
| `stage59_approval_audit_service.py` | 元数据 audit 事件（preflight / blocked / rejected） |
| `verify_stage59_uvr_ab.py` | `--approval-preflight`、`--confirm-execute`、`--approval-token`、`--requested-mode` |
| `main.py` | `POST /api/stage59/short-chain/uvr-ab/approval-preflight` |

### 支持的模式

- `dry_run` / `readiness` / `mock_execute`（沿用 C-0–C-2）
- `approval_preflight`（本阶段新增，200 + `real_execute_allowed=false`）
- `real_execute`（请求即阻断，403/exit 1）

### 批准条件（全部需在 preflight 中可解释）

- `confirm_execute=true`
- `approval_token` 以 `stage59-` 开头且长度达标
- `entry_id` + 安全 manifest 路径 + whitelist + `uvr_ab` chain
- `max_items=1`，`clip_seconds` 在 20–60
- disk/sandbox/timeout 元数据预检通过
- **仍** `real_runner_enabled=false`（C-3 硬编码）

---

## 4. API / CLI 行为摘要

| 路径 / 命令 | 结果 |
| --- | --- |
| `POST .../approval-preflight`（无 token） | 200，`warnings` 含 missing 字段，`real_execute_allowed=false` |
| `POST .../approval-preflight`（完整 token） | 200，`approval_complete=true`，仍 `real_execute_allowed=false` |
| `POST .../approval-preflight` + `requested_mode=real_execute` | **403** |
| `POST .../execute` | **403**（未变） |
| `POST .../mock-execute` | 200（C-2 回归通过） |
| CLI `--approval-preflight` | PASS |
| CLI `--approval-preflight --confirm-execute --approval-token stage59-local-approval` | PASS，`real_execute_allowed=false` |
| CLI `--requested-mode real_execute` | FAIL exit 1，`real_uvr_runner_not_enabled_stage59c3` |

---

## 5. Sandbox 与 caps

- 规划根：`shared_data/stage59_runtime/<run_id>/`
- `files_created=false`，`cleanup_required=true`
- 拒绝 `max_items > 1`、clip 超出 20–60

---

## 6. 验证结果（本地）

- Stage59C-3 定向 pytest：**22 passed**
- 全量 `pytest -q`：**263 passed**
- 脱敏 manifest CLI：dry-run / readiness / mock-execute / approval-preflight 均 **PASS**
- `--requested-mode real_execute`：**FAIL**（预期原因）

---

## 7. 项目方手动验收流程

1. `cd D:\FeiSharkStudio-v2`
2. 运行：
   - `python backend\verify_stage59_uvr_ab.py --dry-run --manifest docs\agent-md\evidence\stage59-short-chain-manifest.redacted.json --skip-file-exists`
   - `python backend\verify_stage59_uvr_ab.py --mock-execute --manifest ... --entry-id stage59_redacted_cover_source --skip-file-exists`
   - `python backend\verify_stage59_uvr_ab.py --approval-preflight --confirm-execute --approval-token stage59-local-approval --manifest ... --entry-id stage59_redacted_cover_source --skip-file-exists`
3. 确认输出均含 `real_execute_allowed=false`
4. 运行 `--requested-mode real_execute` 同名参数 → 应 FAIL 且原因为 `real_uvr_runner_not_enabled_stage59c3`
5. `python -m pytest -q` 全绿
6. **不要**启动 RVC/UVR 或在外部 UI 点真实执行

---

## 8. 下一 stage

**Stage59C-4: tiny real UVR smoke behind approval gate** — 至多一条 20–45s 样本、沙箱目录、超时与失败清理；仍默认无 RVC/GPU。