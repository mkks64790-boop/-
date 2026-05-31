# Stage 36A 执行汇报：Studio 真实 ffmpeg DSP v0 后端渲染

## 启动检查

- Stage 35A 报告是否已读取：是，已读取 `stage-35a-studio-version-master-contract-report.md`。
- Stage 35B 报告是否已读取：是，已读取 `stage-35b-studio-version-ux-cleanup-report.md`。
- ffmpeg 是否可用：是。
- ffmpeg 路径：`C:\Users\ASUS\scoop\shims\ffmpeg.exe`。
- ffmpeg 版本：`ffmpeg version 8.1-full_build-www.gyan.dev`。

## 完成情况

- 已完成：新增 `GET /api/studio/effect-rack/capabilities`。
- 已完成：扩展 `POST /api/studio/effect-rack/export` 请求字段 `render_engine`。
- 已完成：保留 `render_engine=copy_only` 默认行为，旧 copy-only 合同不变。
- 已完成：新增 `render_engine=ffmpeg_dsp_v0` 真实 ffmpeg 渲染分支，使用 `subprocess.run([...], shell=False, timeout=...)`。
- 已完成：新增真实渲染 artifact：`stage_name=studio_effect_render`，`artifact_type=studio_effect_render_master`，`processing_mode=ffmpeg_dsp_v0`，`is_final=false`。
- 已完成：`GET /api/tracks/{track_id}/studio-versions` 纳入 `studio_effect_render_master`。
- 已完成：`POST /api/tracks/{track_id}/master` 允许合法 `studio_effect_render_master` 被显式设置为当前主成品。
- 已完成：新增 unit/API 测试，覆盖 capabilities、非法 render_engine、ffmpeg 不可用、真实渲染、versions、master 合同。

## 修改文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\studio_effect_service.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\tests\unit\test_studio_render_service.py`
- `D:\FeiSharkStudio-v2\tests\api\test_studio_effect_render_api.py`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-36a-studio-ffmpeg-dsp-v0-report.md`

本阶段未修改：

- Dashboard / Factory / Studio 前端 UI
- RVC / UVR / 训练主链
- Stage 34/35 copy-only 与 versions UI 语义
- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`

## API 合同

### GET /api/studio/effect-rack/capabilities

返回示例：

```json
{
  "ok": true,
  "engines": [
    {
      "id": "copy_only",
      "label": "登记草稿",
      "available": true,
      "processing_mode": "copy_only_no_dsp"
    },
    {
      "id": "ffmpeg_dsp_v0",
      "label": "ffmpeg DSP v0",
      "available": true,
      "processing_mode": "ffmpeg_dsp_v0",
      "ffmpeg_path": "C:\\Users\\ASUS\\scoop\\shims\\ffmpeg.exe"
    }
  ],
  "artifact_types": [
    "studio_effect_draft_master",
    "studio_effect_render_master"
  ]
}
```

如果 ffmpeg 不可用：

- `copy_only.available = true`
- `ffmpeg_dsp_v0.available = false`
- capabilities 接口仍返回 `ok=true`

### POST /api/studio/effect-rack/export

新增字段：

```json
{
  "render_engine": "copy_only | ffmpeg_dsp_v0"
}
```

默认行为：

- 缺省 `render_engine` 时等同 `copy_only`。
- `copy_only` 行为与 Stage 34/35 完全一致。

非法值错误：

```json
{
  "detail": {
    "code": "unsupported_render_engine",
    "message": "Unsupported render engine: vst_native"
  }
}
```

ffmpeg 不可用错误：

```json
{
  "detail": {
    "code": "ffmpeg_not_available",
    "message": "ffmpeg is not available on this machine."
  }
}
```

ffmpeg 渲染失败错误：

```json
{
  "detail": {
    "code": "ffmpeg_render_failed",
    "message": "ffmpeg render failed: ..."
  }
}
```

stderr 会截断到安全长度，不会完整透传。

## Artifact 与 Processing Mode

### copy-only

```text
render_engine = copy_only
stage_name = studio_effect_export
artifact_type = studio_effect_draft_master
processing_mode = copy_only_no_dsp
is_final = false
```

语义：只复制源音频并登记 Effect Rack 参数，不执行真实 DSP/VST，不自动设为当前主成品。

### ffmpeg DSP v0

```text
render_engine = ffmpeg_dsp_v0
stage_name = studio_effect_render
artifact_type = studio_effect_render_master
processing_mode = ffmpeg_dsp_v0
is_final = false
```

输出路径：

