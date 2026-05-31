# Stage 31：Effect Rack 导出链路架构合同

你现在是 FeiShark Studio 的架构 agent。

产品线 Stage 30B 已完成：Studio 已经有 Effect Rack 前端草稿壳，插件槽状态能按 `track_id / job_id / artifact_id` 保存在 localStorage，但不会真实改变音频。

你的任务不是写产品 UI，也不是重跑真实训练链。你的任务是为下一步“导出处理版”制定稳定架构合同，避免后端、产品、地基各做各的。

## 必读文件

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-30b-studio-product-shell-plugin-slots-report.md`
- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\backend\services\audio_material_service.py`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-29-regression-closure-product-acceptance-report.md`

## 本阶段目标

1. 定义 Effect Rack 导出处理版的后端协议。
2. 明确 `effectRackState` 如何从前端草稿映射到后端请求体。
3. 明确导出产物应该挂到哪个 job / artifact / track 语义下。
4. 明确 Stage 32 或后续阶段如何接 WebAudio / ffmpeg / 后端 DSP / 原生 VST Host。
5. 给地基 agent 一个可执行的最小闭环边界。

## 建议合同

请评审并固化类似接口：

```text
POST /api/studio/effect-rack/export

request:
{
  "track_id": "...",
  "source_job_id": "...",
  "source_artifact_id": "...",
  "effect_rack": [
    {
      "id": "eq",
      "enabled": false,
      "status": "draft",
      "params": { "low": 0, "mid": 0, "high": 0 }
    }
  ],
  "export_profile": "studio_balanced"
}

response:
{
  "job_id": "...",
  "status": "queued|completed",
  "artifact_id": "... optional",
  "studio_url": "... optional"
}
```

如果你认为路径或字段应调整，请写明原因。

## 必须回答的问题

- 这应当是普通 job、子 job、还是 track artifact 版本？
- 第一阶段最小闭环是否允许“复制原音频并登记新 artifact”，而不真实 DSP？
- 如果允许，UI 文案应如何避免误导用户？
- effect rack 参数应该保存在 `jobs.metadata_json`、artifact metadata，还是独立表？
- 新 artifact 类型命名是什么？例如 `studio_effect_draft_master` 或 `studio_processed_master`。
- 下载入口如何复用现有 `/api/download/...`。
- 新 smoke 最小要验证哪些 API 字段和 UI 字段？

## 并行边界

允许修改：

- `docs\agent-md\handoff\stage-31-effect-rack-export-contract-handoff.md`
- `docs\agent-md\worker\stage-31-architecture-effect-rack-export-contract-report.md`
- 如确需补充小型架构注释，可新增 docs 文件。

不要修改：

- `frontend\studio.html`
- `frontend\js\studio.js`
- `frontend\css\app.css`
- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- `README.md`
- RVC / UVR / ffmpeg 执行层

## 验证要求

本阶段以架构合同为主，至少执行：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
```

如果未执行，请在 report 说明原因。

## 交付

必须写入：

- `D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-31-effect-rack-export-contract-handoff.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-31-architecture-effect-rack-export-contract-report.md`

报告必须包含：

1. 最终 API 合同。
2. 最终数据模型建议。
3. 最小闭环实现边界。
4. 对地基 agent 的执行指令。
5. 风险与不做事项。
6. 验证结果。
