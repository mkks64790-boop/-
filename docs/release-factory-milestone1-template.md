# Release Factory / Milestone 1 需求模板

基于当前 FeiShark Studio 现状：
- FastAPI + SQLite
- 本地任务队列与 `jobs` 编排
- 已有 `Dashboard / Studio`
- 已稳定 `cover / train` 主链路

本阶段只做最小增量：批量导入 + 歌词工位。

## 1. 目标与非目标

### 目标
- 建立批次（batch）与曲目（track）的基础数据层。
- 支持一次导入多首歌曲，生成可追踪的曲目记录。
- 提供歌词文档与歌词时间轴版本管理。
- 保留审计事件，方便回溯导入、抽取、对齐与晋级动作。
- 增加最轻量的 `factory` 入口页，承接批量导入与歌词工位。
- 不破坏现有 `Dashboard / Studio / cover / train`。

### 非目标
- 不做 AI MV。
- 不引入 Redis / Celery / WebSocket。
- 不重写现有 Dashboard / Studio。
- 不做分布式 worker。
- 不替换现有 SQLite 与本地队列。

## 2. 业务范围

### 包含
- 批量导入多首曲目。
- 曲目基础信息维护。
- 歌词文档创建、对齐与版本晋级。
- 以批次为单位查看曲目列表与处理结果。
- 基础审计追踪。

### 暂不包含
- 封面生成。
- MV 生成。
- 完整 DAW 编辑。
- 云端协作。

## 3. 数据模型增量

### 新表
- `release_batches`
- `tracks`
- `lyric_documents`
- `lyric_timeline_versions`
- `audit_events`

### `jobs` 扩展字段
- `track_id`
- `job_kind`
- `resource_class`
- `depends_on_json`

### 设计原则
- 兼容旧数据。
- 所有新增字段必须给默认值。
- 旧的 `cover/train` 记录继续可读。

## 4. API 列表

### 批次
- `POST /api/batches`
- `GET /api/batches`
- `GET /api/batches/{batch_id}`

### 曲目
- `POST /api/batches/{batch_id}/tracks/import`
- `GET /api/batches/{batch_id}/tracks`
- `GET /api/tracks/{track_id}`
- `PATCH /api/tracks/{track_id}`

### 歌词
- `POST /api/tracks/{track_id}/lyrics/extract`
- `POST /api/tracks/{track_id}/lyrics/align`
- `GET /api/tracks/{track_id}/lyrics/versions`
- `POST /api/tracks/{track_id}/lyrics/{timeline_id}/promote`

### 可选补充
- `GET /api/factory/summary`

## 5. 前端入口与页面结构

### 新入口页
- `frontend/factory.html`

### 页面骨架
- 批次列表
- 批次详情
- 曲目列表
- 歌词工位
- 版本列表
- 审计摘要

### 交互原则
- 先看批次，再看曲目，再看歌词。
- 默认只展示必要信息。
- 技术字段默认折叠。

## 6. 测试清单

### 单元测试
- `tests/unit/test_batch_service.py`
- `tests/unit/test_track_service.py`
- `tests/unit/test_lyric_service.py`

### API 测试
- `tests/api/test_batches_api.py`
- `tests/api/test_tracks_api.py`
- `tests/api/test_lyrics_api.py`

### 回归
- `python -X utf8 backend/self_check.py`
- 现有 `smoke` 与 `verify` 继续通过

## 7. 验收标准

- 可以创建 batch。
- 可以一次导入多首 track。
- 可以查看单个 track 详情。
- 可以创建歌词文档。
- 可以生成歌词时间轴版本。
- 可以晋级当前歌词版本。
- `cover/train` 不回退。
- `self_check.py` 继续 PASS。

## 8. 风险与红线

### 风险
- 旧数据兼容迁移遗漏。
- 路径落盘规则不一致。
- 歌词工位过早引入复杂流程。

### 红线
- 不碰 AI MV。
- 不引入新中间件。
- 不破坏现有 `Dashboard / Studio`。
- 不只写接口不验收。

