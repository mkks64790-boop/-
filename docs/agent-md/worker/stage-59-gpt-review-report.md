# FeiShark Studio — 两环节工作评审报告（供 GPT 审阅）

Date: 2026-06-03  
Project: `D:\FeiSharkStudio-v2`  
Author: Grok Agent（Cursor）  
Audience: 外部评审（GPT / 主控 / 人类开发者）

---

## 0. 评审说明（给 GPT 的 prompt 建议）

请基于本报告审阅以下两方面：

1. **环节 A**：只读代码审查后并行修复的 4 项技术债（bug / 双表清理 / 下载沙箱 / 工程化）。
2. **环节 B**：Stage 59A「显式资产生命周期」实现 + 主控 PR 拆分文档。

评审维度建议：正确性、安全性、与 Stage58 smoke_filter 策略是否冲突、测试是否足够、59B–59D 衔接是否清晰、未提交 Git 风险。

当前自动化证据：`python -m pytest -q` → **138 passed**, 2 warnings（FastAPI `on_event` 弃用）。

---

## 1. 背景与目标

| 项 | 内容 |
| --- | --- |
| 产品 | 本地 AI 翻唱 / RVC 训练工作台（FastAPI + 原生前端） |
| Stage58 现状 | `smoke_filter.py` 用 regex/metadata 默认隐藏测试 job/model，改善 UI 噪声 |
| Stage59 方向 | 不再只靠 regex「藏垃圾」；每条资产有显式 `lifecycle_state`；再接真实素材短链 → UVR A/B → RVC fresh cover |
| 用户诉求 | 先 59A，再让主控按 MD 拆 PR；本报告覆盖 **环节 A + 环节 B** |

---

## 2. 环节 A：审查 + 四项并行修复

### 2.1 触发方式

用户对 `D:\FeiSharkStudio-v2` 做**只读审查**（不改代码）。结论：pytest 114 passed，但存在确定 bug、双表清理漏扫、下载路径不一致、工程化缺口。用户要求分 4 个子 agent 并行修复。

### 2.2 修复清单与实现摘要

| # | 问题 | 实现 | 新增测试 |
| --- | --- | --- | --- |
| A1 | `add_voice_asset()` 永远 `return True` | `backend/db.py`：区分 INSERT/实质更新 vs 完全重复；日志 `[OK]`/`[SKIP]` 互斥 | `tests/unit/test_db_voice_asset.py`（3） |
| A2 | `file_lifecycle_cleanup()` 只查 `tasks`，jobs-only cover 漏清理 | `backend/db.py`：`_collect_lifecycle_cleanup_ids()` 合并 tasks+jobs 终态 cover，去重 | `tests/unit/test_file_lifecycle_cleanup.py`（5） |
| A3 | artifact 下载未做项目根沙箱 | `resolve_project_file_path()` 抽到 `asset_service.py`；`main.py` 统一 `_download_file_response()` | `tests/api/test_download_path_sandbox_api.py`（9） |
| A4 | 无 `requirements.txt`；多 service 未跟踪 | 根目录 `requirements.txt`；**未**拆 `main.py` / `factory/main.js` | 全量 pytest 回归 |

### 2.3 环节 A 测试演进

- 修复前：**114 passed**
- 环节 A 后：**130 passed**（+16）
- 环节 B 后：**138 passed**（+8）

### 2.4 环节 A 优点（供 GPT 打分）

- 每项修复范围克制，有单测锚点。
- 下载沙箱与 source-audio 下载行为一致。
- 双表清理用 `_normalize_status()` 统一终态，减少中英 status 漏网。

### 2.5 环节 A 遗留 / 风险

| 风险 | 说明 |
| --- | --- |
| Git 未提交 | 大量 `M` + `??` backend/services；合并前需 `git add` |
| 后台清理线程 | 部分单测 DB 无 `jobs` 表时，异步 `file_lifecycle_cleanup` 曾报 `no such table`（pass 但有 warning）；59A 已加 `_table_exists` 防护 |
| CORS | `allow_origins=["*"]` + `allow_credentials=True` 仍不规范（审查项，未改） |
| 巨型文件 | `main.py` ~2558 行、`factory/main.js` ~3117 行未拆 |

