# 第27阶段：训练成果入库联动 + 模型库桥接翻唱入口

你现在是 FeiShark Studio 的工作 agent。

第26阶段已经把“真实长干声训练是否走对链路”这件事验清楚了，关键结论已经成立：

- `C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3` 已经真实跑通训练链，并完成到 `train_register_model`
- 真实训练产物 `.pth / .index` 已生成
- 短样本 `朱朱干声.mp3` 也已经被正确拦截，不再误走 `single_long_preprocess`

但现在还有一个明显的产品断层：

训练虽然完成了，模型虽然入库了，但“训练成果”还没有被真正产品化成一个可管理、可解释、可一键用于翻唱的模型资产。

也就是说，第26阶段证明了“能训练”，第27阶段要解决的是：

1. 训练出来的模型，在模型库里必须像一个真正的产品资产，而不是一条模糊记录
2. 用户必须看得懂这个模型是怎么来的，来自哪个训练任务，属于哪种训练策略
3. 用户必须能从模型面板一键把这个模型送进翻唱入口，而不是自己手工找下拉框
4. 模型库、任务详情、翻唱入口，这三者之间要形成明确联动

本阶段不做真实翻唱闭环，不做 Studio 成品验收，不做 DAW / VST。
这些是第28阶段再做的事。

## 必读文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\db.py`
- `D:\FeiSharkStudio-v2\backend\model_trainer.py`
- `D:\FeiSharkStudio-v2\backend\services\model_service.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\backend\services\dataset_service.py`
- `D:\FeiSharkStudio-v2\backend\services\audio_material_service.py`
- `D:\FeiSharkStudio-v2\backend\self_check.py`
- `D:\FeiSharkStudio-v2\backend\verify_stage26_real_audio_training.py`
- `D:\FeiSharkStudio-v2\frontend\index.html`
- `D:\FeiSharkStudio-v2\frontend\js\models.js`
- `D:\FeiSharkStudio-v2\frontend\js\cover.js`
- `D:\FeiSharkStudio-v2\frontend\js\jobs.js`
- `D:\FeiSharkStudio-v2\frontend\js\ui.js`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-26-real-audio-training-acceptance-report.md`

## 实施范围

### 允许修改

- 模型资产入库元数据
- `/api/models` 和 `/api/models/{model_id}` 返回结构
- Dashboard 的模型面板与翻唱入口联动
- 任务详情与模型来源信息的轻量联动
- 轻量测试 / smoke / verify 脚本
- 本阶段 architect / worker / handoff 文档

### 禁止事项

- 不要改 RVC 推理或训练执行层核心逻辑
- 不要做新的独立页面
- 不要开始做第28阶段的真实翻唱闭环
- 不要引入 Redis / WebSocket / Celery
- 不要为了存一点来源信息就新造一套重型模型管理后台
- 不要破坏现有 `/api/models` 的基础兼容字段

## 具体任务

### 1. 把训练模型正式做成“有来源的资产”

当前模型库已经能看到模型，但还不够产品化。

请把训练产出的模型正式补齐“来源语义”，优先复用现有结构：

- `voice_models.source_job_id`
- `voice_models.metadata_json`

只有在确实不够时，才考虑加字段；优先轻量、兼容、可迁移。

训练模型至少要能稳定追溯这些信息：

- `origin_kind`
  - 建议值：
    - `trained_local`
    - `imported_external`
    - `rescanned_local`
- `source_job_id`
- `source_strategy_key`
  - 例如：
    - `single_long_preprocess`
    - `multi_clean_direct`
- `source_dataset_id`
- `source_material_profile`
  - 例如：
    - `single_long_candidate`
    - `multi_file_dataset`
- `source_file_count`
- `source_duration_label`
  - 如适用
- `created_at / updated_at`

最低要求：

- 第26阶段真实训练出来的模型，在 `/api/models/{id}` 里必须能清楚看到它来自哪一个 train job
- 导入模型和训练模型要能在来源类型上区分开
- 不能再让“训练模型”和“手工导入模型”在产品语义上长得一模一样

### 2. 扩展模型 API，让前端拿得到“够用的信息”

请补强：

- `GET /api/models`
- `GET /api/models/{model_id}`

要求：

- 保留现有兼容字段：
  - `model_id`
  - `model_name`
  - `default_pitch`
  - `usable`
  - `resolved_pth_path`
  - `resolved_source`
- 在不破坏旧调用的前提下，新增前端真正需要的来源摘要字段

建议至少返回：

- `origin_kind`
- `source_job_id`
- `source_strategy_key`
- `source_material_profile`
- `source_file_count`
- `source_duration_label`
- `source_summary`
  - 给前端直接显示的一句人话摘要

如果模型来自训练任务，还建议 detail 中补充：

- `source_job_status`
- `source_job_current_stage`
- `source_job_created_at`

要求是：

- 模型卡片能做摘要展示
- 模型详情能做来源解释
- 不需要前端自己拼一堆字段才能看懂

### 3. 重构模型面板，让它像“模型资产库”，不是纯技术列表

当前 `frontend/js/models.js` 已经有模型列表和详情，但现在还偏技术视角。

请把它重构为更产品化的“模型资产库”表现，重点不是变花，而是变清楚：

- 在模型卡片上直接显示来源标签：
  - `本地训练`
  - `外部导入`
  - `目录扫描`
- 对训练模型，直接显示关键摘要：
  - 来源训练策略
  - 来源 job_id
  - 是否可直接用于翻唱
- 对不可用模型，明确说明“为什么当前不可用”

详情区至少拆出这些块：

- `核心信息`
- `当前判定`
- `来源训练 / 来源导入`
- `路径与技术详情`

要求：

- 不要让来源信息淹没在“技术详情”抽屉里
- “技术详情”仍可以默认折叠
- 但“来源信息”必须默认可见

### 4. 在模型详情里加两个关键动作

#### 动作 A：`用于翻唱`

点击后应做到：

- 自动把该模型写入 `coverModelSelect`
- 同步触发必要的前端状态更新
- 滚动或聚焦到 `AI 一键翻唱` 卡片
- 给出清楚 toast，例如：
  - `已将模型 xxx 选入翻唱入口`

如果模型不可用：

- 不允许执行该动作
- 要给出明确阻止原因

#### 动作 B：`查看来源任务`

点击后应做到：

- 滚动到任务中心
- 尽可能定位到对应 train job
- 如果当前前端已有任务详情加载能力，则直接载入该 job 的详情

最低要求：

- 用户至少能从模型详情跳回来源 train job，而不是只看到一个裸 `job_id`

### 5. 增加“训练完成 -> 模型入库 -> 前端可见”的联动

这轮要把“模型已经注册成功，但前端没感知到”这件事补齐。

至少做到以下其一，推荐同时做到：

- 当前页面在 jobs 轮询时，一旦发现 train job 进入 `train_register_model / 完成`，自动刷新模型面板
- 如果当前选中的任务正好是这个 train job，任务详情里直接显示：
  - 生成的 `model_id`
  - 一个“在模型库打开”按钮

要求：

- 不要靠用户手工点 3 次刷新才发现模型已经能用了
- 但也不要大改整套轮询架构

### 6. 用第26阶段真实训练结果做这轮验收种子

本阶段验收，优先使用第26阶段真实训练生成的模型作为样本。

也就是报告里提到的真实训练 job 与产物：

- train job：
  - `train_d8cd4ed377ca`
- 真实模型文件：
  - `D:\FeiSharkStudio-v2\shared_data\jobs\train_d8cd4ed377ca\artifacts\train_register_model\stage26_real_long_1780063446.pth`
  - `D:\FeiSharkStudio-v2\shared_data\jobs\train_d8cd4ed377ca\artifacts\train_register_model\stage26_real_long_1780063446.index`

要求：

- 优先验证这个真实训练模型已经能被模型库识别并展示来源
- 不要为了本轮 smoke 再重新跑一轮长训练，除非你确实没有别的办法

如果本地环境里这个真实模型记录不存在或已被清理：

- 允许用轻量方式补一个 linked model 测试样本
- 但必须在报告里写清楚你用的是“真实 Stage26 样本”还是“测试替身样本”

### 7. 测试补齐

至少跑：

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`

