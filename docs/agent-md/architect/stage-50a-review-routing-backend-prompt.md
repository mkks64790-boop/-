# Stage 50A：试听验收路由契约后端化

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本轮任务是把 Stage49 的 `listening_review` 从“单个 artifact 的 metadata”升级为稳定的后端路由契约，让前端可以直接知道一个成品下一步应该去哪里。

## 当前事实

Stage49 已完成：

```text
GET   /api/jobs/{job_id}/source-audio/download
GET   /api/jobs/{job_id}/artifacts/{artifact_id}/review
PATCH /api/jobs/{job_id}/artifacts/{artifact_id}/review
```

验收结果存储在：

```text
job_artifacts.metadata_json.listening_review
```

允许的 `verdict`：

```text
unreviewed
needs_work
usable
release_candidate
rejected
```

## 本轮目标

让后端列表接口和新增汇总接口都能暴露“试听验收摘要 + 下一步路由”，但不启动任何训练、RVC、UVR 或 cover 任务。

## 必须实现

### 1. 新增 review summary 纯函数

在合适的服务文件中实现一个纯函数，例如：

```python
def summarize_listening_review(metadata: dict | str | None) -> dict:
    ...
```

输出字段必须稳定：

```json
{
  "verdict": "unreviewed",
  "label": "未验收",
  "route": "needs_human_review",
  "priority": 30,
  "overall_score": null,
  "vocal_score": null,
  "noise_score": null,
  "mix_score": null,
  "notes_preview": "",
  "reviewed_at": "",
  "is_human_reviewed": false
}
```

路由映射必须固定：

```text
unreviewed        -> needs_human_review
needs_work        -> route_to_rework
usable            -> route_to_candidate_pool
release_candidate -> route_to_release_candidate
rejected          -> route_to_archive_or_rerun
```

`notes_preview` 最多 80 个字符，禁止列表接口返回超长备注撑爆前端。

如果发现 Stage49 smoke 写入的备注：

```text
stage49 browser smoke only - not a human quality verdict
```

必须把 `is_human_reviewed` 标为 `false`，不要误判为人工验收。

### 2. 扩展 artifact 列表契约

修改：

```text
GET /api/jobs/{job_id}/artifacts
```

每个 artifact item 必须增加：

```json
{
  "listening_review_summary": {},
  "review_verdict": "unreviewed",
  "review_route": "needs_human_review"
}
```

要求：

- 不删除原有字段。
- 不改变下载 URL。
- 不改变 `is_final` 逻辑。
- 不把完整 `metadata_json` 直接铺给前端作为主列表依赖。

### 3. 扩展 jobs 列表的最终成品验收摘要

修改：

```text
GET /api/jobs
GET /api/jobs/{job_id}
```

如果 job 有最终 cover artifact，需要附带：

```json
{
  "final_artifact_review_summary": {},
  "final_artifact_review_verdict": "unreviewed",
  "final_artifact_review_route": "needs_human_review"
}
```

如果没有最终 artifact，则返回空摘要或 `unreviewed`，但必须清楚表达“没有可验收成品”，不能伪装成验收通过。

### 4. 新增轻量汇总接口

新增：

```text
GET /api/reviews/artifacts
```

用于产品侧读取成品验收队列。返回最近 cover final artifacts，字段至少包括：

```json
{
  "items": [
    {
      "job_id": "",
      "artifact_id": "",
      "artifact_type": "cover_master",
      "file_name": "",
      "download_url": "",
      "studio_url": "",
      "review_summary": {},
      "created_at": ""
    }
  ],
  "summary": {
    "total": 0,
    "unreviewed": 0,
    "needs_work": 0,
    "usable": 0,
    "release_candidate": 0,
    "rejected": 0
  }
}
```

支持可选 query：

```text
?verdict=unreviewed
?verdict=needs_work
?verdict=release_candidate
?limit=20
```

必须限制 `limit` 上限，建议最多 100。

### 5. 测试

新增：

```text
tests\api\test_stage50_review_routing_api.py
```

至少覆盖：

- `summarize_listening_review` 对五种 verdict 的 route 映射。
- Stage49 smoke 备注不算人工验收。
- `/api/jobs/{job_id}/artifacts` 返回 review summary。
- `/api/reviews/artifacts` 返回 summary count 和 studio_url。
- 非法 verdict query 返回 422 或明确错误。
- 不触发训练、RVC、UVR、cover job。

## 禁止事项

```text
禁止启动真实训练。
禁止启动真实 RVC 推理。
禁止启动 UVR 分离。
禁止为了测试而覆盖真实人工试听结论。
禁止删除 Stage49 已有 review API。
禁止把 smoke note 当成人工验收通过。
禁止让列表接口返回超长 metadata 导致前端撑爆。
```

## 必跑验证

```powershell
python -m pytest tests\api\test_stage49_listening_review_api.py tests\api\test_stage50_review_routing_api.py -q
python -m pytest tests\api\test_track_studio_versions_api.py -q
python -m backend.self_check
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-50a-review-routing-backend-report.md
```

报告必须包含：

```text
是否完成
新增/修改的接口
review route 映射表
Stage49 API 是否保持兼容
是否检测到 smoke note 且未算人工验收
测试命令与结果
是否触发训练/RVC/UVR/cover：必须为否
是否存在中文乱码：必须为否
```

