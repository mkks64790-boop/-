# FeiShark Release Factory 总体策划蓝图

适用对象：小型 AI 音乐工作室、本地优先生产环境、单机起步但可演进到多机协作。  
基于现状：复用现有 `FastAPI + SQLite + 本地任务队列 + Frontend 工作台`，避免推倒重来。  
目标：把“单首歌手工整理”为“批量歌曲流水线式发行工厂”。

---

## 0. 执行摘要

你要的不是一个“又多一个页面”，而是一条完整的内容生产线：

1. 批量导入多首歌曲与元数据。
2. 自动抽取歌词并生成多版本时间轴。
3. 调用 AI 生成封面和 MV 素材。
4. 提供歌词时间轴优化、人工复核、母带优化、导出发行包。
5. 输出平台发布文案、AIGC 声明、短标题、封面卡片、MV、LRC、SRT、WAV、MP3、说明文件。
6. 全程保留任务状态、产物版本、审计记录，支持失败重试与二次编辑。

核心判断：

- `v1` 不建议先上分布式大架构。
- `v1` 应该继续沿用现有 FeiShark 的单机本地优先模式，把任务系统抽象成“通用流水线引擎”。
- 先把“批量歌曲发行工厂”跑通，再考虑多人协作、远程渲染、云端 provider。

---

## 1. 需求分析与概念建模

### 1.1 产品目标

- 批量管理歌曲，从“输入素材”到“发行包导出”一站式完成。
- 降低重复劳动，把歌词、封面、MV、母带、包装全部串起来。
- 把“可发”变成“可批量复用、可审计、可回滚、可模板化”。

### 1.2 目标用户

- 制作人：导入歌曲、设定风格、审批成品。
- 内容运营：编辑短标题、描述、AIGC 声明、平台文案。
- 后期工程师：调整歌词时间轴、母带参数、MV 模板。
- 复核人员：检查时轴、封面、导出包、平台发布素材。

### 1.3 v1 关键业务能力

- 批量导入：
  - 支持单次导入多首 `wav/mp3/flac`
  - 支持 CSV/Excel 元数据导入
  - 支持从现有 FeiShark 成品或外部音频导入
- 歌词工位：
  - ASR 抽词
  - 原词文本校对
  - 多策略对齐
  - LRC/SRT/ASS 多版本预览与切换
- 封面工位：
  - AI 生成多张候选图
  - 模板裁切为平台封面比例
  - 支持“静态封面”与“卡片封面”
- MV 工位：
  - 歌词字幕 MV
  - 封面动画 MV
  - AI 画面 + 歌词字幕 MV
  - 多模板切换
- 母带工位：
  - 在线参数调节
  - 智能预设
  - A/B 对比试听
  - Loudness / True Peak 可视化
- 发行工位：
  - 一键输出发行包
  - 生成说明文档、宣传文案、平台描述、短标题、AIGC 声明
  - 批量导出 ZIP

### 1.4 v1 不做

- 不做多人实时协同编辑。
- 不做复杂 DAW 级别时间线编辑。
- 不做云端多租户 SaaS。
- 不做完整数字发行商对接。

### 1.5 核心领域模型

建议在现有 `jobs / job_artifacts / datasets / voice_models` 之上增加以下业务对象：

| 对象 | 作用 | 关键字段 |
|---|---|---|
| `release_batches` | 一次批量发行任务 | `batch_id`, `batch_name`, `status`, `target_platforms`, `output_root` |
| `tracks` | 单首歌业务实体 | `track_id`, `batch_id`, `title`, `artist`, `source_type`, `status` |
| `track_versions` | 同一首歌的可回滚版本 | `version_id`, `track_id`, `kind`, `is_current`, `notes` |
| `lyric_documents` | 纯歌词文本与结构化段落 | `lyric_id`, `track_id`, `source`, `text`, `structure_json` |
| `lyric_timeline_versions` | 对齐结果版本 | `timeline_id`, `track_id`, `engine`, `qa_score`, `lrc_path`, `srt_path`, `ass_path` |
| `visual_projects` | 封面或 MV 的工程定义 | `visual_id`, `track_id`, `type`, `template_key`, `prompt_json`, `status` |
| `mastering_projects` | 母带工程与参数版本 | `master_id`, `track_id`, `preset_key`, `params_json`, `metrics_json` |
| `package_exports` | 导出发行包记录 | `export_id`, `track_id`, `batch_id`, `manifest_json`, `zip_path` |
| `publish_profiles` | 平台发布模板 | `profile_id`, `platform`, `title_template`, `description_template`, `disclosure_template` |
| `audit_events` | 合规和操作审计 | `event_id`, `entity_type`, `entity_id`, `action`, `detail_json` |