---

## 3. 环节 B：Stage 59A 显式资产生命周期

### 3.1 设计契约

**五态枚举**（`backend/services/lifecycle_service.py`）：

| `lifecycle_state` | 含义 | 典型场景 |
| --- | --- | --- |
| `active` | 用户/发布级资产，可下载 | `cover_master`、训练 `.pth` |
| `transient` | 流水线中间体，可删文件 | `cover_vocal`、`vocal.wav` 等 |
| `archived` | 归档/隔离，默认不删 | material `quarantined` 映射 |
| `purged` | 文件已删，DB 行保留意图 | 清理后标记 |
| `test_data` | 测试/冒烟数据 | metadata.smoke、smoke_ 前缀 job |

**职责分离**：

- `smoke_filter`：**列表默认隐藏**（UI/Factory 噪声过滤，保留）
- `lifecycle_state`：**清理门禁、下载 410、注册写入、API 展示**（59A 权威）

**映射**：`material_assets.retention_status` → `lifecycle_state`（`RETENTION_TO_LIFECYCLE`）。

### 3.2 Schema 与迁移

`backend/db.py` `init_db()`：

- 新表定义含 `lifecycle_state TEXT NOT NULL DEFAULT 'active'`（`job_artifacts`, `audio_assets`, `voice_models`, `material_assets`）
- `_migrate_add_column` 兼容旧库
- `_backfill_asset_lifecycle_states()` 启动时按 smoke/metadata/artifact_type 推断回填

### 3.3 写入路径

| 入口 | 行为 |
| --- | --- |
| `register_job_artifact` | 按 job metadata + `is_final` + `artifact_type` 写入 lifecycle |
| `register_audio_asset` | 按 `asset_role` + job 是否 test_data |
| `upsert_voice_model` | `infer_voice_model_lifecycle` 后写入 |
| `file_lifecycle_cleanup` | 删中间文件后 `mark_job_transient_artifacts_purged()` |
| `cleanup_job_transients` | 同上，返回 `purged_artifact_rows` |

### 3.4 API 暴露

| 端点 | 变更 |
| --- | --- |
| `GET /api/jobs/{job_id}/artifacts` | 每项含 `lifecycle_state`, `lifecycle_deletable`, `lifecycle_downloadable` |
| `GET /api/lifecycle/contract` | 返回枚举、retention 映射、cleanup 可删态说明 |
| `GET /api/jobs/.../artifacts/.../download` | `purged`/`archived` → **410** `artifact_lifecycle_not_downloadable` |
| `GET /api/models` | `_enrich_model_row` 含 `lifecycle_state` |
| material library 列表 | `_material_row_to_dict` → `enrich_material_asset` |

### 3.5 环节 B 测试

| 文件 | 用例数 | 覆盖点 |
| --- | --- | --- |
| `tests/unit/test_lifecycle_service.py` | 5 | transient/active/test_data/retention 映射 |
| `tests/api/test_stage59a_asset_lifecycle_api.py` | 3 | contract API、真实 job artifact 状态、smoke job |

### 3.6 环节 B 相对 PR 计划的差距（GPT 可重点评）

`docs/agent-md/worker/stage-59-pr-plan.md` 中 59A 原计划部分能力**未做**或**简化**：

| 计划项 | 实际 |
| --- | --- |
| `job_service`/`model_service` 默认列表按 lifecycle SQL 过滤 | **未改**列表 SQL；仍主要靠 `smoke_filter`，lifecycle 仅展示+清理 |
| `PATCH .../lifecycle` 人工改状态 | **未实现** |
| `transition_lifecycle` / `should_default_hide` 独立 API | **未实现**；逻辑在 infer/enrich 函数内 |
| 清理跳过 `active`+`is_final` 关联路径的精细规则 | 实现为：删固定文件名 + 将 transient/test_data 标 purged |
| 测试文件名 `test_stage59_lifecycle_api.py` | 实际为 `test_stage59a_asset_lifecycle_api.py` |

**评价**：59A 是「最小可合并闭环」——DB 字段 + 推断 + API 展示 + 清理标记；列表过滤双轨留到 59B 或后续 PATCH PR 合理。

