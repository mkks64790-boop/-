# Stage 36B 执行汇报：Studio 渲染模式 UI 接入

## 启动条件检查

- Stage 36A 报告是否已读取：是，已读取 `stage-36a-studio-ffmpeg-dsp-v0-report.md`。
- Stage 35B 报告是否已读取：是，已读取 `stage-35b-studio-version-ux-cleanup-report.md`。
- capabilities 是否可用：是，`GET /api/studio/effect-rack/capabilities` 返回 200。
- ffmpeg_dsp_v0 是否可用：是，`ffmpeg_path=C:\Users\ASUS\scoop\shims\ffmpeg.EXE`。
- 本阶段是否修改后端核心渲染逻辑：否。

## 完成情况

- 已完成：Studio 初始化接入 `GET /api/studio/effect-rack/capabilities`。
- 已完成：Effect Rack 新增输出模式选择 `[登记草稿] [真实渲染 v0]`。
- 已完成：默认选择 `copy_only`，capabilities 失败时仍降级允许登记草稿。
- 已完成：`ffmpeg_dsp_v0` 不可用时禁用真实渲染按钮并显示原因。
- 已完成：导出请求体发送 `render_engine: "copy_only" | "ffmpeg_dsp_v0"`。
- 已完成：导出按钮文案按模式切换：
  - copy-only：`导出处理版草稿`
  - ffmpeg_dsp_v0：`渲染处理版 v0`
- 已完成：成功提示按模式切换：
  - copy-only：`已生成处理版草稿；当前未执行真实 DSP/VST`
  - ffmpeg_dsp_v0：`已生成 ffmpeg v0 渲染版；当前不是 VST`
- 已完成：版本抽屉新增映射：
  - `studio_effect_render_master -> 已渲染处理版`
  - `ffmpeg_dsp_v0 -> ffmpeg v0 已应用`
- 已完成：当版本 metadata 可读时，展示 `已应用：EQ、Compressor、Limiter` / `暂未支持：Reverb`。
- 已完成：当前主成品卡片区分原始翻唱成品、处理版草稿、ffmpeg v0 已渲染处理版。
- 已完成：当前试听版本与当前主成品不一致时，明确显示 `当前正在试听：...` 和 `当前主成品：...`。
- 已完成：新增 `frontend\playwright_stage36b_studio_render_mode_smoke.cjs`。

## 修改文件

- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\playwright_stage36b_studio_render_mode_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-36b-studio-render-mode-ux-report.md`

## capabilities 读取结果

```json
{
  "ok": true,
  "engines": [
    {
      "id": "copy_only",
      "available": true,
      "processing_mode": "copy_only_no_dsp"
    },
    {
      "id": "ffmpeg_dsp_v0",
      "available": true,
      "processing_mode": "ffmpeg_dsp_v0",
      "ffmpeg_path": "C:\\Users\\ASUS\\scoop\\shims\\ffmpeg.EXE"
    }
  ],
  "artifact_types": [
    "studio_effect_draft_master",
    "studio_effect_render_master"
  ]
}
```

## UI 截图

```text
Stage 36B screenshot = D:\FeiSharkStudio-v2\stage36b_studio_render_mode.png
```

## UI 行为

- copy-only：默认选中，说明为保存参数和版本、不改变真实音频；导出后生成 `studio_effect_draft_master`，继续明确标注未执行真实 DSP/VST。
- ffmpeg_dsp_v0：capabilities 可用时可选，说明为调用本机 ffmpeg 离线生成新音频、不是 VST；导出后生成 `studio_effect_render_master`，版本抽屉显示 `已渲染处理版` 和 `ffmpeg v0 已应用`。
- ffmpeg 不可用降级：保留 copy-only；真实渲染按钮禁用，提示本机未检测到可用 ffmpeg 或 capabilities 失败原因。

## 验证结果

```text
node frontend\playwright_stage36b_studio_render_mode_smoke.cjs
结果：PASS
track_id=trk_ecadf93e88
job_id=task_739ef70c765a
source_artifact_id=art_2a1c4d23b27a
copy_artifact_id=art_06981c5e8c68
ffmpeg_available=yes
render_artifact_id=art_47a014f4d062
screenshot=D:\FeiSharkStudio-v2\stage36b_studio_render_mode.png

node frontend\playwright_stage35b_studio_version_ux_smoke.cjs
结果：PASS
track_id=trk_ecadf93e88
job_id=task_739ef70c765a
draft_artifact_id=art_06981c5e8c68
screenshot=D:\FeiSharkStudio-v2\stage35b_studio_version_ux.png

node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
结果：PASS
exported_artifact_id=art_9c6e045c85b7
screenshot=D:\FeiSharkStudio-v2\stage34b_effect_rack_export_ui.png

node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
结果：PASS
job_id=task_739ef70c765a
track_id=trk_ecadf93e88
screenshot=D:\FeiSharkStudio-v2\stage30b_studio_product_shell.png

python -m pytest -q
结果：PASS，39 passed, 2 warnings in 6.94s

python -X utf8 backend\self_check.py
结果：FAIL
失败项：cover preflight usable model，model_id=v_77d72349，preflight_ok=False
定位：`/api/preflight/cover?model_id=v_77d72349` 返回 RVC service offline / rvc_model_load_probe failed，需要外部 RVC / Gradio 服务可用后重跑。
```

## 风险与限制

- `ffmpeg_dsp_v0` 只是可验证的本机 ffmpeg v0 处理链，不是 VST，也不是母带级处理。
- Reverb 当前由后端写入 `unsupported_effects`，UI 会显示暂未支持，不假装已应用。
- `studio_effect_render_master` 默认不会自动替换当前主成品，仍需要用户显式点击“设为当前主成品”。
- 本次 `self_check.py` 的失败来自外部 RVC 服务不可用，不在 36B 前端接入范围内；前端 smoke 与后端 pytest 已通过。

## 交接说明

- 36B 可以交给验收：Studio 已能在 Effect Rack 里显式选择“登记草稿”或“真实渲染 v0”。
- 后续若进入波形 / 片段编辑，应继续复用当前 `render_engine` 与版本账本语义，不要覆盖 `copy_only_no_dsp` 与 `ffmpeg_dsp_v0`。
- 仍建议人工真机听感确认：copy-only 版本音频应不变，ffmpeg v0 版本应体现 EQ / Compressor / Limiter 的基础处理，Reverb 不应生效。
