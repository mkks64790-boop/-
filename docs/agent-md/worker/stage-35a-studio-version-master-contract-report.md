# Stage 35A 执行汇报：Studio 版本账本与主成品合同硬化

## 完成情况

- 已完成：新增 Track 维度 Studio 版本账本读取能力 `GET /api/tracks/{track_id}/studio-versions`。
- 已完成：硬化 `POST /api/tracks/{track_id}/master`，允许合法 `cover_master` 与 `studio_effect_draft_master` 显式设为当前主成品。
- 已完成：修正 `GET /api/tracks/{track_id}/jobs` 在当前主成品为同一 cover job 下 draft artifact 时的状态表达。
- 已完成：保持 Stage 34 `copy_only_no_dsp` 语义不变，draft 不自动成为主成品，仍需用户显式调用 master 接口。
- 已完成：新增 API 回归测试，覆盖版本账本、多 draft、draft 主成品、非音频/训练 artifact 拒绝、其他 track artifact 拒绝、缺失文件不返回为可下载版本。

## 修改文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\tests\api\test_track_studio_versions_api.py`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-35a-studio-version-master-contract-report.md`

本阶段未修改：

- Dashboard / Factory / Studio 前端 UI
- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- RVC / UVR / ffmpeg 执行层
- Stage 34A 的 copy-only 导出服务语义

## 新增 / 变更 API 合同

### GET /api/tracks/{track_id}/studio-versions

用途：按 Track 读取 Studio 可试听成品版本账本，稳定区分原始 cover master、处理版草稿和当前主成品。

返回结构：

```json
{
  "track_id": "trk_xxx",
  "current_master_job_id": "task_xxx",
  "current_master_artifact_id": "art_xxx",
  "current_master": {},
  "items": [
    {
      "version_id": "art_xxx",
      "job_id": "task_xxx",
      "track_id": "trk_xxx",
      "artifact_id": "art_xxx",
      "artifact_type": "cover_master",
      "stage_name": "cover_mix",
      "file_name": "final_master.wav",
      "file_path": "...",
      "file_size": 123,
      "created_at": "...",
      "is_final": true,
      "is_current_master": false,
      "is_processing_draft": false,
      "processing_mode": "original_cover",
      "source_job_id": "",
      "source_artifact_id": "",
      "downloadable": true,
      "download_url": "/api/jobs/task_xxx/artifacts/art_xxx/download",
      "studio_url": "/studio?track_id=trk_xxx&job_id=task_xxx&artifact_id=art_xxx",
      "warning": ""
    }
  ],
  "limit": 50,
  "offset": 0
}
```

账本过滤规则：

- 只返回当前 Track 下已完成 cover job 的 Studio 可用音频 artifact。
- `cover_master` 的 `processing_mode = original_cover`。
- `studio_effect_draft_master` 的 `processing_mode` 读取 artifact metadata，当前应为 `copy_only_no_dsp`。
- 不返回训练模型 `.pth/.index`、非音频 artifact、其他 Track 的 artifact。
- 文件不存在的 artifact 不作为可下载版本返回。

### POST /api/tracks/{track_id}/master

用途：显式设置当前 Track 主成品。

请求：

```json
{
  "job_id": "task_xxx",
  "artifact_id": "art_xxx"
}
```

返回补强：

```json
{
  "ok": true,
  "track_id": "trk_xxx",
  "current_master_job_id": "task_xxx",
  "current_master_artifact_id": "art_xxx",
  "current_master_artifact_type": "studio_effect_draft_master",
  "current_master_processing_mode": "copy_only_no_dsp",
  "current_master": {}
}
```

校验规则：

- job 必须属于当前 track。
- job 必须是 cover 类型。
- job 必须为完成状态。
- artifact 必须属于该 job。
- artifact 文件必须存在。
- artifact 必须是支持的音频扩展：`.wav`、`.mp3`、`.flac`、`.m4a`、`.aac`、`.ogg`。
- artifact type 只能是 `cover_master` 或 `studio_effect_draft_master`。
- 训练模型、index、非音频、其他 track artifact 均不能设为主成品。

### GET /api/tracks/{track_id}/jobs

