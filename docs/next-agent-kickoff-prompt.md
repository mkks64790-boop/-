# FeiShark Release Factory - Next Agent Kickoff Prompt

你现在是这个项目的主实施 agent。请基于现有代码库，按架构蓝图推进 FeiShark Studio 从“本地 AI 翻唱/训练工作台”升级为“批量歌曲发行工厂”。

## 你的任务目标

请优先实施 `Milestone 1：批量歌曲与歌词工位`，不要跳步去先做 AI MV 或炫酷页面。  
你的工作重点是：把数据模型、流水线抽象、批量导入、歌词抽取、多版本时间轴、版本晋升和基础工作台先做稳。

## 先读这些文件

- `D:\FeiSharkStudio-v2\docs\release-factory-blueprint.md`
- `D:\FeiSharkStudio-v2\backend\main.py`
- `D:\FeiSharkStudio-v2\backend\db.py`
- `D:\FeiSharkStudio-v2\backend\services\job_service.py`
- `D:\FeiSharkStudio-v2\backend\services\asset_service.py`
- `D:\FeiSharkStudio-v2\frontend\js\api.js`
- `D:\FeiSharkStudio-v2\frontend\js\studio.js`
- `D:\FeiSharkStudio-v2\README.md`

## 现状认知

当前项目已经具备：

- `FastAPI` 后端
- `SQLite` 数据库
- 本地任务队列
- `jobs / job_artifacts / job_stage_logs / voice_models / datasets`
- 现有 `Dashboard / Studio`
- 基础 Playwright smoke
- `cover/train` 两类任务链路

你不要推倒重来。  
你要做的是在现有代码上做“可演进增强”。

## 本阶段必须完成的范围

### 1. 数据模型扩展

在 `backend/db.py` 上安全迁移，新增最少这几张表：

- `release_batches`
- `tracks`
- `lyric_documents`
- `lyric_timeline_versions`
- `audit_events`

同时扩展 `jobs` 表，新增以下字段：

- `track_id`
- `job_kind`
- `resource_class`
- `depends_on_json`

要求：

- 迁移必须兼容旧数据
- 不破坏现有 `cover/train`
- 所有新增字段有合理默认值

### 2. 通用流水线抽象

把现有 job 体系往“通用 pipeline step”方向抽象，但不要一次改爆。

本阶段最低要求：

- 保持旧 `cover/train` 可运行
- 支持新增 job kind：
  - `ingest`
  - `lyrics_extract`
  - `lyrics_align`
- 为后续 DAG 编排预留接口

建议新增：

- `backend/pipelines/registry.py`
- `backend/pipelines/runner.py`

### 3. 批量导入 API

新增 API：

- `POST /api/batches`
- `GET /api/batches`
- `GET /api/batches/{batch_id}`
- `POST /api/batches/{batch_id}/tracks/import`
- `GET /api/tracks/{track_id}`
- `PATCH /api/tracks/{track_id}`

要求：

- 支持一次导入多首歌曲
- 支持基础元数据：
  - 标题
  - 艺人
  - 来源类型
  - 备注
- 文件安全落盘到 `shared_data/batches/{batch_id}/tracks/{track_id}/source/`

### 4. 歌词工位后端

新增 API：

- `POST /api/tracks/{track_id}/lyrics/extract`
- `POST /api/tracks/{track_id}/lyrics/align`
- `GET /api/tracks/{track_id}/lyrics/versions`
- `POST /api/tracks/{track_id}/lyrics/{timeline_id}/promote`

要求：

- 可基于音频生成原始歌词文本
- 可基于歌词文本生成时间轴版本
- 输出至少：
  - `txt`
  - `lrc`
  - `srt`
  - `ass`
- 支持多版本并存
- 支持将某个版本晋升为“当前发行版”

### 5. 基础前端工作台

不要一开始大改全站。  
新增一个轻量入口即可，建议：

- `frontend/factory.html`
- `frontend/js/factory/`

本阶段前端最低要有：

- 批次列表
- 批次详情
- track 列表
- 单首歌歌词版本列表
- “抽取歌词”
- “生成时间轴”
- “晋升当前版本”

### 6. 审计记录

至少为以下动作写入 `audit_events`：

- 创建 batch
- 导入 track
- 抽取歌词
- 生成时间轴版本
- 晋升歌词版本

## 本阶段不要做

- 不要先做 AI 封面生成
- 不要先做 AI MV 场景生成
- 不要先做复杂在线母带 UI
- 不要引入 Redis / Celery / WebSocket
- 不要全量重写前端框架
- 不要破坏现有 `self_check.py`

## 代码组织要求

请尽量按这个结构新增代码：

```text
backend/
  api/routes/
    batches.py
    tracks.py
    lyrics.py
  services/
    batch_service.py
    track_service.py
    lyric_service.py
    audit_service.py
  pipelines/
    registry.py
    runner.py
frontend/
  factory.html
  js/factory/
    main.js
    batches.js
    lyrics.js
```

如果你选择别的结构，也必须保持清晰分层，不要把大量业务逻辑继续堆进 `main.py`。

## 测试要求

你必须补测试，不能只靠手点。

至少补这些测试：

- `tests/unit/test_batch_service.py`
- `tests/unit/test_lyric_service.py`
- `tests/api/test_batches_api.py`
- `tests/api/test_lyrics_api.py`

如果项目里还没有统一测试目录，请你顺手建立合理结构。

同时：

- 保证现有 `python -X utf8 backend/self_check.py` 仍通过
- 如可行，新增一个最小 Playwright smoke 覆盖 `factory.html`

## 建议实施顺序

请按这个顺序工作：

1. 读蓝图和现有后端核心文件
2. 设计并实现数据库迁移
3. 抽象批次与 track 服务
4. 新增批量导入 API
5. 抽象歌词服务
6. 接入歌词抽取与多版本时间轴
7. 新增前端工位
8. 补单元测试和 API 测试
9. 跑自检和回归验证

## 交付要求

完成后请输出：

1. 你做了哪些模块
2. 新增了哪些 API
3. 做了哪些数据库迁移
4. 跑了哪些测试，结果如何
5. 当前已知风险或下一阶段建议

## 质量红线

- 不要删改用户已有数据
- 不要破坏旧 `cover/train` 任务链
- 不要用破坏性 git 命令
- 不要跳过测试
- 不要只交付半套接口不验证

## 完成标准

只有当以下都成立时，这个阶段才算完成：

- 可以创建 batch
- 可以批量导入多首 track
- 可以对某首 track 执行歌词抽取
- 可以生成多个歌词时间轴版本
- 可以晋升某个歌词版本为当前版本
- 前端可完成基础操作
- 现有自检不被破坏
- 新测试可以运行

现在开始工作。先阅读蓝图和核心文件，然后给出一个简洁计划，再直接动手实现。