### 1.6 任务抽象

现有 `jobs` 继续保留，但要从“cover/train 两类任务”提升为“通用流水线步骤”：

- `job_kind`
  - `ingest`
  - `lyrics_extract`
  - `lyrics_align`
  - `artwork_generate`
  - `mv_generate`
  - `mastering_render`
  - `package_build`
  - `publish_copy_render`
  - `cover`
  - `train`
- `resource_class`
  - `gpu_heavy`
  - `cpu_heavy`
  - `io_heavy`
  - `network_bound`
- `depends_on_json`
  - 前置步骤依赖
- `track_id`
  - 将作业绑定到具体歌曲

这一步是全局关键。只有把 `job` 泛化，后面所有批处理、重试、编排、监控才会稳。

---

## 2. 架构设计与接口契约

### 2.1 总体架构

建议采用“单体应用 + 模块化流水线 + 可插拔 provider”的目标架构：

```text
Frontend Workbench
  ├─ Batch Dashboard
  ├─ Lyrics Lab
  ├─ Artwork Studio
  ├─ MV Studio
  ├─ Mastering Desk
  └─ Packaging Center

FastAPI Backend
  ├─ API Layer
  ├─ Domain Services
  ├─ Pipeline Orchestrator
  ├─ Provider Adapters
  ├─ Packaging Service
  └─ Audit & Metrics

Worker Runtime
  ├─ CPU Queue
  ├─ GPU Queue
  ├─ Media Tools (ffmpeg / whisper / imagemagick 等)
  └─ AI Provider Clients

Storage
  ├─ SQLite v1
  ├─ Local Filesystem
  └─ Optional Object Storage v2
```

### 2.2 与现有项目的衔接策略

直接复用：

- `backend/main.py`
- `backend/db.py`
- `backend/services/job_service.py`
- `backend/services/asset_service.py`
- `backend/services/preflight_service.py`
- 现有 `job_artifacts` 与 `job_stage_logs`

新增但不破坏旧功能：

- `/factory` 新页面或新入口
- 新增 `release_batches`、`tracks`、`lyric_*`、`mastering_*` 表
- 新增 `pipelines/`、`providers/`、`domain/` 模块
- 保留现有 `Dashboard / Studio`

### 2.3 代码分层建议

```text
backend/
  api/
    routes/
      batches.py
      tracks.py
      lyrics.py
      visuals.py
      mastering.py
      packages.py
      publish.py
  domain/
    models/
    schemas/
    enums.py
  services/
    batch_service.py
    track_service.py
    lyric_service.py
    mastering_service.py
    packaging_service.py
    publish_service.py
  pipelines/
    registry.py
    runner.py
    step_types/
      lyrics_extract.py
      lyrics_align.py
      artwork_generate.py
      mv_generate.py
      mastering_render.py
      package_build.py
  providers/
    asr/
    image/
    video/
    mastering/
  tests/
    unit/
    api/
    integration/
    fixtures/
```

### 2.4 前端架构建议

不建议第一阶段立刻整体迁移到 React。  
建议采用“两阶段前端演进”：

- `Phase A`
  - 继续用当前 `HTML + CSS + JS module`
  - 新增 `factory.html`
  - 新增 `frontend/js/factory/` 模块
- `Phase B`
  - 如果批量工作台复杂度明显上升，再评估迁移到 `React + TypeScript + Vite`

原因：

