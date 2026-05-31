# Stage 29 执行汇报：回归脚本收口 + 产品验收路径固化

## 阶段标题

Stage 29：Regression Closure + Product Acceptance

## 完成情况

- 已完成：`backend\smoke_stage9.py` 的旧单文件训练正向路径已改为 Stage 26 后的新规则验收。
- 已完成：`backend\verify_stage11_train_flow.py` 的旧单文件训练正向路径已改为短单文件 422 拒绝验收。
- 已完成：多文件短干声训练仍保持正向验收，最终到达 `train_register_model`，并继续校验真实 `.pth / .index` 产物。
- 已完成：`README.md` 的常用验证路径已按“轻量基础验收 / 真实素材重型验收 / Stage 28 真实闭环验收”拆分。
- 已完成：补跑 Stage 28 真实闭环 smoke，确认 `Train -> Model Registry -> Cover -> Factory -> Studio` 未被本轮改动破坏。

## 修改文件

- `D:\FeiSharkStudio-v2\backend\smoke_stage9.py`
- `D:\FeiSharkStudio-v2\backend\verify_stage11_train_flow.py`
- `D:\FeiSharkStudio-v2\README.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-29-regression-closure-product-acceptance-report.md`

本轮没有修改：

- `backend\services\audio_material_service.py`
- `backend\main.py`
- `backend\services\dataset_service.py`
- `frontend\playwright_trained_model_cover_studio_smoke.cjs`
- Factory / Studio / cover / train 主链路实现

## 功能结果

### 后端规则

- 短单文件训练拒绝语义保持：1 个约 3 秒文件不能再进入 `single_long_preprocess`。
- 短单文件通过 `/api/train` 返回结构化 `422 train_material_not_eligible`。
- 多文件短干声训练仍走 `multi_clean_direct`，并能完整执行到 `train_register_model`。
- 没有为了让旧脚本通过而放宽 Stage 26 的素材校验规则。

### `smoke_stage9.py`

旧失败点：

- 原脚本把 `shared_data\uploads\train_c12177a47818.wav` 这个约 3 秒单文件样本当作合法单文件训练素材，并期待训练成功。
- Stage 26 之后，该素材必须被识别为 `single_short_out_of_window` 并被拒绝，所以旧脚本会在 `/api/train` 处失败。

新验收语义：

- cover smoke 保留，继续验证上传、process、cover 完成、`cover_master` 和下载接口。
- 3 秒单文件训练样本改为预期拒绝验收，断言 HTTP `422` 和结构化错误字段。
- 多文件训练继续作为正向训练验收，断言 `train_direct_prepare`、最终 `train_register_model`、`.pth / .index` 产物存在。

最终结果：

- `python -X utf8 backend\smoke_stage9.py` PASS。
- cover job：`task_96d1bd74c900`
- multi train job：`train_af568a9b3dde`
- multi train final stage：`train_register_model`

### `verify_stage11_train_flow.py`

旧失败点：

- 原脚本把 3 秒单文件样本当作 `train_preprocess` 正向路径。
- 这与 Stage 26 的真实素材规则冲突。

新验收语义：

- 保留“前端只能通过后端 `/api/train`，不能直连 RVC WebUI / 7866 / infer-web.py / gradio_client”的检查。
- 新增短单文件拒绝验收：3 秒单文件必须由 `/api/train` 返回 `422 train_material_not_eligible`。
- 保留多文件正向训练验收：`multi_clean_direct`、`train_direct_prepare`、`train_register_model`、`.pth / .index` 真实产物，并用 `faiss.read_index(...)` 校验 `.index` 可读。

最终结果：

- `python -X utf8 backend\verify_stage11_train_flow.py` PASS。
- multi train job：`train_e0b3cafe45ca`
- final stage：`train_register_model`

### README

README 的“常用验证”已调整为三组：

- 快速基础验收：
  - `python -m pytest -q`
  - `python -X utf8 backend\self_check.py`
  - `python -X utf8 backend\smoke_stage9.py`
  - `python -X utf8 backend\verify_stage11_train_flow.py`
- 真实素材重型验收：
  - `python -X utf8 backend\verify_stage26_real_audio_training.py`
  - 明确说明依赖桌面真实长干声素材和本机 RVC 训练环境，不是每轮轻量回归都必须跑。
- 真实训练模型翻唱闭环验收：
  - `node frontend\playwright_trained_model_cover_studio_smoke.cjs`
  - 明确说明依赖运行中的 `http://127.0.0.1:8000`、RVC/AudioPipeline、真实训练模型和桌面真实源歌曲。

## 单文件短样本拒绝验收

本轮实际返回字段来自 `smoke_stage9.py`：

