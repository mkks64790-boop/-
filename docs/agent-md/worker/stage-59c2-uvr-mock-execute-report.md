# Stage59C-2 UVR Mock Execute 集成报告

Date: 2026-06-03  
Workspace: `D:\FeiSharkStudio-v2`  
状态: **PASS**（mock execute + 元数据 transient artifacts；**非**真实 UVR）

---

## 1. 评分：4 / 5

| 维度 | 分 | 说明 |
| --- | --- | --- |
| 安全 | 5 | 无引擎/无音频写盘/execute 仍 403 |
| 合同 | 4 | mock execute + listening bridge + CLI/API |
| 持久化 | 3 | 内存 store，`requires_later_db_integration=true` |
| 可进 59C-3 | 4 | 闸门与合同已齐，缺显式人工批准层 |

---

## 2. 技术限制与不可能路径

- `register_job_artifact()` 要求 `os.path.exists` → **未**写入 `job_artifacts` 表。
- 本阶段 **不可能**：真实 UVR、RVC 7866、GPU、ffmpeg、物理 wav。
- 下一 stage：**59C-3 real execute approval gate**（非直接开 UVR）。

---

## 3. 变更摘要

| 文件 | 作用 |
| --- | --- |
| `stage59_uvr_mock_execute_service.py` | readiness → mock execute 编排 |
| `stage59_transient_artifact_service.py` | 内存 transient 元数据 |
| `stage59_listening_bridge_service.py` | Stage49 兼容 A/B 合同 |
| `verify_stage59_uvr_ab.py` | `--mock-execute` |
| `main.py` | `POST .../mock-execute`、`GET .../listening-contract` |

---

## 4. 仍保持阻断

- `POST /api/stage59/short-chain/uvr-ab/execute` → **403**
- `--runner real` / readiness real → **FAIL** `real_uvr_runner_requires_manual_approval`
- `invalid runner_mode` → **422**（Pydantic + runner contract）
- `playback_enabled=false`、`download_enabled=false`

---

## 5. Mock execute 响应形状（摘要）

```json
{
  "ok": true,
  "mode": "mock_execute",
  "stage": "stage59c2",
  "run_id": "stage59c2_<entry_id>_<hex>",
  "real_execute_allowed": false,
  "audio_files_written": false,
  "metadata_only": true,
  "material_entry_id": "<entry_id>",
  "artifact_records": [
    {"artifact_id": "stage59c2_<id>_uvr_vocal", "lifecycle_state": "transient", ...},
    {"artifact_id": "stage59c2_<id>_uvr_instrumental", ...}
  ],
  "listening_contract": { "schema": "stage59_uvr_listening_bridge_v1", ... },
  "requires_later_db_integration": true
}
```

---

## 6. Transient artifact 合同

- 稳定 id：`stage59c2_{entry_id}_uvr_vocal|uvr_instrumental`
- `planned_path` 仅规划路径，`file_exists=false`
- 存储：进程内 `_RUN_STORE`（测试可 `clear_transient_store()`）

---

## 7. Stage49 listening bridge

- `schema`: `stage59_uvr_listening_bridge_v1`
- `compatible_with`: `stage49_listening_review_v1`
- `sides`: `a_source`, `b_uvr_vocal`, `c_uvr_instrumental`
- `ab_pairs`: source vs vocal、vocal vs instrumental
- `next_action`: `requires_real_uvr_execute`

---

## 8. 验收命令与输出

```text
59B+59C0+59C1 回归                           → 全部 passed
59C-2 定向 (15 unit/api + 5 cli 子集)        → 15 passed
verify short_chain + dry-run + readiness   → PASS
verify --mock-execute ...                    → PASS (artifact_records=2)
verify --readiness --runner real             → FAIL (expected)
pytest -q                                    → 241 passed, 2 warnings
```

---

## 9. Git commit

`Stage59C-2: add UVR mock execute artifact bridge`（见本地 hash）

---

## 10. 下一阶段

**Stage59C-3**：显式 `requires_manual_approval` 闸门 + caps + 可选 DB 持久化 + mock/real runner 分界；仍不在 59C-3 默认跑真实 UVR。

---

*报告: `docs/agent-md/worker/stage-59c2-uvr-mock-execute-report.md`*