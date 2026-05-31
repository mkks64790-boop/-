# Stage 35B：Studio 版本管理 UI 收口（产品 Agent）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-产品”agent。本阶段只做 Studio 产品 UI 与前端 smoke，不改后端主逻辑。

## 启动条件

必须等 Stage 35A 完成后再开始。

开始前必须读取：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-35a-studio-version-master-contract-report.md
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-34b-effect-rack-export-ui-hookup-report.md
D:\FeiSharkStudio-v2\frontend\studio.html
D:\FeiSharkStudio-v2\frontend\js\studio.js
D:\FeiSharkStudio-v2\frontend\css\app.css
```

如果 Stage 35A 报告不存在，停止并报告“缺少后端版本合同，不能开始 35B”。

## 背景

Studio 现在已经有：

- 当前成品工作台。
- Track 成品历史抽屉。
- 试听品库抽屉。
- Effect Rack 参数草稿。
- 导出处理版草稿按钮。

但 UI 仍然偏工程控制台，不像一个干净的创作工作台。核心混乱点是“成品历史 / 试听品库 / 处理版草稿 / 当前主成品”没有聚合成一个清楚的版本管理区。

## 目标

把 Studio 右侧资源区收口成“当前主成品 + 版本抽屉”的产品结构。用户必须能一眼看懂：

- 现在听的是哪个版本。
- 哪个版本是当前主成品。
- 哪些是原始 cover master。
- 哪些是处理版草稿。
- 处理版草稿当前只是 copy-only/no DSP。
- 如何打开、下载、设为当前主成品。

## 必做任务

1. 接入 Stage 35A 的版本账本 API。

使用：

```text
GET /api/tracks/{track_id}/studio-versions?limit=50&offset=0
```

如果接口不存在或返回失败：

- 不要崩页面。
- 保留现有 `GET /api/tracks/{track_id}/jobs` 的历史能力作为降级。
- 显示明确提示：“版本账本暂不可用，已退回旧成品历史。”

2. 重构 Studio 右侧资源区。

把右侧资源区调整为：

```text
当前主成品卡片
版本抽屉（默认折叠）
试听品库抽屉（默认折叠，降级入口）
Inspector（默认只展示摘要，技术字段可折叠）
```

要求：

- “当前主成品卡片”必须固定显示，不要藏在长列表下面。
- “版本抽屉”默认折叠，只显示数量和当前选择摘要。
- 展开后每个版本卡片最多两行动作，不允许无限堆字段。
- 长路径必须单行截断，hover/title 显示完整值。
- 移动端不能出现横向撑爆。

3. 版本卡片字段与动作。

每个 version item 显示：

- 音色/任务短名。
- artifact 类型：
  - `cover_master` 显示“原始翻唱成品”。
  - `studio_effect_draft_master` 显示“处理版草稿”。
- processing mode：
  - `original_cover` 显示“原始成品”。
  - `copy_only_no_dsp` 显示“仅登记草稿，未执行真实 DSP/VST”。
- 当前主成品 badge。
- 当前正在播放 badge。
- 创建时间。
- 操作：
  - 打开此版本。
  - 下载。
  - 设为当前主成品。

4. Effect Rack 导出后的 UI 行为。

点击“导出处理版草稿”成功后：

- 仍然可以跳转后端返回的 `studio_url`。
- 进入新 artifact 后必须刷新版本账本。
- 新版本应在版本抽屉中可见。
- 不要自动把草稿设为当前主成品，除非用户再点“设为当前主成品”。
- Toast 必须继续明确：“当前未执行真实 DSP/VST”。

5. 文案收口。

避免工程味过重，但不能误导：

- 可以叫“处理版草稿”。
- 不要叫“母带完成版”。
- 不要暗示 EQ/压缩/混响已经真实作用到音频。
- `copy_only_no_dsp` 要翻译成人话，不直接裸露给普通用户，但 Inspector 可以保留技术字段。

6. 新增前端 smoke。

新增：

```text
frontend\playwright_stage35b_studio_version_ux_smoke.cjs
```

至少验证：

- Studio 页面能加载版本账本。
- 当前主成品卡片存在。
- 版本抽屉默认折叠且可展开/收起。
- 至少能看到 `cover_master` 版本。
- 如果存在 `studio_effect_draft_master`，必须显示“处理版草稿”和“未执行真实 DSP/VST”。
- 点击“设为当前主成品”后页面能刷新 badge 或提示成功。
- Effect Rack 导出按钮仍然可用。

## 禁止事项

- 禁止改后端主链路。
- 禁止接真实 VST。
- 禁止把浏览器说成能直接加载 Windows VST。
- 禁止删除现有 Dashboard / Factory 入口。
- 禁止让全部详情默认展开。
- 禁止把 copy-only 草稿文案包装成真实处理完成。

## 验证命令

必须运行：

```powershell
node frontend\playwright_stage35b_studio_version_ux_smoke.cjs
node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
node frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs
python -m pytest -q
python -X utf8 backend\self_check.py
```

## 输出报告

完成后填写：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-35b-studio-version-ux-cleanup-report.md
```

报告必须包含：

- 修改文件清单。
- UI 结构截图路径。
- 版本账本字段使用说明。
- 降级行为说明。
- 完整 smoke / pytest / self_check 结果。
- 未完成项和风险。