```text
status_code = 422
code = train_material_not_eligible
material_profile = single_short_out_of_window
duration_seconds = 3.0
duration_label = 3秒
recommended_route = multi_clean_direct
single_long_eligible = False
submission_allowed = False
reason = 单文件时长约 3秒，未达到 30 分钟下限，不能按单文件长干声快速训练处理。
next_step = 请改用多文件精训素材，或准备 30-50 分钟单干声后再提交。
```

这确认旧的“3 秒单文件训练正向通过”世界观已移除。

## 多文件训练验收

本轮 `verify_stage11_train_flow.py` 的实际结果：

```text
job_id = train_e0b3cafe45ca
final_status = 完成
final_stage = train_register_model
expected_prepare_stage = train_direct_prepare
strategy_key = multi_clean_direct
generated_model_id = v_7bc74dde
generated_model_name = stage11_multi_smoke_1780076175
pth_artifact = train_model_pth / art_8ff4aeca531a / 55,229,665 bytes
index_artifact = train_model_index / art_df1efa02fe20 / 939,539 bytes
index_faiss_check = PASS，verify_stage11_train_flow.py 内部使用 faiss.read_index(...) 校验通过
```

本轮 `smoke_stage9.py` 的多文件正向结果：

```text
job_id = train_af568a9b3dde
final_status = 完成
final_stage = train_register_model
expected_prepare_stage = train_direct_prepare
strategy_key = multi_clean_direct
generated_model_id = v_da0a0393
generated_model_name = stage10_multi_smoke_1780076144
pth_artifact = train_model_pth / art_2c2642d2914e / 55,229,665 bytes
index_artifact = train_model_index / art_3bc4b479b5fb / 939,539 bytes
```

## 验证结果

```text
python -m pytest -q
结果：PASS，19 passed, 2 warnings in 3.26s

python -X utf8 backend\self_check.py
结果：PASS，SELF_CHECK_SUMMARY PASS

python -X utf8 backend\smoke_stage9.py
结果：PASS，cover pass；single short train rejection pass；multi train pass；all smoke checks pass

python -X utf8 backend\verify_stage11_train_flow.py
结果：PASS，short single rejected -> train_material_not_eligible / single_short_out_of_window；multi ok -> train_e0b3cafe45ca；stage11 verification PASS

node frontend\playwright_trained_model_cover_studio_smoke.cjs
结果：PASS，STAGE28_TRAINED_MODEL_COVER_SMOKE PASS
```

Stage 28 真实闭环本轮补跑结果：

```text
model_id = v_b5c8427a
source_job_id = train_d8cd4ed377ca
track_id = trk_64c93e738c
cover_job_id = task_6c51b2254e67
final_stage = cover_mix
studio_url = /studio?batch_id=batch_e371154921&track_id=trk_64c93e738c&job_id=task_6c51b2254e67&artifact_id=art_ea79add8dd19
audio_path = C:/Users/ASUS/Desktop/归不了岸的船.mp3
master_set = yes
screenshot = D:\FeiSharkStudio-v2\stage28_trained_model_cover_studio.png
```

## 未执行的重型验收

本轮没有执行：

```text
python -X utf8 backend\verify_stage26_real_audio_training.py
```

原因：

- Stage 29 的目标是修复旧 smoke / verify 脚本与 Stage 26 素材规则的冲突。
- 本轮未修改 `audio_material_service.py`、训练素材判定逻辑、长样本训练实现或 RVC 主训练链。
- Stage 26 长样本脚本会触发真实 30-50 分钟级单文件训练，属于重型验收，不适合每轮轻量回归默认执行。
- Stage 28 真实闭环已补跑通过，可作为本轮未破坏真实训练模型后续 cover / Factory / Studio 链路的强信号。

## Stage 28 闭环回归风险

- 是否修改了 `frontend\playwright_trained_model_cover_studio_smoke.cjs`：否。
- 是否修改了 Factory / Studio 主链路：否。
- 是否修改了 cover / train 主链路：否。
- 是否发现 `Train -> Model Registry -> Cover -> Factory -> Studio` 回退风险：未发现。
- 补跑 Stage 28 真实闭环：PASS。

## 风险与限制

- 当前工作区存在大量前序阶段未提交文件，本轮只对 Stage 29 允许范围内文件做了收口，没有回滚或清理其他阶段改动。
- `README.md` 在当前工作区显示为未跟踪文件；本轮按现有项目状态更新其中“常用验证”部分，未尝试重建仓库历史。
- Stage 26 的 45 分钟级真实训练脚本本轮未跑，后续若修改长样本训练判定、RVC 训练编排或真实素材入口，需要单独补跑。

## 交接说明

下一轮 agent 或架构师继续工作前，建议优先关注：

- 继续保持 3 秒单文件训练样本的拒绝语义，不要再把它恢复成单文件训练正向样本。
- 日常轻量回归优先跑 README 中的四条基础命令。
- 涉及真实训练模型闭环时，再跑 `frontend\playwright_trained_model_cover_studio_smoke.cjs`。
