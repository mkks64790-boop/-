# 第29阶段：回归脚本收口 + 产品验收口径固化

你现在是 FeiShark Studio 的工作 agent。

第28阶段已经证明真实主链路成立：

`Train -> Model Registry -> Cover -> Factory -> Studio`

当前不要继续新增大功能，也不要继续做 UI 大改。

这轮的核心任务是把“已经跑通的主链路”收束成稳定验收体系：旧 smoke / verify 脚本必须跟上第26阶段之后的真实素材规则，不能再把 3 秒单文件训练样本当成合法单文件长干声训练。

## 背景

架构师已复查当前工作区，结论如下：

- `python -m pytest -q` 当前通过：`19 passed, 2 warnings`
- `python -X utf8 backend\self_check.py` 当前通过：`SELF_CHECK_SUMMARY PASS`
- 第28阶段真实闭环报告显示真实 cover 已成功：
  - `model_id = v_b5c8427a`
  - `source_job_id = train_d8cd4ed377ca`
  - `cover_job_id = task_721c3f57df0b`
  - `track_id = trk_1ac7b6405e`
  - `artifact_id = art_e0dddc8477d8`
  - `final_stage = cover_mix`
  - `studio_url = /studio?batch_id=batch_f1732cb864&track_id=trk_1ac7b6405e&job_id=task_721c3f57df0b&artifact_id=art_e0dddc8477d8`
- 旧脚本当前失败不是主链路坏了，而是验收口径过期：
  - `backend\smoke_stage9.py` 会先完成 cover，然后在单文件 3 秒训练样本处被 `422 train_material_not_eligible` 拦截
  - `backend\verify_stage11_train_flow.py` 同样在单文件 3 秒训练样本处被 `422 train_material_not_eligible` 拦截

第26阶段后，单文件训练的规则已经变为：

- `1 个文件 + 30-50 分钟长干声` 才能走 `single_long_preprocess`
- `1 个短文件` 必须被拒绝，并返回结构化 `422 train_material_not_eligible`
- `多个已清洗短干声文件` 才走 `multi_clean_direct`

所以本轮要修的是“旧验证脚本的世界观”，不是放宽后端规则。

## 本阶段目标

1. 修复旧 smoke / verify，使它们接受第26阶段的新训练语义。
2. 固化常用验收命令，让 README 和真实可执行脚本一致。
3. 不破坏第28阶段真实训练模型 cover 闭环。
4. 让以后每轮开发前至少有一组稳定、快速、可重复的基础验收命令。

## 必读文件

- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-26-real-audio-training-acceptance-report.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-27-model-registry-linkage-report.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-28-trained-model-cover-studio-closure-report.md`
- `D:\FeiSharkStudio-v2\backend\smoke_stage9.py`
- `D:\FeiSharkStudio-v2\backend\verify_stage11_train_flow.py`
- `D:\FeiSharkStudio-v2\backend\verify_stage26_real_audio_training.py`
- `D:\FeiSharkStudio-v2\frontend\playwright_trained_model_cover_studio_smoke.cjs`
- `D:\FeiSharkStudio-v2\backend\services\audio_material_service.py`
- `D:\FeiSharkStudio-v2\backend\services\dataset_service.py`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\README.md`

## 实施范围

### 允许修改

- `backend\smoke_stage9.py`
- `backend\verify_stage11_train_flow.py`
- 与训练素材路由测试直接相关的测试文件
- `README.md` 中的常用验证说明
- 本阶段 worker report

### 谨慎修改

- `backend\services\audio_material_service.py`
- `backend\main.py`
- `backend\services\dataset_service.py`

只有发现真实 bug 时才改这些后端主链路文件；不要为了让旧脚本通过而降低 Stage 26 的硬校验。

### 禁止事项

- 不要放宽 `1 个短文件` 的训练限制。
- 不要把 3 秒单文件样本重新允许进入 `single_long_preprocess`。
- 不要重跑 45 分钟真实长干声训练，除非已有验证脚本确实必须且你在 report 里说明原因。
- 不要重写 RVC 执行层、Factory、Studio。
- 不要引入 Redis、Celery、WebSocket、复杂模型热缓存。
- 不要新增 VST、波形编辑器、修音室大功能。

## 具体任务

### 1. 修复 `backend\smoke_stage9.py`

当前问题：

- `run_cover(...)` 可以通过。
- `run_train(...)` 对单文件 3 秒样本仍然期待成功，这已经过时。

请把脚本语义调整为：

1. cover smoke 继续保留，仍然验证：
   - 上传
   - process
   - cover 完成
   - `cover_master` 存在
   - 下载接口可用
2. 单文件 3 秒训练样本改成“预期拒绝”验收：
   - 使用现有 `shared_data\uploads\train_c12177a47818.wav`
   - 调用 `/api/train`
   - 期待 HTTP `422`
   - 期待 `code = train_material_not_eligible`
   - 期待 `material_profile = single_short_out_of_window`
   - 期待 `recommended_route = multi_clean_direct`
   - 期待 `submission_allowed = false`
3. 多文件短干声训练仍然作为正向训练验收：
   - 使用现有 `train_e5790874eb1e.wav` 与 `train_def71bf124f9.wav`
   - 期待创建成功
   - 期待最终 `train_register_model`
   - 期待包含 `train_direct_prepare`
   - 期待 `.pth / .index` 产物存在

