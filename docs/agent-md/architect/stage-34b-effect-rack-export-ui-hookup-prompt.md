# Stage 34B：Studio Effect Rack 导出按钮接入

你现在是 FeiShark Studio 的产品体验 agent。

必须在 Stage 34A 地基 agent 完成后执行。  
你的任务是把 Studio 里的 `导出处理版` 按钮接入后端最小闭环 API。注意：后端第一版只是复制源音频并登记新 artifact，不是真实 DSP/VST。

## 必读文件

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-34a-effect-rack-export-backend-minimal-loop-report.md`
- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\playwright_stage30b_studio_product_shell_smoke.cjs`
- `D:\FeiSharkStudio-v2\frontend\playwright_trained_model_cover_studio_smoke.cjs`

如果 Stage 34A report 还没完成，不要执行本阶段。

## 允许修改

- `frontend\studio.html`
- `frontend\js\studio.js`
- `frontend\css\app.css`
- 新增：
  - `frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs`
- 本阶段 report：
  - `docs\agent-md\worker\stage-34b-effect-rack-export-ui-hookup-report.md`

## 禁止修改

- 后端任何文件
- Dashboard / Factory 文件
- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- README

## UI 接入要求

### 1. 按钮启用

当前 Studio 里 `#studioEffectRackExportBtn` 是 disabled 的预留按钮。

现在改为：

- 有当前 `track_id`
- 有当前 `job_id`
- 有当前可播放 artifact
- 后端 API 可用

则按钮可点击。

按钮文案必须避免误导：

```text
导出处理版草稿
```

按钮附近必须显示提示：

```text
当前导出为 copy-only 草稿：会登记新版本，但暂不执行真实 DSP/VST。
```

### 2. 请求后端

点击按钮时 POST：

```text
/api/studio/effect-rack/export
```

body：

```json
{
  "track_id": "...",
  "source_job_id": "...",
  "source_artifact_id": "...",
  "effect_rack": state.effectRackState,
  "export_profile": "studio_balanced",
  "note": "optional"
}
```

### 3. 成功行为

成功后：

- toast 告知：
  - `已生成处理版草稿；当前未执行真实 DSP/VST`
- 使用 response 的 `studio_url` 跳转或重新加载当前 Studio。
- 新 artifact 应能成为当前试听 artifact。
- Inspector 应能看到 artifact type 或 stage 为 `studio_effect_draft_master / studio_effect_export`。

### 4. 失败行为

失败时：

- 保持当前页面状态。
- toast 显示后端 `code/message`。
- 不清空 Effect Rack 草稿。

### 5. Smoke

新增：

- `frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs`

至少验证：

1. 打开一个有 track/job/artifact 的 Studio URL。
2. Effect Rack 可见。
3. 开启 EQ 或修改一个参数。
4. 点击 `导出处理版草稿`。
5. 后端返回成功。
6. 页面跳到带新 `artifact_id` 的 Studio URL。
7. 下载按钮可用。
8. 页面文本包含：
   - `copy-only`
   - `暂不执行真实 DSP/VST`
   - 或 `处理版草稿`
9. 截图：
   - `stage34b_effect_rack_export_ui.png`

## 验证要求

必须执行：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

建议执行：

```powershell
node frontend\playwright_stage32b_three_page_layout_smoke.cjs
node frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs
```

如果建议项没跑，写明原因。

## 交付要求

必须写入：

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-34b-effect-rack-export-ui-hookup-report.md`

report 必须包含：

1. UI 按钮如何启用。
2. 请求体字段。
3. 成功后如何跳转。
4. 如何避免误导用户以为真实 DSP/VST 已执行。
5. 新 smoke 结果。
6. 是否修改后端：必须为否。

## 完成标准

- Studio 能从 Effect Rack 导出一个处理版草稿 artifact。
- 新 artifact 可下载、可通过 Studio URL 打开。
- UI 文案明确 copy-only / no DSP / no VST。
- Stage 28 真实闭环不回退。