兼容性保持：

- 保留既有 `final_artifact_id`、`final_artifact_type`、`final_artifact_download_url`、`studio_url` 字段。
- 当当前主成品是同一 cover job 下的 `studio_effect_draft_master` 时，该 job 会正确标识：
  - `is_current_master = true`
  - `is_current_master_job = true`
  - `current_master_artifact_id = art_xxx`
  - `current_master_artifact_type = studio_effect_draft_master`
  - `current_master_processing_mode = copy_only_no_dsp`

## 当前主成品语义

- `cover_master`：翻唱主链生成的原始成品，`processing_mode = original_cover`。
- `studio_effect_draft_master`：Studio Effect Rack 导出的处理版草稿，当前仍是 copy-only，`processing_mode = copy_only_no_dsp`。
- `studio_effect_draft_master` 不会因为导出而自动替换主成品。只有用户显式调用 `POST /api/tracks/{track_id}/master` 后，才会成为当前主成品。
- Track 的当前主成品由 `tracks.current_master_job_id` 与 `tracks.current_master_artifact_id` 共同决定。

## copy_only_no_dsp 语义

保持不变：

- 是否真实 DSP：否。
- 是否接 VST：否。
- 是否自动变更主成品：否。
- 是否仅复制源音频并登记参数：是。
- 是否继续通过 metadata 暴露 `processing_mode=copy_only_no_dsp`：是。

## 回归验证

```text
python -m pytest -q tests\api\test_track_studio_versions_api.py tests\api\test_track_jobs_api.py tests\api\test_studio_effect_export_api.py
结果：PASS，12 passed, 2 warnings in 3.30s

python -m pytest -q
结果：PASS，32 passed, 2 warnings in 5.65s

python -X utf8 backend\self_check.py
结果：PASS，SELF_CHECK_SUMMARY PASS

node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
结果：PASS，STAGE34B_EFFECT_RACK_EXPORT_UI_SMOKE PASS
exported_artifact_id=art_37b11efcb637
download_href=http://127.0.0.1:8000/api/jobs/task_90ba4a68b59f/artifacts/art_37b11efcb637/download

node frontend\playwright_trained_model_cover_studio_smoke.cjs
结果：PASS，STAGE28_TRAINED_MODEL_COVER_SMOKE PASS
model_id=v_b5c8427a
source_job_id=train_d8cd4ed377ca
track_id=trk_9545bc8c01
cover_job_id=task_90ba4a68b59f
final_stage=cover_mix
studio_url=/studio?batch_id=batch_a0daef1058&track_id=trk_9545bc8c01&job_id=task_90ba4a68b59f&artifact_id=art_c57131d1bdcd
```

补充：`stage34b_effect_rack_export_ui_smoke` 首次运行曾在“导出后下载按钮启用”等待点超时，未修改代码直接复跑通过。最终验收结果以复跑 PASS 为准，推断为浏览器/CDP 等待瞬态问题，不是本阶段 API 合同失败。

## 风险与限制

- 风险 1：`studio_effect_draft_master` 当前仍是 copy-only 草稿，听感不会因 Effect Rack 参数变化。
- 风险 2：版本账本当前只覆盖 Studio 可试听成品版本，不承担训练模型、index 或其他产物清单职责。
- 风险 3：`GET /api/tracks/{track_id}/jobs` 保留旧字段名 `final_artifact_*`，当当前主成品是 draft 时，旧字段会指向当前可打开的音频 artifact；新字段用于明确 current master 语义。

## 交接给产品 Agent

- Studio / Factory 要读取成品版本时，优先使用 `GET /api/tracks/{track_id}/studio-versions`。
- UI 展示版本类型时：
  - `cover_master + original_cover` 显示为原始翻唱成品。
  - `studio_effect_draft_master + copy_only_no_dsp` 显示为处理版草稿，必须提示尚未执行真实 DSP/VST。
- 设置主成品必须显式调用 `POST /api/tracks/{track_id}/master`，不要在导出 draft 后自动替换。
- 后续接真实 WebAudio / ffmpeg / VST 时，应新增新的 `processing_mode`，不要覆盖 `copy_only_no_dsp`。
