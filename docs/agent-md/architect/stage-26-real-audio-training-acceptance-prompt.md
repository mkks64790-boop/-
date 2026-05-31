# 第26阶段：真实干声训练验收 + 短素材分流收口

你现在是 FeiShark Studio 的工作 agent。

第25阶段已经独立验收通过，当前项目已经具备：

- `Dashboard / Factory / Studio` 三个页面分区
- `Factory -> Studio` 成品上下文联动
- `当前试听 / 最新版本 / 当前主成品` 的区分
- 本地 RVC 引擎在线，后端健康检查正常

但现在还差一件非常关键的事情：

不是继续堆 UI，而是拿用户桌面的真实干声素材，把“训练入口到底能不能按照原始大纲正确分流并执行”这件事彻底验掉。

这次请严格围绕下面两份真实样本做开发与验收：

- `C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3`
  - 已确认：`2709.995s`，约 `45分10秒`
  - `mp3 / 44.1kHz / stereo / 320kbps`
  - 这份样本符合最初大纲里“30-50 分钟单文件快速训练”的目标素材
- `C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3`
  - 已确认：`932.702s`，约 `15分33秒`
  - `mp3 / 44.1kHz / stereo / 320kbps`
  - 这份样本不符合“30-50 分钟单文件快速训练”的目标素材

本阶段要做的核心，不是训练质量优化，也不是新页面，而是：

1. 让系统真正识别“单文件快速训练”和“短素材/不合规长短”的区别
2. 让真实长干声样本能从当前网页入口进入训练任务链，至少跑到可验证的真实阶段
3. 让短样本不会被误判成合规长干声，然后悄悄跑错流程
4. 把失败原因、下一步建议、实际素材判定结果，明确暴露给前端和验收脚本

## 必读文件

- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\model_trainer.py`
- `D:\FeiSharkStudio-v2\backend\self_check.py`
- `D:\FeiSharkStudio-v2\backend\services\dataset_service.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\backend\services\preflight_service.py`
- `D:\FeiSharkStudio-v2\backend\strategies\strategy_registry.py`
- `D:\FeiSharkStudio-v2\frontend\index.html`
- `D:\FeiSharkStudio-v2\frontend\js\train.js`
- `D:\FeiSharkStudio-v2\frontend\js\diagnostics.js`
- `D:\FeiSharkStudio-v2\frontend\js\jobs.js`
- `D:\FeiSharkStudio-v2\feishark-launcher.ps1`
- `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-25-track-master-registry-report.md`

## 实施范围

### 允许修改

- 训练入口相关后端校验与返回结构
- 音频素材元数据识别与训练路由判定
- Dashboard 中训练入口的提示文案、状态反馈、失败可读性
- 真实验收脚本 / 辅助脚本 / smoke / pytest
- 本阶段 architect / worker / handoff 文档

### 禁止事项

- 不要重写 RVC 执行层
- 不要引入 Redis / WebSocket / Celery
- 不要新开一套训练页面
- 不要把这轮做成“大而化之的 UI 美化”
- 不要伪造“真实训练已成功”结论
- 如果真实训练没跑通，必须报告真实停止阶段和失败原因

## 具体任务

### 1. 给单文件训练补上“真实素材画像”判定

当前 `/api/train` 只按 `file_count` 决定：

- 1 个文件 -> `single_long_preprocess`
- 多个文件 -> `multi_clean_direct`

这个逻辑不够，必须补上素材画像判断，至少识别：

- `duration_seconds`
- `sample_rate`
- `channels`
- `codec/container`
- 是否命中“30-50 分钟单文件快速训练”窗口

建议新增一个轻量素材判定层，单文件至少要产出类似语义：

- `material_profile`
- `duration_seconds`
- `duration_label`
- `recommended_route`
- `single_long_eligible`
- `reason`
- `next_step`

最低要求：

- 当用户上传单文件且时长在 `1800s ~ 3000s` 之间时，才允许把它视为合规的 `single_long_preprocess` 候选
- 当单文件明显短于 `1800s` 时，不能再静默当成“单文件快速训练”合规素材
- 这种短素材要么被明确拒绝进入单文件长干声链路，要么被明确提示“请改走多文件精训”

不要只在前端做提示，后端必须具备真实约束。

### 2. 让训练接口返回可读的“为什么能跑 / 为什么不能跑”

当前 `TrainResponse` 太薄，用户无法知道：

- 当前样本被识别成什么类型
- 为什么被允许或不允许进入该训练链
- 如果不符合，下一步到底应该怎么做

请扩展训练创建返回值和失败返回值，至少让前端能拿到：

- 本次素材画像
- 路由判定结果
- 是否合规
- 失败原因
- 建议动作

如果你需要：

- 可以扩展 `TrainResponse`
- 可以为 `422` 或 `400` 返回结构补上更强的 detail
- 可以在 job / stage log 中记录素材画像判定

但要求是：最终用户在网页里能读懂，而不是只能看控制台。

### 3. 改造 Dashboard 训练区，让它在提交前就说人话

当前 `frontend/js/train.js` 只显示笼统的 preflight 结果，这不够。

请让训练区在用户选中文件后，明确告诉他：

- 当前文件的时长与基础元数据
- 是否符合“单文件快速训练”的素材要求
- 如果不符合，应该去哪里
- 当前选择会进入哪条策略链

对这两份真实样本，前端至少要表现出下面这种级别的区分：

- `朱朱干声唱.mp3`
  - 明确显示：符合单文件快速训练窗口
  - 会进入 `single_long_preprocess`
- `朱朱干声.mp3`
  - 明确显示：只有约 15 分钟，不符合 30-50 分钟单文件长干声标准
  - 给出下一步建议：改用多文件精训素材，或准备更长单干声

注意：

- 这里不是只改静态文案
- 必须和后端真实判定一致，不能前后端各说各话

### 4. 用真实样本做一次“真训练链”验收

必须使用下面这份真实样本进行实际训练验收：

- `C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3`

要求：

- 通过当前项目的真实入口提交训练任务
- 不是 mock，不是 smoke 假任务
- 真实进入当前训练链
- 至少能明确记录它实际跑到了哪个阶段

理想结果：

- 成功经过：`train_upload -> train_preflight -> single_long_preprocess -> feature/pitch -> train_core -> index_build -> register_model`

如果受运行时间、RVC 环境、GPU 资源等限制，没能完整跑完，也可以接受，但前提是：

- 不能假装成功
- 必须精确汇报它卡在哪一阶段
- 必须附上错误信息和当前可见证据

### 5. 用短样本做一次“错误分流”验收

必须使用下面这份真实样本进行分流或失败提示验收：

- `C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3`

预期目标不是训练成功，而是行为正确：

- 不能被悄悄当成合规长干声直接塞进 `single_long_preprocess`
- 用户必须能在提交前或提交时明确看到“不合规”的原因
- 必须给出下一步建议

这轮如果你愿意，也可以让它被显式拒绝创建单文件训练任务；这比“错误地继续跑”更对。

### 6. 增加一个可重复执行的真实验收脚本

请新增一份真正能帮助架构师和用户反复验收的脚本，建议名字类似：

- `D:\FeiSharkStudio-v2\backend\verify_stage26_real_audio_training.py`
  或
- `D:\FeiSharkStudio-v2\scripts\verify_stage26_real_audio_training.ps1`

要求：

- 自动检查 `/api/health`
- 自动检查训练 preflight
- 自动读取这两份桌面样本的素材信息
- 自动验证：
  - 长样本是否被识别为 `single_long_eligible`
  - 短样本是否被识别为不合规单文件长干声
- 如可行，自动发起长样本训练任务并轮询阶段
- 最终打印一个清晰摘要，而不是散乱日志

### 7. 测试补齐

至少补齐以下验证：

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`

并新增与本阶段直接对应的测试，至少包含其中一部分：

- 训练素材画像 / 时长分流的单测或 API 测试
- 单文件长样本命中 `single_long_preprocess`
- 单文件短样本被拒绝或给出明确分流建议
- 如可行，增加一个轻量前端 smoke，验证训练面板能正确显示两类样本的不同提示

## 交付要求

完成后必须输出：

1. 修改了哪些文件
2. 增加了哪些素材画像 / 路由判定字段
3. `朱朱干声唱.mp3` 被如何识别，是否真正进入训练链，实际跑到哪一阶段
4. `朱朱干声.mp3` 被如何识别，系统如何阻止误走单文件长干声链
5. 前端训练区具体变成了什么反馈
6. 新增了哪些脚本 / 测试
7. 跑了哪些验证命令，结果是什么
8. 还剩哪些已知限制
9. 将本轮汇报写入：
   - `D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-26-real-audio-training-acceptance-report.md`

## 验证要求

- `python -m pytest -q`
- `python -X utf8 backend/self_check.py`
- 运行你新增的 Stage 26 真实验收脚本

如果你额外补了前端 smoke，也要实际跑一遍，并把结果写进 report。

## 完成标准

- 单文件训练不再只靠 `file_count` 粗暴分流
- 系统能识别“合规长干声单文件”和“过短单文件”的区别
- 前端训练区能把这件事说清楚
- `朱朱干声唱.mp3` 至少被真实送入训练链并能汇报真实阶段
- `朱朱干声.mp3` 不会再误走单文件长干声训练主链
- 架构师和用户可以通过新增脚本重复验收这轮结果
