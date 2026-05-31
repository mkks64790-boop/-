# 第28阶段：训练模型真实翻唱闭环 + Studio 成品验收

你现在是 FeiShark Studio 的工作 agent。

第27阶段已经独立验收通过，当前项目已经具备：

- 第26阶段：真实长干声训练链通过
- 第27阶段：训练成果正式入模型库，并能一键送入翻唱入口
- Dashboard 模型库已经能区分：
  - `本地训练`
  - `外部导入`
  - `目录扫描`

现在最重要的，不是继续补模型库字段，也不是继续做 UI 微调。

现在要打通的是这条真正有业务意义的链：

`Train -> Model Registry -> Cover -> Factory -> Studio`

也就是说，要证明：

1. 第26阶段真实训练出来的模型，不只是“在模型库里能看”
2. 它必须能真的被拿去做一次真实翻唱
3. 翻唱成品必须能进入 `Studio`
4. `Factory / Studio / 当前主成品` 这一套产品语义，在真实训练模型生成的 cover 上依然成立

这轮仍然不做 VST，不做修音页，不做大型 UI 重构。
这轮只做真实闭环验收与必要的轻量联动补强。

## 真实素材与目标模型

### 优先使用的训练模型

优先模型：

- `model_id = v_b5c8427a`
- `model_name = stage26_real_long_1780063446`
- `origin_kind = trained_local`
- `source_job_id = train_d8cd4ed377ca`

如果本地这条记录不存在或不可用，按下面顺序降级：

1. 查找 `source_job_id = train_d8cd4ed377ca` 的可用训练模型
2. 再查找任意 `origin_kind = trained_local` 且 `usable = true` 的模型
3. 如果最终只能使用其他训练模型，必须在 report 里明确写清楚

### 优先使用的真实翻唱源音频

首选：

- `C:\Users\ASUS\Desktop\归不了岸的船.mp3`
  - 已确认：约 `180.036s`
  - `mp3 / 44.1kHz / stereo`

备选：

- `C:\Users\ASUS\Desktop\晚风失约.mp3`
  - 已确认：约 `239.520s`
  - `mp3 / 48kHz / stereo`

优先使用更短的首选素材，以减少真实 cover 验收时间。