并补一组与本阶段直接相关的验证。

建议至少包含：

- API 测试：
  - 训练模型 detail 含来源字段
  - 导入模型与训练模型 `origin_kind` 可区分
  - `source_job_id` 在 detail 中可回溯
- 前端 smoke 或 verify：
  - 模型详情能显示来源信息
  - 点击 `用于翻唱` 后，翻唱下拉框正确切换
  - 点击 `查看来源任务` 后，任务详情能够定位或至少成功跳转聚焦

建议命名类似：

- `tests/api/test_model_registry_lineage_api.py`
- `frontend/playwright_model_registry_linkage_smoke.cjs`
  或
- `backend/verify_stage27_model_registry_linkage.py`

## 交付要求

完成后必须输出：

1. 修改了哪些文件
2. 模型库新增了哪些来源字段
3. 训练模型和导入模型如何区分
4. 第26阶段真实训练模型在模型库里显示成了什么样
5. `用于翻唱` 动作如何工作
6. `查看来源任务` 动作如何工作
7. 自动联动刷新是否完成，如何触发
8. 新增了哪些测试 / smoke / verify
9. 跑了哪些命令，结果是什么
10. 还剩哪些限制
11. 将本轮汇报写入：
   - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-27-model-registry-linkage-report.md`

## 验证要求

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`
- 运行你新增的 Stage 27 验证脚本或 smoke

如果你补了前端 smoke，必须实际跑一遍，而不是只创建文件不执行。

## 完成标准

- 训练产出的模型在模型库中有清楚来源，不再是模糊记录
- 模型库能区分 `本地训练` 和 `外部导入`
- 模型详情可以直接把模型送入翻唱入口
- 模型详情可以跳回来源训练任务
- 训练完成后，模型面板能更快感知并展示新模型
- 至少一条真实训练模型样本已完成本轮联动验收
