# Stage 35B 执行汇报：Studio 版本管理 UI 收口

## 启动条件检查

- Stage 35A 报告是否已读取：是，已读取 `stage-35a-studio-version-master-contract-report.md`。
- 版本账本 API 是否可用：是，重启本地 uvicorn 后 `GET /api/tracks/{track_id}/studio-versions` 返回 200。

## 完成情况

- 已完成：接入 `/api/tracks/{track_id}/studio-versions`。
- 已完成：新增固定显示的当前主成品卡片 `#studioCurrentMasterCard`。
- 已完成：把原 `#studioTrackHistory*` 区域收口为“版本抽屉”，默认折叠，保留原 selector 兼容旧 smoke。
- 已完成：版本卡片展示原始翻唱成品 / 处理版草稿、当前正在播放、当前主成品、创建时间、打开、下载、设为当前主成品。
- 已完成：保留试听品库抽屉作为全局降级入口。
- 已完成：保留 copy-only/no DSP 文案，不暗示真实 DSP/VST 已执行。

## 修改文件

- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\frontend\playwright_stage35b_studio_version_ux_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-35b-studio-version-ux-cleanup-report.md`

## UI 截图

```text
Stage 35B screenshot = D:\FeiSharkStudio-v2\stage35b_studio_version_ux.png
```

## 版本账本字段使用

- `items[].artifact_type`
  - `cover_master` 显示为“原始翻唱成品”。
  - `studio_effect_draft_master` 显示为“处理版草稿”。
- `items[].processing_mode`
  - `original_cover` 显示为“原始成品”。
  - `copy_only_no_dsp` 显示为“仅登记草稿，未执行真实 DSP/VST”。
- `items[].is_current_master` 用于显示“当前主成品” badge，并决定是否隐藏“设为当前主成品”按钮。
- 当前正在播放由当前 `job_id + artifact_id` 与 version item 匹配后显示“当前正在播放”。
- `download_url` 用于版本卡片下载按钮和当前主成品下载按钮。
- `studio_url` 用于“打开此版本”和当前主成品“打开”按钮。
- `current_master` 用于固定的当前主成品卡片。

## 降级行为

- 优先调用 `GET /api/tracks/{track_id}/studio-versions?limit=50&offset=0`。
- 如果版本账本接口不存在或请求失败，前端不会崩溃，会退回 `GET /api/tracks/{track_id}/jobs?limit=50&offset=0`。
- 降级时显示提示：“版本账本暂不可用，已退回旧成品历史。”
- 试听品库抽屉继续默认折叠保留，作为非 Track 入口或降级入口。

## 验证结果

```text
node frontend\playwright_stage35b_studio_version_ux_smoke.cjs
结果：PASS，STAGE35B_STUDIO_VERSION_UX_SMOKE PASS
track_id=trk_9545bc8c01
job_id=task_90ba4a68b59f
cover_artifact_id=art_c57131d1bdcd
draft_artifact_id=art_37b11efcb637
screenshot=D:\FeiSharkStudio-v2\stage35b_studio_version_ux.png

node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
结果：PASS，STAGE34B_EFFECT_RACK_EXPORT_UI_SMOKE PASS
exported_artifact_id=art_9c3a21ea8f4f

node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
结果：PASS，STAGE30B_STUDIO_PRODUCT_SHELL_SMOKE PASS

node frontend\playwright_stage33a_ui_hotfix_guard_smoke.cjs
结果：PASS，STAGE33A_UI_HOTFIX_GUARD_SMOKE PASS

python -m pytest -q
结果：PASS，32 passed, 2 warnings in 5.62s

python -X utf8 backend\self_check.py
结果：PASS，SELF_CHECK_SUMMARY PASS
```

补充：开始时当前 8000 端口服务未加载 Stage 35A 新路由，`/studio-versions` 返回 404。已重启本地 uvicorn，确认 API 返回 200 后执行前端接入与验证。

## 风险与限制

- 风险 1：`studio_effect_draft_master` 仍是 copy-only 草稿，听感不会因 Effect Rack 参数变化。
- 风险 2：版本账本当前只展示 Studio 可试听音频版本，不展示训练模型、index 或其他非音频产物。
- 风险 3：Stage 35B smoke 会显式点击“设为当前主成品”，测试数据中当前主成品会被切换到一个处理版草稿；这是 Stage 35A 合同允许的显式用户行为。

## 交接说明

- 下一阶段可以进入真实 DSP v0 的产品设计，但必须新增 processing mode，不能覆盖 `copy_only_no_dsp`。
- 真实 DSP 接入前，UI 继续把处理版草稿明确标为“仅登记草稿，未执行真实 DSP/VST”。
- 仍需人工真机确认：右侧版本抽屉在用户真实多版本数据下的视觉密度、移动端滚动手感、主成品切换后的用户理解成本。
