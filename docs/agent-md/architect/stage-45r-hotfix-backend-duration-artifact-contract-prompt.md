# Stage 45R Hotfix A：分离产物契约与时长异常收口（地基 Agent 返工）

项目根目录：

```text
D:\FeiSharkStudio-v2
```

你是“肥鲨-地基”Agent。本轮不是新功能发挥，是返工收口。Stage45RA 虽然完成了真实 UVR 分离审计，但留下了关键风险：45 秒输入被 UVR 输出成 26.807 秒 stem。这个问题没有解释清楚前，不允许恢复真实训练。

## 已验收事实

```text
GET /api/separation/eval/sources：真实可用，发现 D:\测试音乐 4 首。
GET /api/separation/eval/runs：真实可用。
GET /api/separation/eval/runs/{run_id}：真实可用。
POST /api/separation/eval/run：404。
最新 run：stage45r_20260602_171704_201ec7ff。
original_excerpt：45.0s。
vocal/instrumental：26.807s。
```

## 必须返工

### 1. 分离产物必须给浏览器可用 URL

当前 run detail 只有 Windows 文件路径：

```text
products.original_excerpt = D:\...\original_excerpt.wav
products.vocal = D:\...\vocal.wav
products.instrumental = D:\...\instrumental.wav
```

浏览器无法直接用这些路径播放。必须新增安全下载/播放端点，例如：

```text
GET /api/separation/eval/runs/{run_id}/items/{item_index}/artifacts/original
GET /api/separation/eval/runs/{run_id}/items/{item_index}/artifacts/vocal
GET /api/separation/eval/runs/{run_id}/items/{item_index}/artifacts/instrumental
```

要求：

- 只允许访问 `shared_data/separation_eval/runs` 内文件。
- 防 path traversal。
- 文件不存在返回 404。
- content-type 至少为 `audio/wav`。
- run detail 返回：

```json
{
  "artifact_urls": {
    "original": "/api/separation/eval/runs/.../artifacts/original",
    "vocal": "...",
    "instrumental": "..."
  }
}
```

### 2. 处理 45s -> 26.807s 时长异常

必须在 `quality_report.json` 和 API detail 中加入：

```json
{
  "duration_mismatch": true,
  "duration_ratio": 0.5957,
  "duration_mismatch_risk": "high",
  "duration_mismatch_next_step": "inspect UVR runner output trimming before training"
}
```

要求：

- 如果 vocal/instrumental 与 original_excerpt 时长差异超过 5%，标记 high。
- `noise_risk` 不能因为高频指标低就整体低估。
- 报告必须明确：时长不一致是训练/翻唱前必须处理的问题。

### 3. POST run 接口要么安全实现，要么明确禁用

当前产品侧出现按钮调用 `POST /api/separation/eval/run`，但后端 404。

二选一：

- 实现安全 POST，限制 `limit <= 1`、`clip_seconds <= 60`，并返回真实 run。
- 或返回结构化 `405/501`，让产品明确置灰。

不允许产品继续以为接口存在。

### 4. 验证脚本增强

更新：

```text
backend/verify_stage45r_separation_quality_audit.py
```

新增检查：

- latest run 的 artifact URLs 可下载。
- original/vocal/instrumental 都可读。
- duration mismatch 能被检测出来。
- 如果 mismatch 存在，脚本仍可 PASS，但必须输出 `BLOCK_TRAINING=true`。

## 禁止事项

```text
禁止启动 train.py。
禁止 RVC 推理。
禁止删除/移动 D:\测试音乐。
禁止把 duration mismatch 静默忽略。
```

## 必测

```powershell
python -m pytest -q
python -m backend.self_check
python backend\verify_stage45r_separation_quality_audit.py
python -X utf8 -c "from fastapi.testclient import TestClient; import backend.main as m; c=TestClient(m.app); print(c.get('/api/separation/eval/runs/stage45r_20260602_171704_201ec7ff').json())"
```

## 完成后报告

写入：

```text
D:\FeiSharkStudio-v2\docs\agent-md\worker\stage-45r-hotfix-backend-duration-artifact-contract-report.md
```

报告必须明确：

```text
是否完成
artifact URL 是否可播放/下载
duration mismatch 是否检测
BLOCK_TRAINING 是否为 true
POST run 接口最终策略
是否启动 train.py：必须为否
测试结果
```
