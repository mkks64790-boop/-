# Stage 36A：Studio 真实 ffmpeg DSP v0 后端渲染（地基 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”agent。本阶段只做后端真实音频渲染 v0、合同、测试，不做 UI 美化，不接 VST。

## 背景

Stage 35 已完成：

- `GET /api/tracks/{track_id}/studio-versions`
- `POST /api/tracks/{track_id}/master`
- Studio 右侧“当前主成品 + 版本抽屉”
- 当前 `studio_effect_draft_master` 仍是 `copy_only_no_dsp`

现在要进入下一层：让 Studio Effect Rack 至少能导出一个“真实处理过的音频版本”。本阶段目标不是母带级效果，也不是 VST，而是可验证、可回归、可解释的 ffmpeg DSP v0。

## 启动前必须读取

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-35a-studio-version-master-contract-report.md
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-35b-studio-version-ux-cleanup-report.md
D:\FeiSharkStudio-v2\backend\services\studio_effect_service.py
D:\FeiSharkStudio-v2\backend\services\track_service.py
D:\FeiSharkStudio-v2\backend\main.py
D:\FeiSharkStudio-v2\tests\api\test_track_studio_versions_api.py
D:\FeiSharkStudio-v2\tests\api\test_studio_effect_export_api.py
```

## 核心目标

在不破坏旧 copy-only 行为的前提下，为 `POST /api/studio/effect-rack/export` 增加一个可选真实渲染引擎：

```text
render_engine = copy_only        -> 旧行为，processing_mode=copy_only_no_dsp
render_engine = ffmpeg_dsp_v0    -> 新行为，processing_mode=ffmpeg_dsp_v0
```

默认必须仍是 `copy_only`，保证 Stage 34/35 旧 UI 和旧测试不被破坏。

## 必做任务

### 1. 新增渲染能力探测 API

新增：

```text
GET /api/studio/effect-rack/capabilities
```

返回建议：

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
      "ffmpeg_path": "..."
    }
  ],
  "artifact_types": [
    "studio_effect_draft_master",
    "studio_effect_render_master"
  ]
}
```

如果找不到 ffmpeg：

- `copy_only` 仍 available。
- `ffmpeg_dsp_v0.available=false`。
- 不要让整个接口失败。

### 2. 扩展导出请求合同

扩展 `StudioEffectExportRequest`：

```python
render_engine: str = "copy_only"
```

允许值：

```text
copy_only
ffmpeg_dsp_v0
```

非法值返回结构化错误：

```json
{
  "detail": {
    "code": "unsupported_render_engine",
    "message": "Unsupported render engine: xxx"
  }
}
```

### 3. 保留 copy-only 原语义

当 `render_engine` 缺失或等于 `copy_only`：

- 行为必须和 Stage 34/35 一致。
- artifact type 仍为 `studio_effect_draft_master`。
- stage 仍为 `studio_effect_export`。
- processing_mode 仍为 `copy_only_no_dsp`。
- 不自动设为当前主成品。

### 4. 新增 ffmpeg DSP v0 真实渲染

当 `render_engine=ffmpeg_dsp_v0`：

- 必须调用本机 ffmpeg，不允许只复制文件冒充。
- 使用 `subprocess.run([...], shell=False, timeout=...)`。
- 输出新 artifact：

```text
stage_name = studio_effect_render
artifact_type = studio_effect_render_master
processing_mode = ffmpeg_dsp_v0
is_final = false
```

输出路径建议：

```text
shared_data/jobs/{source_job_id}/artifacts/studio_effect_render/studio_effect_render_{uuid}.wav
```

metadata 至少包含：

```json
{
  "source_job_id": "task_xxx",
  "source_artifact_id": "art_xxx",
  "track_id": "trk_xxx",
  "effect_rack": [],
  "export_profile": "studio_balanced",
  "render_engine": "ffmpeg_dsp_v0",
  "processing_mode": "ffmpeg_dsp_v0",
  "applied_effects": [],
  "unsupported_effects": []
}
```

### 5. v0 支持范围要保守

不要承诺母带级效果。v0 只要求完成以下可验证映射：

- `eq`：可用 ffmpeg `equalizer` 过滤器实现 low/mid/high 三段增益，频点可固定为 100Hz / 1000Hz / 8000Hz。
- `compressor`：可用 ffmpeg `acompressor`，阈值和 ratio 来自参数。
- `limiter`：可用 ffmpeg `alimiter` 或安全等价处理。
- `reverb`：如果实现复杂，可以先标记到 `unsupported_effects`，不要假装已处理。

如果某个 slot disabled，不应加入 filter。

如果没有任何可应用 effect：

- 可以执行一次安全转码，processing_mode 仍为 `ffmpeg_dsp_v0`。
- metadata 里 `applied_effects=[]`。
- UI 后续会显示“已渲染，但没有启用可应用效果”。

### 6. 错误处理

必须结构化错误：

- `ffmpeg_not_available`
- `ffmpeg_render_failed`
- `unsupported_render_engine`
- 继续保留 Stage 34 已有错误码。

ffmpeg stderr 不要全部返回给前端，截断到安全长度，例如 1000 字符以内。

### 7. 更新版本账本与主成品合同

`GET /api/tracks/{track_id}/studio-versions` 必须纳入：

```text
studio_effect_render_master
```

`POST /api/tracks/{track_id}/master` 必须允许合法的：

```text
cover_master
studio_effect_draft_master
studio_effect_render_master
```

processing mode：

```text
cover_master -> original_cover
studio_effect_draft_master -> copy_only_no_dsp
studio_effect_render_master -> ffmpeg_dsp_v0
```

### 8. 测试

新增或扩展：

```text
tests\unit\test_studio_render_service.py
tests\api\test_studio_effect_render_api.py
tests\api\test_track_studio_versions_api.py
```

至少覆盖：

- 默认缺省 `render_engine` 仍走 copy-only，旧断言不变。
- `GET /api/studio/effect-rack/capabilities` 总是返回 copy_only，ffmpeg 状态可被读取。
- `render_engine=ffmpeg_dsp_v0` 能生成 `studio_effect_render_master`。
- render artifact 能进入 `/studio-versions`。
- render artifact 能被显式设为当前主成品。
- 非法 render_engine 返回 `unsupported_render_engine`。
- ffmpeg 不可用时返回 `ffmpeg_not_available`，不能静默降级成 copy-only。

## 禁止事项

- 禁止接 VST。
- 禁止在浏览器端做 Windows VST。
- 禁止让 `ffmpeg_dsp_v0` 静默失败后伪装成功。
- 禁止覆盖 `copy_only_no_dsp` 的旧语义。
- 禁止导出后自动设为当前主成品。
- 禁止重写 RVC / UVR / 训练主链。

## 验证命令

必须运行：

```powershell
python -m pytest -q tests\unit\test_studio_render_service.py tests\api\test_studio_effect_render_api.py tests\api\test_studio_effect_export_api.py tests\api\test_track_studio_versions_api.py
python -m pytest -q
python -X utf8 backend\self_check.py
node frontend\playwright_stage35b_studio_version_ux_smoke.cjs
node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

## 输出报告

填写：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-36a-studio-ffmpeg-dsp-v0-report.md
```

报告必须写清楚：

- ffmpeg 是否可用。
- 新增 API / 字段 / artifact type。
- 哪些 effect 真正应用，哪些暂未支持。
- `copy_only_no_dsp` 是否保持旧语义。
- 全部验证结果。
- 风险与限制。