- 当前项目已经有稳定的静态前端与 Playwright smoke。
- 先跑通业务，再迁移前端技术栈，风险更低。

### 2.5 目录与文件落盘规范

```text
shared_data/
  batches/
    {batch_id}/
      manifest.json
      tracks/
        {track_id}/
          source/
          lyrics/
          visuals/
          mastering/
          package/
          publish/
  jobs/
    {job_id}/
      artifacts/
      logs/
```

原则：

- 业务目录按 `batch/track` 组织。
- 运行目录按 `job` 组织。
- 任一导出文件都能从数据库反查到 `track -> batch -> job -> artifact`。

### 2.6 Provider 抽象

所有 AI 能力必须走 provider adapter，不允许控制器里直接拼第三方请求。

统一接口：

- `ASRProvider`
  - `transcribe(audio_path, language, mode) -> segments`
- `ImageProvider`
  - `generate_cover(prompt, style_preset, size, count) -> images`
- `VideoProvider`
  - `generate_mv(script, images, lyrics_timeline, template) -> video`
- `MasteringProvider`
  - `analyze(audio) -> metrics`
  - `render(audio, preset, params) -> mastered_audio`

这样做的好处：

- 能本地跑，也能切第三方云 provider。
- 方便 mock 测试。
- 方便记录 prompt、模型版本、耗时、成本。

### 2.7 流水线编排

推荐把每首歌的发行流水线定义为 DAG：

```text
ingest
  -> lyrics_extract
  -> lyrics_align
  -> artwork_generate
  -> mv_generate
  -> mastering_render
  -> package_build
  -> publish_copy_render
```

可选分支：

- `artwork_generate` 可跳过，直接用上传封面。
- `mv_generate` 可选择：
  - `lyric_mv`
  - `cover_motion_mv`
  - `ai_scene_mv`
- `mastering_render` 可选择：
  - `safe`
  - `streaming`
  - `vocal_forward`
  - `warm_ballad`

### 2.8 REST API 契约

建议保留 REST 风格，先不引入 WebSocket。  
前端继续轮询，后续如有需要再加 SSE。

#### 批次与歌曲

- `POST /api/batches`
- `GET /api/batches`
- `GET /api/batches/{batch_id}`
- `POST /api/batches/{batch_id}/tracks/import`
- `GET /api/tracks/{track_id}`
- `PATCH /api/tracks/{track_id}`

#### 歌词

- `POST /api/tracks/{track_id}/lyrics/extract`
- `POST /api/tracks/{track_id}/lyrics/align`
- `GET /api/tracks/{track_id}/lyrics/versions`
- `POST /api/tracks/{track_id}/lyrics/{timeline_id}/promote`

`lyrics/align` 请求示例：

```json
{
  "lyric_text": "完整歌词文本",
  "engine": "whisper_medium",
  "align_mode": "strict_lyric_match",
  "line_split_mode": "balanced",
  "append_outro_card": true
}
```

#### 封面与 MV

- `POST /api/tracks/{track_id}/artwork/generate`
- `GET /api/tracks/{track_id}/artwork/variants`
- `POST /api/tracks/{track_id}/artwork/{variant_id}/promote`
- `POST /api/tracks/{track_id}/mv/render`
- `GET /api/tracks/{track_id}/mv/versions`

#### 母带

- `POST /api/tracks/{track_id}/mastering/analyze`
- `POST /api/tracks/{track_id}/mastering/render`
- `GET /api/tracks/{track_id}/mastering/versions`
- `POST /api/tracks/{track_id}/mastering/{master_id}/promote`

`mastering/render` 请求示例：

```json
{
  "preset_key": "warm_ballad",
  "target_lufs": -11.5,
  "true_peak_dbtp": -1.0,
  "params": {
    "presence": 1.2,
    "warmth": 0.8,
    "stereo_width": 0.1
  }
}
```

#### 发行包与发布文案

- `POST /api/tracks/{track_id}/package/build`
- `POST /api/batches/{batch_id}/package/build`
- `GET /api/packages/{export_id}`
- `POST /api/tracks/{track_id}/publish/render-copy`
- `GET /api/publish/profiles`

