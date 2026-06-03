# Stage 50A Review Routing Backend Report

## 是否完成

已完成。

## 新增/修改的接口

- 扩展 `GET /api/jobs/{job_id}/artifacts`：每个 artifact 追加 `listening_review_summary`、`review_verdict`、`review_route`，保留原有字段与下载 URL 逻辑。
- 扩展 `GET /api/jobs`：每个 job 追加 `has_reviewable_final_artifact`、`final_artifact_review_summary`、`final_artifact_review_verdict`、`final_artifact_review_route`。
- 扩展 `GET /api/jobs/{job_id}`：追加同样的最终 cover artifact 验收摘要字段。
- 新增 `GET /api/reviews/artifacts`：返回最近 final `cover_master` artifacts，支持 `verdict` 与 `limit` query，`limit` 在 service 层上限 100。

## Review Route 映射表

- `unreviewed` -> `needs_human_review`
- `needs_work` -> `route_to_rework`
- `usable` -> `route_to_candidate_pool`
- `release_candidate` -> `route_to_release_candidate`
- `rejected` -> `route_to_archive_or_rerun`

## Stage49 API 是否保持兼容

是。保留并回归通过：

- `GET /api/jobs/{job_id}/source-audio/download`
- `GET /api/jobs/{job_id}/artifacts/{artifact_id}/review`
- `PATCH /api/jobs/{job_id}/artifacts/{artifact_id}/review`

未覆盖真实人工试听结论，Stage49 review 写入仍只由 PATCH 接口更新 `metadata_json.listening_review`。

## Smoke Note 处理

已检测 `stage49 browser smoke only - not a human quality verdict`，即使 verdict 是 `release_candidate`，`is_human_reviewed` 仍返回 `false`，不会被误判为人工验收。

## 测试命令与结果

- `python -m pytest tests\api\test_stage49_listening_review_api.py tests\api\test_stage50_review_routing_api.py -q`：10 passed。
- `python -m pytest tests\api\test_track_studio_versions_api.py -q`：6 passed。
- `python -m backend.self_check`：`CODE_STRUCTURE_SUMMARY PASS`、`RUNTIME_ENVIRONMENT_SUMMARY PASS`、`SELF_CHECK_SUMMARY PASS`。

## 是否触发训练/RVC/UVR/cover

否。本次实现与 Stage50 API 测试未启动训练、RVC 推理、UVR 分离或 cover 执行任务。

## 是否存在中文乱码

否。本次新增/修改内容按 UTF-8 写入，未引入中文乱码。
