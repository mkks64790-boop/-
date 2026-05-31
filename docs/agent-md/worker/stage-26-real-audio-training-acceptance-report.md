# 第26阶段执行汇报：真实干声训练验收 + 短素材分流收口

## 完成情况

- 已完成：
  - 单文件训练不再只按 `file_count` 粗暴分流。
  - 后端已补上真实素材画像识别：`duration_seconds / duration_label / sample_rate / channels / codec / container / bit_rate / material_profile / recommended_route / single_long_eligible / reason / next_step`。
  - `C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3` 已被真实识别为合规单文件长干声，并通过真实训练链完整跑到 `train_register_model`。
  - `C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3` 已被明确识别为不合规单文件长干声，并在提交时被 422 拦截，不再误入 `single_long_preprocess`。
  - Dashboard 训练入口已能在选中文件后展示素材时长、建议链路、失败原因与下一步建议。
  - 已新增可重复执行的 Stage 26 真实验收脚本。

## 修改文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\self_check.py`
- `D:\FeiSharkStudio-v2\backend\services\audio_material_service.py`
- `D:\FeiSharkStudio-v2\backend\services\dataset_service.py`
- `D:\FeiSharkStudio-v2\backend\services\preflight_service.py`
- `D:\FeiSharkStudio-v2\backend\strategies\strategy_registry.py`
- `D:\FeiSharkStudio-v2\backend\verify_stage26_real_audio_training.py`
- `D:\FeiSharkStudio-v2\frontend\index.html`
- `D:\FeiSharkStudio-v2\frontend\js\train.js`
- `D:\FeiSharkStudio-v2\tests\api\test_train_material_routing_api.py`
- `D:\FeiSharkStudio-v2\tests\unit\test_audio_material_service.py`

## 样本分析结果

### 1. 长样本：`朱朱干声唱.mp3`

- 路径：
  - `C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3`
- 读取到的元数据：
  - 时长：`2709.9951s`，约 `45分10秒`
  - 采样率：`44100`
  - 声道：`2`
  - 格式：`mp3`
  - 码率：`320000`
  - 文件大小：`108400926`
- 系统判定：
  - `material_profile = single_long_candidate`
  - `single_long_eligible = true`
  - `recommended_route = single_long_preprocess`
  - `reason = 单文件时长约 45分10秒，命中 30-50 分钟快速训练窗口。`

### 2. 短样本：`朱朱干声.mp3`

- 路径：
  - `C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3`
- 读取到的元数据：
  - 时长：`932.702025s`，约 `15分33秒`
  - 采样率：`44100`
  - 声道：`2`
  - 格式：`mp3`
  - 码率：`320000`
  - 文件大小：`37309203`
- 系统判定：
  - `material_profile = single_short_out_of_window`
  - `single_long_eligible = false`
  - `recommended_route = multi_clean_direct`
  - `reason = 单文件时长约 15分33秒，未达到 30 分钟下限，不能按单文件长干声快速训练处理。`
  - `next_step = 请改用多文件精训素材，或准备 30-50 分钟单干声后再提交。`

## 功能结果

### 后端

- 做了什么：
  - 新增 `audio_material_service.py`，统一负责音频元数据探测和训练路由判定。
  - `/api/preflight/train` 现在支持基于 `duration_seconds` 做真实单文件长短判断。
  - `/api/train` 现在会在文件落盘后用 `ffprobe` 做后端权威验收，再决定是否允许进入训练链。
  - 单文件短样本提交时改为返回结构化 `422`，包含 `material_profile / recommended_route / single_long_eligible / reason / next_step`。
  - 训练 job / dataset / upload stage log 都会携带 `material_decision`，方便 UI 和验收脚本读取。
- 训练路由如何变化：
  - 以前：`1 文件 -> single_long_preprocess`，`多文件 -> multi_clean_direct`
  - 现在：
    - `1 文件 + 1800s~3000s -> single_long_preprocess`
    - `1 文件 + <1800s -> 拒绝单文件快速训练，并明确建议改走多文件精训`
    - `多文件 -> multi_clean_direct`
- 返回结构增加了什么：
  - `/api/preflight/train` 与 `/api/train` 都新增了素材画像与路由判定字段。
- 短样本如何被阻止误入单文件长干声训练：
  - 前端提交前会先展示“不合规”原因。
  - 后端提交时仍会再次验收。
  - 若仍尝试提交，则直接 `422` 拒绝，不创建真实单文件训练任务。

### 前端

- 训练入口增加了哪些提示：
  - 单文件入口会读取本地音频时长。
  - 文件提示区会显示：文件名 / 大小 / 时长。
  - 模式提示区会显示：建议链路。
  - 可用性提示区会显示：是否命中 30-50 分钟窗口、为什么不能走单文件快速训练、下一步该怎么做。
- 用户在选中长样本后能看到什么：
  - 约 `45分10秒`
  - 命中单文件快速训练窗口
  - 将进入 `single_long_preprocess`
- 用户在选中短样本后能看到什么：
  - 约 `15分33秒`
  - 未达到 30 分钟下限
  - 不会进入 `single_long_preprocess`
  - 建议改用多文件精训素材，或准备更长单干声
