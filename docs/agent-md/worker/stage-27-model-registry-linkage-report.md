# 第27阶段执行汇报：训练成果入库联动 + 模型库桥接翻唱入口

## 完成情况

- 已完成：
  - 训练模型现在会带着“来源语义”进入模型库，不再只是模糊记录。
  - `/api/models` 与 `/api/models/{model_id}` 已补齐可直接给前端使用的来源字段。
  - Dashboard 模型面板现在能区分 `本地训练 / 外部导入 / 目录扫描`。
  - 模型详情新增了 `用于翻唱` 与 `查看来源任务` 两个关键动作。
  - train job 完成后，任务详情能直接显示生成的 `model_id`，并支持一键在模型库打开。
  - 已补 API 测试与前端 smoke，并实际跑通。

## 修改文件

- `D:\FeiSharkStudio-v2\backend\services\model_service.py`
- `D:\FeiSharkStudio-v2\backend\db.py`
- `D:\FeiSharkStudio-v2\backend\model_trainer.py`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\frontend\js\ui.js`
- `D:\FeiSharkStudio-v2\frontend\js\models.js`
- `D:\FeiSharkStudio-v2\frontend\js\jobs.js`
- `D:\FeiSharkStudio-v2\frontend\js\main.js`
- `D:\FeiSharkStudio-v2\frontend\css\app.css`
- `D:\FeiSharkStudio-v2\tests\api\test_model_registry_lineage_api.py`
- `D:\FeiSharkStudio-v2\frontend\playwright_model_registry_linkage_smoke.cjs`

## 模型来源字段

- 新增或补齐了这些字段：
  - `origin_kind`
  - `source_job_id`
  - `source_strategy_key`
  - `source_dataset_id`
  - `source_material_profile`
  - `source_file_count`
  - `source_duration_label`
  - `source_summary`
  - detail 额外补充：
    - `source_job_status`
    - `source_job_current_stage`
    - `source_job_created_at`
    - `resolved_index_path`
    - `resolved_index_source`

- 这些字段写入到了哪里：
  - `voice_models.source_job_id`
  - `voice_models.metadata_json`

- 训练模型如何写入这些字段：
  - `backend/model_trainer.py` 在 `register_trained_model(...)` 时调用 `build_trained_model_metadata(source_job_id)`。
  - `backend/db.py` 的 `add_voice_asset(...)` 现在支持写入 `metadata_json`，训练模型会落入：
    - `origin_kind = trained_local`
    - 以及来源 job / dataset / 素材画像摘要。

- 导入模型如何写入这些字段：
  - `backend/services/model_service.py` 的 `import_voice_model(...)` 默认写：
    - `origin_kind = imported_external`
    - `source_summary = 来自外部导入，路径由用户手动登记。`

- 目录扫描模型如何写入这些字段：
  - `rescan_voice_models(...)` 现在调用 `import_voice_model(..., origin_kind="rescanned_local")`。

## 功能结果

### 后端

- `/api/models` 增加了什么：
  - 保留原兼容字段：
    - `model_id`
    - `model_name`
    - `default_pitch`
    - `usable`
    - `resolved_pth_path`
    - `resolved_source`
  - 新增可直接渲染的来源字段：
    - `origin_kind`
    - `source_job_id`
    - `source_strategy_key`
    - `source_dataset_id`
    - `source_material_profile`
    - `source_file_count`
    - `source_duration_label`
    - `source_summary`
    - `resolved_index_path`

- `/api/models/{model_id}` 增加了什么：
  - 除列表字段外，detail 还会返回：
    - `source_job_status`
    - `source_job_current_stage`
    - `source_job_created_at`
    - `metadata`
    - `index_exists`
    - `resolved_index_source`

- 如何区分 `trained_local / imported_external / rescanned_local`：
  - 训练模型优先看 `source_job_id` 与 metadata，标成 `trained_local`
  - 手工导入模型写成 `imported_external`
  - 目录重扫新发现模型写成 `rescanned_local`

- 如何回溯来源 train job：
  - 先看 `voice_models.source_job_id`
  - 再通过 `jobs` + `datasets` + `material_decision` 组装来源语义
  - 对于 Stage 26 之前已入库但 metadata 为空的训练模型，也能通过 `source_job_id` 动态补出来源摘要

- train job detail 的轻量联动：
  - `/api/jobs/{job_id}` 现在新增：
    - `generated_model_id`
    - `generated_model_name`
    - `generated_model_usable`
    - `generated_model_origin_kind`
    - `generated_model_summary`

### 前端模型库

- 模型卡片现在会显示什么：
  - 模型名 / model_id
  - 可用状态
  - 来源标签：
    - `本地训练`
    - `外部导入`
    - `目录扫描`
  - 来源摘要一句话
  - 当前解析到的 `.pth`

- 模型详情现在会显示什么：
  - 第一层：模型判定
    - 这个模型能不能用于翻唱
    - 它来自哪里
    - 下一步建议做什么
  - 第二层：核心信息 / 来源信息 / 当前判定 / 当前解析结果
  - 第三层：技术详情抽屉

- 默认可见的信息有哪些：
  - 模型状态
  - 来源类型
  - 来源摘要
  - 来源任务 / 训练策略 / 素材画像 / 文件数量 / 时长
  - 当前解析到的 `.pth / .index`

- 默认折叠的信息有哪些：
  - 原始登记路径
  - 原始后端状态
  - 解析来源等技术字段

### 动作联动

#### 1. `用于翻唱`

- 点击后发生了什么：
  - 直接把当前模型写入 `coverModelSelect`
  - 同步更新 `selectedCoverModelId`
  - 触发 `change` 事件，让现有 cover 可用性逻辑继续工作
  - 自动切回 Dashboard 主区并滚动到创建入口
  - 弹 toast：
    - `已将模型 xxx 选入翻唱入口`

- 如何同步 `coverModelSelect`：
  - 仍然复用现有 DOM id，不新造状态总线。
  - 由 `models.js -> useModelForCover()` 直接驱动现有下拉框。

- 不可用模型如何阻止：
  - 不显示 `用于翻唱` 主按钮。
  - 摘要区直接说明不可用原因与下一步建议。
  - 如果通过异常路径触发，会 toast 提示阻止原因。

#### 2. `查看来源任务`

- 点击后发生了什么：
  - 切回 Dashboard
  - 滚动到任务中心
  - 派发 `feishark:focus-job`
  - `jobs.js` 接到事件后加载对应 train job detail

- 是否能直接加载来源任务详情：
  - 能。
  - 即使当前列表页不一定正好高亮到该 row，也会直接加载该 job 的详情区。

- 当前最小可用行为：
  - 用户至少能从模型详情一键跳回来源 train job 详情，不再只看到裸 `job_id`。

### 自动刷新联动

- train job 完成后，模型面板如何感知：
  - `jobs.js` 在列表轮询时，会检测当前页是否出现 `train_register_model / completed` 的 train job 签名变化。
  - `main.js` 收到 `modelsMayBeStale` 后，会补一次 `refreshModels()` 与 `refreshDiagnostics()`。
  - 如果当前选中的详情正好是完成 train job，`loadJobDetail(...)` 还会派发 `feishark:train-model-registered` 再触发一次模型刷新。

- 是否需要手工刷新：
  - 不需要作为默认路径。
  - 正常轮询下，模型库会在 train job 注册完成后自动感知。

- 如果仍有延迟，延迟点在哪里：
  - 当前仍是轮询架构，不是推送架构。
  - 最坏情况会等到下一次 jobs 刷新周期，属于当前阶段允许的轻量语义。

## 验收样本

### 优先样本

- 是否使用了第26阶段真实训练模型：
  - 是

- 来源 job_id：
  - `train_d8cd4ed377ca`

- 模型 id：
  - `v_b5c8427a`

- 模型名称：
  - `stage26_real_long_1780063446`

- 页面上如何展示：
  - 来源标签：`本地训练`
  - 来源摘要：
    - `来自本地训练任务 train_d8cd4ed377ca · 单文件快速训练 · 单文件长样本 · 1 个文件 · 45分10秒`
  - 任务详情可显示：
    - `generated_model_id = v_b5c8427a`
    - `在模型库打开`

## 验证结果

```text
python -m pytest -q
结果：
19 passed, 2 warnings in 3.32s

