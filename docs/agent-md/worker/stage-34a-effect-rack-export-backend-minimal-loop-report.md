# Stage 34A 执行汇报：Effect Rack 导出处理版后端最小闭环

## 完成情况

- 已完成：新增 `POST /api/studio/effect-rack/export`。
- 已完成：新增 `studio_effect_service.py`，封装 Effect Rack 参数归一化、slot 校验、copy-only 导出与 artifact 登记。
- 已完成：新增 unit/API 测试，覆盖参数裁剪、未知 slot、缺失 track、source job 归属校验、source artifact 缺失、成功导出与下载。
- 已完成：明确当前不是 DSP/VST，只复制源成品音频并登记 `studio_effect_draft_master`。
- 已完成：必跑验证与建议验证均通过。

## 修改文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\studio_effect_service.py`
- `D:\FeiSharkStudio-v2\tests\unit\test_studio_effect_service.py`
- `D:\FeiSharkStudio-v2\tests\api\test_studio_effect_export_api.py`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-34a-effect-rack-export-backend-minimal-loop-report.md`

本阶段未修改：

- `frontend\studio.html`
- `frontend\js\studio.js`
- `frontend\css\app.css`
- Dashboard / Factory 前端文件
- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- README

说明：工作区中存在前序阶段遗留 dirty 文件；本轮未回滚或改写这些文件。

## API 合同

```text
method = POST
path = /api/studio/effect-rack/export
```

Request：

```json
{
  "track_id": "trk_xxx",
  "source_job_id": "task_xxx",
  "source_artifact_id": "art_xxx",
  "effect_rack": [
    {
      "id": "eq",
      "enabled": true,
      "status": "draft",
      "params": { "low": 0, "mid": 0, "high": 0 }
    }
  ],
  "export_profile": "studio_balanced",
  "note": "optional local note"
}
```

Response：

```json
{
  "ok": true,
  "processing_mode": "copy_only_no_dsp",
  "track_id": "trk_xxx",
  "source_job_id": "task_xxx",
  "source_artifact_id": "art_xxx",
  "artifact_id": "art_xxx",
  "artifact_type": "studio_effect_draft_master",
  "download_url": "/api/jobs/task_xxx/artifacts/art_xxx/download",
  "studio_url": "/studio?track_id=trk_xxx&job_id=task_xxx&artifact_id=art_xxx",
  "message": "已登记处理版草稿；当前为复制源音频，不包含真实 DSP/VST 处理。"
}
```

Error shape：

```json
{
  "detail": {
    "code": "source_artifact_not_found",
    "message": "Source artifact does not exist or is not downloadable."
  }
}
```

已实现错误码包括：

- `track_not_found`
- `source_job_not_found`
- `source_job_not_for_track`
- `invalid_effect_rack`
- `unknown_effect_slot`
- `source_artifact_not_found`
- `source_artifact_not_audio`
- `studio_effect_export_failed`

## 服务文件

新增：

```text
D:\FeiSharkStudio-v2\backend\services\studio_effect_service.py
```

主要函数：

- `normalize_effect_rack_payload(...)`
- `validate_effect_rack_slots(...)`
- `export_effect_rack_draft(...)`

支持 slot：

- `eq`
- `compressor`
- `reverb`
- `limiter`

参数范围：

```text
eq.low/mid/high = -6 到 6
compressor.threshold = -30 到 0
compressor.ratio = 1 到 8
reverb.mix = 0 到 100
limiter.ceiling = -6 到 0
```

行为：

- 未知 slot 直接拒绝，返回 `unknown_effect_slot`。
- params 只保留允许字段。
- 数值参数做类型转换与范围裁剪。
- `effect_rack` 必须是数组。

## Artifact 结果

```text
stage_name = studio_effect_export
artifact_type = studio_effect_draft_master
is_final = false
metadata.processing_mode = copy_only_no_dsp
download_url = /api/jobs/{source_job_id}/artifacts/{artifact_id}/download
studio_url = /studio?track_id={track_id}&job_id={source_job_id}&artifact_id={artifact_id}
```

文件写入：

```text
shared_data/jobs/{source_job_id}/artifacts/studio_effect_export/studio_effect_draft_{uuid}.wav
```

metadata 写入：

- `source_job_id`
- `source_artifact_id`
- `track_id`
- `effect_rack`
- `export_profile`
- `processing_mode = copy_only_no_dsp`
- `warning = 当前未执行真实 DSP/VST，只复制源音频作为处理版草稿。`
- `note`，如果请求传入

## 音频处理真实性

```text
是否真实 DSP = 否
是否接 VST = 否
是否复制源音频 = 是
UI 是否必须提示 copy_only_no_dsp = 是
```

本阶段只打通“版本管理 / artifact / 下载 / Studio URL”最小闭环。不得向用户暗示已经执行 EQ、压缩、混响、限制器或 VST 处理。

## 测试结果

```text
python -m pytest -q tests\unit\test_studio_effect_service.py tests\api\test_studio_effect_export_api.py
结果：PASS，7 passed, 2 warnings in 1.28s

python -m pytest -q
结果：PASS，26 passed, 2 warnings in 4.28s

python -X utf8 backend\self_check.py
结果：PASS，SELF_CHECK_SUMMARY PASS

node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
结果：PASS，STAGE30B_STUDIO_PRODUCT_SHELL_SMOKE PASS
studio_url=http://127.0.0.1:8000/studio?track_id=trk_c66cc953d5&job_id=task_ece82726a4c3

node frontend\playwright_trained_model_cover_studio_smoke.cjs
结果：PASS，STAGE28_TRAINED_MODEL_COVER_SMOKE PASS
model_id=v_b5c8427a；source_job_id=train_d8cd4ed377ca；track_id=trk_7df9d48f70；cover_job_id=task_f2a9b4b59616；final_stage=cover_mix
studio_url=/studio?batch_id=batch_dfdf9c4631&track_id=trk_7df9d48f70&job_id=task_f2a9b4b59616&artifact_id=art_736c6c7422f4
```

## 给产品 agent 的接入说明

- 请求路径：`POST /api/studio/effect-rack/export`
- 必传字段：`track_id`、`source_job_id`、`effect_rack`
- 推荐传入字段：`source_artifact_id`，避免默认 final artifact 与用户当前选择不一致
- 成功后跳转：使用响应里的 `studio_url`
- 下载：使用响应里的 `download_url`
- 失败显示：读取 `detail.code` 与 `detail.message`
- 必须保留文案约束：当前导出为 `copy_only_no_dsp`，只复制源音频作为处理版草稿，不包含真实 DSP/VST 处理

建议前端成功提示：

```text
已生成处理版草稿。当前版本仅复制源音频并记录 Effect Rack 参数，尚未执行真实 DSP/VST。
```

## 风险与限制

- 风险 1：当前 artifact 是 copy-only 草稿，音频听感不会因为 Effect Rack 参数改变。
- 风险 2：`studio_effect_draft_master` 当前 `is_final=false`，不会替换 track current master；如果后续要“设为主成品”，需要走现有 master 选择语义或单独设计。
- 风险 3：目前未接前端按钮，Stage 34A 只提供后端 API 和测试。

## 交接说明

- 下一阶段接前端时，不要复写 Studio 主链；只在现有 Effect Rack 导出按钮处调用本 API。
- 前端必须把 `processing_mode=copy_only_no_dsp` 显示成人话，避免误导用户以为真实效果已处理。
- 如果后续接真实 WebAudio / ffmpeg / VST，需要新增 processing mode，不要覆盖本阶段 copy-only 语义。
