# Stage 50 架构师记忆快照 - 2026-06-03

项目根目录：

```text
D:\FeiSharkStudio-v2
```

## 当前产品定位

FeiShark Studio 是本地 AI 音乐/RVC 工作站，目标不是复制别人的商业软件，而是围绕本地 RVC/UVR/ffmpeg 流程做：

```text
训练专属音色 -> 原唱/录音分离 -> RVC 变声 -> 混音输出 -> Studio A/B 试听 -> Factory 候选成品管理
```

当前优先级不是继续盲目堆功能，而是把已跑通的真实闭环变成用户能看懂、能决策的产品流程。

## 当前真实闭环

Stage47/49 已经形成一条真实 smoke 链路：

```text
训练 job：train_7f4d6b4e611e
模型：v_d4d7e1c1 / 朱朱_stage47_single_long
cover job：task_b2272d133fff
artifact：art_f99f7e4afb10
最终音频：final_master.wav
```

Stage49 已增加 Studio A/B 试听验收：

```text
GET   /api/jobs/{job_id}/source-audio/download
GET   /api/jobs/{job_id}/artifacts/{artifact_id}/review
PATCH /api/jobs/{job_id}/artifacts/{artifact_id}/review
```

review 存储在：

```text
job_artifacts.metadata_json.listening_review
```

Stage49 browser smoke 写入过一条非人工验收备注：

```text
stage49 browser smoke only - not a human quality verdict
```

这只能证明持久化成功，不能当成人工质量结论。

## 最近验证状态

已通过：

```text
python -m backend.self_check -> SELF_CHECK_SUMMARY PASS
python -m pytest tests\api\test_stage49_listening_review_api.py tests\api\test_track_studio_versions_api.py -q -> 9 passed
```

不要轻易重启真实训练、UVR、RVC 或大音频任务，除非用户明确批准。

## Stage50 目标

Stage50 要把 Stage49 的“能保存试听验收”升级为“验收结果驱动下一步路由”：

```text
unreviewed        -> needs_human_review
needs_work        -> route_to_rework
usable            -> route_to_candidate_pool
release_candidate -> route_to_release_candidate
rejected          -> route_to_archive_or_rerun
```

后端要提供稳定 review summary 和 `/api/reviews/artifacts`。

前端要在 Dashboard / Factory / Studio 显示：

```text
哪些成品未验收
哪些需要返工
哪些可以当候选成品
保存验收后下一步该去哪里
```

同时继续主屏减负：长日志、长路径、模型列表、批次列表、技术详情默认折叠。

## 当前 Stage50 指令文件

```text
D:\FeiSharkStudio-v2\docs\agent-md\handoff\stage-50-review-driven-routing-plan.md
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-50a-review-routing-backend-prompt.md
D:\FeiSharkStudio-v2\docs\agent-md\architect\stage-50b-review-routing-product-prompt.md
```

## sub-agent 状态

架构师曾启动两个内部 sub-agent：

```text
地基 sub-agent：Gibbs / 019e88ea-753e-75a1-b469-e3b8040f0542
产品 sub-agent：Descartes / 019e88ea-75f9-7663-92be-3a1e7ca61cb3
```

它们均因中转站额度不足失败，不是代码失败：

```text
403 Forbidden
订阅总额度不足: subscription quota insufficient
url: https://ergouzi.life/v1/responses
```

因此 Stage50 需要架构师主线程接管实现。

## 当前工作规则

```text
不回滚用户或历史 agent 改动。
不删除既有阶段报告。
不启动真实训练/RVC/UVR/cover。
先做可验收的小闭环，再继续大功能。
所有新增 worker/architect 文档必须 UTF-8 中文正常显示。
```