```text
shared_data/jobs/{source_job_id}/artifacts/studio_effect_render/studio_effect_render_{uuid}.wav
```

metadata 至少包含：

- `source_job_id`
- `source_artifact_id`
- `track_id`
- `effect_rack`
- `export_profile`
- `render_engine = ffmpeg_dsp_v0`
- `processing_mode = ffmpeg_dsp_v0`
- `applied_effects`
- `unsupported_effects`
- `ffmpeg_path`
- `ffmpeg_filtergraph`

## 已支持效果

- EQ：支持。映射为 ffmpeg `equalizer`，固定频点：
  - low = 100Hz
  - mid = 1000Hz
  - high = 8000Hz
- Compressor：支持。映射为 ffmpeg `acompressor`，threshold 从 dB 转为线性值，ratio 直接使用。
- Limiter：支持。映射为 ffmpeg `alimiter`，ceiling 从 dB 转为线性 limit。
- Reverb：暂不支持。启用时写入 `unsupported_effects`，不假装已经处理。

如果没有启用任何可应用 effect，会执行一次安全转码，`processing_mode` 仍为 `ffmpeg_dsp_v0`，`applied_effects=[]`。

## Track Versions / Master 合同更新

`GET /api/tracks/{track_id}/studio-versions` 新增纳入：

```text
studio_effect_render_master
```

processing mode 映射：

```text
cover_master -> original_cover
studio_effect_draft_master -> copy_only_no_dsp
studio_effect_render_master -> ffmpeg_dsp_v0
```

`POST /api/tracks/{track_id}/master` 允许合法：

```text
cover_master
studio_effect_draft_master
studio_effect_render_master
```

仍然要求：

- job 属于当前 track
- job 是 cover 类型
- job 已完成
- artifact 属于该 job
- artifact 文件存在
- artifact 是音频文件
- 必须用户显式调用 master 接口才会替换当前主成品

## 回归验证

```text
python -m pytest -q tests\unit\test_studio_render_service.py tests\api\test_studio_effect_render_api.py tests\api\test_studio_effect_export_api.py tests\api\test_track_studio_versions_api.py
结果：PASS，16 passed, 2 warnings in 2.69s

python -m pytest -q
结果：PASS，39 passed, 2 warnings in 6.73s

python -X utf8 backend\self_check.py
结果：PASS，SELF_CHECK_SUMMARY PASS

node frontend\playwright_stage35b_studio_version_ux_smoke.cjs
结果：PASS，STAGE35B_STUDIO_VERSION_UX_SMOKE PASS
track_id=trk_33d3b2375e
job_id=task_aeac59158ccb
draft_artifact_id=art_26d4797921a5

node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
结果：PASS，STAGE34B_EFFECT_RACK_EXPORT_UI_SMOKE PASS
exported_artifact_id=art_cac25b720c64

node frontend\playwright_trained_model_cover_studio_smoke.cjs
结果：PASS，STAGE28_TRAINED_MODEL_COVER_SMOKE PASS
model_id=v_b5c8427a
source_job_id=train_d8cd4ed377ca
track_id=trk_aac1741483
cover_job_id=task_1acf9a46b90b
final_stage=cover_mix
```

## 风险与限制

- 风险 1：ffmpeg DSP v0 是可验证的基础处理，不是母带级处理，不接 VST。
- 风险 2：Reverb 当前只进入 `unsupported_effects`，不会被真实应用。
- 风险 3：ffmpeg 不可用时，`ffmpeg_dsp_v0` 会显式失败为 `ffmpeg_not_available`，不会静默降级成 copy-only。
- 风险 4：Stage 34B UI 目前默认仍调用 copy-only；本阶段只提供后端真实渲染能力，未修改 UI。
- 风险 5：`studio_effect_render_master` 默认 `is_final=false`，不会自动替换当前主成品。

## 交接给产品 Agent

- 进入 Studio 时可以先调用 `GET /api/studio/effect-rack/capabilities` 判断 `ffmpeg_dsp_v0.available`。
- 仍要保留 `copy_only` 作为安全默认。
- 用户选择真实渲染时，请在导出请求里传：

```json
{
  "render_engine": "ffmpeg_dsp_v0"
}
```

- UI 展示 `ffmpeg_dsp_v0` 时可说“已执行 ffmpeg DSP v0 渲染”，但不能说 VST 或母带级处理。
- UI 展示 `unsupported_effects` 时，应明确显示哪些效果暂未应用，例如 Reverb。
- 如果用户要把渲染版设为当前主成品，必须显式调用 `POST /api/tracks/{track_id}/master`。