完成后，`python -X utf8 backend\smoke_stage9.py` 必须返回 0。

### 2. 修复 `backend\verify_stage11_train_flow.py`

当前问题：

- 这个脚本仍把单文件 3 秒样本当成 `train_preprocess` 正向路径。
- 这和第26阶段真实素材规则冲突。

请把它调整为 Stage 26 之后的新契约验收：

1. 保留前端不能直连 RVC 的检查：
   - `/api/train`
   - 不出现 `7866`
   - 不出现 `infer-web.py`
   - 不出现 `gradio_client`
2. 增加或改造单文件短样本拒绝检查：
   - 3 秒单文件必须被 `/api/train` 以 422 拒绝
   - 必须校验结构化错误字段
3. 保留多文件训练正向验收：
   - 多文件短干声走 `train_direct_prepare`
   - 最终到 `train_register_model`
   - `.pth / .index` 真实存在
   - `.index` 继续用 `faiss.read_index(...)` 校验
4. 不要在这个脚本里默认重跑 45 分钟长样本训练。
   - 长样本真实训练仍由 `backend\verify_stage26_real_audio_training.py` 单独负责。
   - 如果需要说明单文件长样本已由 Stage 26 证明，请在脚本注释或 report 中写明。

完成后，`python -X utf8 backend\verify_stage11_train_flow.py` 必须返回 0。

### 3. 补齐或调整 API 测试

如果现有测试已经覆盖短单文件拒绝，可以只补必要断言。

至少确认测试中覆盖这些语义：

- 单文件短样本不允许走单文件长干声训练。
- 422 响应包含：
  - `code`
  - `material_profile`
  - `recommended_route`
  - `single_long_eligible`
  - `submission_allowed`
  - `reason`
  - `next_step`
- 多文件训练路由仍然是 `multi_clean_direct`。

注意：不要为了测试通过去降低后端规则。

### 4. 更新 README 常用验证口径

`README.md` 当前仍把旧脚本列为常用验证，但它们还没跟 Stage 26 新语义收口。

请更新“常用验证”部分，让它表达清楚：

- 快速基础验收：
  - `python -m pytest -q`
  - `python -X utf8 backend\self_check.py`
  - `python -X utf8 backend\smoke_stage9.py`
  - `python -X utf8 backend\verify_stage11_train_flow.py`
- 真实素材重型验收：
  - `python -X utf8 backend\verify_stage26_real_audio_training.py`
  - 说明它依赖桌面真实长干声素材和 RVC 环境，不是每轮都必须跑
- 真实训练模型翻唱闭环验收：
  - `node frontend\playwright_trained_model_cover_studio_smoke.cjs`
  - 说明它依赖正在运行的 `http://127.0.0.1:8000`、可用 RVC/AudioPipeline、真实源歌曲

### 5. 保持 Stage 28 闭环不回退

本轮不要求重新跑一次完整 Stage 28 真实 cover，但必须至少做到：

- 不删除、不改坏 `frontend\playwright_trained_model_cover_studio_smoke.cjs`
- 不删除 Stage 28 report 中已经记录的模型来源字段
- 如果时间和环境允许，可以补跑：
  - `node frontend\playwright_trained_model_cover_studio_smoke.cjs`
- 如果不跑，必须在 report 里写明原因，例如：
  - 当前没有稳定运行的 8000 服务
  - 真实 cover 耗时较长，本轮只做基础回归收口
  - RVC/AudioPipeline 当前不可用

## 交付要求

完成后必须输出并写入 report：

1. 修改了哪些文件。
2. `smoke_stage9.py` 的旧失败点如何改成新语义。
3. `verify_stage11_train_flow.py` 的旧失败点如何改成新语义。
4. 单文件短样本拒绝验收的实际返回字段。
5. 多文件训练是否仍能成功到 `train_register_model`。
6. README 常用验证口径改了什么。
7. 实际执行过哪些命令，结果是什么。
8. 哪些重型验收没有执行，原因是什么。
9. 是否发现第28阶段真实闭环有回退风险。
10. 将本轮汇报写入：
    - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-29-regression-closure-product-acceptance-report.md`

## 验证要求

必须执行：

```powershell
python -m pytest -q
python -X utf8 backend\self_check.py
python -X utf8 backend\smoke_stage9.py
python -X utf8 backend\verify_stage11_train_flow.py
```

按环境选择执行：

```powershell
node frontend\playwright_trained_model_cover_studio_smoke.cjs
```

不要默认执行 45 分钟真实长样本训练脚本，除非本轮修改直接影响 Stage 26 长样本训练语义。

## 完成标准

- `pytest` 通过。
- `self_check` 通过。
- `smoke_stage9.py` 通过，并且不再把 3 秒单文件训练样本当成合法训练。
- `verify_stage11_train_flow.py` 通过，并且明确验证短单文件被 422 拒绝。
- 多文件短干声训练正向路径仍可用。
- README 的常用验证说明不再误导下一轮 agent。
- 第28阶段 `Train -> Model Registry -> Cover -> Factory -> Studio` 的真实闭环文件和语义未被破坏。
