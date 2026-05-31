# Stage 36B：Studio 渲染模式 UI 接入（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”agent。本阶段只做 Studio 前端接入与 smoke，不改后端核心渲染逻辑。

## 启动条件

必须等 Stage 36A 完成后再开始。

开始前必须读取：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-36a-studio-ffmpeg-dsp-v0-report.md
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-35b-studio-version-ux-cleanup-report.md
D:\FeiSharkStudio-v2\frontend\studio.html
D:\FeiSharkStudio-v2\frontend\js\studio.js
D:\FeiSharkStudio-v2\frontend\css\app.css
```

如果 Stage 36A 报告不存在，停止并报告“缺少后端真实渲染合同，不能开始 36B”。

## 背景

Stage 36A 应提供：

- `GET /api/studio/effect-rack/capabilities`
- `POST /api/studio/effect-rack/export` 支持 `render_engine`
- `copy_only -> copy_only_no_dsp -> studio_effect_draft_master`
- `ffmpeg_dsp_v0 -> ffmpeg_dsp_v0 -> studio_effect_render_master`

本阶段目标是让用户在 Studio 里明确选择“登记草稿”还是“真实渲染 v0”，并让版本抽屉正确显示渲染版本。

## 必做任务

### 1. 接入 capabilities

Studio 初始化时调用：

```text
GET /api/studio/effect-rack/capabilities
```

UI 必须能区分：

- `copy_only.available=true`
- `ffmpeg_dsp_v0.available=true/false`

如果 capabilities 失败：

- 不崩页面。
- 默认只允许 copy-only。
- 显示“真实渲染能力暂不可用，可先登记草稿”。

### 2. 增加渲染模式选择

在 Effect Rack 区域新增清晰选择：

```text
输出模式
[登记草稿] [真实渲染 v0]
```

要求：

- 默认选中“登记草稿”。
- “登记草稿”说明：保存参数和版本，不改变真实音频。
- “真实渲染 v0”说明：调用本机 ffmpeg 离线生成新音频，不是 VST。
- 如果 ffmpeg 不可用，“真实渲染 v0”禁用，并显示原因。

### 3. 导出按钮行为

现有 `#studioEffectRackExportBtn` 可以复用，但文案必须随模式变化：

- copy-only：`导出处理版草稿`
- ffmpeg_dsp_v0：`渲染处理版 v0`

请求体必须带：

```json
{
  "render_engine": "copy_only | ffmpeg_dsp_v0"
}
```

成功提示：

- copy-only：`已生成处理版草稿；当前未执行真实 DSP/VST`
- ffmpeg_dsp_v0：`已生成 ffmpeg v0 渲染版；当前不是 VST`

### 4. 版本抽屉显示新版本类型

版本卡片新增映射：

```text
artifact_type=studio_effect_render_master -> 已渲染处理版
processing_mode=ffmpeg_dsp_v0 -> ffmpeg v0 已应用
```

如果 metadata 里有：

- `applied_effects`
- `unsupported_effects`

则展示成人话：

- 已应用：EQ、Compressor、Limiter
- 暂未支持：Reverb

不要把 `studio_effect_render_master` 误标为母带完成版。

### 5. 当前主成品卡片

当前主成品卡片必须能显示三种来源：

- 原始翻唱成品
- 处理版草稿，仅登记未渲染
- 已渲染处理版，ffmpeg v0

如果当前正在试听的版本不是当前主成品，要明确显示：

```text
当前正在试听：xxx
当前主成品：yyy
```

避免用户误以为播放的一定是主成品。

### 6. Smoke

新增：

```text
frontend\playwright_stage36b_studio_render_mode_smoke.cjs
```

至少验证：

- capabilities 能读取。
- 输出模式 UI 存在。
- copy-only 模式仍可导出草稿。
- 如果 `ffmpeg_dsp_v0.available=true`：
  - 选择真实渲染 v0。
  - 点击渲染。
  - 成功后页面进入新 artifact。
  - 版本抽屉出现“已渲染处理版”。
  - 页面出现“ffmpeg v0 已应用”。
- Stage 35B 版本 UI 仍通过。

## 禁止事项

- 禁止修改后端核心渲染逻辑。
- 禁止接 VST。
- 禁止说浏览器已支持 Windows VST。
- 禁止把 `ffmpeg_dsp_v0` 包装成母带级处理。
- 禁止让全部技术细节默认展开。
- 禁止删除 copy-only 模式。

## 验证命令

必须运行：

```powershell
node frontend\playwright_stage36b_studio_render_mode_smoke.cjs
node frontend\playwright_stage35b_studio_version_ux_smoke.cjs
node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
python -m pytest -q
python -X utf8 backend\self_check.py
```

## 输出报告

填写：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-36b-studio-render-mode-ux-report.md
```

报告必须包含：

- 修改文件清单。
- capabilities 读取结果。
- copy-only 与 ffmpeg v0 的 UI 行为。
- 新截图路径。
- 全部验证结果。
- 风险与限制。
