# Stage 34A：Effect Rack 导出处理版后端最小闭环

你现在是 FeiShark Studio 的地基 agent。

Stage 33 已经把 Dashboard / Factory 的明显 UI 问题收口。现在回到开发主线：给 Studio 的 Effect Rack 做一个安全、可追踪、不会误导用户的“导出处理版”最小闭环。

注意：本阶段不做真实 DSP，不接 VST，不改 Studio UI。  
第一版只允许复制源成品音频并登记一个新的 `job_artifact`，用于打通版本管理、下载和 Studio URL 链路。

## 阶段目标

实现后端 API：

```text
POST /api/studio/effect-rack/export
```

它接收 Studio 前端保存的 `effect_rack` 草稿参数，校验来源 track/job/artifact，复制源音频到一个新的 artifact，并返回可打开的新 Studio URL。

## 必读文件

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-33a-ui-hotfix-regression-guard-report.md`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\asset_service.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\backend\services\stage_log_service.py`
- `D:\FeiSharkStudio-v2\tests`

## 允许修改

- `backend\main.py`
- 新增：
  - `backend\services\studio_effect_service.py`
- 新增或修改测试：
  - `tests\unit\test_studio_effect_service.py`
  - `tests\api\test_studio_effect_export_api.py`
- 本阶段 report：
  - `docs\agent-md\worker\stage-34a-effect-rack-export-backend-minimal-loop-report.md`

## 禁止修改

- `frontend\studio.html`
- `frontend\js\studio.js`
- `frontend\css\app.css`
- Dashboard / Factory 前端文件
- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- RVC / UVR / ffmpeg 执行层
- README

## API 合同

### Request

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

### Response

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

### Error shape

用 FastAPI `HTTPException` 返回结构化 detail。建议：

```json
{
  "code": "source_artifact_not_found",
  "message": "源产物不存在或不可下载"
}
```

## 服务实现要求

新增 `backend\services\studio_effect_service.py`，至少包含：

- `normalize_effect_rack_payload(...)`
- `validate_effect_rack_slots(...)`
- `export_effect_rack_draft(...)`

### 校验规则

- `track_id` 必须存在。
- `source_job_id` 必须存在。
- `source_job_id` 必须属于 `track_id`。
- `source_job_id` 必须是可打开 Studio 的 cover job，或至少有可下载音频 artifact。
- `source_artifact_id` 如果传入，必须属于 `source_job_id`。
- 如果没传 `source_artifact_id`，可回退到 `get_final_job_artifact(source_job_id)`。
- 源 artifact 文件必须存在。
- `effect_rack` 必须是数组。
- 支持 slot id：
  - `eq`
  - `compressor`
  - `reverb`
  - `limiter`
- 未知 slot 直接拒绝，返回 `unknown_effect_slot`。
- params 只保留允许字段，数值做类型转换和范围裁剪。

### 参数范围

```text
eq.low/mid/high = -6 到 6
compressor.threshold = -30 到 0
compressor.ratio = 1 到 8
reverb.mix = 0 到 100
limiter.ceiling = -6 到 0
```

### artifact 规则

- 新 artifact stage：
  - `studio_effect_export`
- 新 artifact type：
  - `studio_effect_draft_master`
- `is_final = false`
- 复制源音频到：
  - `shared_data/jobs/{source_job_id}/artifacts/studio_effect_export/`
- 文件名必须唯一，例如：
  - `studio_effect_draft_{artifact_id或短uuid}.wav`
- metadata 必须写入：
  - `source_job_id`
  - `source_artifact_id`
  - `track_id`
  - `effect_rack`
  - `export_profile`
  - `processing_mode = copy_only_no_dsp`
  - `warning = 当前未执行真实 DSP/VST，只复制源音频作为处理版草稿`

## API 路由要求

在 `backend\main.py` 增加 Pydantic request model 和 route。

不要把业务逻辑塞进 route；route 只做请求转发和异常映射。

## 测试要求

至少覆盖：

1. `normalize_effect_rack_payload` 能裁剪参数。
2. 未知 slot 被拒绝。
3. 缺失 track 返回结构化错误。
4. source job 不属于 track 被拒绝。
5. source artifact 不存在被拒绝。
6. 成功导出时：
   - 新 artifact 存在
   - artifact type = `studio_effect_draft_master`
   - metadata 包含 `copy_only_no_dsp`
   - download_url 可用
   - studio_url 带 `artifact_id`

## 验证要求

必须执行：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
```

如果新增 API 测试，请确保 pytest 覆盖它。

建议执行：

```powershell
node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

如果没跑建议项，写明原因。

## 交付要求

必须写入：

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-34a-effect-rack-export-backend-minimal-loop-report.md`

report 必须包含：

1. 新 API 路径和 request/response。
2. 新服务文件。
3. artifact type / stage / metadata。
4. 明确说明是否真实 DSP/VST：必须为否。
5. 测试和验证结果。
6. 给产品 agent 的接入说明。

## 完成标准

- 后端 API 可用。
- 成功请求能生成新的可下载 artifact。
- 新 artifact 可通过 Studio URL 指定打开。
- API 和 metadata 明确标注 `copy_only_no_dsp`。
- 不修改前端。