python -X utf8 backend/self_check.py
结果：
SELF_CHECK_SUMMARY PASS

node frontend/playwright_model_registry_linkage_smoke.cjs
结果：
STAGE27_MODEL_REGISTRY_SMOKE PASS model=v_b5c8427a source_job=train_d8cd4ed377ca
```

额外补充核验：

```text
通过 TestClient 查询 /api/models?include_unavailable=true
结果：
Stage 26 真实模型 v_b5c8427a 返回 origin_kind/source_job_id/source_summary 全部正确

通过 TestClient 查询 /api/jobs/train_d8cd4ed377ca
结果：
generated_model_id = v_b5c8427a
generated_model_summary = 来自本地训练任务 train_d8cd4ed377ca · 单文件快速训练 · 单文件长样本 · 1 个文件 · 45分10秒
```

浏览器产物：

- 截图：
  - `D:\FeiSharkStudio-v2\stage27_model_registry_linkage.png`

## 风险与限制

- 还没补齐的来源信息：
  - 对于历史上已经入库、且 `metadata_json` 为空的外部导入/旧扫描模型，当前仍主要依赖现有登记路径与动态推断。
  - 训练模型因为有 `source_job_id`，这轮已经能完整回溯；旧外部模型如果没有明确来源，只能保留 `imported_external` 语义。

- 当前联动还不够顺滑的地方：
  - `查看来源任务` 能稳定加载详情，但如果当前列表页过滤条件或分页不包含该 row，列表不一定同步高亮到那一行。
  - 这轮优先保证“详情能打开、上下文能回溯”，没有重写整套列表定位逻辑。

- 为什么这轮先不做真实翻唱闭环：
  - Stage 27 的目标是“训练成果产品化入库 + 模型资产桥接翻唱入口”。
  - 真实 cover 成品验收与 Studio 闭环属于 Stage 28 范围，按架构约束刻意延后。

## 交接说明

下一轮 agent 或架构师继续工作前，优先关注：

- 事项 1：
  - 如果要继续做 Stage 28，可直接基于 `generated_model_id`、`source_job_id`、`source_summary` 去打通真实 cover 闭环，不需要再重复做模型来源抽象。

- 事项 2：
  - 如果要补“来源任务列表精准定位”，建议在不改 API 契约的前提下，为 jobs 面板增加按 `job_id` 的本地定位/翻页辅助，而不是重写整个任务中心。

- 事项 3：
  - 如果要清理历史模型来源，可补一个一次性 backfill 脚本，把旧 `voice_models.metadata_json` 里的 `origin_kind/source_summary` 批量补齐；这轮没有为了过度迁移去动历史数据。