### 2.9 状态模型

统一状态：

- `pending`
- `queued`
- `running`
- `review_required`
- `completed`
- `failed`
- `cancelled`

统一响应字段：

- `entity_id`
- `status`
- `current_stage`
- `progress_percent`
- `warnings`
- `artifacts`
- `updated_at`

### 2.10 合规与审计

必须从第一期就做：

- 记录每个 AI 产物的：
  - provider
  - model/version
  - prompt
  - 生成时间
  - 账号计划信息
  - 输入素材 hash
- 为平台发布生成：
  - AIGC 声明文案
  - 短标题候选
  - 描述候选
  - 话题候选
- 记录操作日志：
  - 谁导入
  - 谁改了歌词
  - 谁选了第几版封面
  - 谁确认导出

---

## 3. 本地编码与单元测试驱动

### 3.1 开发顺序

按以下顺序推进，收益最高：

1. 数据模型扩展
2. 批次与歌曲导入
3. 歌词抽取与多版本时间轴
4. 母带分析与渲染
5. 封面与 MV provider 抽象
6. 发行包导出
7. 发布文案与 AIGC 声明
8. 批量工作台 UI

### 3.2 TDD 策略

先写测试，再写实现，尤其是以下部分：

- 歌词对齐规则
- 导出包 manifest 正确性
- 状态机流转
- job 依赖关系
- 平台文案模板渲染
- 母带指标计算

### 3.3 测试分层

- 单元测试
  - 对齐算法
  - prompt builder
  - package manifest builder
  - 状态转换器
- API 测试
  - FastAPI route contract
  - 错误处理
  - 参数校验
- 集成测试
  - 从歌曲导入到 ZIP 导出
  - 失败重试
  - 版本晋升
- 冒烟测试
  - Playwright 跑关键页面

### 3.4 样例测试清单

- `test_batch_create_and_import_tracks.py`
- `test_lyrics_alignment_promote_latest.py`
- `test_mastering_metrics_and_promotion.py`
- `test_package_build_manifest_contains_all_assets.py`
- `test_publish_profile_renders_wechat_video_copy.py`
- `test_pipeline_retry_keeps_previous_artifacts.py`

### 3.5 质量门槛

- 新增路由必须有 API 测试。
- 新增 pipeline step 必须有单元测试。
- 导出 ZIP 逻辑必须有 golden file 测试。
- 不允许只靠手点页面验证核心逻辑。

---

## 4. 代码评审与分支合并

### 4.1 分支策略

- `main`
  - 始终可运行
- `feature/release-factory-*`
  - 单个能力开发
- `release/*`
  - 合并前稳定期

### 4.2 PR 颗粒度

每个 PR 只做一类事：

- 一个数据迁移
- 一组 API
- 一个 pipeline step
- 一个前端子页面

不要把“数据库迁移 + UI 重构 + provider 接入 + 导出修复”塞进同一个 PR。

### 4.3 PR 检查清单

- 是否破坏现有 `cover/train` 主链
- 是否新增数据库迁移
- 是否补了自测与自动化测试
- 是否保留失败重试
- 是否保留产物可追溯
- 是否写清回滚方案

### 4.4 评审重点

优先看：

- 状态机是否会卡死
- 文件落盘路径是否稳定
- 重试是否幂等
- 产物是否重复注册
- provider 异常是否可恢复
- UI 是否支持批量场景

---

## 5. 持续集成与自动化集成测试

### 5.1 CI 分层

建议三条工作流：

- `ci-fast`
  - Python 语法检查
  - 单元测试
  - API contract test
- `ci-ui`
  - 前端静态检查
  - Playwright 冒烟
- `ci-media-integration`
  - 使用样例音频跑歌词、母带、导出链路

### 5.2 运行环境建议

- `Ubuntu runner`
  - 纯 Python 单测
  - 前端测试
- `Windows runner`
  - 路径兼容
  - ffmpeg 集成
  - 打包流程
- `Self-hosted Windows GPU runner`
  - 夜间或手动触发完整 AI 集成验证

