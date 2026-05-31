# Stage 34B 执行汇报：Studio Effect Rack 导出按钮接入

## 完成情况

- 已完成：Studio `#studioEffectRackExportBtn` 已接入 `POST /api/studio/effect-rack/export`。
- 已完成：按钮按 Track / Job / 可播放 Artifact / 后端 API 可用状态启用。
- 已完成：UI 明确提示当前是 `copy-only` 草稿，不执行真实 DSP/VST。
- 已完成：新增 Stage 34B UI smoke，并完成必选与建议验证。
- 部分完成：无。
- 未完成：无。

## 修改文件

- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-34b-effect-rack-export-ui-hookup-report.md`

## UI 行为

```text
按钮 id = #studioEffectRackExportBtn
按钮文案 = 导出处理版草稿
按钮启用条件 = 有 state.sourceTrackId；有 state.selectedJob.job_id；有 state.sourceArtifactId；当前 artifact 有 download_url；/api/health 可访问；当前没有导出请求进行中
请求路径 = POST /api/studio/effect-rack/export
成功后跳转 = 优先使用 response.studio_url 设置 window.location.href；如果没有 studio_url，则用 response.artifact_id 重新 loadJob
失败后行为 = 保持当前页面和 Effect Rack 草稿状态；toast 显示 detail.code / detail.message
```

## 请求体字段

```json
{
  "track_id": "state.sourceTrackId",
  "source_job_id": "state.selectedJob.job_id",
  "source_artifact_id": "state.sourceArtifactId",
  "effect_rack": "state.effectRackState",
  "export_profile": "studio_balanced",
  "note": "studioJobNoteInput 的本机备注，最多 240 字"
}
```

## 防误导文案

```text
copy-only 提示 = 当前导出为 copy-only 草稿：会登记新版本，但暂不执行真实 DSP/VST。
no DSP/VST 提示 = 当前是 copy-only 后处理参数草稿，导出会登记新版本，但暂不执行真实 DSP/VST。
处理版草稿提示 = 导出处理版草稿 / 已生成处理版草稿；当前未执行真实 DSP/VST
```

说明：UI 没有暗示 EQ、压缩、混响、Limiter 已真实作用到音频。导出后的 artifact 仍按 Stage 34A 合同标记为 `studio_effect_draft_master` / `studio_effect_export`，当前只是复制源音频并登记新版本。

## Smoke 结果

```text
python -m pytest -q
结果：PASS，26 passed, 2 warnings in 4.56s

python -X utf8 backend\self_check.py
结果：PASS，SELF_CHECK_SUMMARY PASS

node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
结果：PASS，STAGE34B_EFFECT_RACK_EXPORT_UI_SMOKE PASS
source_studio_url=http://127.0.0.1:8000/studio?track_id=trk_7df9d48f70&job_id=task_f2a9b4b59616&artifact_id=art_736c6c7422f4
exported_studio_url=http://127.0.0.1:8000/studio?job_id=task_f2a9b4b59616&artifact_id=art_b0d25bbcb441&track_id=trk_7df9d48f70&batch_id=batch_dfdf9c4631
exported_artifact_id=art_b0d25bbcb441
download_href=http://127.0.0.1:8000/api/jobs/task_f2a9b4b59616/artifacts/art_b0d25bbcb441/download

node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
结果：PASS，STAGE30B_STUDIO_PRODUCT_SHELL_SMOKE PASS

node frontend\playwright_trained_model_cover_studio_smoke.cjs
结果：PASS，STAGE28_TRAINED_MODEL_COVER_SMOKE PASS
model_id=v_b5c8427a
source_job_id=train_d8cd4ed377ca
track_id=trk_44e386c6ed
cover_job_id=task_d07fdba3ce5c
final_stage=cover_mix
```

建议项：

```text
node frontend\playwright_stage32b_three_page_layout_smoke.cjs
结果：PASS，STAGE32B_THREE_PAGE_LAYOUT_SMOKE PASS

node frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs
结果：PASS，STAGE33A_UI_HOTFIX_GUARD_SMOKE PASS
```

补充：首次执行 Stage 34B UI smoke 时，当前 8000 端口运行的是未加载 Stage 34A 路由的旧 FastAPI 进程，`POST /api/studio/effect-rack/export` 返回 404。已重启本地 uvicorn 后确认该 API 返回 200，并重跑 Stage 34B smoke 通过。

## 截图

```text
Stage 34B screenshot = D:\FeiSharkStudio-v2\stage34b_effect_rack_export_ui.png
```

## 并行边界

```text
是否修改后端 = 否
是否修改 Dashboard / Factory = 否
是否修改第29回归脚本 = 否
是否修改 README = 否
是否修改 Stage 31 Effect Rack 导出合同 = 否
```

## 风险与限制

- 风险 1：当前导出仍是 copy-only 草稿，音频听感不会因为 Effect Rack 参数变化。
- 风险 2：导出的 `studio_effect_draft_master` 当前不自动设置为 Track 主成品；后续如需“设为主成品”，应复用既有 master 语义另行设计。

## 交接说明

- 事项 1：Effect Rack 参数已随导出请求发送并登记到 artifact metadata。
- 事项 2：成功后使用后端 `studio_url` 打开新 artifact，Studio Inspector 能显示 `studio_effect_export`。
- 事项 3：后续接真实 DSP/VST 时，应新增 processing mode，不要覆盖 `copy_only_no_dsp` 语义。
