# Stage 35A：Studio 版本账本与主成品合同硬化（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”agent。本阶段只做后端合同、服务层与回归测试，不做 UI 美化，不接真实 DSP/VST。

## 背景

Stage 34 已经打通 `POST /api/studio/effect-rack/export`，但当前产物是 `copy_only_no_dsp` 的 `studio_effect_draft_master`：只复制源音频并登记 artifact，不改变真实听感。

现在的问题是：Studio 已经能导出“处理版草稿”，但 Track 维度还没有一个清晰的“版本账本”。如果继续直接接 DSP/VST，后续会分不清：

- 哪个是原始 cover master。
- 哪个是处理版草稿。
- 哪个是当前主成品。
- 当前主成品是否来自 copy-only 草稿。
- 多次导出草稿时，Studio/Factory 应该展示哪个版本。

本阶段目标是把这些后端语义锁死。

## 读取上下文

开始前必须读取：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-34a-effect-rack-export-backend-minimal-loop-report.md
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-34b-effect-rack-export-ui-hookup-report.md
D:\FeiSharkStudio-v2\backend\services\studio_effect_service.py
D:\FeiSharkStudio-v2\backend\services\track_service.py
D:\FeiSharkStudio-v2\backend\services\asset_service.py
D:\FeiSharkStudio-v2\tests\api\test_track_jobs_api.py
D:\FeiSharkStudio-v2\tests\api\test_studio_effect_export_api.py
```

## 目标

新增或硬化 Track 维度的 Studio 成品版本合同，让前端可以稳定读取“原始成品 + 处理版草稿 + 当前主成品”。

## 必做任务

1. 新增 Track 版本账本读取能力。

建议新增服务函数：

```text
backend\services\track_service.py
list_track_studio_versions(track_id, limit=50, offset=0)
```

建议新增 API：

```text
GET /api/tracks/{track_id}/studio-versions?limit=50&offset=0
```

返回结构必须稳定，至少包含：

```json
{
  "track_id": "trk_xxx",
  "current_master_job_id": "task_xxx",
  "current_master_artifact_id": "art_xxx",
  "current_master": {},
  "items": [
    {
      "version_id": "art_xxx",
      "job_id": "task_xxx",
      "track_id": "trk_xxx",
      "artifact_id": "art_xxx",
      "artifact_type": "cover_master | studio_effect_draft_master",
      "stage_name": "cover_mix | studio_effect_export",
      "file_name": "final_master.wav",
      "file_path": "...",
      "file_size": 123,
      "created_at": "...",
      "is_final": true,
      "is_current_master": false,
      "is_processing_draft": false,
      "processing_mode": "original_cover | copy_only_no_dsp",
      "source_job_id": "",
      "source_artifact_id": "",
      "download_url": "/api/jobs/{job_id}/artifacts/{artifact_id}/download",
      "studio_url": "/studio?track_id={track_id}&job_id={job_id}&artifact_id={artifact_id}",
      "warning": ""
    }
  ],
  "limit": 50,
  "offset": 0
}
```

合同要求：

- `cover_master` 使用 `processing_mode = original_cover`。
- `studio_effect_draft_master` 使用 artifact metadata 内的 `processing_mode`，当前应为 `copy_only_no_dsp`。
- 只返回当前 Track 下完成态 cover job 的可下载音频 artifact。
- 不要把训练模型 `.pth/.index` 混入这个版本账本。
- 如果文件不存在，不应作为可下载版本返回，或者必须显式 `downloadable=false`，并在测试里锁死行为。

2. 硬化 `POST /api/tracks/{track_id}/master`。

现有主成品接口要允许合法的 `cover_master` 和 `studio_effect_draft_master` 成为当前主成品，但必须校验：

- job 必须属于这个 track。
- job 必须是 cover 类型。
- job 必须是完成态。
- artifact 必须属于这个 job。
- artifact 文件必须存在。
- artifact 类型只能是 `cover_master` 或 `studio_effect_draft_master`。
- 禁止训练模型、index、非音频、其他 track 的 artifact 被设为主成品。

返回体建议补充：

```json
{
  "ok": true,
  "track_id": "trk_xxx",
  "current_master_job_id": "task_xxx",
  "current_master_artifact_id": "art_xxx",
  "current_master_artifact_type": "studio_effect_draft_master",
  "current_master_processing_mode": "copy_only_no_dsp",
  "current_master": {}
}
```

3. 修正 `GET /api/tracks/{track_id}/jobs` 对当前主成品的标识一致性。

如果当前主成品是同一个 cover job 下的 `studio_effect_draft_master`，不要再让 jobs 列表误判“没有当前主成品”。

最低要求：

- `current_master_job_id/current_master_artifact_id` 仍然返回。
- 对应 job 项应能表达“这个 job 承载当前主成品 artifact”。
- 不要破坏既有 `final_artifact_id/final_artifact_download_url/studio_url` 字段。
- 如果你新增字段，字段名要自解释，例如：
  - `is_current_master_job`
  - `current_master_artifact_id`
  - `current_master_artifact_type`
  - `current_master_processing_mode`

4. 保持 Stage 34 语义不变。

- 不要把 `copy_only_no_dsp` 改成真实处理。
- 不要把 `studio_effect_draft_master` 默认写成 `is_final=true`。
- 不要让导出草稿自动替换当前主成品，除非用户显式调用 master 接口。

5. 补测试。

至少新增或扩展以下测试：

```text
tests\api\test_track_studio_versions_api.py
```

覆盖：

- 一个 cover job 的 `cover_master` 能进入 studio versions。
- 同一个 job 多次导出 `studio_effect_draft_master` 后，versions 能列出多个草稿。
- `studio_effect_draft_master` 可被显式设为当前主成品，并返回 `copy_only_no_dsp`。
- 非音频 artifact 或训练 artifact 不能设为当前主成品。
- 其他 track 的 job/artifact 不能设为当前主成品。
- `GET /api/tracks/{track_id}/jobs` 在当前主成品是 draft artifact 时仍能表达一致状态。

## 禁止事项

- 禁止修改 Dashboard / Factory / Studio UI。
- 禁止接真实 VST。
- 禁止引入浏览器 VST 方案。
- 禁止破坏 `/api/jobs`、`/api/models`、`/api/tracks/{track_id}/jobs` 既有字段。
- 禁止重写训练/翻唱主链路。
- 禁止删除旧数据或清空数据库。

## 验证命令

必须运行：

```powershell
python -m pytest -q tests\api\test_track_studio_versions_api.py tests\api\test_track_jobs_api.py tests\api\test_studio_effect_export_api.py
python -m pytest -q
python -X utf8 backend\self_check.py
node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

如果有 UI smoke 因端口旧进程导致 404，必须重启本地 uvicorn 后复跑，并在报告里写明。

## 输出报告

完成后填写：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-35a-studio-version-master-contract-report.md
```

报告必须包含：

- 修改文件清单。
- 新增/变更 API 合同。
- 当前主成品语义说明。
- `copy_only_no_dsp` 是否仍保持不变。
- 完整验证命令与结果。
- 未完成项和风险。