### 5.3 必须自动化的场景

- 批量导入 3 首歌
- 每首歌生成 2 个歌词版本
- 选择其中 1 个版本晋升
- 执行母带渲染
- 生成 MV
- 打包成 ZIP
- 校验 ZIP 内文件齐全

### 5.4 失败阻断规则

- API contract 失败，禁止合并。
- job 状态机测试失败，禁止合并。
- ZIP manifest 校验失败，禁止合并。
- Playwright 主流程失败，禁止合并到 `main`。

---

## 6. 部署、监控与日志审计

### 6.1 部署形态

`v1` 推荐：

- Windows 本地部署
- FastAPI 单进程
- 本地 SQLite
- 本地文件系统
- ffmpeg / whisper / provider client 就地运行

`v2` 可选：

- Docker Compose
- PostgreSQL
- MinIO
- 独立 worker 进程

### 6.2 监控指标

最低限度要有：

- 每类 job 数量
- 每类 job 成功率
- 平均耗时
- GPU 队列长度
- 导出失败率
- provider 调用失败率

### 6.3 日志规范

所有服务输出结构化日志：

- `event`
- `job_id`
- `track_id`
- `batch_id`
- `stage`
- `status`
- `duration_ms`
- `provider`
- `artifact_path`

### 6.4 审计重点

- 每次歌词晋升
- 每次母带参数变更
- 每次封面晋升
- 每次发行包导出
- 每次平台文案生成

### 6.5 告警建议

- 某 step 连续失败超过阈值
- GPU 队列积压过久
- package_build 失败率异常
- provider API 超时异常
- 单批次产物缺失

---

## 7. 实施路线图

### Milestone 1：批量歌曲与歌词工位

交付：

- `release_batches` / `tracks` 表
- 批量导入页面
- 歌词抽取与多版本对齐
- LRC/SRT/ASS 晋升机制

完成标准：

- 可一次性导入至少 10 首歌
- 每首歌可生成至少 2 个歌词时间轴版本
- 可选中某一版本作为发行版本

### Milestone 2：母带工位与发行包

交付：

- 母带分析与渲染接口
- 母带预设库
- 批量导出发行包
- manifest 与说明文件

完成标准：

- 可对多首歌批量生成发行版 WAV/MP3
- 导出 ZIP 包含音频、歌词、说明、封面

### Milestone 3：封面与 MV 工位

交付：

- Image provider adapter
- Video provider adapter
- 封面候选与晋升
- 歌词 MV 渲染模板

完成标准：

- 每首歌至少支持 3 张封面候选
- 每首歌至少支持 2 种 MV 模板

### Milestone 4：发布工位与合规审计

交付：

- 平台发布模板
- AIGC 声明生成
- 短标题、描述、话题模板
- 审计事件与操作日志

完成标准：

- 可为视频号自动生成短标题、描述、声明
- 可追溯任一产物的生成来源

---

## 8. 对下一位 Agent 的实施建议

下一位 agent 不要从“做个新网页”开始，而要从下面顺序开始：

1. 扩展数据库：
  - 新建 `release_batches`、`tracks`、`lyric_documents`、`lyric_timeline_versions`、`mastering_projects`、`package_exports`、`audit_events`
  - 给 `jobs`、`job_artifacts` 增加 `track_id`、`job_kind`、`resource_class`、`depends_on_json`
2. 抽象 pipeline step registry：
  - 把现有 `cover/train` 统一进通用 step runner
3. 新建批量导入与 track 列表 API
4. 先做歌词工位，不要先做 AI MV
5. 歌词工位稳定后再接母带工位
6. 发行包导出稳定后再接封面和 MV provider

一句话原则：

先把“数据模型 + 流水线 + 版本晋升 + 导出包”做稳，再做炫酷生成能力。

---

## 9. 参考落地原则

- 业务状态优先于页面状态。
- 产物版本优先于临时预览。
- 可重试优先于一次跑通。
- 审计可追溯优先于“先做出来再说”。
- 单机本地稳定优先于过早分布式。

