# Stage 31：Effect Rack 导出后端最小闭环地基

你现在是 FeiShark Studio 的地基 agent。

产品线 Stage 30B 已完成 Studio 产品壳和 Effect Rack 前端草稿；架构线将补充 Stage 31 导出合同。你的任务是准备后端最小闭环地基，但要严格避免和产品 UI、第29回归脚本抢文件。

## 必读文件

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-30b-studio-product-shell-plugin-slots-report.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-31-architecture-effect-rack-export-contract-prompt.md`
- 如果已存在，请优先读取：
  - `D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-31-effect-rack-export-contract-handoff.md`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\tests`

## 本阶段目标

实现或准备一个不误导用户的 Effect Rack 导出最小闭环：

1. 接收前端 Effect Rack 草稿参数。
2. 校验 `track_id / source_job_id / source_artifact_id`。
3. 生成一个可追踪的导出 job 或 artifact 记录。
4. 第一阶段可以只登记“处理版草稿导出”或复制源音频，不要声称真实 DSP / VST 已生效。
5. 补测试覆盖 API 合同和错误分支。

## 建议边界

如果架构 handoff 已存在，以 handoff 为准。

如果 handoff 还不存在，先只做以下准备，不要大改：

- 新增独立服务文件，例如 `backend\services\studio_effect_service.py`。
- 新增纯函数校验 effect rack payload。
- 新增单元测试覆盖 payload normalize / validation。
- 暂不改 Studio UI。
- 暂不接真实 ffmpeg / DSP / VST。

## 强约束

不要修改：

- `frontend\studio.html`
- `frontend\js\studio.js`
- `frontend\css\app.css`
- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- `README.md`
- RVC / UVR / ffmpeg 执行层

如确需修改 `backend\main.py` 增加 API 路由，必须非常小，并在 report 说明。

## 验证要求

必须执行：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
```

如果新增 API，再补充对应测试或轻量 smoke。

不要执行 Stage 28 真实闭环 smoke，除非你修改了 Studio / Factory / track master 语义。

## 交付

必须写入：

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-31-foundation-effect-rack-export-minimal-loop-report.md`

报告必须包含：

1. 是否读取了架构 handoff。
2. 修改了哪些文件。
3. 实现了哪些 payload 校验。
4. 是否新增 API。
5. 是否真实改变音频。
6. 哪些行为只是草稿 / 占位。
7. 验证结果。
8. 是否触碰第29阶段文件或产品 UI 文件。
