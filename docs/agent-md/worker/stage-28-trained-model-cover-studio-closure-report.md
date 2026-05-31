# 第28阶段执行汇报：训练模型真实翻唱闭环 + Studio 成品验收

## 完成情况

- 已完成：
  - 真实训练模型 `v_b5c8427a` 已经不只是“能在模型库里看见”，而是被真实用于一次新的 Factory track cover。
  - 真实 cover job 创建时会写入模型来源快照，并沿着 `jobs -> track jobs -> Factory -> Studio` 一路可见。
  - 真实 cover 成品成功进入 `Studio`，并在 Studio 默认可见摘要里展示“这次成品用的是哪个模型、模型来自哪次本地训练”。
  - 新建 Track 的这次真实成品，已经在 Studio 中设为 `当前主成品`，回到 Factory 后可见同步结果。
  - 已补 Stage 28 专用真实闭环 smoke 脚本，可重复执行。
- 部分完成：
  - 额外手跑了 `backend/smoke_stage9.py` 与 `backend/verify_stage11_train_flow.py`，它们当前会被 Stage 26 引入的“短单文件训练硬拦截”语义打断；这不是本轮新改动引入，但说明旧验收脚本仍未完全跟随 Stage 26 新规则收口。
- 未完成：
  - 无。

## 修改文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\tests\api\test_track_jobs_api.py`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\playwright_trained_model_cover_studio_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-28-trained-model-cover-studio-closure-report.md`

## 本轮素材与模型

### 训练模型

- 实际使用的模型：
  - `model_id = v_b5c8427a`
  - `model_name = stage26_real_long_1780063446`
  - `origin_kind = trained_local`
  - `source_job_id = train_d8cd4ed377ca`
- 为什么选它：
  - 这是 Stage 26 明确验收过的真实长样本训练模型。
  - 模型可用、来源清晰、并且已经在 Stage 27 进入模型库。

### 真实翻唱源音频

- 实际使用的歌曲：
  - `C:\Users\ASUS\Desktop\归不了岸的船.mp3`
- 时长与格式：
  - 约 `180.036s`
  - `mp3 / 44.1kHz / stereo`
- 为什么选它：
  - 这是 Prompt 指定的首选真实素材，且比备选更短，更适合做真实闭环验收。

## 功能结果

### 后端

- cover job 新增的模型来源字段：
  - `voice_model_origin_kind`
  - `voice_model_source_job_id`
  - `voice_model_source_summary`
  - `voice_model_source_strategy_key`
  - `voice_model_source_material_profile`

- 这些字段写到了哪里：
  - 写入 `jobs.metadata_json`
  - 当前真实 job `task_721c3f57df0b` 的落库内容如下：
    - `voice_model_origin_kind = trained_local`
    - `voice_model_source_job_id = train_d8cd4ed377ca`
    - `voice_model_source_summary = 来自本地训练任务 train_d8cd4ed377ca · 单文件快速训练 · 单文件长样本 · 1 个文件 · 45分10秒`
    - `voice_model_source_strategy_key = single_long_preprocess`
    - `voice_model_source_material_profile = single_long_candidate`

- `Factory / Studio / job detail` 如何读到这些字段：
  - `/api/jobs/{job_id}` 现在会返回上述 `voice_model_source_*` 字段，供 Studio 按 job_id 直接加载。
  - `/api/tracks/{track_id}/jobs` 与 `current_master` 现在也会暴露同一份快照，供 Factory 与 Studio 轨道历史直接消费。
  - `Factory -> current master / latest cover / related jobs` 都不再需要临时反查模型库才能解释来源。

### 前端

#### Factory

- 真实成品完成后显示了什么：
  - 最新成品卡、当前主成品卡、关联任务列表都会默认显示：
    - `voice_name / voice_model_id`
    - 模型来源 pill（本地训练 / 外部导入 / 目录扫描）
    - `voice_model_source_summary`
    - 如有 `source_job_id` 也会直接展示
- 是否能直接进入 Studio：
  - 能。
- 是否能看到模型来源摘要：
  - 能，且不是塞进技术抽屉，而是直接放在成品摘要主视图里。

#### Studio

- 页面加载后显示了什么：
  - 来源 Track / Batch / 当前音色 / 当前任务
  - 当前成品摘要
  - 模型来源摘要与来源 pill
- 是否能看到本次 cover 使用的是哪个训练模型：
  - 能。