## 必读文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\backend\services\track_service.py`
- `D:\FeiSharkStudio-v2\backend\services\model_service.py`
- `D:\FeiSharkStudio-v2\backend\services\asset_service.py`
- `D:\FeiSharkStudio-v2\backend\strategies\cover_strategy.py`
- `D:\FeiSharkStudio-v2\backend\self_check.py`
- `D:\FeiSharkStudio-v2\frontend\factory.html`
- `D:\FeiSharkStudio-v2\frontend\studio.html`
- `D:\FeiSharkStudio-v2\frontend\js\factory\main.js`
- `D:\FeiSharkStudio-v2\frontend\js\models.js`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\frontend\js\jobs.js`
- `D:\FeiSharkStudio-v2\frontend\playwright_factory_to_studio_context_smoke.cjs`
- `D:\FeiSharkStudio-v2\frontend\playwright_studio_track_history_smoke.cjs`
- `D:\FeiSharkStudio-v2\frontend\playwright_track_master_registry_smoke.cjs`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-26-real-audio-training-acceptance-report.md`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-27-model-registry-linkage-report.md`

## 实施范围

### 允许修改

- 真实 cover 创建链路中与模型来源联动直接相关的后端字段与返回结构
- `Factory` / `Studio` 中与本轮真实闭环验收直接相关的摘要信息
- 真实 cover 验收脚本 / Playwright smoke / 轻量 API 测试
- 任务详情与成品详情中的模型来源可读性
- 本阶段 architect / worker / handoff 文档

### 禁止事项

- 不要重写 RVC 推理执行层
- 不要重写 Studio 页面结构
- 不要开始做 VST、修音、波形编辑器
- 不要为了本轮验证再次重跑 45 分钟长训练，除非确实找不到第26阶段的真实训练模型
- 不要引入 Redis / WebSocket / Celery
- 不要把本轮做成“新增一堆测试页面”

## 具体任务

### 1. 给真实 cover job 记录“所用模型的来源快照”

第27阶段已经把模型来源做进了模型库。
但一旦模型被拿去做 cover，cover job / Factory / Studio 里也要能知道：

- 这次翻唱用的是哪个模型
- 这个模型来自哪里
- 是本地训练模型，还是外部导入模型
- 如果是训练模型，来自哪个 train job

请在 cover job 创建或激活时，给 job 写入一份轻量来源快照，建议字段语义至少包含：

- `voice_model_origin_kind`
- `voice_model_source_job_id`
- `voice_model_source_summary`
- 如有必要，可补：
  - `voice_model_source_strategy_key`
  - `voice_model_source_material_profile`

要求：

- 这份信息是“创建 cover 时的快照”，不要只靠前端临时再去查模型库猜
- 要能在 job / track job / studio 数据里被直接消费

### 2. 用真实训练模型发起一次真实 cover

这轮必须是真 cover，不允许：

- 复用旧 cover job 充数
- 只跑 mock / smoke 假任务
- 只在 API 层造完成状态

优先走产品主链：

- 通过 `Factory` 的真实 track 流程导入源歌曲
- 再通过 `POST /api/tracks/{track_id}/cover-jobs` 或其当前真实前端入口创建 cover

不要优先走通用 `/api/upload_task` 老入口，因为那条链不完整，无法代表当前产品闭环。

要求：

- 使用第27阶段确认可用的训练模型
- 使用上述真实本地歌曲之一
- 真正进入 cover 执行链
- 至少完整记录这些真实阶段：
  - `cover_split`
  - `cover_pitch`
  - `cover_voice`
  - `cover_mix`

如果失败：

- 必须精确写明停在哪一阶段
- 必须记录错误文本
- 不得伪装成功

### 3. 打通 `Factory -> Studio` 的真实训练模型成品闭环

真实 cover 完成后，至少要验证：

- `Factory` 当前曲目详情区能看到新完成的成品
- 成品条目能进入 `Studio`
- `Studio` 页面能载入对应音频资源
- 下载按钮、资源摘要、当前 job 上下文都能成立

这轮重点不是 Studio 的外观，而是语义链：

- 这首成品是谁唱的
- 用的是哪个模型
- 这个模型来自哪一个训练任务

所以请至少在 `Factory` 或 `Studio` 的一个主摘要区，把下列信息做成默认可见：

- `voice_model_id`
- `voice_name`
- `voice_model_origin_kind`
- `voice_model_source_summary`

要求：

- 不要把这套信息只塞进技术细节抽屉
- 用户必须能一眼看出“这个成品不是随便哪个模型做的，而是来自某次本地训练”

### 4. 真实 cover 完成后，补一次“当前主成品”落位

如果本轮真实 cover 进入的是一个新的 track，且当前主成品未指定：

- 请在 `Studio` 中把该真实 cover 设为 `当前主成品`
- 然后返回 `Factory`
- 验证 `Factory` 当前曲目摘要已同步

如果当前 track 上已经有更合理的主成品策略，也可以保持不改，但必须在 report 里解释：

- 为什么没设置
- 当前页面如何呈现

### 5. 增加一份可重复执行的真实闭环验收脚本

请新增一条专门针对本轮目标的验证脚本，建议命名：

- `D:\FeiSharkStudio-v2\frontend\playwright_trained_model_cover_studio_smoke.cjs`

或在你判断更适合时，另补一个后端 verify 脚本。

这条脚本至少要做：

1. 检查 `8000` API 健康状态
2. 解析并锁定本轮优先训练模型
3. 导入一首真实本地歌曲到 `Factory` track 流程
4. 创建真实 cover job
5. 轮询直到：
   - 完成
   - 或失败
   - 或超时
6. 如果完成：
   - 进入 `Studio`
   - 验证成品资源和摘要信息
   - 如可行，设为 `当前主成品`
   - 返回 `Factory` 验证同步
7. 最终输出清晰摘要

脚本输出建议至少包含：

- `STAGE28_TRAINED_MODEL_COVER_SMOKE PASS/FAIL`
- `model_id`
- `source_job_id`
- `track_id`
- `cover_job_id`
- `final_stage`
- `studio_url`

### 6. 测试补齐

至少跑：

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`
- 运行你新增的 Stage 28 真实闭环 smoke / verify

建议补测试：

- API 测试：
  - cover job / track job 能返回模型来源快照
  - studio 所需数据能读到模型来源摘要
- 前端 smoke：
  - 使用训练模型完成真实 cover
  - 进入 Studio
  - 看到来源摘要
  - 回写主成品

## 交付要求

完成后必须输出：

1. 修改了哪些文件
2. cover job 新增了哪些模型来源字段
3. 本轮实际使用的是哪个训练模型
4. 本轮实际使用的是哪首真实歌曲
5. 真实 cover 是否成功，完整跑到了哪一阶段
6. `Factory` 里如何展示这次真实成品
7. `Studio` 里如何展示这次真实成品及模型来源
8. 是否成功设为 `当前主成品`
9. 新增了哪些测试 / smoke / verify
10. 跑了哪些命令，结果是什么
11. 还剩哪些限制
12. 将本轮汇报写入：
   - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-28-trained-model-cover-studio-closure-report.md`

## 验证要求

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`
- 运行你新增的 Stage 28 真实闭环 smoke / verify

如果真实 cover 失败，也必须把 smoke 结果和失败阶段写进 report。

## 完成标准

- 第26阶段真实训练模型至少有一条被真实用于 cover
- 真实 cover 结果能进入 `Factory -> Studio`
- 成品上下文中能看出所用模型及其训练来源
- 至少一条真实成品已被验证可作为 `当前主成品`
- 有一条可重复执行的 Stage 28 闭环验收脚本