### 3.7 环节 B 优点

- 模块边界清晰：`lifecycle_service.py` 单文件契约，易给 59C/59D 复用。
- 与 Stage58 不打架：smoke 继续 hide，lifecycle 管物理语义。
- 契约端点 `/api/lifecycle/contract` 利于前端/主控对齐。
- 全量 138 tests 无回归失败。

### 3.8 环节 B 风险与建议

| 项 | 严重度 | 说明 |
| --- | --- | --- |
| 列表仍 regex 优先 | 中 | 用户可见列表与 lifecycle 可能短暂不一致；59B manifest 应显式绑定 lifecycle |
| `purged` 行仍在 DB | 低 | 符合「先表达意图不 mass delete」原则 |
| `add_voice_asset` 与 `upsert_voice_model` 双写路径 | 低 | 需长期统一 voice_assets/voice_models |
| FastAPI lifespan | 低 | 弃用 warning，计划 59F |
| 生产 DB 回填 | 中 | 首次启动 `init_db` 会 backfill；大库需观察启动时间 |

---

## 4. 主控文档（环节 B 附属交付）

| 文件 | 用途 |
| --- | --- |
| `docs/agent-md/worker/stage-59-pr-plan.md` | PR DAG（59A–59F）、验收命令、回滚、Git 指引、DoD |
| `docs/agent-md/worker/stage-59-gpt-review-report.md` | 本文件 |

59A 在 plan 中已标 **DONE**；59B–59D 仍为待实现规格。

---

## 5. 文件变更总览（两环节合计）

### 5.1 新增

- `backend/services/lifecycle_service.py`
- `requirements.txt`
- `tests/unit/test_db_voice_asset.py`
- `tests/unit/test_file_lifecycle_cleanup.py`
- `tests/api/test_download_path_sandbox_api.py`
- `tests/unit/test_lifecycle_service.py`
- `tests/api/test_stage59a_asset_lifecycle_api.py`
- `docs/agent-md/worker/stage-59-pr-plan.md`
- `docs/agent-md/worker/stage-59-gpt-review-report.md`

### 5.2 主要修改

- `backend/db.py`（voice_asset 语义、双表清理、lifecycle 列+回填、jobs 表存在检查）
- `backend/services/asset_service.py`（沙箱、lifecycle 注册/列表/下载门禁）
- `backend/main.py`（下载统一、lifecycle contract、410）
- `backend/services/model_service.py`（lifecycle 写入/列表）
- `backend/services/material_library_service.py`（material enrich）
- `backend/temp_cleanup_service.py`（purged 标记）

---

## 6. 验收命令（可复制给 GPT 复现）

```powershell
cd D:\FeiSharkStudio-v2

# 全量
python -m pytest -q

# 环节 A 聚焦
python -m pytest tests/unit/test_db_voice_asset.py tests/unit/test_file_lifecycle_cleanup.py tests/api/test_download_path_sandbox_api.py -q

# 环节 B 聚焦
python -m pytest tests/unit/test_lifecycle_service.py tests/api/test_stage59a_asset_lifecycle_api.py -q

# 可选（写生产 DB，审查时慎用）
python -X utf8 backend\self_check.py
```

---

## 7. 建议 GPT 输出的评审结构

请 GPT 按以下模板回复用户：

1. **总评**（1–5 分 + 一句话）
2. **环节 A**：每项修复是否正确、测试是否够
3. **环节 B**：架构是否合理、与 Stage58 关系、59B 衔接缺口
4. **必须修**（blocking）vs **可延期**（non-blocking）
5. **主控合并建议**：几个 commit/PR、顺序、是否先 `git add` 未跟踪 services

---

## 8. 主控下一步（非 GPT 范围，供对照）

| 顺序 | PR | 状态 |
| --- | --- | --- |
| 1 | 59A-lifecycle + 环节 A hotfixes | **代码在本地，建议单 PR 或拆两 PR** |
| 2 | 59B-short-chain-manifest | 未开始 |
| 3 | 59C-uvr-ab | 未开始 |
| 4 | 59D-rvc-fresh-cover | 未开始 |

---

*End of report.*