- 是否能看到该模型来自哪个 train job：
  - 能，默认可见 `train_d8cd4ed377ca`。

### 当前主成品

- 是否把这次真实 cover 设为 `当前主成品`：
  - 是。
- 在 Studio 如何设置：
  - 通过现有 Track History 区域里的“设为当前主成品”按钮完成。
- 返回 Factory 后如何同步显示：
  - `tracks.current_master_job_id = task_721c3f57df0b`
  - `tracks.current_master_artifact_id = art_e0dddc8477d8`
  - `Factory` 的当前主成品卡与关联任务列表都同步显示为这次真实成品。

## 真实运行结果

### 真实 cover job

- `track_id = trk_1ac7b6405e`
- `cover_job_id = task_721c3f57df0b`
- `studio_url = /studio?batch_id=batch_f1732cb864&track_id=trk_1ac7b6405e&job_id=task_721c3f57df0b&artifact_id=art_e0dddc8477d8`
- 实际阶段轨迹：
  - `cover_preflight`
  - `cover_split`
  - `cover_pitch`
  - `cover_voice`
  - `cover_mix`
- 最终结果：
  - 成功
- 最终阶段：
  - `cover_mix`

### 成品验收

- 是否生成最终成品：
  - 是。
- 是否可以下载：
  - 是。
- 是否可以在 Studio 打开：
  - 是。
- 是否能读取音频资源：
  - 是。
- 截图：
  - `D:\FeiSharkStudio-v2\stage28_trained_model_cover_studio.png`

## 验证结果

```text
python -m pytest -q
结果：19 passed, 2 warnings in 3.39s

python -X utf8 backend/self_check.py
结果：SELF_CHECK_SUMMARY PASS

node D:\FeiSharkStudio-v2\frontend\playwright_trained_model_cover_studio_smoke.cjs
结果：STAGE28_TRAINED_MODEL_COVER_SMOKE PASS
model_id=v_b5c8427a
source_job_id=train_d8cd4ed377ca
track_id=trk_1ac7b6405e
cover_job_id=task_721c3f57df0b
final_stage=cover_mix
studio_url=/studio?batch_id=batch_f1732cb864&track_id=trk_1ac7b6405e&job_id=task_721c3f57df0b&artifact_id=art_e0dddc8477d8
audio_path=C:/Users/ASUS/Desktop/归不了岸的船.mp3
master_set=yes
```

额外补跑：

```text
python -X utf8 backend/smoke_stage9.py
结果：FAIL
原因：脚本里的 3 秒单文件训练样本现在会被 Stage 26 的真实素材路由规则以 422 拦截，不再允许误入单文件长干声训练。

python -X utf8 backend/verify_stage11_train_flow.py
结果：FAIL
原因：同样依赖旧的短单文件训练样本，现已被 Stage 26 的后端硬校验拒绝。
```

说明：

- 上面两条额外回归失败不是本轮 Stage 28 新引入的 cover / Studio 问题，而是旧脚本尚未完全收口到 Stage 26 的真实训练分流新语义。
- 本轮 Prompt 的必需验证项已经满足：`pytest`、`self_check`、Stage 28 真实闭环 smoke。

## 风险与限制

- 当前闭环依然依赖桌面本机已有 RVC / AudioPipeline 环境；环境一旦变化，真实 cover 仍会受外部安装影响。
- 这轮只把“训练模型来源快照”做进了 cover job / Factory / Studio 主摘要，没有去重写更多模型资产页的历史结构。
- `backend/smoke_stage9.py` 与 `backend/verify_stage11_train_flow.py` 仍然需要在后续阶段按 Stage 26 的真实训练材料规则改造，否则会继续因为 3 秒短样本被拒而失败。

## 交接说明

下一轮 agent 或架构师继续工作前，优先关注：

- 事项 1：
  - 把 `backend/smoke_stage9.py` 与 `backend/verify_stage11_train_flow.py` 改造成兼容 Stage 26 新语义，不再依赖会被硬拦截的 3 秒单文件训练样本。
- 事项 2：
  - 如果后续要继续做 Studio 产品化，可以沿用本轮已经打通的 `voice_model_source_*` 字段，不需要重新设计模型来源传递链。
- 事项 3：
  - 如果后续要做“来源训练任务 -> 来源数据集 -> 来源素材画像”的更完整可视化，优先继续复用 `jobs.metadata_json` 里的快照，而不是在前端实时拼接多跳查询。
