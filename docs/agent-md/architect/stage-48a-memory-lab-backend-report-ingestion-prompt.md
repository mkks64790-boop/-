# Stage 48A：Memory Lab 后端记忆库与报告归档

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本轮目标是把 Memory Lab 做成真实本地工程记忆库，不是 UI 装饰。

## 当前验收事实

架构师在工程内未检出以下任一内容：

```text
Memory Lab
memoryLab
memory-lab
记忆实验室
```

因此当前 Memory Lab 不能算已落地。

## 目标

建立本地记忆系统，用于保存：

- 阶段结论。
- 架构决策。
- 模型训练成果。
- 已知 blocker。
- 测试结果。
- agent 报告索引。
- 用户偏好与工程约束。

Memory Lab 必须完全本地化，不调用外部 AI，不上传数据。

## 必须实现

### 1. 数据层

在现有数据库中新增本地记忆表，建议：

```text
project_memories
```

字段至少包含：

```text
memory_id
category
title
summary
source_type
source_path
source_stage
tags_json
importance
pinned
metadata_json
created_at
updated_at
```

要求：

- 不破坏现有表。
- 支持幂等 upsert。
- `source_path` 指向本地文件时必须防止越权读取。

### 2. 报告自动归档

扫描：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker
D:\FeiSharkStudio-v2\docs\agent-md\architect
D:\FeiSharkStudio-v2\docs\agent-md\handoff
```

把 `.md` 文件索引成 memory。

要求：

- 不需要全文塞数据库，可以保存摘要、路径、stage、mtime、tags。
- 能识别 Stage47A / Stage47B / Stage46B 等阶段。
- 对最新关键结论生成高重要性 memory，例如：

```text
UVR duration fixed: BLOCK_TRAINING=false
Stage47 real model: v_d4d7e1c1 / 朱朱_stage47_single_long
Stage47 cover smoke: task_b2272d133fff
```

### 3. API

新增只读/轻写接口：

```text
GET  /api/memory
GET  /api/memory/summary
POST /api/memory/rescan
POST /api/memory
PATCH /api/memory/{memory_id}
```

要求：

- `GET /api/memory` 支持 category、tag、q、pinned 过滤。
- `POST /api/memory/rescan` 只扫描项目内允许目录。
- 不允许删除用户文件。
- 返回结构稳定，供前端真实渲染。

### 4. 自检

更新：

```text
backend/self_check.py
```

加入 Memory Lab contract：

- memory summary 可读。
- rescan 后至少能读取若干 agent-md 报告 memory。
- Stage47A 关键 memory 可被检索。

## 禁止事项

```text
禁止调用外部 AI。
禁止上传文件。
禁止扫描整个 D 盘。
禁止把用户隐私文件全文塞进页面。
禁止删除/移动 docs 或 shared_data。
```

## 必测

```powershell
python -m pytest -q
python -m backend.self_check
python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.post('/api/memory/rescan').json()); print(c.get('/api/memory/summary').json())"
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-48a-memory-lab-backend-report-ingestion-report.md
```

报告必须包含：

```text
是否完成
新增表/API
rescan 结果
memory 数量
Stage47A memory 是否可检索
是否调用外部 AI：必须为否
测试结果
```