- 提交失败或分流时能看到什么：
  - 结构化失败原因
  - 明确下一步建议

### 真实验收脚本

- 新增脚本路径：
  - `D:\FeiSharkStudio-v2\backend\verify_stage26_real_audio_training.py`
- 脚本做了什么：
  - 启动隔离的本地 `uvicorn`（`127.0.0.1:8016`）
  - 检查 `/api/health`
  - 检查训练 preflight
  - 读取两份桌面真实样本元数据
  - 验证长样本命中 `single_long_preprocess`
  - 验证短样本不合规并被拒绝
  - 真实发起长样本训练并轮询阶段
  - 长样本完成后自动核对 `.pth` / `.index` 产物存在且非空
- 输出摘要长什么样：
  - `STAGE26_VERIFY PASS`
  - `LONG_SAMPLE_PROBE / SHORT_SAMPLE_PROBE`
  - `LONG_SAMPLE_PREFLIGHT / SHORT_SAMPLE_PREFLIGHT`
  - `LONG_SAMPLE_SUBMISSION / LONG_SAMPLE_RUNTIME`
  - `SHORT_SAMPLE_SUBMIT_REJECTION`
  - `LONG_SAMPLE_ARTIFACTS`

## 真实训练验收结果

### 长样本训练

- 是否真实创建任务：
  - 是
- 任务 ID：
  - `train_d8cd4ed377ca`
- 实际进入策略：
  - `single_long_preprocess`
- 实际运行阶段轨迹：
  - `train_upload`
  - `train_preflight`
  - `train_dataset_prepare`
  - `train_preprocess`
  - `train_pitch_extract`
  - `train_feature_extract`
  - `train_core`
  - `train_index`
  - `train_register_model`
- 最终结果：
  - `完成`
- 最终阶段：
  - `train_register_model`
- 真实产物：
  - `.pth`
    - `D:\FeiSharkStudio-v2\shared_data\jobs\train_d8cd4ed377ca\artifacts\train_register_model\stage26_real_long_1780063446.pth`
    - `55229665 bytes`
  - `.index`
    - `D:\FeiSharkStudio-v2\shared_data\jobs\train_d8cd4ed377ca\artifacts\train_register_model\stage26_real_long_1780063446.index`
    - `292128899 bytes`
- 额外核验：
  - 使用 `D:\Miniconda3\envs\rvc\python.exe` 调用 `faiss.read_index(...)` 读取 `.index` 成功，返回 `ok`

### 短样本分流

- 是否允许创建单文件训练任务：
  - 否
- 系统给出的提示：
  - `单文件时长约 15分33秒，未达到 30 分钟下限，不能按单文件长干声快速训练处理。`
  - `请改用多文件精训素材，或准备 30-50 分钟单干声后再提交。`
- 最终行为是否符合“不误走单文件长干声主链”：
  - 是
- 返回结构核心字段：
  - `code = train_material_not_eligible`
  - `material_profile = single_short_out_of_window`
  - `recommended_route = multi_clean_direct`
  - `single_long_eligible = false`

## 验证结果

```text
python -m pytest -q
结果：
17 passed, 2 warnings in 2.84s

python -X utf8 backend/self_check.py
结果：
SELF_CHECK_SUMMARY PASS

python -X utf8 backend/verify_stage26_real_audio_training.py
结果：
STAGE26_VERIFY PASS
长样本真实完成到 train_register_model
短样本真实提交被 422 拒绝
```

额外补充核验：

```text
通过 /api/jobs/train_d8cd4ed377ca/artifacts 查询真实产物
结果：
train_model_pth / train_model_index 均存在，且 index 文件大小 292128899 bytes

使用 RVC Python + faiss.read_index 校验真实 index
结果：
ok
```

## 风险与限制

- 当前“合规单文件快速训练”仍主要基于时长窗口判定，还没有继续做更重的“干声纯度 / 静音比例 / 伴奏泄漏”质量评分。
- 前端本地时长读取依赖浏览器音频 metadata；如果浏览器读不出时长，后端仍会在真实提交时再次做权威验收。
- 本轮真实验收脚本使用隔离 `uvicorn` 跑在 `8016` 端口，避免污染桌面上已有的 `8000` 工作台服务；若要在常驻服务上立即生效，仍需重启当前正在运行的 `8000` 实例。

## 交接说明

下一轮 agent 或架构师继续工作前，优先关注：

- 事项 1：
  - 如果后续还要继续收紧单文件素材质量标准，可在 `audio_material_service.py` 上叠加更细的音频质量 heuristics，但不要回退当前“短样本硬拦截”语义。
- 事项 2：
  - 如果要把这套素材画像展示得更完整，可在 Dashboard 训练卡片上继续补 `sample_rate / channels / codec` 的可视化，但必须保持和后端字段一致。
- 事项 3：
  - 如要把真实样本验收纳入更广的回归流水，优先直接复用 `backend/verify_stage26_real_audio_training.py`，不要再起一套平行脚本。
