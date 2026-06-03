# FeiShark Stage 56: RVC 短翻唱 Smoke 与引擎路线定序

项目根目录：`D:\FeiSharkStudio-v2`

你是肥鲨工作室的工作 agent。本阶段目标是进入真实 RVC 翻唱闭环，但只允许做短 smoke，不允许开启新一轮长训练。完成后把报告写入：

`docs\agent-md\worker\stage-56-rvc-short-cover-smoke-and-engine-sequencing-report.md`

## 核心结论先锁死

- RVC：本阶段开始验证，使用现有已登记模型 `v_d4d7e1c1 / 朱朱_stage47_single_long` 跑短翻唱 smoke。
- UVC/SVC：本阶段不开发、不接入、不训练，只写入路线图，等 RVC baseline 稳定后再作为备用引擎。
- VST：本阶段不接真实 VST 插件，不做插件宿主，只保留 Studio 后处理接口方向。VST 是修音/后处理，不是训练模型。

## 禁止事项

- 不跑 30-50 分钟朱朱长训练。
- 不启动新的长训练任务。
- 不修改 `D:\RVC\RVCv2` 第三方整合包源码。
- 不删除历史 job、模型、音频资产；如需隔离，只能归档到 quarantine。
- 不使用来路不明网络歌曲做默认测试。
- 不把工程可用模型宣传为音质合格模型。
- 不把 UVC/SVC/VST 和 RVC 在同一阶段混写成一个大改造。

## 目标 A：RVC 短翻唱 smoke 前置检查

先检查并报告：

- `/api/training/gpu-status` 是否 `gpu_acceleration_available=true`。
- `/api/training/observer/latest` 是否能读到 `train_7f4d6b4e611e` 或其它最新完成训练。
- 模型 `v_d4d7e1c1` 是否 `usable=true`，`.pth` 和 `.index` 是否存在。
- `/api/preflight/cover?model_id=v_d4d7e1c1` 是否通过。
- 当前是否存在正在运行的训练/cover job；如果 GPU 显存忙，不启动真实 smoke，只写阻断原因。

## 目标 B：选择合法短素材

优先从以下位置找 20-60 秒以内的授权短素材：

- `shared_data\material_library`
- `shared_data\separation_eval\input`
- 用户明确放入项目内的测试素材

如果只找到成品母带或来源不明音乐：

- 允许作为 UVR 分离 smoke，但报告必须标记 `not_training_candidate`。
- 不允许作为训练素材。
- 不允许把结果纳入音质结论，只能作为流程连通性证据。

如果没有合法短素材：

- 不要随便扫描 D 盘。
- 不要下载歌曲。
- 返回 blocked 报告，并说明用户需要放入一段 20-60 秒授权短素材。

## 目标 C：运行一个短 RVC 翻唱闭环

如果目标 A/B 均通过，提交一个短 cover job：

- 使用模型：`v_d4d7e1c1`
- 只跑一个短任务。
- 必须记录 job_id。
- 必须等待任务进入完成、失败或明确超时。
- 必须采集 stage logs：`cover_upload`、`cover_preflight`、`cover_split`、`cover_infer`、`cover_mix`。
- 必须验证 artifact：
  - 是否生成 `cover_master`
  - 是否有下载 URL
  - 是否能进入 Studio
  - 文件大小、时长、采样率是否可读

如果失败：

- 不要重复硬跑。
- 报告失败阶段、错误文本、GPU 状态、临时文件状态、下一步修复建议。

## 目标 D：Dashboard/Studio 最小可见闭环

不要大改 UI，只做最小必要验证或修补：

- Dashboard 训练观察器的“用该模型翻唱”按钮必须能把 `v_d4d7e1c1` 填到 AI 翻唱入口。
- cover job 完成后，任务详情必须能看到最终产物入口。
- 有可播放 `cover_master` 时，Studio 跳转按钮必须存在。
- 如果没有可播放产物，前端必须说明卡在哪个阶段，而不是空白。

## 目标 E：写清 RVC/UVC/VST 路线图

在报告里单独写一节：

- RVC 下一步：短 smoke 通过后，才进入短训练/参数调优/更好干声训练。
- UVC/SVC 下一步：等 RVC baseline 稳定后，用同一素材和同一模型资产接口设计备用引擎，不抢当前训练链。
- VST 下一步：等 Studio 可稳定读 cover 成品后，再设计 WebAudio/插件宿主/导出链，不抢当前 RVC 验收。

## 验证命令

必须至少执行：

- `python -m py_compile backend\main.py backend\services\training_observer_service.py backend\services\training_gpu_service.py backend\services\preflight_service.py`
- `python -m pytest tests\api\test_stage55_training_observer_api.py -q`
- `python -m pytest tests\api\test_stage54_training_gpu_api.py -q`
- `python -m pytest -q`
- `python -m backend.self_check`
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\jobs.js','rb').read())"" | node --input-type=module --check"`
- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\cover.js','rb').read())"" | node --input-type=module --check"`
- 如果修改 Studio：`cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\studio.js','rb').read())"" | node --input-type=module --check"`

## 报告要求

报告必须写清：

- 是否实际运行 RVC cover smoke。
- 如果运行，使用的素材路径、模型 ID、job_id、最终 artifact、Studio URL。
- 如果未运行，阻断原因。
- GPU 空闲/占用状态。
- RVC/UVC/VST 三条路线分别处于哪个阶段。
- 修改文件清单。
- 验证命令与结果。
- 下一阶段建议。

