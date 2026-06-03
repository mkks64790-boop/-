# Stage 43A：Studio 入口契约 + Engine Manager 收口 + 训练调教契约（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本阶段只做后端契约、轻量验收和安全登记。不启动长训练，不跑长 cover，不删除/移动/覆盖 `D:\RVC\RVCv2` 里的任何文件。

## 启动前必读

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-43-studio-entry-engine-cache-training-tuning-plan.md
D:\FeiSharkStudio-v2\backend\main.py
D:\FeiSharkStudio-v2\backend\services\engine_manager_service.py
D:\FeiSharkStudio-v2\backend\services\track_service.py
D:\FeiSharkStudio-v2\backend\services\asset_service.py
D:\FeiSharkStudio-v2\backend\services\model_service.py
D:\FeiSharkStudio-v2\backend\services\job_service.py
```

## 必做任务

### 1. 修复 completed cover job 的 Studio 入口契约

当前实测：

```text
GET /api/jobs/task_stage41_ce1b32f2
status = 完成
current_stage = cover_mix
track_id = trk_stage41_cfc34dfd
can_open_studio = null
final_artifact_download_url = null
```

要求：

- 对已完成 cover job，如果存在 final `cover_master` artifact，`GET /api/jobs/{job_id}` 必须返回：

```json
{
  "can_open_studio": true,
  "final_artifact_id": "...",
  "final_artifact_download_url": "/api/jobs/{job_id}/artifacts/{artifact_id}/download",
  "studio_url": "/studio?track_id=...&job_id=...",
  "studio_track_id": "...",
  "studio_artifact_id": "..."
}
```

- `GET /api/task_status/{job_id}` 也要保留轻量字段：

```json
{
  "can_open_studio": true,
  "final_artifact_download_url": "...",
  "studio_url": "..."
}
```

- 不允许伪造。只有 artifact 文件存在且非空时才返回可打开。
- 对旧 cover job 也要兼容，不只写死 `task_stage41_ce1b32f2`。

### 2. 新增 Studio 入口验收脚本

新增：

```text
backend/verify_stage43_studio_entry_contract.py
```

默认只验证现有任务，不创建新任务：

```powershell
python backend\verify_stage43_studio_entry_contract.py
```

验收项：

- `task_stage41_ce1b32f2` 有 final artifact。
- job detail 返回 `can_open_studio=true`。
- download URL 200 且非空。
- Studio URL 字段存在。
- 如果任务不存在或 artifact 缺失，输出明确原因，不报假 PASS。

### 3. RVC models API 分页、搜索与过滤

增强：

```text
GET /api/engines/rvc/models
```

支持 query：

```text
limit
offset
q
registered=true|false|all
has_index=true|false|all
```

返回结构：

```json
{
  "engine_key": "rvc_webui",
  "status": "online",
  "read_only": true,
  "total": 400,
  "limit": 50,
  "offset": 0,
  "items": [],
  "warnings": []
}
```

兼容旧字段，不要让现有产品层崩。

### 4. Engine Manager 轻缓存

为 RVC 扫描增加简单 TTL 缓存，避免每次 Factory 刷新都扫 400 个模型。

要求：

- 默认 TTL 10-30 秒即可。
- `POST /api/engines/scan` 支持 `force=true` 强制刷新。
- 不引入 Redis。
- 缓存必须只影响扫描性能，不影响模型真实文件安全。

### 5. 外部 RVC 模型安全登记入口

新增安全登记 API，建议：

```text
POST /api/models/import-rvc
```

输入：

```json
{
  "pth_path": "D:\\RVC\\RVCv2\\assets\\weights\\xxx.pth",
  "index_path": "D:\\RVC\\RVCv2\\assets\\indices\\xxx.index",
  "model_name": "xxx",
  "default_pitch": 0
}
```

要求：

- 只登记 FeiShark 数据库。
- 不复制、不删除、不移动、不覆盖 RVC 文件。
- 必须校验 `.pth` 存在。
- `.index` 可选，但如果传入必须存在。
- 登记后 `/api/models` 可见，`/api/preflight/cover` 可判断。
- 重名时给清晰错误或自动安全后缀，但不能覆盖已有模型。

### 6. 训练调教契约 v0

新增轻量契约，不启动训练：

```text
GET /api/training/presets
POST /api/training/estimate
```

预设至少包含：

```text
fast_preview：快速预览
balanced：均衡推荐
quality：高质量慢速
```

返回内容包括：

```text
epochs
batch_size
sample_rate
f0_enabled
index_enabled
gpu_risk_label
estimated_runtime_label
notes
```

`POST /api/training/estimate` 根据素材时长、文件数量、preset 返回风险提示，不创建 job。

## 禁止事项

```text
禁止启动 train.py。
禁止跑长训练。
禁止跑长 cover。
禁止删除/移动/覆盖 D:\RVC\RVCv2 文件。
禁止把 SVC/SVT 假装成可用。
禁止为了让测试过而硬编码 task_stage41_ce1b32f2。
```

## 必测

```powershell
python -m pytest -q
python -m backend.self_check
python backend\verify_stage41_recovered_model_cover_smoke.py
python backend\verify_stage43_studio_entry_contract.py
python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/engines/rvc/models?limit=5&offset=0').json())"
python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/training/presets').json())"
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-43a-studio-entry-engine-cache-training-contract-report.md
```

报告必须包含：

```text
是否完成
修改文件清单
Studio 入口契约修复结果
RVC models 分页/搜索/缓存结果
外部 RVC 模型登记 API 结果
训练调教契约结果
是否启动 train.py：必须为否
是否修改 D:\RVC\RVCv2：必须为否
测试结果
遗留风险
```
